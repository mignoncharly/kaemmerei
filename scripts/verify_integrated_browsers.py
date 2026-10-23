"""Fail-fast, source-bound acceptance of all three isolated synthetic browser suites."""
import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
import subprocess
import sys
from uuid import uuid4

from scripts.browser_diagnostics import diagnostic, EXCEPTIONS, SUMMARIES
from scripts.pilot_verification import ROOT, source_identity, write_report

SUITES = (
    ('redesign', 'verify_frontend_redesign.py', 'ohvr-redesign-browser-v1',
     {'source_unchanged', 'pilot_mfa_replay_denied', 'unscanned_documents_not_downloadable', 'redesign_no_csp_violations'}),
    ('toolbar', 'verify_contract_toolbar.py', 'ohvr-toolbar-browser-v1',
     {'source_unchanged', 'native_no_js_filtering', 'no_csp_violations'}),
    ('excel', 'verify_excel_selection.py', 'ohvr-excel-selection-browser-v1',
     {'source_unchanged', 'reviewer_no_import', 'admin_import_success', 'kultur_import_success', 'bau_import_success'}),
)


def validate_result(path, source, run_id, suite, exit_code):
    invalid = {'check_count': None, 'failed_check': None, **diagnostic('browser_result_invalid', 'result_validation')}
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
        checks = data['checks']
        if (data['source'] != source or data['run_id'] != run_id or data['format'] != suite[2]
                or data['synthetic_only'] is not True or not isinstance(checks, list)
                or not all(isinstance(c, str) and re.fullmatch('[a-z][a-z0-9_]{0,99}', c) for c in checks)
                or len(set(checks)) != len(checks)):
            return False, invalid
        evidence = {'check_count': len(checks), 'failed_check': None, 'result_sha256': sha256(path.read_bytes()).hexdigest()}
        if exit_code == 0 and data['status'] == 'passed' and data.get('stage') == 'complete':
            if not suite[3].issubset(checks) or data.get('failed_check') or data.get('error_code'):
                return False, invalid
            return True, evidence
        if exit_code != 0 and data['status'] == 'failed' and data.get('error_code') in SUMMARIES:
            evidence.update(diagnostic(data['error_code'], data.get('failing_stage')))
            if data.get('exception_type') in EXCEPTIONS:
                evidence['exception_type'] = data['exception_type']
            if type(data.get('winerror')) is int:
                evidence['winerror'] = data['winerror']
            value = data.get('failed_check')
            if isinstance(value, str) and re.fullmatch('[a-z][a-z0-9_]{0,99}', value):
                evidence['failed_check'] = value
            return False, evidence
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return False, invalid


def run_suites(source, channel, output):
    report = {'format': 'ohvr-integrated-browsers-v1', 'source': source, 'synthetic_only': True,
              'started_at': datetime.now(timezone.utc).isoformat(), 'status': 'failed',
              'visual_inspection': 'NOT_PERFORMED', 'suites': []}
    code = 2
    stage = 'source_validation'
    try:
        source_identity(source)
        for suite in SUITES:
            stage = 'source_validation'
            source_identity(source)
            run_id = uuid4().hex
            stage = 'child_execution'
            with (output / (suite[0] + '-private.log')).open('xb') as log:
                child = subprocess.run([sys.executable, '-u', str(ROOT / 'scripts' / suite[1]),
                    '--channel', channel, '--output', str(output / suite[0]), '--run-id', run_id],
                    cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
            # Keep the child's exact failure code, including when final source validation fails.
            code = child.returncode or 2
            stage = 'result_validation'
            passed, evidence = validate_result(output / suite[0] / 'result.json', source, run_id, suite, child.returncode)
            report['suites'].append({'suite': suite[0], 'exit_code': child.returncode,
                                    'status': 'passed' if passed else 'failed', **evidence})
            stage = 'source_validation'
            source_identity(source)
            if not passed:
                break
        else:
            source_identity(source)
            report['status'] = 'passed'
            code = 0
    except Exception:
        # Never print exception text or child output; fixed diagnostic vocabulary only.
        report.update(diagnostic('source_validation_failed' if stage == 'source_validation'
                                 else 'verification_launcher_failed', stage))
    report.update(exit_code=code, finished_at=datetime.now(timezone.utc).isoformat())
    write_report(output / 'sanitized-report.json', report)
    print('SUCCESS' if code == 0 else 'FAILED: browser acceptance incomplete; inspect sanitized-report.json.')
    return code


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--expected-source', required=True)
    parser.add_argument('--channel', choices=('msedge', 'chrome', 'chromium'), default='msedge')
    args = parser.parse_args()
    if not re.fullmatch('[a-f0-9]{40}', args.expected_source):
        raise SystemExit(2)
    from app.documents import reject_links
    output = ROOT / '.verification' / ('integrated-browsers-' + uuid4().hex)
    reject_links(output)
    output.mkdir(parents=True, exist_ok=False)
    print('Evidence: ' + str(output.relative_to(ROOT)))
    return run_suites(args.expected_source, args.channel, output)


if __name__ == '__main__':
    try:
        code = main()
    except Exception:
        print('FAILED: verification launcher could not start.')
        code = 2
    raise SystemExit(code)
