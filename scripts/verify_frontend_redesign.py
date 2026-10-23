"""Real-browser redesign coverage on disposable synthetic resources only.

Requires a committed source and an authorized local Windows terminal. This adds
responsive screenshots/keyboard checks to the unchanged U026 browser journeys.
No arbitrary target URL, credentials, real files or municipal records are accepted.
"""
import argparse
from dataclasses import replace
from datetime import date, timedelta
import json
from pathlib import Path
import socket
import sys
import threading
import time
from uuid import UUID

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
if (ROOT/'.verification/browser-tools/playwright').exists():
    sys.path.insert(0,str(ROOT/'.verification/browser-tools'))

def seed_extended(client, app):
    """Valid migrated metadata for unavailable documents; never mark it scan-clean."""
    from uuid import uuid4
    from tests.support import login, create_contract
    from app.models import Contract, ContractDocument, ContractReview, ContactIdentity, Department, RecipientTeam, RecipientMembership, User
    from sqlalchemy import select
    login(client,'admin')
    cid=create_contract(client,designation='SYNTHETISCH | Nutzung der Sporthalle')
    create_contract(client,'2',designation='PRIVATE_SYNTHETIC_OTHER_DEPARTMENT')
    with app.state.session_factory() as db:
        empty_department=Department(name='Synthetischer Leerbestand');db.add(empty_department);db.flush()
        db.add(User(username='leer',role='department',department_id=empty_department.id,password_hash=db.get(User,1).password_hash))
        db.add(ContactIdentity(display_name='Synthetic Browser Contact',department_id=1,scope_key=1,is_active=True))
        reviewer=db.scalar(select(User).where(User.username=='pruefer'));reviewer.can_approve=True
        team=RecipientTeam(name='Synthetische Prüfstelle');db.add(team);db.flush()
        db.add(RecipientMembership(team_id=team.id,user_id=reviewer.id))
        contract=db.get(Contract,cid)
        db.add(ContractReview(contract_id=cid,recipient=team.name,subject='Synthetische Dokumentenprüfung',
            status='open',request_text='Vollständigkeit prüfen.',result_text='',created_by_id=1,
            team_id=team.id,assigned_user_id=reviewer.id,content_revision=contract.content_revision,
            due_date=date.today()+timedelta(days=5)))
        for state in ('pending','rejected','legacy_unverified'):
            db.add(ContractDocument(contract_id=cid,uploaded_by_id=1,original_filename=f'synthetic-{state}.txt',
                storage_key=uuid4().hex,content_type='text/plain',size_bytes=12,state=state,scan_result='pending' if state=='pending' else 'unverified'))
        db.commit()
    return cid


def extended(args, output, result):
    result['stage']='dependencies'
    from scripts.browser_layout import measure_reflow
    from playwright.sync_api import sync_playwright
    import uvicorn
    from tests.support import environment_context, csrf_from, PASSWORD, contract_payload
    from app.models import User
    from sqlalchemy import select
    def check(name, condition):
        if not condition:
            result['failed_check']=name
            raise AssertionError(name)
        result['checks'].append(name)
    result['stage']='synthetic_fixture'
    with environment_context('sqlite') as (client, app):
        cid=seed_extended(client,app)
        @app.get('/__synthetic_error_500')
        def simulated_failure():
            raise RuntimeError('Synthetic failure for safe error-page verification')
        sock=socket.socket();sock.bind(('127.0.0.1',0));sock.listen(128)
        address=f'http://localhost:{sock.getsockname()[1]}'
        server=uvicorn.Server(uvicorn.Config(app,log_level='critical',access_log=False,lifespan='off'))
        thread=threading.Thread(target=server.run,kwargs={'sockets':[sock]},daemon=True);thread.start()
        try:
            deadline=time.monotonic()+15
            while not server.started and time.monotonic()<deadline:time.sleep(.05)
            check('redesign_server_started',server.started)
            result['stage']='automation_driver'
            with sync_playwright() as pw:
                result['stage']='browser_launch'
                browser=pw.chromium.launch(headless=True,channel=args.channel)
                result['browser_version']=browser.version
                result['stage']='browser_scenarios'
                captures=result.setdefault('screenshots',[]);csp=[]
                def sign_in(page, name):
                    page.goto(address+'/login')
                    page.locator('#username').fill(name);page.locator('#password').fill(PASSWORD)
                    page.get_by_role('button',name='Anmelden',exact=True).click()
                    page.wait_for_load_state('networkidle')
                def capture(page,name):
                    page.screenshot(path=str(output/(name+'.png')),full_page=True)
                    captures.append(name+'.png')
                for role in ('pruefer','kultur','admin'):
                    context=browser.new_context(viewport={'width':1440,'height':1000},locale='de-DE')
                    page=context.new_page()
                    page.on('console',lambda msg:csp.append('CSP violation') if 'Content Security Policy' in msg.text else None)
                    page.goto(address+'/login')
                    if role=='admin':capture(page,'login-desktop')
                    sign_in(page,role)
                    check(role+'_sidebar_admin_visibility',(page.locator('.sidebar a[href="/admin/users"]').count()>0)==(role=='admin'))
                    paths=[('dashboard','/dashboard'),('contracts','/'),('detail',f'/contracts/{cid}'),
                           ('inbox','/reviews'),('reports','/reports'),('password','/account/password'),
                           ('not-found','/contracts/999999')]
                    if role!='pruefer':paths += [('create','/contracts/new'),('edit',f'/contracts/{cid}/edit')]
                    if role=='admin':paths += [('users','/admin/users'),('new-user','/admin/users/new'),
                                              ('edit-user','/admin/users/2/edit'),('identities','/admin/identities'),('integrations','/admin/integrations')]
                    else:paths += [('forbidden','/admin/users')]
                    for width in (1440,1280,768,390,320):
                        page.set_viewport_size({'width':width,'height':1000})
                        for name,path in paths:
                            page.goto(address+path)
                            check(f'{role}_{name.replace("-","_")}_reflow_{width}',measure_reflow(page,output,result,f'{role}_{name.replace("-","_")}_reflow_{width}'))
                            check(f'{role}_{name.replace("-","_")}_main_{width}',page.locator('main h1').count()==1)
                            if width==1440 or (width in (390,320) and name in ('dashboard','contracts','create','detail','identities')):
                                capture(page,f'{role}-{name}-{width}')
                    page.set_viewport_size({'width':390,'height':900});page.goto(address+'/dashboard')
                    opener=page.get_by_role('button',name='Navigation öffnen',exact=True);opener.click()
                    check(role+'_drawer_open',page.locator('.sidebar').get_attribute('aria-modal')=='true')
                    capture(page,role+'-mobile-navigation')
                    page.keyboard.press('Shift+Tab');page.keyboard.press('Tab')
                    check(role+'_drawer_focus_trapped',page.evaluate('!!document.activeElement.closest(".sidebar")'))
                    page.keyboard.press('Escape')
                    check(role+'_drawer_escape_focus_return',opener.evaluate('(e)=>e===document.activeElement'))
                    page.goto(address+'/?q=NO_MATCH_SYNTHETIC')
                    capture(page,role+'-empty-results')
                    if role=='kultur':check('redesign_department_isolation','PRIVATE_SYNTHETIC_OTHER_DEPARTMENT' not in page.content())
                    if role=='pruefer':
                        page.goto(address+f'/contracts/{cid}')
                        check('reviewer_no_contract_edit',page.locator(f'a[href="/contracts/{cid}/edit"]').count()==0)
                        page.locator('.review-update summary').click()
                        page.locator('.review-update select[name=status]').select_option('in_review')
                        page.locator('.review-update textarea').fill('Synthetische Prüfung begonnen.')
                        page.get_by_role('button',name='Rückmeldung speichern',exact=True).click()
                        page.wait_for_load_state('networkidle')
                        check('redesign_reviewer_action','Synthetische Prüfung begonnen.' in page.content())
                    if role=='admin':
                        page.set_viewport_size({'width':1440,'height':1000})
                        page.goto(address+f'/contracts/{cid}')
                        check('unscanned_documents_not_downloadable',page.locator('.document-actions a').count()==0)
                        page.goto(address+'/?page=0');capture(page,'validation-422')
                        page.goto(address+'/__synthetic_error_500');capture(page,'server-error-500')
                        page.goto(address+'/')
                        page.locator('.excel-import-panel summary').click()
                        page.locator('#excel-file').set_input_files({'name':'synthetic-invalid.xlsx','mimeType':'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet','buffer':b'Invalid synthetic workbook'})
                        page.get_by_role('button',name='Import starten',exact=True).click();page.wait_for_load_state('networkidle')
                        capture(page,'import-error')
                        page.goto(address+f'/contracts/{cid}/edit')
                        payload=contract_payload(designation='Concurrent synthetic change')
                        current=client.get(f'/contracts/{cid}/edit')
                        import re
                        payload.update(csrf_token=csrf_from(current.text),version=re.search(r'name="version" value="(\d+)"',current.text)[1])
                        client.post(f'/contracts/{cid}/edit',data=payload)
                        page.locator('#designation').fill('Preserved synthetic input')
                        page.get_by_role('button',name='Änderungen speichern',exact=True).click();page.wait_for_load_state('networkidle')
                        check('redesign_conflict_input_preserved',page.locator('.recovery-values').inner_text().find('Bezeichnung')>=0)
                        capture(page,'conflict-409')
                    context.close()
                context=browser.new_context(locale='de-DE');page=context.new_page();sign_in(page,'leer')
                page.goto(address+'/dashboard')
                check('empty_scoped_dashboard','Ihr Vertragsregister ist bereit.' in page.content())
                capture(page,'empty-dashboard');context.close()
                result['stage']='mfa'
                # Initial password and MFA use dedicated synthetic accounts.
                with app.state.session_factory() as db:
                    user=db.scalar(select(User).where(User.username=='bau'));user.must_change_password=True;db.commit()
                context=browser.new_context(locale='de-DE');page=context.new_page();sign_in(page,'bau')
                check('initial_password_without_sidebar',page.locator('.sidebar').count()==0);capture(page,'initial-password')
                context.close()
                from cryptography.fernet import Fernet
                from app.mfa_codec import SeedCipher
                from app.mfa_service import authorize_enrollment,enforce_policy
                import pyotp
                key=Path(app.state.document_storage_dir).parent/'redesign-mfa-key.json'
                key.write_text(json.dumps([Fernet.generate_key().decode()]),encoding='utf-8')
                app.state.mfa_cipher=SeedCipher(key);app.state.config=replace(app.state.config,require_mfa=True,mfa_key_file=key)
                with app.state.session_factory() as db:
                    authorize_enrollment(db,'kultur','SYNTHETIC-REDESIGN');enforce_policy(db,'SYNTHETIC-REDESIGN');db.commit()
                context=browser.new_context(locale='de-DE');page=context.new_page();sign_in(page,'kultur')
                capture(page,'mfa-enrollment-start')
                page.get_by_role('button',name='Einrichtung starten',exact=True).click()
                seed=page.locator('#enrollment-secret').input_value()
                page.screenshot(path=str(output/'mfa-enrollment-masked.png'),full_page=True,mask=[page.locator('#enrollment-secret')]);captures.append('mfa-enrollment-masked.png')
                page.locator('#mfa-code').fill(pyotp.TOTP(seed).now())
                page.get_by_role('button',name='Anmeldung abschließen',exact=True).click();page.wait_for_load_state('networkidle')
                context.close();context=browser.new_context(locale='de-DE');page=context.new_page();sign_in(page,'kultur')
                capture(page,'mfa-verification');context.close()
                check('redesign_no_csp_violations',not csp)
                result['screenshots']=captures
                browser.close()
        finally:
            server.should_exit=True;thread.join(timeout=15);sock.close()

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--channel',choices=('msedge','chrome','chromium'),default='msedge')
    parser.add_argument('--output',type=Path,default=ROOT/'.verification/redesign-browser')
    parser.add_argument('--run-id',type=lambda value: UUID(hex=value).hex)
    args=parser.parse_args()
    from scripts.pilot_verification import source_identity
    from scripts.browser_diagnostics import failure
    from app.documents import reject_links
    output=args.output.absolute();reject_links(output);output=output.resolve()
    if not output.is_relative_to(ROOT/'.verification'):raise ValueError('Verification output must stay in .verification')
    output.mkdir(parents=True,exist_ok=False)
    result={'format':'ohvr-redesign-browser-v1','synthetic_only':True,'scanner':'synthetic',
            'checks':[],'stage':'source_validation','visual_inspection':'NOT_PERFORMED','screen_reader':'NOT_PERFORMED'}
    result['run_id']=args.run_id
    try:
        result['source']=source_identity()
        # Retain the original tested journeys: create/edit, upload/download,
        # department isolation, archive and MFA enrollment/replay protection.
        from scripts.verify_phase8_browser import execute
        execute(args,output,result)
        extended(args,output,result)
        result['stage']='source_validation';source_identity(result['source'])
        result['checks'].append('source_unchanged')
        result.update(status='passed',stage='complete')
    except Exception as exc:
        result.update(status='failed',**failure(exc,result['stage'],result.get('failed_check')))
    (output/'result.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result))
    if result['status']!='passed':raise SystemExit(1)

if __name__=='__main__':main()
