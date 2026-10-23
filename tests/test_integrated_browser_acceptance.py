"""Regression coverage for the actual failed integrated acceptance runs."""
import json
import builtins
from pathlib import Path
import subprocess
import sys
from types import ModuleType, SimpleNamespace

import pytest
from sqlalchemy import select

from app.models import ContractDocument
from scripts import verify_integrated_browsers as runner
from scripts.browser_layout import measure_reflow
from tests.support import scratch_directory


@pytest.fixture
def acceptance_tmp():
    with scratch_directory('ohvr-acceptance-test-') as folder:
        yield Path(folder)


def test_extended_fixture_obeys_migrations_and_keeps_unscanned_downloads_blocked(environment):
    from scripts.verify_frontend_redesign import seed_extended
    client, app = environment
    cid = seed_extended(client, app)
    with app.state.session_factory() as db:
        docs = db.scalars(select(ContractDocument).where(ContractDocument.contract_id == cid)).all()
        assert {d.state for d in docs} == {'pending', 'rejected', 'legacy_unverified'}
        assert len({d.storage_key for d in docs}) == 3
        for doc in docs:
            assert doc.storage_key and doc.external_url is None and doc.scan_result != 'clean'
            assert client.get(f'/contracts/{cid}/documents/{doc.id}?download=1').status_code == 409


def test_fixture_failure_is_not_reported_as_prior_successful_mfa(monkeypatch, capsys):
    from scripts import verify_frontend_redesign as browser, verify_phase8_browser, pilot_verification
    # No browser or driver needed to reproduce a fixture failure after legacy MFA.
    fake = ModuleType('playwright.sync_api')
    fake.sync_playwright = lambda: pytest.fail('Driver must not be reached')
    monkeypatch.setitem(sys.modules, 'playwright.sync_api', fake)
    def legacy(args, output, result):
        result.update(stage='mfa', checks=['pilot_mfa_enrollment_login', 'pilot_mfa_replay_denied'])
    def broken_seed(*args):
        raise RuntimeError('SECRET database parameters and MFA seed')
    monkeypatch.setattr(verify_phase8_browser, 'execute', legacy)
    monkeypatch.setattr(browser, 'seed_extended', broken_seed)
    monkeypatch.setattr(pilot_verification, 'source_identity', lambda *args: 'a' * 40)
    with scratch_directory('ohvr-fixture-failure-') as folder:
        output = Path(folder) / 'browser'
        monkeypatch.setattr(sys, 'argv', ['browser', '--output', str(output)])
        with pytest.raises(SystemExit) as error:
            browser.main()
        assert error.value.code == 1
        data = json.loads((output / 'result.json').read_text())
        assert data['status'] == 'failed' and data['failing_stage'] == 'synthetic_fixture'
        assert data['checks'] == ['pilot_mfa_enrollment_login', 'pilot_mfa_replay_denied']
        assert 'SECRET' not in json.dumps(data) + capsys.readouterr().out


def test_reflow_failure_preserves_measurements_and_screenshot_before_assertion(acceptance_tmp):
    class Page:
        def evaluate(self, expression):
            assert 'textContent' not in expression and 'innerHTML' not in expression
            return {'viewport': 390, 'pageWidth': 816, 'passed': False, 'boxes': {}}
        def screenshot(self, *, path, full_page):
            assert full_page
            Path(path).write_bytes(b'test-only-screenshot-stub')
    result = {}
    assert not measure_reflow(Page(), acceptance_tmp, result, 'admin_reflow_390')
    assert result['layout_measurements']['admin_reflow_390']['pageWidth'] == 816
    assert (acceptance_tmp / result['screenshots'][0]).is_file()


@pytest.mark.parametrize('module_name,function', [
    ('verify_frontend_redesign', 'extended'), ('verify_contract_toolbar', 'execute'),
    ('verify_excel_selection', 'execute')])
def test_dependency_failure_does_not_keep_previous_stage(monkeypatch, module_name, function):
    from importlib import import_module
    module = import_module('scripts.' + module_name)
    original_import = builtins.__import__
    def importing(name, *args, **kwargs):
        if name == 'playwright.sync_api':
            raise ModuleNotFoundError('SECRET private path')
        return original_import(name, *args, **kwargs)
    monkeypatch.setattr(builtins, '__import__', importing)
    result = {'stage': 'source_validation', 'checks': []}
    with pytest.raises(ModuleNotFoundError):
        getattr(module, function)(None, None, result)
    assert result['stage'] == 'dependencies'


def child_result(suite, source, run_id):
    return {'source': source, 'run_id': run_id, 'format': suite[2], 'synthetic_only': True,
            'status': 'passed', 'stage': 'complete', 'checks': sorted(suite[3])}


@pytest.mark.parametrize('fault', ['none', 'child_failed', 'zero_failed', 'malformed', 'wrong_source',
    'wrong_nonce', 'missing_check', 'duplicate', 'dirty_during_run', 'dirty_before_run'])
def test_coordinator_fail_fast_provenance_and_exit_code(monkeypatch, capsys, fault):
    source = 'a' * 40
    calls, validations = [], []
    def identity(expected):
        assert expected == source
        validations.append(expected)
        if fault == 'dirty_before_run' or (fault == 'dirty_during_run' and calls):
            raise ValueError('SECRET dirty source details')
        return source
    def child(command, **kwargs):
        suite = runner.SUITES[len(calls)]
        calls.append(suite[0])
        assert kwargs['stdout'] == kwargs['stderr'] or kwargs['stderr'] == subprocess.STDOUT
        assert '--output' in command and '--run-id' in command and kwargs['cwd'] == runner.ROOT
        output = Path(command[command.index('--output') + 1])
        output.mkdir()
        nonce = command[command.index('--run-id') + 1]
        data = child_result(suite, source, nonce)
        code = 0
        if fault in ('child_failed', 'zero_failed'):
            code = 37 if fault == 'child_failed' else 0
            data.update(status='failed', stage='browser_scenarios', error_code='browser_assertion_failed',
                        failing_stage='browser_scenarios', failed_check='admin_reflow_390',
                        diagnostic_summary='SECRET private session', exception_type='AssertionError')
        if fault == 'wrong_source': data['source'] = 'b' * 40
        if fault == 'wrong_nonce': data['run_id'] = 'b' * 32
        if fault == 'missing_check': data['checks'].remove('source_unchanged')
        if fault == 'duplicate': data['checks'].append('source_unchanged')
        (output / 'result.json').write_text('invalid' if fault == 'malformed' else json.dumps(data))
        return SimpleNamespace(returncode=code)
    monkeypatch.setattr(runner, 'source_identity', identity)
    monkeypatch.setattr(runner.subprocess, 'run', child)
    with scratch_directory('ohvr-integrated-runner-') as folder:
        code = runner.run_suites(source, 'msedge', Path(folder))
        result = json.loads((Path(folder) / 'sanitized-report.json').read_text())
        assert code == (0 if fault == 'none' else 37 if fault == 'child_failed' else 2)
        assert len(calls) == (3 if fault == 'none' else 0 if fault == 'dirty_before_run' else 1)
        assert (result['status'] == 'passed') == (fault == 'none')
        text = capsys.readouterr().out
        assert ('SUCCESS' in text) == (fault == 'none')
        assert 'SECRET' not in json.dumps(result) + text
        if fault == 'child_failed':
            evidence = result['suites'][0]
            assert evidence['check_count'] == len(runner.SUITES[0][3])
            assert evidence['failed_check'] == 'admin_reflow_390'
            assert evidence['failing_stage'] == 'browser_scenarios'
        assert len(validations) >= (1 if fault == 'dirty_before_run' else 3)


@pytest.mark.skipif(sys.platform != 'win32', reason='Windows PowerShell launcher integration')
def test_powershell_launcher_preserves_native_failure_exit_code(acceptance_tmp):
    fake_python = acceptance_tmp / 'failing-python.cmd'
    fake_python.write_text('@exit /b 37\n')
    child = subprocess.run(['powershell.exe', '-NoProfile', '-File',
        str(runner.ROOT / 'scripts/Invoke-IntegratedBrowserVerification.ps1'),
        '-ExpectedSource', 'a' * 40, '-Python', str(fake_python)], capture_output=True)
    assert child.returncode == 37
    assert b'SUCCESS' not in child.stdout + child.stderr
