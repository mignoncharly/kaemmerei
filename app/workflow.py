"""Aggregate mutation protocol. Callers parse input first and commit exactly once."""
from fastapi import HTTPException
from sqlalchemy import select, text, inspect
from app.authorization import load_contract, can_decide_review
from app.identity_service import lock_identities
from app.logic import active_access, can_write
from app.models import ContractReview, ReviewDecision, Revision, LoginSession, now_utc
from uuid import UUID


class WorkflowConflict(HTTPException):
    def __init__(self,form,current_version):
        super().__init__(409,'Changed since this form was loaded')
        self.submitted={k:str(v)[:5000] for k,v in form.items() if k not in ('csrf_token','request_id')}
        self.current_version=current_version


def submission(db,user,contract,form):
    try:
        key=str(UUID(str(form.get('request_id',''))))
    except ValueError:
        raise HTTPException(400,'A submission ID is required; reload the form') from None
    if db.scalar(select(Revision.id).where(Revision.contract_id==contract.id,
            Revision.actor_id==user.id,Revision.after['request_id'].as_string()==key)):
        raise WorkflowConflict(form,contract.version)
    db.info['submission_id']=key

MATERIAL_FIELDS = frozenset(('designation','contract_type','contract_partner','relevant_date',
    'end_date','notice_period_months','automatic_renewal','renewal_period_months',
    'contract_value','annual_value','financial_direction','payment_interval','budget_assignment',
    'date_description','department_id','contact_person','deputy_contact_person'))
TERMINAL = frozenset(('approved','changes_requested','rejected','withdrawn'))


def lock_actor(db,user):
    # Same order for identity, assignment and aggregate writers. The existing
    # guard obtains SQLite's writer lock before the protected parent is reloaded.
    lock_identities(db)
    actor_id=inspect(user).identity[0]
    if db.info.get('enforce_rls'):
        context=db.info['request_context']
        db.connection().execute(text('SELECT ohvr_security.prepare_context(:session,:token,:correlation)'),
            {'session':context.get('session_hash',''),'token':context.get('token_hash',''),
             'correlation':context['correlation_id']})
        if db.scalar(text('SELECT ohvr_security.uid()'))!=actor_id:
            raise HTTPException(403,'Session was revoked before mutation')
    else:
        session=db.get(LoginSession,db.info.get('request_context',{}).get('session_hash',''))
        if session is None or session.user_id!=actor_id or session.expires_at<=now_utc():
            raise HTTPException(403,'Session was revoked before mutation')
    if not active_access(user):
        raise HTTPException(403, 'Active membership required')


def begin_mutation(db, user, contract_id, *, writer=True):
    lock_actor(db,user)
    contract = load_contract(db,user,contract_id,lock=True)
    if contract.archived_at is not None:
        raise HTTPException(409,'Archived contract is immutable')
    if writer and not can_write(user,contract):
        raise HTTPException(403,'Contract write capability required')
    return contract


def expected_version(entity, form):
    try:
        expected=int(form.get('version',''))
    except (ValueError,TypeError):
        raise HTTPException(400,'Expected version is required') from None
    if entity.version != expected:
        raise WorkflowConflict(form,entity.version)


def material_change(db, contract, actor, *, bump_version=True):
    contract.content_revision += 1
    if bump_version:
        contract.version+=1
    contract.updated_by_id=actor.id
    contract.updated_at=now_utc()
    contract.material_actor_id=actor.id
    contract.approval_provenance='pending'
    if contract.status=='active':
        contract.status='in_progress'
    if contract.tax_review_status=='completed':
        contract.tax_review_status='in_progress'
        contract.tax_reviewed_at=contract.tax_reviewed_by_id=None
        contract.tax_provenance='unverified'
    for review in db.scalars(select(ContractReview).where(ContractReview.contract_id==contract.id)):
        db.add(Revision(contract_id=contract.id,actor_id=actor.id,action='review_superseded',
            before={'review_id':review.id,'status':review.status,'result':review.result_text,
                    'content_revision':review.content_revision,'provenance':review.provenance,
                    'updated_by_id':review.updated_by_id,'updated_at':review.updated_at.isoformat(),
                    'team_id':review.team_id,'assigned_user_id':review.assigned_user_id},
            after={'content_revision':contract.content_revision}))
        review.status='open'
        review.result_text=''
        review.content_revision=contract.content_revision
        review.provenance='superseded'
        review.version+=1


def decide(db,user,contract,review,status,reason):
    if not can_decide_review(db,user,contract,review):
        raise HTTPException(403,'Explicit decision capability and assignment required')
    if status not in ('open','in_review',*TERMINAL):
        raise HTTPException(400,'Invalid review state')
    if not reason.strip():
        raise HTTPException(422,'A reason is required for every transition')
    if review.status in TERMINAL and not (status=='open' and user.role=='admin'):
        raise HTTPException(409,'Terminal decision must be explicitly reopened by an administrator')
    if status=='approved' and (review.assigned_user_id!=user.id or review.team_id is None or
            user.id in (contract.created_by_id,contract.material_actor_id)):
        raise HTTPException(403,'Independent assigned approver required')
    if review.content_revision not in (None,contract.content_revision):
        raise HTTPException(409,'Request refers to an older content revision')
    if review.status in TERMINAL and status=='open':
        contract.approval_provenance='pending'
        if contract.status=='active':
            contract.status='in_progress'
    db.add(ReviewDecision(contract_id=contract.id,review_id=review.id,
        review_version=review.version,content_revision=contract.content_revision,
        actor_id=user.id,team_id=review.team_id,assigned_user_id=review.assigned_user_id,
        status=status,reason=reason,decided_at=now_utc()))
    review.status,review.result_text=status,reason
    review.content_revision=contract.content_revision
    review.provenance='current'
    review.version+=1


def activation(db,contract,recipients):
    for recipient in recipients:
        if not db.scalar(select(ReviewDecision.id).join(ContractReview,ContractReview.id==ReviewDecision.review_id).where(
            ContractReview.contract_id==contract.id,ContractReview.recipient==recipient,
            ContractReview.status=='approved',ContractReview.provenance=='current',
            ReviewDecision.review_version==ContractReview.version-1,
            ReviewDecision.content_revision==contract.content_revision,ReviewDecision.status=='approved')):
            raise HTTPException(409,'Current independent approval missing: '+recipient)
    contract.approval_provenance='verified'


def tax_values(user,contract,values):
    old_status=contract.tax_review_status if contract else 'not_checked'
    old_result=contract.tax_review_result if contract else ''
    changed=values['tax_review_status']!=old_status or values['tax_review_result']!=old_result
    if changed and user.role!='admin':
        raise HTTPException(403,'tax_assess capability is restricted to administrators')
    completed=values['tax_review_status']=='completed'
    values['tax_reviewed_by_id']=user.id if completed and changed else (contract.tax_reviewed_by_id if completed and contract else None)
    values['tax_reviewed_at']=now_utc() if completed and changed else (contract.tax_reviewed_at if completed and contract else None)
    if completed and (changed or contract is None):
        values['tax_provenance']='current'
    elif not completed:
        values['tax_provenance']='unverified'
