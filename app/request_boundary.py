"""Bound ASGI ingress before multipart spooling; hand parsed forms to sync routes.

Limits are per process. The production proxy must enforce installation-wide limits.
No request bodies, query strings, credentials or client identifiers are logged.
"""
import json
import logging
from ipaddress import ip_address, ip_network
from time import monotonic
from uuid import uuid4
from urllib.parse import parse_qsl

import anyio
from fastapi import HTTPException
from starlette.datastructures import UploadFile, FormData
from starlette.requests import Request, ClientDisconnect
from starlette.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.formparsers import MultiPartException, MultiPartParser

log = logging.getLogger('ohvr.requests')


def parsed_form(request, *, max_files=5, max_fields=40):
    """Synchronous access only after the ASGI boundary completed bounded parsing."""
    form = request.state.parsed_form
    files = sum(isinstance(value, UploadFile) for _, value in form.multi_items())
    if files > max_files or len(form.multi_items()) - files > max_fields:
        raise HTTPException(400, 'Too many form parts')
    return form


class RequestBoundary:
    def __init__(self, app, settings):
        self.app, self.settings = app, settings
        self.active = self.uploads = 0
        self.proxies = tuple(ip_network(x) for x in settings.trusted_proxy_networks)

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        cfg = self.settings
        headers = {}
        for key, value in scope.get('headers', ()):
            headers.setdefault(key.lower(), []).append(value)
        # Reject ambiguous authority/Windows file paths before URL construction,
        # routing or StaticFiles.realpath can perform filesystem/network access.
        hosts = headers.get(b'host', [])
        path = scope.get('path','')
        if (len(hosts)>1 or any(any(byte<=32 or byte>=127 or byte in b'/\\?#@' for byte in host) for host in hosts)
                or not path.startswith('/') or path.startswith('//')
                or any(char in path for char in ('\\',':','\x00','\r','\n'))):
            return await JSONResponse({'detail':'Invalid request authority or path'},status_code=400)(scope,receive,send)
        client = scope.get('client')
        try:
            trusted = client and any(ip_address(client[0]) in network for network in self.proxies)
        except ValueError:
            trusted = False
        # The upstream server MUST disable its own automatic proxy-header rewrite.
        if trusted:
            proto = headers.get(b'x-forwarded-proto', [])
            forwarded = headers.get(b'x-forwarded-for', [])
            try:
                if len(proto) != 1 or proto[0] not in (b'http', b'https') or len(forwarded) != 1:
                    raise ValueError()
                address = str(ip_address(forwarded[0].decode('ascii')))
            except (ValueError, UnicodeError):
                return await JSONResponse({'detail':'Invalid proxy identity'}, status_code=400)(scope,receive,send)
            scope = {**scope, 'scheme': proto[0].decode('ascii'), 'client': (address, 0)}
        if cfg.production and scope.get('scheme') != 'https':
            return await JSONResponse({'detail':'HTTPS required'}, status_code=421)(scope,receive,send)
        correlation = str(uuid4())
        scope.setdefault('state', {})['correlation_id'] = correlation
        content_type = headers.get(b'content-type', [b''])[0].lower()
        multipart = content_type.startswith(b'multipart/form-data')
        encoded_form = content_type.startswith(b'application/x-www-form-urlencoded')
        started, status = monotonic(), 500

        async def observed_send(message):
            nonlocal status
            if message['type'] == 'http.response.start':
                status = message['status']
                message['headers'] = [*message.get('headers', ()), (b'x-request-id', correlation.encode()),
                    (b'x-content-type-options', b'nosniff'), (b'cache-control', b'no-store')]
            await send(message)

        async def reject(code):
            await JSONResponse({'detail': {400:'Invalid request body',408:'Request receive deadline exceeded',
                413:'Request exceeds configured limits',503:'Request capacity exhausted'}[code]},
                status_code=code, headers={'Retry-After':'5'} if code==503 else None)(scope,receive,observed_send)

        # No await between admission check and increment: atomic within the ASGI loop.
        if self.active >= cfg.request_concurrency or multipart and self.uploads >= cfg.upload_concurrency:
            return await reject(503)
        self.active += 1
        self.uploads += int(multipart)
        form = parser = None
        try:
            lengths = headers.get(b'content-length', [])
            if lengths and (len(lengths)!=1 or not lengths[0].isdigit()):
                return await reject(400)
            if lengths and (len(lengths[0])>10 or int(lengths[0])>cfg.request_max_bytes):
                return await reject(413)
            chunks, size = [], 0
            # Non-multipart requests never need the aggregate attachment budget.
            body_limit = cfg.request_max_bytes if multipart else min(cfg.request_max_bytes,1024*1024)
            try:
                with anyio.fail_after(cfg.request_timeout_seconds):
                    while True:
                        message = await receive()
                        if message['type']=='http.disconnect':
                            return
                        chunk = message.get('body', b'')
                        size += len(chunk)
                        if size > body_limit:
                            return await reject(413)
                        chunks.append(chunk)
                        if not message.get('more_body', False):
                            break
                    if lengths and int(lengths[0]) != size:
                        return await reject(400)
                    # Parse ONLY after the complete body passed its byte boundary.
                    # Replay <=64KiB chunks to bound parser callback work per turn.
                    body = b''.join(chunks)
                    chunks.clear()
                    # Starlette's URL-encoded parser has no max_fields argument.
                    # Reject separator bombs before allocating per-field objects.
                    if encoded_form and body and body.count(b'&')+1>cfg.form_max_fields:
                        return await reject(413)
                    offset = 0
                    delivered = False

                    async def replay():
                        nonlocal offset, delivered
                        if delivered:
                            return await receive()
                        block = body[offset:offset+65536]
                        offset += len(block)
                        delivered = offset >= len(body)
                        return {'type':'http.request','body':block,'more_body':offset<len(body)}

                    request = Request(scope, replay)
                    if multipart:
                        parser = MultiPartParser(request.headers, request.stream(), max_files=cfg.form_max_files,
                            max_fields=cfg.form_max_fields, max_part_size=cfg.form_field_bytes)
                        form = await parser.parse()
                    elif encoded_form:
                        # The pinned python-multipart QuerystringParser has an
                        # advisory for semicolon-induced quadratic work. Use the
                        # bounded standard parser with HTML's '&' separator only.
                        form = FormData(parse_qsl(body.decode('utf-8'),keep_blank_values=True,
                            encoding='utf-8',errors='strict',max_num_fields=cfg.form_max_fields,separator='&'))
                    else:
                        form = await request.form(max_files=0,max_fields=cfg.form_max_fields)
                    fields = files = 0
                    for key, value in form.multi_items():
                        if len(key.encode('utf-8'))>256:
                            return await reject(413)
                        if isinstance(value, UploadFile):
                            files += 1
                            if value.size is None or value.size > 25*1024*1024:
                                return await reject(413)
                        else:
                            fields += 1
                            if len(value.encode('utf-8'))>cfg.form_field_bytes:
                                return await reject(413)
                    if fields>cfg.form_max_fields or files>cfg.form_max_files:
                        return await reject(413)
                    scope['state']['parsed_form'] = form
            except TimeoutError:
                return await reject(408)
            except (StarletteHTTPException, MultiPartException, ClientDisconnect, UnicodeError, ValueError):
                return await reject(400)
            offset = 0
            delivered = False
            await self.app(scope, replay, observed_send)
        finally:
            try:
                with anyio.CancelScope(shield=True):
                    if form is not None:
                        await form.close()
                    if parser is not None:
                        # Pinned Starlette tracks every opened part here, including
                        # incomplete parts absent from FormData. Also close on timeout
                        # or disconnect: Starlette closes these only on parser errors.
                        for file in parser._files_to_close_on_error:
                            await anyio.to_thread.run_sync(file.close)
            finally:
                self.active -= 1
                self.uploads -= int(multipart)
            log.info(json.dumps({'event':'request_completed','request_id':correlation,'status':status,
                'duration_ms':round((monotonic()-started)*1000), 'received_bytes':size if 'size' in locals() else 0}))
