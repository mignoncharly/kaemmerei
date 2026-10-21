"""Password-proven challenges never authorize ordinary application operations."""
import pyotp
from fastapi import Depends, HTTPException, Request
from fastapi.responses import RedirectResponse

from app.identity_service import lock_identities
from app.logic import active_access
from app.mfa_codec import matching_step
from app import mfa_service
from app.models import LoginAttempt, User
from app.request_boundary import parsed_form
from app.security import (attempt_key,cookie_response,get_login_session,new_session,
                          require_csrf,reserve_login,throttled)


def install_mfa_routes(app,*,get_db,html):
    def challenge(request,db):
        session=get_login_session(request,db)
        if (session is None or session.user_id is not None or session.pending_user_id is None
                or session.mfa_attempts>=5):
            raise HTTPException(303,headers={'Location':'/login'})
        user=db.get(User,session.pending_user_id)
        if user is None or not active_access(user):
            raise HTTPException(403,'Anmeldung nicht mehr berechtigt')
        if app.state.mfa_cipher is None:
            raise HTTPException(503,'Mehrfaktor-Anmeldung ist derzeit nicht verfügbar')
        return session,user

    def context(request,db,session,user,*,error=''):
        state=mfa_service.material(db,session)
        if state is None:
            raise HTTPException(403,'Die lokale Administration muss die Einrichtung nach Identitätsprüfung freigeben')
        seed=None
        if state['ciphertext'] and not state['enabled']:
            try:seed=app.state.mfa_cipher.decrypt(user.id,state['ciphertext'])
            except ValueError:
                raise HTTPException(503,'Mehrfaktor-Einrichtung nicht verfügbar; Administration kontaktieren') from None
        return dict(csrf_token=session.csrf_token,enrolling=not state['enabled'],seed=seed,
                    username=user.username,error=error,user=None)

    @app.get('/account/mfa')
    def mfa_page(request:Request,db=Depends(get_db)):
        lock_identities(db)
        session,user=challenge(request,db)
        values=context(request,db,session,user)
        db.commit()
        return html(request,'mfa.html',values)

    @app.post('/account/mfa/start')
    def mfa_start(request:Request,db=Depends(get_db)):
        form=parsed_form(request,max_files=0,max_fields=1)
        lock_identities(db)
        session,user=challenge(request,db)
        require_csrf(request,db,str(form.get('csrf_token','')))
        candidate=app.state.mfa_cipher.encrypt(user.id,pyotp.random_base32())
        if mfa_service.material(db,session,candidate) is None:
            raise HTTPException(403,'Einrichtung muss durch die Administration freigegeben werden')
        db.commit()
        return RedirectResponse('/account/mfa',status_code=303)

    @app.post('/account/mfa')
    def mfa_verify(request:Request,db=Depends(get_db)):
        form=parsed_form(request,max_files=0,max_fields=2)
        lock_identities(db)
        session,user=challenge(request,db)
        require_csrf(request,db,str(form.get('csrf_token','')))
        ip=request.client.host if request.client else 'unknown'
        key=attempt_key('mfa:'+str(user.id),ip)
        if throttled(db,key) or not reserve_login(db,'mfa:'+str(user.id),ip):
            db.commit()
            raise HTTPException(429,'Codeprüfung vorübergehend gesperrt; später erneut anmelden')
        state=mfa_service.material(db,session)
        if state is None or not state['ciphertext']:
            raise HTTPException(403,'Mehrfaktor-Einrichtung zuerst freigeben und starten')
        # Both account/window counters and this challenge's attempts persist.
        session.mfa_attempts+=1
        db.flush()
        try:seed=app.state.mfa_cipher.decrypt(user.id,state['ciphertext'])
        except ValueError:
            db.rollback()
            raise HTTPException(503,'Mehrfaktor-Anmeldung nicht verfügbar; Administration kontaktieren') from None
        step=matching_step(seed,str(form.get('code','')).strip(),state['last_step'])
        if step is None or not mfa_service.confirm(db,session,step):
            db.add(LoginAttempt(key_hash=key))
            mfa_service.denied(db,session)
            if session.mfa_attempts>=5:
                db.delete(session);db.commit()
                return RedirectResponse('/login',status_code=303)
            values=context(request,db,session,user,error='Code ungültig, abgelaufen oder bereits verwendet.')
            db.commit()
            return html(request,'mfa.html',values,401)
        db.delete(session)
        db.flush()
        _,token=new_session(db,app.state.config.session_hours,user.id,mfa_verified=True)
        db.commit()
        return cookie_response(RedirectResponse('/',status_code=303),token,
            production=app.state.config.production,hours=app.state.config.session_hours)
