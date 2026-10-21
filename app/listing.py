"""One bounded, authorized filter specification for HTML pages and XLSX export."""
from sqlalchemy import select
from app.authorization import contract_query
from app.models import Contract, ContractReview, Department
from app.options import CONTRACT_STATUSES, TAX_REVIEW_STATUSES

FILTER_LIMITS = dict(q=100,department=10,focus=16,contract_type=120,contact_person=160,
                     deputy_contact_person=160,status=20,tax_review_status=20)
EXPORT_MAX_ROWS = 5000


def normalize_filters(values):
    result={key:str(values.get(key,'')).strip()[:limit] for key,limit in FILTER_LIMITS.items()}
    if result['status'] not in {k for k,_ in CONTRACT_STATUSES}|{'archived'}:result['status']=''
    if result['tax_review_status'] not in {k for k,_ in TAX_REVIEW_STATUSES}:result['tax_review_status']=''
    if result['focus'] not in ('active','expiring','review','approval','ended') or result['status']=='archived':result['focus']=''
    dept=result['department']
    result['department']=str(int(dept)) if dept.isascii() and dept.isdecimal() and 0<int(dept)<=2147483647 else ''
    return result


def filtered_contracts(user, f, *, upcoming_ids=()):
    stmt=contract_query(user).where(Contract.archived_at.is_not(None) if f['status']=='archived' else Contract.archived_at.is_(None))
    if f['q']:
        q=f['q']
        match=(Contract.designation.contains(q,autoescape=True)|Contract.contract_number.contains(q,autoescape=True)|
            Contract.contract_partner.contains(q,autoescape=True)|Contract.contact_person.contains(q,autoescape=True)|
            Contract.deputy_contact_person.contains(q,autoescape=True)|Contract.contract_type.contains(q,autoescape=True)|
            Contract.tax_review_result.contains(q,autoescape=True)|Contract.department.has(Department.name.contains(q,autoescape=True)))
        for column,options in ((Contract.status,CONTRACT_STATUSES),(Contract.tax_review_status,TAX_REVIEW_STATUSES)):
            codes=[code for code,label in options if q.casefold() in code.casefold() or q.casefold() in label.casefold()]
            if codes:match=match|column.in_(codes)
        stmt=stmt.where(match)
    if user.role!='department' and f['department']:stmt=stmt.where(Contract.department_id==int(f['department']))
    for key in ('contract_type','contact_person','deputy_contact_person','tax_review_status'):
        if f[key]:stmt=stmt.where(getattr(Contract,key)==f[key])
    if f['status'] and f['status']!='archived':stmt=stmt.where(Contract.status==f['status'])
    focus=f['focus']
    if focus=='active':stmt=stmt.where(Contract.status=='active')
    elif focus=='review':stmt=stmt.where(Contract.status.in_(('draft','in_progress')))
    elif focus=='approval':stmt=stmt.where(Contract.id.in_(select(ContractReview.contract_id).where(ContractReview.status.in_(('open','in_review')))))
    elif focus=='ended':stmt=stmt.where(Contract.status.in_(('terminated','ended')))
    elif focus=='expiring':stmt=stmt.where(Contract.id.in_(upcoming_ids))
    return stmt
