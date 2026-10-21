"""Availability boundaries and real shared database reservations."""
import asyncio
from dataclasses import replace
import inspect
import json
from datetime import timedelta
from unittest.mock import patch

import httpx
import pytest
from sqlalchemy import select, update
from starlette.responses import PlainTextResponse

from app.config import Settings
from app.request_boundary import RequestBoundary
from app.models import LoginAttempt, now_utc
from tests.support import environment_context, login, csrf_from, create_contract
from tests.runtime_support import runtime_environment


def scope(headers=(), client='127.0.0.1', scheme='http'):
    return dict(type='http', http_version='1.1', method='POST', path='/test', raw_path=b'/test',
        query_string=b'', headers=[(key.lower(),value) for key,value in headers], client=(client,1234), server=('localhost',80), scheme=scheme)


async def invoke(boundary, *, messages=None, headers=(), delay=0, request_scope=None):
    output=[]
    incoming=iter(messages or [dict(type='http.request',body=b'',more_body=False)])
    async def receive():
        if delay:await asyncio.sleep(delay)
        try:return next(incoming)
        except StopIteration:
            await asyncio.Event().wait()
    async def send(message):output.append(message)
    await boundary(request_scope or scope(headers),receive,send)
    return output


def test_streamed_body_rejected_before_parser_or_application():
    async def app(*args):raise AssertionError('oversized body reached application')
    boundary=RequestBoundary(app,Settings(request_max_bytes=1024))
    chunks=[dict(type='http.request',body=b'a'*800,more_body=True),
            dict(type='http.request',body=b'b'*800,more_body=False)]
    with patch('starlette.requests.Request.form',side_effect=AssertionError('body spooled too early')), \
         patch('starlette.formparsers.MultiPartParser.parse',side_effect=AssertionError('multipart spooled too early')):
        result=asyncio.run(invoke(boundary,messages=chunks))
    assert result[0]['status']==413
    assert boundary.active==boundary.uploads==0


@pytest.mark.parametrize('headers,status',[
    ([(b'content-length',b'1025')],413),
    ([(b'content-length',b'3')],400),
    ([(b'content-length',b'-1')],400),
    ([(b'content-length',b'0'),(b'content-length',b'0')],400),
])
def test_declared_body_lengths_fail_closed(headers,status):
    async def app(*args):raise AssertionError('invalid body reached application')
    result=asyncio.run(invoke(RequestBoundary(app,Settings(request_max_bytes=1024)),headers=headers))
    assert result[0]['status']==status


def test_slow_body_has_total_deadline_and_releases_slot():
    async def app(*args):raise AssertionError('slow body reached application')
    boundary=RequestBoundary(app,Settings(request_timeout_seconds=1))
    result=asyncio.run(invoke(boundary,delay=1.1))
    assert result[0]['status']==408 and boundary.active==0


def test_parser_deadline_closes_incomplete_spooled_parts():
    from io import BytesIO
    opened=BytesIO(b'partial')
    async def parser(instance):
        instance._files_to_close_on_error.append(opened)
        await asyncio.sleep(2)
    async def app(*args):raise AssertionError('unfinished parser reached application')
    boundary=RequestBoundary(app,Settings(request_timeout_seconds=1))
    with patch('starlette.formparsers.MultiPartParser.parse',parser):
        result=asyncio.run(invoke(boundary,headers=[(b'content-type',b'multipart/form-data; boundary=test')]))
    assert result[0]['status']==408 and opened.closed
    assert boundary.active==boundary.uploads==0


def test_form_field_bomb_rejected_before_parse():
    async def app(*args):raise AssertionError('field bomb reached application')
    with patch('starlette.requests.Request.form',side_effect=AssertionError('field bomb parsed')):
        result=asyncio.run(invoke(RequestBoundary(app,Settings()),
            headers=[(b'content-type',b'application/x-www-form-urlencoded')],
            messages=[dict(type='http.request',body=b'a=&'*41,more_body=False)]))
    assert result[0]['status']==413


def test_multipart_file_limit_and_field_size():
    async def app(*args):raise AssertionError('invalid form reached application')
    for files, data in [([('files',('test.txt',b'x'))]*6,None),
                         ([('files',('test.txt',b'x'))],{'field':'x'*65537})]:
        request=httpx.Request('POST','http://localhost/test',files=files,data=data)
        body=request.read()
        result=asyncio.run(invoke(RequestBoundary(app,Settings()),headers=request.headers.raw,
            messages=[dict(type='http.request',body=body,more_body=False)]))
        assert result[0]['status'] in (400,413)


def test_admission_rejects_without_queue_and_recovers():
    async def scenario():
        entered,release=asyncio.Event(),asyncio.Event()
        async def app(s,r,send):
            entered.set();await release.wait();await PlainTextResponse('OK')(s,r,send)
        boundary=RequestBoundary(app,Settings(request_concurrency=1,upload_concurrency=1))
        first=asyncio.create_task(invoke(boundary));await entered.wait()
        second=await invoke(boundary)
        assert second[0]['status']==503
        release.set();assert (await first)[0]['status']==200
        assert boundary.active==0
        assert (await invoke(boundary))[0]['status']==200
    asyncio.run(scenario())


def test_forwarded_identity_requires_explicit_proxy_and_tls():
    seen=[]
    async def app(s,r,send):
        seen.append((s['client'][0],s['scheme']))
        await PlainTextResponse('OK')(s,r,send)
    headers=[(b'x-forwarded-for',b'192.0.2.7'),(b'x-forwarded-proto',b'https')]
    asyncio.run(invoke(RequestBoundary(app,Settings()),request_scope=scope(headers)))
    assert seen[-1]==('127.0.0.1','http')
    cfg=Settings(trusted_proxy_networks=('127.0.0.1/32',),environment='production')
    result=asyncio.run(invoke(RequestBoundary(app,cfg),request_scope=scope(headers)))
    assert result[0]['status']==200 and seen[-1]==('192.0.2.7','https')
    assert asyncio.run(invoke(RequestBoundary(app,cfg),request_scope=scope()))[0]['status']==400
    assert asyncio.run(invoke(RequestBoundary(app,cfg),request_scope=scope(client='192.0.2.8')))[0]['status']==421
    spoof=headers+[(b'x-forwarded-for',b'198.51.100.1')]
    assert asyncio.run(invoke(RequestBoundary(app,cfg),request_scope=scope(spoof)))[0]['status']==400


def test_production_requires_verified_database_tls_and_narrow_proxy_trust():
    cfg=Settings(environment='production',allowed_hosts=('register.example.invalid',),
        database_url='postgresql+psycopg://web@db.invalid/register',
        integration_database_url='postgresql+psycopg://integration@db.invalid/register',enforce_database_security=True)
    with pytest.raises(ValueError,match='verify-full'):cfg.validate()
    for networks in [('0.0.0.0/0',),('::/0',)]:
        with pytest.raises(ValueError,match='proxy networks'):replace(Settings(),trusted_proxy_networks=networks).validate()


@pytest.fixture
def operations(request):
    if request.config.getoption('--database')=='postgresql':
        with runtime_environment() as r:yield r.client,r.app,r.owner
    else:
        with environment_context('sqlite') as (client,app):yield client,app,app


def test_login_spraying_budget_shared_and_expires(operations):
    client,app,owner=operations
    token=csrf_from(client.get('/login').text)
    with patch('app.main.verify_password',return_value=False) as hashing:
        for i in range(32):
            response=client.post('/login',data=dict(username=f'spray_{i}',password='bad',csrf_token=token))
            assert response.status_code==401
        assert client.post('/login',data=dict(username='different',password='bad',csrf_token=token)).status_code==429
        assert hashing.call_count==32
        # Counters are durable across application instances, not Python globals.
        from app.main import create_app
        from starlette.testclient import TestClient
        other=create_app(app.state.config)
        with TestClient(other) as second:
            csrf=csrf_from(second.get('/login').text)
            assert second.post('/login',data=dict(username='fresh',password='bad',csrf_token=csrf)).status_code==429
        with owner.state.session_factory() as db:
            db.execute(update(LoginAttempt).values(created_at=now_utc()-timedelta(minutes=16)));db.commit()
        assert client.post('/login',data=dict(username='after_window',password='bad',csrf_token=token)).status_code==401


def test_shared_api_budget_and_no_direct_integration_table_access(operations):
    client,app,owner=operations
    from app.api_rate import reserve_api
    args=dict(enforced=app.state.config.enforce_database_security,credential='synthetic',address='192.0.2.9')
    for _ in range(119):assert reserve_api(app.state.integration_session_factory,**args)
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=2) as executor:
        results=list(executor.map(lambda _:reserve_api(app.state.integration_session_factory,**args),range(2)))
    assert sum(results)==1
    assert not reserve_api(app.state.integration_session_factory,**args)
    # A new token cannot bypass the shared address ceiling.
    for i in range(120):assert reserve_api(app.state.integration_session_factory,**{**args,'credential':str(i)})
    assert not reserve_api(app.state.integration_session_factory,**{**args,'credential':'rotated'})
    if args['enforced']:
        from sqlalchemy import text
        from sqlalchemy.exc import DBAPIError
        with app.state.integration_engine.connect() as connection:
            with pytest.raises(DBAPIError):connection.execute(text('SELECT * FROM login_attempts'))


def test_mutations_are_sync_workers_and_correlation_is_redacted(operations,caplog):
    client,app,owner=operations
    from fastapi.routing import APIRoute
    for route in app.routes:
        if isinstance(route,APIRoute) and 'POST' in route.methods:
            assert not inspect.iscoroutinefunction(route.endpoint),route.path
    with caplog.at_level('INFO',logger='ohvr.requests'):
        login(client,'admin');cid=create_contract(client)
        response=client.get(f'/contracts/{cid}?credential=DO_NOT_LOG')
    request_id=response.headers['x-request-id']
    assert len(request_id)==36
    records=[json.loads(record.message) for record in caplog.records if record.name=='ohvr.requests']
    assert any(item['request_id']==request_id for item in records)
    assert 'DO_NOT_LOG' not in '\n'.join(record.message for record in caplog.records)


def test_v2_reauthentication_reserves_once_without_committing_business_read(operations):
    from tests.test_phase6 import token
    from app.api_rate import reserve_api
    client,app,owner=operations
    login(client,'admin');create_contract(client)
    headers,_=token(operations)
    with patch('app.api_rate.reserve_api',wraps=reserve_api) as reserve:
        assert client.get('/api/v2/snapshot',headers=headers).status_code==200
        assert reserve.call_count==1
        assert client.get('/api/v2/snapshot',headers=headers).status_code==200
        assert reserve.call_count==2


def test_storage_quota_preserves_existing_bytes(operations):
    from io import BytesIO
    from starlette.datastructures import UploadFile
    from fastapi import HTTPException
    from app.documents import stage_upload_sync, storage_budget
    client,app,owner=operations
    root=app.state.document_storage_dir
    old=root/'staging'/('a'*32+'.txt');old.write_bytes(b'preserved')
    cfg=replace(app.state.config,document_storage_quota_bytes=1024)
    legacy=root/('b'*32+'.txt');legacy.write_bytes(b'old legacy')
    assert storage_budget(root,cfg)==1024-len(b'preserved')-len(b'old legacy')
    source=UploadFile(BytesIO(b'x'*1024),filename='quota.txt')
    with pytest.raises(HTTPException) as exc:stage_upload_sync(source,root,cfg)
    assert exc.value.status_code==507 and old.read_bytes()==b'preserved'
    assert list((root/'staging').iterdir())==[old]


def test_blocking_password_work_does_not_starve_liveness(operations):
    import threading
    from concurrent.futures import ThreadPoolExecutor
    client,app,owner=operations
    entered,release=threading.Event(),threading.Event()
    token=csrf_from(client.get('/login').text)
    def slow_hash(*args):
        entered.set()
        if not release.wait(10):raise AssertionError('worker was not released')
        return False
    with patch('app.main.verify_password',side_effect=slow_hash),ThreadPoolExecutor(max_workers=1) as executor:
        future=executor.submit(client.post,'/login',data=dict(username='slow',password='bad',csrf_token=token))
        try:
            assert entered.wait(10)
            assert client.get('/health/live').status_code==204
            assert client.get('/health/ready').status_code==204
        finally:release.set()
        assert future.result(timeout=10).status_code==401
