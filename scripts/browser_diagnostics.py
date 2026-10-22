"""Fixed, shareable browser diagnostics: never serialize exception text or URLs."""
import re

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
    if isinstance(getattr(error,'winerror',None),int):result['winerror']=error.winerror
    if failed_check and re.fullmatch('[a-z][a-z0-9_]{0,99}',failed_check):result['failed_check']=failed_check
    return result


def browser_result(path,source,started_at,exit_code):
    """Validate provenance and sanitize an untrusted child result, including failures."""
    import json
    from datetime import datetime
    if not path.is_file():
        return False,diagnostic('browser_child_failed_without_result' if exit_code else 'browser_result_invalid','child_execution')
    try:
        data=json.loads(path.read_text(encoding='utf-8'))
        checks=data['checks']
        if (path.stat().st_mtime < datetime.fromisoformat(started_at).timestamp()
                or data['source']!=source or data['format']!='ohvr-browser-verification-v2'
                or data['synthetic_only'] is not True or not isinstance(checks,list)
                or not all(isinstance(v,str) and re.fullmatch('[a-z][a-z0-9_]{0,99}',v) for v in checks)
                or len(set(checks))!=len(checks)):
            raise ValueError()
        if exit_code==0 and data['status']=='passed' and len(checks)>=30 and 'source_unchanged' in checks:
            return True,{'check_count':len(checks),'error_code':None,'stage':'complete'}
        if exit_code and data['status']=='failed' and data.get('error_code') in SUMMARIES:
            result=diagnostic(data['error_code'],data.get('failing_stage'))
            result['check_count']=len(checks)
            if data.get('exception_type') in EXCEPTIONS:result['exception_type']=data['exception_type']
            value=data.get('failed_check')
            if isinstance(value,str) and re.fullmatch('[a-z][a-z0-9_]{0,99}',value):result['failed_check']=value
            if isinstance(data.get('winerror'),int):result['winerror']=data['winerror']
            return False,result
    except (ValueError,KeyError,TypeError,OSError):pass
    return False,diagnostic('browser_result_invalid','result_validation')
