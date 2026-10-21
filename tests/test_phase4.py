"""Phase 4 behavior on SQLite and genuine restricted PostgreSQL LOGIN roles."""
from uuid import uuid4
import pytest
from sqlalchemy import select,text
from sqlalchemy.exc import DBAPIError
from app.models import Contract,ContractReview,ContractTask,ReviewDecision,User,RecipientTeam,RecipientMembership,Revision
from tests.support import environment_context,login,create_contract,contract_payload,csrf_from,workflow_payload
from tests.runtime_support import runtime_environment


@pytest.fixture
def workflow(request):
    if request.config.getoption('--database')=='postgresql':
        with runtime_environment() as r:
            yield r.client,r.app,r.owner
    else:
        with environment_context('sqlite') as (client,app):
            yield client,app,app


def switch(client,username):
    client.post('/logout',data={'csrf_token':csrf_from(client.get('/').text)})
    assert login(client,username).status_code==303


def post(client,path,**data):
    data.setdefault('csrf_token',csrf_from(client.get('/').text))
    return client.post(path,data=workflow_payload(client,path,data),follow_redirects=False)


def setup_review(workflow):
    client,app,owner=workflow
    assert login(client,'kultur').status_code==303
    record=create_contract(client)
    assert post(client,f'/contracts/{record}/reviews',recipient='Kämmerei',subject='Current content').status_code==303
    with owner.state.session_factory() as db:
        user=db.scalar(select(User).where(User.username=='pruefer'))
        user.can_approve=True
        team=RecipientTeam(name='Independent approval')
        db.add(team);db.flush()
        db.add(RecipientMembership(team_id=team.id,user_id=user.id))
        review=db.scalar(select(ContractReview).where(ContractReview.contract_id==record))
        team_id,user_id,review_id=team.id,user.id,review.id
        db.commit()
    switch(client,'admin')
    assert post(client,f'/contracts/{record}/reviews/{review_id}/assignment',team_id=team_id,user_id=user_id).status_code==303
    return record,review_id


def edit(client,record,**values):
    page=client.get(f'/contracts/{record}/edit')
    import re
    version=re.search('name="version" value="(\\d+)"',page.text).group(1)
    data=contract_payload()
    data.update(values,csrf_token=csrf_from(page.text),version=version)
    return client.post(f'/contracts/{record}/edit',data=data,follow_redirects=False)


def test_approval_bound_to_content_activation_and_material_invalidation(workflow):
    client,app,owner=workflow
    record,review=setup_review(workflow)
    assert edit(client,record,status='active').status_code==409
    switch(client,'pruefer')
    assert post(client,f'/contracts/{record}/reviews/{review}',status='approved',result_text='Independent evidence').status_code==303
    switch(client,'admin')
    assert edit(client,record,status='active').status_code==303
    assert edit(client,record,designation='Material revision B',status='active').status_code==303
    with owner.state.session_factory() as db:
        c=db.get(Contract,record);r=db.get(ContractReview,review)
        assert c.content_revision==2 and c.status=='in_progress' and c.approval_provenance=='pending'
        assert r.status=='open' and r.provenance=='superseded' and r.content_revision==2
        decision=db.scalar(select(ReviewDecision))
        assert decision.content_revision==1 and decision.status=='approved' and decision.actor_id==4
    assert edit(client,record,designation='Material revision B',status='active').status_code==409


def test_documents_invalidate_approval_and_duplicate_submission_is_rejected(workflow):
    client,app,owner=workflow
    record,review=setup_review(workflow)
    switch(client,'pruefer')
    assert post(client,f'/contracts/{record}/reviews/{review}',status='approved',result_text='Version A').status_code==303
    switch(client,'admin')
    key=str(uuid4());path=f'/contracts/{record}/documents/link'
    data={'csrf_token':csrf_from(client.get('/').text),'request_id':key,'document_name':'Material evidence','external_url':'https://example.org/synthetic'}
    assert client.post(path,data=data,follow_redirects=False).status_code==303
    assert client.post(path,data=data,follow_redirects=False).status_code==409
    with owner.state.session_factory() as db:
        assert db.get(Contract,record).content_revision==2
        assert db.get(ContractReview,review).status=='open'


def test_review_versions_terminal_transitions_reopen_and_preserved_conflict_input(workflow):
    client,app,owner=workflow
    record,review=setup_review(workflow)
    switch(client,'pruefer')
    path=f'/contracts/{record}/reviews/{review}'
    data={'csrf_token':csrf_from(client.get('/').text),'version':'2','status':'approved','result_text':'First decision'}
    assert client.post(path,data=data,follow_redirects=False).status_code==303
    data['result_text']='Unsaved stale decision'
    response=client.post(path,data=data,follow_redirects=False)
    assert response.status_code==409 and 'Unsaved stale decision' in response.text
    assert post(client,path,status='rejected',result_text='Overwrite forbidden').status_code==409
    switch(client,'admin')
    assert post(client,path,status='open',result_text='Explicit reopening').status_code==303
    with owner.state.session_factory() as db:
        assert db.scalar(select(ReviewDecision).where(ReviewDecision.status=='approved')).reason=='First decision'
        assert db.get(ContractReview,review).status=='open'


def test_tax_reopen_clears_current_completion_and_department_cannot_assess(workflow):
    client,app,owner=workflow
    assert login(client,'admin').status_code==303
    record=create_contract(client)
    assert edit(client,record,tax_review_status='completed',tax_review_result='Synthetic assessment').status_code==303
    assert edit(client,record,tax_review_status='in_progress',tax_review_result='Reopened').status_code==303
    with owner.state.session_factory() as db:
        c=db.get(Contract,record)
        assert c.tax_reviewed_by_id is None and c.tax_reviewed_at is None
        snapshots=db.scalars(select(Revision).where(Revision.contract_id==record)).all()
        assert any(r.before and r.before.get('tax_reviewed_at') for r in snapshots)
    switch(client,'kultur')
    assert edit(client,record,tax_review_status='completed',tax_review_result='Denied').status_code==403
    switch(client,'admin')
    assert edit(client,record,tax_review_status='completed',tax_review_result='Reassessed').status_code==303


def test_task_versions_required_and_archived_children_are_immutable(workflow):
    client,app,owner=workflow
    assert login(client,'admin').status_code==303
    record=create_contract(client)
    path=f'/contracts/{record}/tasks'
    assert post(client,path,title='Initial task',kind='review').status_code==303
    with owner.state.session_factory() as db:
        task=db.scalar(select(ContractTask));task_id=task.id
    path+=f'/{task_id}'
    data={'csrf_token':csrf_from(client.get('/').text),'title':'Updated task','kind':'review','status':'done'}
    assert client.post(path,data=data).status_code==400
    data['version']='1'
    assert client.post(path,data=data,follow_redirects=False).status_code==303
    assert client.post(path,data=data,follow_redirects=False).status_code==409
    assert post(client,f'/contracts/{record}/archive',version='1').status_code==303
    assert post(client,path,title='Forbidden',kind='review',status='open',version='2').status_code==409
    with owner.state.engine.begin() as c:
        with pytest.raises(DBAPIError),c.begin_nested():
            c.execute(text('UPDATE contract_tasks SET title=title WHERE id=:id'),{'id':task_id})


def test_self_approval_wrong_recipient_and_missing_reason_denied(workflow):
    client,app,owner=workflow
    record,review=setup_review(workflow)
    path=f'/contracts/{record}/reviews/{review}'
    # Administrator is not the assigned independent reviewer.
    assert post(client,path,status='approved',result_text='Unassigned override').status_code==403
    switch(client,'pruefer')
    assert post(client,path,status='approved',result_text='').status_code==400
    with owner.state.session_factory() as db:
        c=db.get(Contract,record);c.material_actor_id=4;db.commit()
    assert post(client,path,status='approved',result_text='Self material approval').status_code==403


def test_decisions_are_append_only_and_new_active_creation_is_rejected(workflow):
    client,app,owner=workflow
    record,review=setup_review(workflow)
    switch(client,'pruefer')
    assert post(client,f'/contracts/{record}/reviews/{review}',status='approved',result_text='Durable decision').status_code==303
    with owner.state.engine.begin() as c:
        for sql in ('UPDATE review_decisions SET reason=reason','DELETE FROM review_decisions'):
            with pytest.raises(DBAPIError),c.begin_nested():c.execute(text(sql))
    switch(client,'admin')
    data=contract_payload();data.update(status='active',csrf_token=csrf_from(client.get('/').text))
    assert client.post('/contracts/new',data=data).status_code==422


def parallel_posts(app,client,submissions):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from fastapi.testclient import TestClient
    from app.security import COOKIE_NAME
    barrier=Barrier(len(submissions))
    cookie=client.cookies.get(COOKIE_NAME)
    def run(item):
        path,data,files=item
        other=TestClient(app)
        other.cookies.set(COOKIE_NAME,cookie)
        try:
            barrier.wait(timeout=10)
            return other.post(path,data=data,files=files,follow_redirects=False).status_code
        finally:
            other.close()
    with ThreadPoolExecutor(max_workers=len(submissions)) as pool:
        return list(pool.map(run,submissions))


def test_concurrent_review_decisions_have_exactly_one_winner(workflow):
    client,app,owner=workflow
    record,review=setup_review(workflow)
    switch(client,'pruefer')
    csrf=csrf_from(client.get('/').text)
    path=f'/contracts/{record}/reviews/{review}'
    results=parallel_posts(app,client,[(path,{'csrf_token':csrf,'version':'2','status':status,'result_text':status},None) for status in ('approved','rejected')])
    assert sorted(results)==[303,409]
    with owner.state.session_factory() as db:
        assert len(db.scalars(select(ReviewDecision)).all())==1
        assert db.get(ContractReview,review).version==3


@pytest.mark.parametrize('operation',['task_create','task_update','review_create','review_update','assignment','document_link','upload','edit','tax'])
def test_archive_races_with_every_mutation_path(workflow,operation):
    client,app,owner=workflow
    record,review=setup_review(workflow)
    assert post(client,f'/contracts/{record}/tasks',title='Race task',kind='review').status_code==303
    with owner.state.session_factory() as db:
        task_id=db.scalar(select(ContractTask.id))
        request=db.get(ContractReview,review)
        team_id,user_id=request.team_id,request.assigned_user_id
    csrf=csrf_from(client.get('/').text)
    root=f'/contracts/{record}'
    data={'csrf_token':csrf,'request_id':str(uuid4())};files=None
    if operation=='task_create':path=root+'/tasks';data.update(title='Racing task',kind='review')
    elif operation=='task_update':path=root+f'/tasks/{task_id}';data.update(title='Edited race task',kind='review',status='done',version='1')
    elif operation=='review_create':path=root+'/reviews';data.update(recipient='Kämmerei',subject='Racing request')
    elif operation=='review_update':path=root+f'/reviews/{review}';data.update(status='in_review',result_text='Racing comment',version='2')
    elif operation=='assignment':path=root+f'/reviews/{review}/assignment';data.update(team_id=team_id,user_id=user_id,version='2')
    elif operation=='document_link':path=root+'/documents/link';data.update(document_name='Race link',external_url='https://example.org/synthetic')
    elif operation=='upload':path=root+'/documents';files={'documents':('synthetic.pdf',b'%PDF-1.4\nSynthetic','application/pdf')}
    else:
        path=root+'/edit';data.update(contract_payload(),version='1')
        if operation=='edit':data['designation']='Racing material edit'
        else:data.update(tax_review_status='completed',tax_review_result='Racing tax assessment')
    results=parallel_posts(app,client,[(root+'/archive',{'csrf_token':csrf,'version':'1'},None),(path,data,files)])
    assert all(code in (303,409) for code in results)
    assert 303 in results
    with owner.state.session_factory() as db:
        current=db.get(Contract,record)
        version=current.version;archived=current.archived_at is not None
    if not archived:
        assert post(client,root+'/archive',version=str(version)).status_code==303
    assert client.post(path,data=data,files=files,follow_redirects=False).status_code==409
    with owner.state.session_factory() as db:
        revisions=db.scalars(select(Revision).where(Revision.contract_id==record).order_by(Revision.id)).all()
        assert revisions[-1].action=='archived'


def test_concurrent_task_updates_have_exactly_one_winner(workflow):
    client,app,owner=workflow
    assert login(client,'admin').status_code==303
    record=create_contract(client)
    assert post(client,f'/contracts/{record}/tasks',title='Task race',kind='review').status_code==303
    with owner.state.session_factory() as db:task_id=db.scalar(select(ContractTask.id))
    csrf=csrf_from(client.get('/').text)
    results=parallel_posts(app,client,[(f'/contracts/{record}/tasks/{task_id}',{'csrf_token':csrf,'version':'1','title':title,'kind':'review','status':'done'},None) for title in ('Winner A','Winner B')])
    assert sorted(results)==[303,409]
