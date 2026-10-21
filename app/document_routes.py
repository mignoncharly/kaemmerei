from app.request_boundary import parsed_form
from app.presentation import safe_values
"""Authorized lifecycle operations retain predecessors and prohibit disposal."""
from fastapi import Depends,HTTPException,Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from starlette.concurrency import run_in_threadpool
from app.authorization import load_child
from app.models import ContractDocument,DocumentJob,Revision
from app.security import require_csrf
from app.workflow import begin_mutation,expected_version,material_change,submission
from app.documents import stage_upload_sync,new_document,process_document
from app.identity_service import audit


def install_document_routes(app,*,get_db,user_csrf):
    def writable(request,db,form,contract_id,document_id):
        user,_=user_csrf(request,db)
        require_csrf(request,db,str(form.get('csrf_token','')))
        contract=begin_mutation(db,user,contract_id)
        _,document=load_child(db,user,contract_id,ContractDocument,document_id)
        expected_version(document,form)
        if document.state in ('superseded','disposed'):raise HTTPException(409,'Inactive document version')
        submission(db,user,contract,form)
        return user,contract,document

    @app.post('/contracts/{contract_id}/documents/{document_id}/replace')
    def replace_document(request:Request,contract_id:int,document_id:int,db=Depends(get_db)):
        form=parsed_form(request, max_files=1,max_fields=4)
        request.state.safe_values = safe_values(form)
        user,contract,old=writable(request,db,form,contract_id,document_id)
        upload=form.get('document')
        if upload is None or not hasattr(upload,'filename'):raise HTTPException(400,'A replacement file is required')
        if db.scalar(select(ContractDocument.id).where(ContractDocument.replaces_id==old.id,
                ContractDocument.state.in_(('pending','quarantined')))):
            raise HTTPException(409,'A replacement is already pending; recover its job')
        stored=stage_upload_sync(upload,app.state.document_storage_dir,app.state.config)
        material_change(db,contract,user)
        document=new_document(db,contract,user,stored,replaces=old)
        db.add(Revision(contract_id=contract.id,actor_id=user.id,action='document_uploaded',before={'document_id':old.id},
            after={'document_id':document.id,'sha256':document.sha256,'replaces_id':old.id}))
        db.commit()
        if not app.state.config.queued_document_scans:
            try:process_document(db,app.state.config,app.state.document_scanner,document.id,user=user)
            except Exception:db.rollback()
        return RedirectResponse(f'/contracts/{contract_id}',status_code=303)

    @app.post('/contracts/{contract_id}/documents/{document_id}/link')
    def correct_link(request:Request,contract_id:int,document_id:int,db=Depends(get_db)):
        from app.main import approved_external_url
        form=parsed_form(request, max_files=0,max_fields=5)
        request.state.safe_values = safe_values(form)
        user,contract,old=writable(request,db,form,contract_id,document_id)
        if not old.external_url:raise HTTPException(400,'Only existing DMS links can be corrected here')
        if db.scalar(select(ContractDocument.id).where(ContractDocument.replaces_id==old.id,
                ContractDocument.state.in_(('pending','quarantined')))):
            raise HTTPException(409,'A replacement is already pending; recover its job')
        url=approved_external_url(app.state.config,str(form.get('external_url','')))
        material_change(db,contract,user)
        new=ContractDocument(contract_id=contract.id,uploaded_by_id=user.id,original_filename=old.original_filename,
            external_url=url,content_type='application/x-dms-link',size_bytes=0,state='link',scan_result='not_applicable',
            provenance='external_link',replaces_id=old.id,replaces_version=old.version)
        old.state='superseded';old.version+=1
        db.add(new);db.flush()
        db.add(Revision(contract_id=contract.id,actor_id=user.id,action='document_uploaded',before={'document_id':old.id},
            after={'document_id':new.id,'replaces_id':old.id,'source':'external_document_system'}))
        db.commit()
        return RedirectResponse(f'/contracts/{contract_id}',status_code=303)

    @app.post('/contracts/{contract_id}/documents/{document_id}/hold')
    def hold(request:Request,contract_id:int,document_id:int,db=Depends(get_db)):
        form=parsed_form(request, max_files=0,max_fields=4)
        request.state.safe_values = safe_values(form)
        user,_=user_csrf(request,db)
        if user.role!='admin':raise HTTPException(403,'Records administrator required')
        user,contract,document=writable(request,db,form,contract_id,document_id)
        # Placing a hold is supported. Release/disposal require separately approved policy.
        if document.legal_hold:raise HTTPException(409,'Document is already held')
        document.legal_hold=True;document.version+=1
        audit(db,user.id,'document_hold_placed',f'document:{document.id}')
        db.commit()
        return RedirectResponse(f'/contracts/{contract_id}',status_code=303)
