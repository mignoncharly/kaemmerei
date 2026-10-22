"""Browser verification using only a disposable synthetic application and accounts."""
import argparse
from io import BytesIO
import json
from pathlib import Path
import socket
import sys
import threading
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
if (ROOT/'.verification/browser-tools/playwright').exists():
    sys.path.insert(0,str(ROOT/'.verification/browser-tools'))


def execute(args,output,result):
    from playwright.sync_api import sync_playwright
    import uvicorn
    from app.excel import read_xlsx
    from tests.support import environment_context, PASSWORD
    from tests.test_contract_toolbar import seed
    from tests.test_phase7 import workbook
    def check(name,value):
        if not value:
            result['failed_check']=name
            raise AssertionError(name)
        result['checks'].append(name)
    with environment_context('sqlite') as (_,app):
        seed(app)
        sock=socket.socket();sock.bind(('127.0.0.1',0));sock.listen(128)
        address=f'http://localhost:{sock.getsockname()[1]}'
        server=uvicorn.Server(uvicorn.Config(app,log_level='error',access_log=False,lifespan='off'))
        thread=threading.Thread(target=server.run,kwargs={'sockets':[sock]},daemon=True);thread.start()
        try:
            deadline=time.monotonic()+15
            while not server.started and time.monotonic()<deadline:time.sleep(.05)
            check('server_started',server.started)
            result['stage']='automation_driver'
            with sync_playwright() as pw:
                result['stage']='browser_launch'
                browser=pw.chromium.launch(headless=True,channel=args.channel)
                result['browser_version']=browser.version;result['stage']='browser_scenarios'
                for role in ('admin','kultur','bau','pruefer'):
                    context=browser.new_context(locale='de-DE');page=context.new_page()
                    page.goto(address+'/login');page.locator('#username').fill(role);page.locator('#password').fill(PASSWORD)
                    page.get_by_role('button',name='Anmelden',exact=True).click();page.wait_for_load_state('networkidle')
                    def capture(name):
                        filename=f'{role}-{name}.png';page.screenshot(path=str(output/filename),full_page=True)
                        result['screenshots'].append(filename)
                    def download_selection(expected):
                        with page.expect_download() as event:
                            page.get_by_role('button',name='Ausgewählte Verträge exportieren',exact=True).click()
                        return len(read_xlsx(Path(event.value.path()).read_bytes()))==expected
                    for width in (390,768,1280,1440):
                        page.set_viewport_size({'width':width,'height':1000});page.goto(address+'/')
                        boxes=page.locator('.select-contract');all_box=page.locator('#select-page')
                        check(f'{role}_empty_selection_{width}',not page.locator('#selection-export-form').is_visible() and page.locator('#export-selection').is_disabled())
                        check(f'{role}_reflow_{width}',page.evaluate('document.documentElement.scrollWidth<=innerWidth+1'))
                        capture(f'default-{width}')
                        boxes.first.focus();page.keyboard.press('Space')
                        check(f'{role}_keyboard_selection_{width}',boxes.first.is_checked() and all_box.evaluate('(e)=>e.indeterminate'))
                        check(f'{role}_single_export_{width}',download_selection(1))
                        boxes.nth(1).check()
                        check(f'{role}_multiple_export_{width}',download_selection(2))
                        capture(f'selected-{width}')
                        all_box.check()
                        check(f'{role}_select_page_{width}',page.locator('.select-contract:checked').count()==boxes.count() and not all_box.evaluate('(e)=>e.indeterminate'))
                        check(f'{role}_page_export_{width}',download_selection(boxes.count()))
                        boxes.first.uncheck()
                        check(f'{role}_partial_{width}',all_box.evaluate('(e)=>e.indeterminate'))
                        page.get_by_role('button',name='Auswahl aufheben',exact=True).click()
                        check(f'{role}_clear_{width}',not page.locator('#selection-export-form').is_visible() and all_box.evaluate('(e)=>document.activeElement===e'))
                        if role!='pruefer':
                            check(f'{role}_import_notes_closed_{width}',not page.locator('.excel-import-notes').evaluate('(e)=>e.open'))
                            submit=page.locator('#excel-import-submit')
                            check(f'{role}_import_initial_disabled_{width}',submit.is_disabled())
                            controls=[page.locator('.excel-action-row>a'),page.locator('.excel-file-picker'),submit]
                            bounds=[control.bounding_box() for control in controls]
                            def check_centering(state):
                                metrics=[control.evaluate("""(e) => {
                                    const box=e.getBoundingClientRect();
                                    const text=e.querySelector('.action-content').getBoundingClientRect();
                                    const style=getComputedStyle(e);
                                    return {display:style.display, align:style.alignItems,
                                        justify:style.justifyContent, lineHeight:style.lineHeight,
                                        xOffset:text.x+text.width/2-box.x-box.width/2,
                                        yOffset:text.y+text.height/2-box.y-box.height/2,
                                        textCenterY:text.y+text.height/2};
                                }""") for control in controls]
                                result.setdefault('import_alignment',[]).append(
                                    {'role':role,'width':width,'state':state,'controls':metrics})
                                check(f'{role}_content_centered_{state}_{width}',all(
                                    m['display']=='flex' and m['align']=='center' and
                                    m['justify']=='center' and abs(m['xOffset'])<1 and
                                    abs(m['yOffset'])<1 for m in metrics))
                                check(f'{role}_line_height_{state}_{width}',len({m['lineHeight'] for m in metrics})==1)
                                if width>700:
                                    check(f'{role}_text_row_{state}_{width}',
                                          max(m['textCenterY'] for m in metrics)-min(m['textCenterY'] for m in metrics)<1)
                            check_centering('disabled')
                            check(f'{role}_control_heights_{width}',all(abs(b['height']-48)<1 for b in bounds))
                            if width>700:
                                check(f'{role}_controls_aligned_{width}',max(b['y'] for b in bounds)-min(b['y'] for b in bounds)<1)
                            else:
                                check(f'{role}_controls_stacked_{width}',bounds[0]['y']+48<=bounds[1]['y'] and bounds[1]['y']+48<=bounds[2]['y'] and max(b['width'] for b in bounds)-min(b['width'] for b in bounds)<1)
                            page.locator('#excel-file').focus()
                            check(f'{role}_file_keyboard_focus_{width}',page.locator('.excel-file-picker').evaluate('(e)=>e.matches(":focus-within")'))
                            for name,data in [('falsch.csv',b'data'),('leer.xlsx',b''),('gross.xlsx',b'x'*(10*1024*1024+1))]:
                                page.locator('#excel-file').set_input_files({'name':name,'mimeType':'application/octet-stream','buffer':data})
                                check(f'{role}_invalid_file_{width}_{name.split(".")[0]}',submit.is_disabled() and page.locator('#excel-file-error').is_visible())
                            page.locator('#excel-file').set_input_files({'name':'synthetischer-import.xlsx','mimeType':'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet','buffer':workbook()})
                            check(f'{role}_filename_{width}','synthetischer-import.xlsx' in page.locator('.excel-filename').inner_text())
                            check(f'{role}_valid_file_enabled_{width}',submit.is_enabled() and not page.locator('#excel-file-error').is_visible())
                            check_centering('enabled')
                            page.locator('#excel-import-title').scroll_into_view_if_needed();capture(f'import-{width}')
                            page.locator('#excel-file').set_input_files([])
                            check(f'{role}_file_clear_disabled_{width}',submit.is_disabled() and not page.locator('#excel-filename').is_visible())
                    page.goto(address+'/?page_size=1');page.locator('.select-contract').first.check()
                    page.get_by_role('link',name='Nächste Seite',exact=True).click();page.wait_for_load_state('networkidle')
                    check(role+'_pagination_resets',page.locator('.select-contract:checked').count()==0)
                    page.go_back();page.wait_for_load_state('networkidle')
                    check(role+'_back_resets',page.locator('.select-contract:checked').count()==0)
                    page.locator('.select-contract').first.check();page.locator('#filter-toggle').click()
                    page.locator('#q').fill('TOOL')
                    check(role+'_filter_input_resets',page.locator('.select-contract:checked').count()==0)
                    page.locator('#q').press('Enter');page.wait_for_load_state('networkidle')
                    expected=2 if role=='bau' else 30 if role=='kultur' else 32
                    with page.expect_download() as event:
                        page.get_by_role('link',name='Alle Treffer exportieren',exact=True).click()
                    check(role+'_all_filtered',len(read_xlsx(Path(event.value.path()).read_bytes()))==expected)
                    if role!='pruefer':
                        page.goto(address+'/')
                        page.locator('#excel-file').set_input_files({'name':'ungueltig.xlsx','mimeType':'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet','buffer':b'invalid'})
                        page.get_by_role('button',name='Import starten',exact=True).click();page.wait_for_load_state('networkidle')
                        check(role+'_import_error',page.get_by_role('heading',name='Import nicht durchgeführt').is_visible());capture('import-error')
                        page.goto(address+'/')
                        page.locator('#excel-file').set_input_files({'name':'neu.xlsx','mimeType':'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet','buffer':workbook(external_reference='BROWSER-'+role)})
                        page.get_by_role('button',name='Import starten',exact=True).click();page.wait_for_load_state('networkidle')
                        check(role+'_import_success','erfolgreich abgeschlossen' in page.locator('#success-notice').inner_text());capture('import-success')
                    else:check('reviewer_no_import',page.locator('#excel-import-form').count()==0)
                    context.close()
                browser.close()
        finally:
            server.should_exit=True;thread.join(timeout=15);sock.close()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--channel',choices=('msedge','chrome','chromium'),default='msedge')
    parser.add_argument('--output',type=Path,default=ROOT/'.verification/excel-selection-browser')
    args=parser.parse_args()
    from app.documents import reject_links
    from scripts.pilot_verification import source_identity
    from scripts.browser_diagnostics import failure
    output=args.output.absolute();reject_links(output);output=output.resolve()
    if not output.is_relative_to(ROOT/'.verification'):raise ValueError('Local verification output required')
    output.mkdir(parents=True,exist_ok=False)
    result={'format':'ohvr-excel-selection-browser-v1','synthetic_only':True,'checks':[],
            'screenshots':[],'visual_inspection':'NOT_PERFORMED','stage':'source_validation'}
    try:
        result['source']=source_identity();execute(args,output,result)
        result['stage']='source_validation';source_identity(result['source'])
        result.update(status='passed',stage='complete')
    except Exception as error:
        result.update(status='failed',**failure(error,result['stage'],result.get('failed_check')))
    (output/'result.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result))
    if result['status']!='passed':raise SystemExit(1)


if __name__=='__main__':main()
