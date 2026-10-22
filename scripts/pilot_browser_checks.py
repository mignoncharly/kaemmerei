"""Additional browser journeys; disposable fixtures only, never a target URL CLI."""
from dataclasses import replace
import json
from pathlib import Path
import re
from cryptography.fernet import Fernet
import pyotp
from tests.support import PASSWORD,create_contract


def journeys(browser,address,fixture_client,app,check):
    foreign=create_contract(fixture_client,department_id='2',designation='SYNTHETIC foreign department')
    context=browser.new_context(locale='de-DE')
    page=context.new_page()
    def password(name):
        page.goto(address+'/login')
        page.locator('#username').fill(name);page.locator('#password').fill(PASSWORD)
        page.get_by_role('button',name='Anmelden',exact=True).click()
    try:
        password('kultur');page.wait_for_url(address+'/?notice=login')
        check('pilot_department_admin_denied',page.goto(address+'/admin/users').status==403)
        check('pilot_foreign_contract_denied',page.goto(address+f'/contracts/{foreign}').status==404)
        page.goto(address+'/contracts/new')
        page.locator('#designation').fill('SYNTHETIC Fachbereich equipment agreement')
        page.locator('#contract_type').select_option('Mietvertrag')
        page.locator('#relevant_date').fill('2026-01-01')
        page.locator('#contact_person').select_option(label='Synthetic Browser Contact')
        page.get_by_role('button',name='Vertrag speichern',exact=True).click()
        page.wait_for_url(re.compile(re.escape(address)+r'/contracts/\d+.*'))
        cid=int(re.search(r'/contracts/(\d+)',page.url)[1])
        check('pilot_create_contract',page.locator('h1').inner_text().find('SYNTHETIC')>=0)
        page.goto(address+f'/contracts/{cid}/edit')
        page.locator('#designation').fill('SYNTHETIC Fachbereich equipment agreement revised')
        page.get_by_role('button',name='Änderungen speichern',exact=True).click()
        page.wait_for_url(re.compile(re.escape(address)+r'/contracts/'+str(cid)+r'(?:\?.*)?$'))
        check('pilot_edit_history',page.locator('.history').inner_text().find('revised')>=0)
        upload=page.locator('form.document-upload')
        upload.locator('input[type=file]').set_input_files({'name':'synthetic.txt','mimeType':'text/plain','buffer':b'Synthetic contract attachment'})
        upload.locator('button[type=submit]').click();page.wait_for_load_state('networkidle')
        check('pilot_clean_document_listed',page.get_by_text('synthetic.txt',exact=True).count()>0)
        download=page.get_by_role('link',name='Herunterladen',exact=True).first
        with page.expect_download() as event:download.click()
        check('pilot_download',event.value.failure() is None)
        form=page.locator(f'form[action="/contracts/{cid}/reviews"]')
        form.locator('[name=subject]').fill('SYNTHETIC completeness review')
        form.locator('[name=request_text]').fill('Check the synthetic attachment; no financial/legal interpretation.')
        form.locator('button[type=submit]').click();page.wait_for_load_state('networkidle')
        check('pilot_review_request',page.get_by_text('SYNTHETIC completeness review',exact=True).count()>0)
        # A second scoped user must still not acquire access through a review request.
        other=browser.new_context(locale='de-DE')
        try:
            p=other.new_page();p.goto(address+'/login');p.locator('#username').fill('bau');p.locator('#password').fill(PASSWORD)
            p.get_by_role('button',name='Anmelden',exact=True).click();p.wait_for_url(address+'/?notice=login')
            check('pilot_other_department_cannot_read_created_contract',p.goto(address+f'/contracts/{cid}').status==404)
        finally:other.close()
        page.goto(address+f'/contracts/{cid}')
        page.get_by_text('Archivierung prüfen',exact=True).click()
        page.locator('[name=confirm_archive]').check()
        page.get_by_role('button',name='Vertrag jetzt archivieren',exact=True).click();page.wait_for_load_state('networkidle')
        check('pilot_archive_preserves_history',page.get_by_role('heading',name='Archivierter Vertrag',exact=True).count()==1 and page.locator('.history').count()==1)
        check('pilot_archived_edit_denied',page.goto(address+f'/contracts/{cid}/edit').status==409)
    finally:context.close()
    # Enable MFA only inside this already-isolated fixture; never change a real account.
    from app.mfa_codec import SeedCipher
    from app.mfa_service import authorize_enrollment,enforce_policy
    key=Path(app.state.document_storage_dir).parent/'browser-disposable-mfa-key.json'
    key.write_text(json.dumps([Fernet.generate_key().decode()]),encoding='utf-8')
    app.state.mfa_cipher=SeedCipher(key)
    app.state.config=replace(app.state.config,require_mfa=True,mfa_key_file=key)
    with app.state.session_factory() as db:
        authorize_enrollment(db,'kultur','SYNTHETIC-BROWSER');enforce_policy(db,'SYNTHETIC-BROWSER');db.commit()
    context=browser.new_context(locale='de-DE');page=context.new_page()
    try:
        password('kultur');page.wait_for_url(address+'/account/mfa')
        check('pilot_password_alone_not_authenticated',page.goto(address+'/contracts/new').url.endswith('/login'))
        page.goto(address+'/account/mfa')
        page.get_by_role('button',name='Einrichtung starten',exact=True).click()
        seed=page.locator('#enrollment-secret').input_value()
        code=pyotp.TOTP(seed).now()
        page.locator('#mfa-code').fill(code)
        page.get_by_role('button',name='Anmeldung abschließen',exact=True).click();page.wait_for_url(address+'/')
        check('pilot_mfa_enrollment_login',page.locator('h1').count()>0)
        # Fresh context, same code: challenge must reject replay. No seed/code screenshots or report.
        replay=browser.new_context(locale='de-DE')
        try:
            p=replay.new_page();p.goto(address+'/login');p.locator('#username').fill('kultur');p.locator('#password').fill(PASSWORD)
            p.get_by_role('button',name='Anmelden',exact=True).click();p.wait_for_url(address+'/account/mfa')
            p.locator('#mfa-code').fill(code);p.get_by_role('button',name='Anmeldung abschließen',exact=True).click()
            check('pilot_mfa_replay_denied',p.locator('[role=alert]').count()==1 and '/account/mfa' in p.url)
        finally:replay.close()
    finally:context.close()
