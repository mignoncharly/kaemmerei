"""Real before/after browser verification against disposable synthetic data only.

Uses the existing authorized Windows Playwright workflow. The baseline Jinja/CSS
is rendered against the same running application and data, never a mockup.
"""
import argparse
from io import BytesIO
import json
from pathlib import Path
import socket
import subprocess
import sys
import threading
import time
from xml.etree import ElementTree as ET
from zipfile import ZipFile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
if (ROOT/'.verification/browser-tools/playwright').exists():
    sys.path.insert(0,str(ROOT/'.verification/browser-tools'))

def execute(args, output, result):
    from playwright.sync_api import sync_playwright
    from jinja2 import ChoiceLoader, DictLoader
    import uvicorn
    from tests.support import environment_context, PASSWORD
    from tests.test_contract_toolbar import seed
    def check(name, value):
        if not value:
            result['failed_check']=name
            raise AssertionError(name)
        result['checks'].append(name)
    def baseline(path):
        return subprocess.check_output(['git','show',f'{args.baseline_ref}:{path}'],cwd=ROOT).decode('utf-8')
    old_template=baseline('app/templates/list.html')
    old_css=baseline('app/static/site.css');old_js=baseline('app/static/interface.js')
    result['baseline']=subprocess.check_output(['git','rev-parse',args.baseline_ref],cwd=ROOT,text=True).strip()
    result['stage']='synthetic_fixture'
    with environment_context('sqlite') as (_,app):
        from app.main import TEMPLATES
        seed(app)
        sock=socket.socket();sock.bind(('127.0.0.1',0));sock.listen(128)
        address=f'http://localhost:{sock.getsockname()[1]}'
        server=uvicorn.Server(uvicorn.Config(app,log_level='error',access_log=False,lifespan='off'))
        thread=threading.Thread(target=server.run,kwargs={'sockets':[sock]},daemon=True);thread.start()
        loader=TEMPLATES.env.loader
        try:
            deadline=time.monotonic()+15
            while not server.started and time.monotonic()<deadline:time.sleep(.05)
            check('server_started',server.started)
            result['stage']='automation_driver'
            with sync_playwright() as pw:
                result['stage']='browser_launch'
                browser=pw.chromium.launch(headless=True,channel=args.channel)
                result['stage']='browser_scenarios';result['browser_version']=browser.version
                shots=result['screenshots'];positions={};result['first_row_positions']=positions;csp=[]
                def screenshot(page,name):
                    page.screenshot(path=str(output/(name+'.png')),full_page=True);shots.append(name+'.png')
                def sign_in(page,role):
                    page.goto(address+'/login');page.locator('#username').fill(role);page.locator('#password').fill(PASSWORD)
                    page.get_by_role('button',name='Anmelden',exact=True).click();page.wait_for_load_state('networkidle')
                    page.goto(address+'/')
                # Only templates/assets are substituted. Requests and records are real.
                before_context=browser.new_context(locale='de-DE');page=before_context.new_page();sign_in(page,'admin')
                TEMPLATES.env.loader=ChoiceLoader([DictLoader({'list.html':old_template}),loader]);TEMPLATES.env.cache.clear()
                page.route('**/static/site.css*',lambda route:route.fulfill(body=old_css,content_type='text/css'))
                page.route('**/static/interface.js*',lambda route:route.fulfill(body=old_js,content_type='application/javascript'))
                for width in (390,768,1280,1440):
                    page.set_viewport_size({'width':width,'height':1000});page.goto(address+'/')
                    positions[str(width)]={'before':page.locator('.table-panel tbody tr').first.bounding_box()['y']}
                    screenshot(page,f'before-{width}')
                TEMPLATES.env.loader=loader;TEMPLATES.env.cache.clear();before_context.close()
                for role in ('admin','kultur','pruefer'):
                    context=browser.new_context(locale='de-DE');page=context.new_page();sign_in(page,role)
                    page.on('console',lambda message:csp.append('CSP violation') if 'Content Security Policy' in message.text else None)
                    for width in (390,768,1280,1440):
                        page.set_viewport_size({'width':width,'height':1000});page.goto(address+'/')
                        toggle=page.locator('#filter-toggle')
                        check(f'{role}_collapsed_{width}',toggle.get_attribute('aria-expanded')=='false' and not page.locator('#advanced-filter-panel').is_visible())
                        check(f'{role}_reflow_{width}',page.evaluate('document.documentElement.scrollWidth<=innerWidth+1'))
                        screenshot(page,f'after-{role}-{width}')
                        if role=='admin':
                            positions[str(width)]['after']=page.locator('.table-panel tbody tr').first.bounding_box()['y']
                            check(f'rows_higher_{width}',positions[str(width)]['before']-positions[str(width)]['after']>100)
                            if width>=1280:check(f'first_row_visible_{width}',positions[str(width)]['after']<900)
                        row_y=page.locator('.table-panel tbody tr').first.bounding_box()['y']
                        toggle.focus();page.keyboard.press('Enter')
                        dialog=page.locator('.contract-filter-dialog')
                        check(f'{role}_keyboard_expand_{width}',dialog.is_visible() and toggle.get_attribute('aria-expanded')=='true')
                        check(f'{role}_initial_focus_{width}',page.locator('#q').evaluate('(e)=>document.activeElement===e'))
                        check(f'{role}_overlay_no_layout_shift_{width}',abs(page.locator('.table-panel tbody tr').first.bounding_box()['y']-row_y)<2)
                        check(f'{role}_dialog_reflow_{width}',dialog.evaluate('(e)=>e.scrollWidth<=e.clientWidth+1'))
                        page.locator('#status').select_option('draft')
                        screenshot(page,f'expanded-{role}-{width}')
                        page.get_by_role('link',name='Zurücksetzen',exact=True).focus();page.keyboard.press('Tab')
                        check(f'{role}_focus_contained_{width}',dialog.evaluate('(e)=>e.contains(document.activeElement)'))
                        page.keyboard.press('Escape')
                        check(f'{role}_escape_focus_{width}',not dialog.is_visible() and toggle.evaluate('(e)=>document.activeElement===e'))
                        toggle.click()
                        check(f'{role}_reopen_preserves_{width}',page.locator('#status').input_value()=='draft')
                        if width>700:
                            page.mouse.click(4,4)
                            check(f'{role}_outside_dismiss_{width}',not dialog.is_visible())
                            toggle.click()
                        page.locator('#q').fill('Synthetic');page.locator('#q').press('Enter');page.wait_for_load_state('networkidle')
                        check(f'{role}_collapsed_after_apply_{width}',not page.locator('.contract-filter-dialog').is_visible())
                        check(f'{role}_active_chips_{width}',page.locator('.filter-chip').count()==2)
                        screenshot(page,f'active-{role}-{width}')
                        page.get_by_role('link',name='Alle Filter zurücksetzen',exact=True).click();page.wait_for_load_state('networkidle')
                        check(f'{role}_reset_all_{width}',page.locator('.filter-chip').count()==0 and page.locator('#q').input_value()=='')
                    page.locator('#filter-toggle').click()
                    page.locator('#q').fill('Synthetic');page.locator('#q').press('Enter');page.wait_for_load_state('networkidle')
                    expected=30 if role=='kultur' else 32
                    check(role+'_enter_search',page.locator('#q').input_value()=='Synthetic' and page.locator('.contract-result-count').inner_text()==f'({expected})')
                    page.locator('#filter-toggle').click()
                    page.locator('#status').select_option('draft')
                    page.locator('#contract_type').select_option('Miete');page.locator('#contact_person').select_option('Dienststelle')
                    page.locator('#page_size').select_option('25')
                    page.get_by_role('button',name='Filter anwenden',exact=True).click();page.wait_for_load_state('networkidle')
                    check(role+'_active_filter_count','Suche & Filter (4)' in page.locator('#filter-toggle').inner_text())
                    page.get_by_role('link',name='Nächste Seite',exact=True).click();page.wait_for_load_state('networkidle')
                    check(role+'_pagination',page.locator('.table-panel tbody tr').count()==expected-25)
                    with page.expect_download() as event:page.get_by_role('link',name='Alle Treffer exportieren',exact=True).click()
                    download=event.value
                    with ZipFile(BytesIO(Path(download.path()).read_bytes())) as book:
                        sheet=ET.fromstring(book.read('xl/worksheets/sheet1.xml'))
                        check(role+'_export_all_matching_rows',len(sheet.findall('.//{http://schemas.openxmlformats.org/spreadsheetml/2006/main}row'))==expected+1)
                    page.get_by_role('link',name='Status: Entwurf entfernen',exact=True).click();page.wait_for_load_state('networkidle')
                    check(role+'_remove_preserves_search',page.locator('#q').input_value()=='Synthetic' and page.locator('.filter-chip').count()==3)
                    check(role+'_removal_focus',page.locator('#filter-toggle').evaluate('(e)=>document.activeElement===e'))
                    page.go_back();page.wait_for_load_state('networkidle')
                    check(role+'_browser_back',page.locator('.filter-chip').count()==4 and page.locator('#q').input_value()=='Synthetic')
                    page.go_forward();page.wait_for_load_state('networkidle')
                    page.get_by_role('link',name='Suche: Synthetic entfernen',exact=True).click();page.wait_for_load_state('networkidle')
                    check(role+'_clear_search_keeps_filters',page.locator('#q').input_value()=='' and page.locator('.filter-chip').count()==2)
                    page.get_by_role('link',name='Alle Filter zurücksetzen',exact=True).click();page.wait_for_load_state('networkidle')
                    check(role+'_reset',page.locator('.filter-chip').count()==0 and page.locator('#q').input_value()=='')
                    check(role+'_unfiltered_count',page.locator('.contract-result-count').inner_text()==f'({expected+1})')
                    check(role+'_create_permission',(page.locator('.contract-header-actions a[href="/contracts/new"]').count()==1)==(role!='pruefer'))
                    page.emulate_media(reduced_motion='reduce');page.locator('#filter-toggle').click()
                    check(role+'_reduced_motion',page.locator('.contract-filter-dialog').evaluate('(e)=>getComputedStyle(e).animationName')=='none')
                    page.get_by_role('button',name='Suche und Filter schließen').click()
                    check(role+'_close_button',page.locator('#filter-toggle').get_attribute('aria-expanded')=='false')
                    if role=='kultur':check('restricted_contract_denied',page.goto(address+'/contracts/32').status==404)
                    context.close()
                nojs=browser.new_context(java_script_enabled=False,locale='de-DE');page=nojs.new_page();sign_in(page,'admin')
                page.locator('.filter-fallback').click();page.locator('#status').select_option('draft')
                page.get_by_role('button',name='Filter anwenden').click();page.wait_for_load_state('networkidle')
                check('native_no_js_filtering',page.locator('.filter-chip').count()==1);nojs.close()
                check('no_csp_violations',not csp)
                result['screenshots']=shots;result['first_row_positions']=positions;browser.close()
        finally:
            TEMPLATES.env.loader=loader;TEMPLATES.env.cache.clear()
            server.should_exit=True;thread.join(timeout=15);sock.close()

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--channel',default='msedge',choices=('msedge','chrome','chromium'))
    parser.add_argument('--baseline-ref',default='a36fb93')
    parser.add_argument('--output',type=Path,default=ROOT/'.verification/filter-popover-browser')
    args=parser.parse_args()
    from app.documents import reject_links
    from scripts.pilot_verification import source_identity
    from scripts.browser_diagnostics import failure
    output=args.output.absolute();reject_links(output);output=output.resolve()
    if not output.is_relative_to(ROOT/'.verification'):raise ValueError('Local verification output required')
    output.mkdir(parents=True,exist_ok=False)
    result={'format':'ohvr-toolbar-browser-v1','checks':[],'screenshots':[],'synthetic_only':True,
            'stage':'source_validation','visual_inspection':'NOT_PERFORMED'}
    try:
        result['source']=source_identity();execute(args,output,result)
        result['stage']='source_validation';source_identity(result['source']);result.update(status='passed',stage='complete')
    except Exception as error:
        result.update(status='failed',**failure(error,result['stage'],result.get('failed_check')))
    (output/'result.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result))
    if result['status']!='passed':raise SystemExit(1)

if __name__=='__main__':main()
