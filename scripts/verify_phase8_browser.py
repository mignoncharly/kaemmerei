"""Real browser verification against a disposable synthetic SQLite application."""
from pathlib import Path
import argparse
import json
import socket
import sys
import threading
import time
import re

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
# Optional local test-tool wheel extraction; never imported by the application.
if (ROOT/'.verification/browser-tools/playwright').exists():
    sys.path.insert(0,str(ROOT/'.verification/browser-tools'))


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--channel',choices=('chrome','msedge','chromium'),default=None)
    parser.add_argument('--output',type=Path,default=ROOT/'.verification/phase8-browser')
    parser.add_argument('--run-id',help='Parent-issued execution identity; not a credential')
    args=parser.parse_args()
    if args.run_id is not None and not re.fullmatch('[a-f0-9]{32}',args.run_id):
        parser.error('Invalid execution identity')
    from scripts.pilot_verification import source_identity
    from app.documents import reject_links
    source=source_identity()
    output=args.output.absolute();reject_links(output);output=output.resolve()
    if not output.is_relative_to(ROOT/'.verification'):raise ValueError('Local verification output required')
    output.mkdir(parents=True,exist_ok=False)
    results={'format':'ohvr-browser-verification-v2','source':source,'checks':[],'synthetic_only':True,
             'backend':'sqlite','scanner':'synthetic','screen_reader_manual_test':False}
    if args.run_id is not None:results['run_id']=args.run_id
    try:
        execute(args,output,results)
        results['stage']='source_validation'
        if source_identity(source)!=source:raise RuntimeError('Source changed')
        results['checks'].append('source_unchanged')
        results.update(status='passed',stage='complete',error_code=None)
    except Exception as error:
        from scripts.browser_diagnostics import failure
        results.update(status='failed',**failure(error,results['stage'],results.get('failed_check')))
    (output/'result.json').write_text(json.dumps(results,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(results))
    if results['status']!='passed':raise SystemExit(1)


def execute(args,output,results):
    results['stage']='dependencies'
    from playwright.sync_api import sync_playwright
    import uvicorn
    from tests.support import environment_context, login, create_contract, contract_payload, csrf_from, PASSWORD
    from app.models import ContactIdentity
    def check(name,condition):
        if not condition:
            results['failed_check']=name
            raise AssertionError(name)
        results['checks'].append(name)
    results['stage']='synthetic_fixture'
    with environment_context('sqlite') as (client,app):
        login(client,'admin');cid=create_contract(client,designation='Langer synthetischer Vertragsname '+('Vereinbarung '*10))
        edit=contract_payload(designation='Synthetischer Vertrag für Browserprüfung')
        edit.update(csrf_token=csrf_from(client.get(f'/contracts/{cid}/edit').text),version='1',
            annual_value='100',financial_direction='expense',value_basis='net')
        check('fixture_edit',client.post(f'/contracts/{cid}/edit',data=edit,follow_redirects=False).status_code==303)
        with app.state.session_factory() as db:
            db.add(ContactIdentity(display_name='Synthetic Browser Contact',department_id=1,scope_key=1,is_active=True))
            db.commit()
        sock=socket.socket();sock.bind(('127.0.0.1',0));sock.listen(128)
        address=f'http://localhost:{sock.getsockname()[1]}'
        server=uvicorn.Server(uvicorn.Config(app,log_level='error',access_log=False,lifespan='off'))
        thread=threading.Thread(target=server.run,kwargs={'sockets':[sock]},daemon=True);thread.start()
        try:
            deadline=time.monotonic()+15
            while not server.started and time.monotonic()<deadline:time.sleep(.05)
            check('server_started',server.started)
            results['stage']='automation_driver'
            with sync_playwright() as pw:
                results['stage']='browser_launch'
                browser=pw.chromium.launch(headless=True,channel=args.channel)
                results['stage']='browser_scenarios'
                results['browser_version']=browser.version
                context=browser.new_context(viewport={'width':1440,'height':1000},locale='de-DE')
                page=context.new_page();violations=[]
                page.on('console',lambda msg:violations.append(msg.text) if 'Content Security Policy' in msg.text or 'violates' in msg.text else None)
                page.goto(address+'/login');page.get_by_label('Benutzername',exact=True).fill('admin')
                page.get_by_label('Passwort',exact=True).fill(PASSWORD);page.get_by_role('button',name='Anmelden',exact=True).click()
                page.wait_for_url(address+'/?notice=login')
                page.goto(address+'/reports')
                check('chart_css_applied',page.locator('.pct-100').first.evaluate('(e)=>e.getBoundingClientRect().width')>0)
                check('no_inline_styles',page.locator('[style]').count()==0)
                check('html_language',page.locator('html').get_attribute('lang')=='de')
                check('report_table_headers',page.locator('table th').count()>0)
                page.screenshot(path=str(output/'reports-desktop.png'),full_page=True)
                page.goto(address+'/contracts/new')
                page.get_by_label('Bezeichnung *',exact=True).fill('Validation recovery')
                page.get_by_label('Vertragsart *',exact=True).select_option('Mietvertrag')
                page.get_by_label('Vertragsbeginn *',exact=True).fill('2026-01-01')
                page.get_by_label('Zuständige Person *',exact=True).select_option('Synthetic Browser Contact')
                page.get_by_label('Zuständiger Fachbereich *',exact=True).select_option('1')
                page.locator('#annual_value').fill('-1')
                # Submit an invalid server-side value without bypassing app checks.
                page.locator('form[action="/contracts/new"]').evaluate('(f)=>{f.noValidate=true;f.requestSubmit()}')
                page.wait_for_load_state('networkidle')
                check('validation_visible',page.locator('.alert').count()>0)
                page.wait_for_timeout(5500)
                check('error_persists_after_five_seconds',page.locator('.alert').is_visible())
                check('unchecked_renewal_preserved',not page.locator('input[type=checkbox][name=automatic_renewal]').is_checked())
                page.screenshot(path=str(output/'validation-desktop.png'),full_page=True)
                page.goto(address+'/')
                page.keyboard.press('Tab')
                check('keyboard_skip_link',page.evaluate('document.activeElement.classList.contains("skip-link")'))
                page.keyboard.press('Enter')
                check('skip_link_focus',page.evaluate('document.activeElement.id')=='main-content')
                page.goto(address+f'/contracts/{cid}')
                page.get_by_text('Archivierung prüfen',exact=True).click()
                check('archive_confirmation_required',page.locator('input[name=confirm_archive]').get_attribute('required') is not None)
                for width in (390,320):
                    page.set_viewport_size({'width':width,'height':900})
                    page.goto(address+'/contracts/new')
                    check(f'form_reflow_{width}',page.evaluate('document.documentElement.scrollWidth<=innerWidth+1'))
                    page.goto(address+'/reports')
                    check(f'report_reflow_{width}',page.evaluate('document.documentElement.scrollWidth<=innerWidth+1'))
                    page.screenshot(path=str(output/f'reports-{width}.png'),full_page=True)
                check('no_csp_violations',not violations)
                results['csp_violations']=violations
                from scripts.pilot_browser_checks import journeys
                journeys(browser,address,client,app,check,stage=lambda value:results.update(stage=value))
                browser.close()
        finally:
            server.should_exit=True;thread.join(timeout=15);sock.close()
            if thread.is_alive():raise RuntimeError('Synthetic browser server did not stop')


if __name__=='__main__':main()
