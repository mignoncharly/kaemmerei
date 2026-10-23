"""Fixed, shareable browser diagnostics: never serialize exception text or URLs."""
import re
from contextlib import contextmanager
from pathlib import Path

OPERATIONS = {'table_check_scrollable', 'table_press_arrow_right', 'table_wait_scroll',
              'table_read_scroll', 'table_scroll_to_end'}
ERROR_KINDS = {'csp_eval_blocked', 'target_closed', 'execution_context_destroyed',
               'element_detached', 'strict_mode_violation', 'timeout', 'unclassified'}
FRAME_FILES = {'scripts/verify_contract_toolbar.py', 'scripts/verify_excel_selection.py',
               'scripts/browser_layout.py', 'scripts/browser_focus.py'}


@contextmanager
def browser_operation(result, name, page):
    if name not in OPERATIONS:
        raise ValueError('Unknown browser operation')
    try:
        yield
    except Exception:
        result['failed_operation'] = name
        # Capture before context-manager teardown closes pages normally.
        try:
            result['page_closed_at_failure'] = bool(page.is_closed())
        except Exception:
            pass  # An unavailable diagnostic must not replace the original error.
        raise


def safe_execution_details(data, checks):
    """Whitelist optional child diagnostics, even if a child result is untrusted."""
    last = checks[-1] if checks else None
    details = {'last_completed_check': last if isinstance(last, str) and
               re.fullmatch('[a-z][a-z0-9_]{0,99}', last) else None}
    for key, choices in [('failed_operation', OPERATIONS), ('browser_error_kind', ERROR_KINDS)]:
        value = data.get(key)
        if isinstance(value, str) and value in choices:
            details[key] = value
    if type(data.get('page_closed_at_failure')) is bool:
        details['page_closed_at_failure'] = data['page_closed_at_failure']
    frames = data.get('source_frames')
    if isinstance(frames, list):
        details['source_frames'] = [dict(file=f['file'], line=f['line']) for f in frames[:12]
            if isinstance(f, dict) and isinstance(f.get('file'), str) and f['file'] in FRAME_FILES
            and type(f.get('line')) is int and 0 < f['line'] < 100000]
    return details


def execution_details(error, result):
    """No exception text/stack strings, source lines, locals or absolute paths leave here."""
    message = str(error).lower()
    signatures = (
        ('csp_eval_blocked', ('unsafe-eval',)),
        ('target_closed', ('target page, context or browser has been closed', 'target closed')),
        ('execution_context_destroyed', ('execution context was destroyed',)),
        ('element_detached', ('element is not attached', 'element was detached')),
        ('strict_mode_violation', ('strict mode violation',)),
    )
    kind = next((name for name, parts in signatures if any(part in message for part in parts)),
                'timeout' if type(error).__name__ == 'TimeoutError' else 'unclassified')
    frames = []
    known = {str((Path(__file__).resolve().parents[1] / name).resolve()): name for name in FRAME_FILES}
    tb = error.__traceback__
    while tb:
        name = known.get(str(Path(tb.tb_frame.f_code.co_filename).resolve()))
        if name:
            frames.append({'file': name, 'line': tb.tb_lineno})
        tb = tb.tb_next
    return safe_execution_details(dict(result, browser_error_kind=kind, source_frames=frames),
                                  result.get('checks', []))

STAGES={'dependencies','synthetic_fixture','automation_driver','browser_launch',
        'browser_scenarios','document_upload','document_download','review_request',
        'archive','mfa','source_validation','child_execution','result_validation','complete'}
EXCEPTIONS={'AssertionError','PermissionError','ModuleNotFoundError','ImportError',
            'FileNotFoundError','RuntimeError','ValueError','TimeoutError','Error','OSError','Exception'}
SUMMARIES={
 'browser_assertion_failed':'A synthetic browser assertion failed; inspect the named check locally.',
 'browser_dependency_missing':'A required Python verification dependency could not be imported.',
 'automation_driver_permission_denied':'Windows denied an operation while starting the automation driver; the browser launch was not reached.',
 'browser_permission_denied':'Windows denied an operation at the reported browser stage.',
 'browser_launch_failed':'The browser could not be launched using the selected installed channel.',
 'browser_timeout':'A browser operation timed out at the reported stage.',
 'source_validation_failed':'The required clean Git source identity could not be verified.',
 'browser_execution_failed':'The browser exercise failed at the reported stage.',
 'browser_result_invalid':'The browser result is missing, malformed, stale, incomplete or bound to another source.',
 'browser_child_failed_without_result':'The child process failed before producing a structured browser result.',
 'verification_launcher_failed':'The verification launcher could not complete the reported stage.'}


def diagnostic(code,stage):
    return {'error_code':code,'failing_stage':stage if stage in STAGES else 'child_execution',
            'diagnostic_summary':SUMMARIES[code]}


def failure(error,stage,failed_check=None):
    if isinstance(error,AssertionError):code='browser_assertion_failed'
    elif isinstance(error,ImportError):code='browser_dependency_missing'
    elif isinstance(error,PermissionError):
        code='automation_driver_permission_denied' if stage=='automation_driver' else 'browser_permission_denied'
    elif stage=='source_validation':code='source_validation_failed'
    elif type(error).__name__=='TimeoutError':code='browser_timeout'
    elif stage=='browser_launch':code='browser_launch_failed'
    else:code='browser_execution_failed'
    result=diagnostic(code,stage)
    # Only fixed exception class names and numeric OS codes, never str(error).
    name=type(error).__name__
    result['exception_type']=name if name in EXCEPTIONS else 'Exception'
    if type(getattr(error,'winerror',None)) is int:result['winerror']=error.winerror
    if failed_check and re.fullmatch('[a-z][a-z0-9_]{0,99}',failed_check):result['failed_check']=failed_check
    return result


def browser_result(path,source,started_at,exit_code,run_id=None):
    """Validate provenance and sanitize an untrusted child result, including failures."""
    import json
    from datetime import datetime
    def invalid(code,stage):
        # None means no validated evidence, not zero completed checks.
        return False,{'check_count':None,'failed_check':None,**diagnostic(code,stage)}
    if not path.is_file():
        return invalid('browser_child_failed_without_result' if exit_code else 'browser_result_invalid','child_execution')
    try:
        data=json.loads(path.read_text(encoding='utf-8'))
        checks=data['checks']
        # A fresh parent-issued challenge binds the child to this execution.
        # Filesystem and wall-clock timestamps can differ below a millisecond on
        # Windows. Keep the strict legacy freshness gate for callers without a nonce.
        fresh=(isinstance(run_id,str) and re.fullmatch('[a-f0-9]{32}',run_id)
               and data.get('run_id')==run_id) if run_id is not None else (
                   path.stat().st_mtime >= datetime.fromisoformat(started_at).timestamp())
        if (not fresh
                or data['source']!=source or data['format']!='ohvr-browser-verification-v2'
                or data['synthetic_only'] is not True or not isinstance(checks,list)
                or not all(isinstance(v,str) and re.fullmatch('[a-z][a-z0-9_]{0,99}',v) for v in checks)
                or len(set(checks))!=len(checks)):
            raise ValueError()
        if exit_code==0 and data['status']=='passed' and len(checks)>=30 and 'source_unchanged' in checks:
            return True,{'check_count':len(checks),'failed_check':None,'error_code':None,
                         'failing_stage':None,'diagnostic_summary':None,'stage':'complete'}
        if exit_code and data['status']=='failed' and data.get('error_code') in SUMMARIES:
            result=diagnostic(data['error_code'],data.get('failing_stage'))
            result.update(safe_execution_details(data,checks))
            result['check_count']=len(checks)
            result['failed_check']=None
            if data.get('exception_type') in EXCEPTIONS:result['exception_type']=data['exception_type']
            value=data.get('failed_check')
            if isinstance(value,str) and re.fullmatch('[a-z][a-z0-9_]{0,99}',value):result['failed_check']=value
            if type(data.get('winerror')) is int:result['winerror']=data['winerror']
            return False,result
    except (ValueError,KeyError,TypeError,OSError):pass
    return invalid('browser_result_invalid','result_validation')
