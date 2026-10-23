"""Offline release safety tests. No GitHub, publication, credentials or application DB."""
from io import BytesIO
import json
from types import SimpleNamespace
import urllib.request
import xml.etree.ElementTree as ET
import zipfile

import pytest

from scripts import github_release_acceptance as release
from tests.support import scratch_directory

SOURCE = 'a' * 40


@pytest.fixture
def tmp_path():
    # Use the project's existing isolated workspace convention, not Windows TEMP.
    from pathlib import Path
    with scratch_directory('github-release-test-') as path:
        yield Path(path)


def archive(files):
    stream = BytesIO()
    with zipfile.ZipFile(stream, 'w') as output:
        for name, data in files.items():
            info = zipfile.ZipInfo()
            info.filename = name  # Keep adversarial ZIP names unchanged on Windows.
            output.writestr(info, data)
    return stream.getvalue()


def browser_files():
    return {f'{index}/result.json': json.dumps(dict(format=kind, status='passed', source=SOURCE,
        synthetic_only=True, checks=['scenario_passed', 'source_unchanged']))
        for index, kind in enumerate(sorted(release.BROWSER_FORMATS))}


def test_all_ten_jobs_must_really_pass():
    info = dict(status='completed', conclusion='success')
    jobs = [dict(name=name, status='completed', conclusion='success') for name in release.JOBS]
    release.validate_jobs(info, jobs)
    for conclusion in ('failure', 'cancelled', 'skipped', 'neutral', None):
        changed = [dict(j) for j in jobs]
        changed[0]['conclusion'] = conclusion
        with pytest.raises(release.Blocked, match='mandatory_job_not_successful'):
            release.validate_jobs(info, changed)
    with pytest.raises(release.Blocked, match='inventory'):
        release.validate_jobs(info, jobs[:-1])
    with pytest.raises(release.Blocked, match='inventory'):
        release.validate_jobs(info, jobs + [jobs[0]])


def test_failed_run_never_becomes_success_from_green_partial_jobs():
    with pytest.raises(release.Blocked, match='ci_not_successful'):
        release.validate_jobs(dict(status='completed', conclusion='failure'), [])


def test_four_browser_suites_need_exact_source_and_validated_checks():
    files = browser_files()
    report = release.inspect_artifact(archive(files), 'phase8-browser-verification', SOURCE)
    assert len(report['browsers']) == 4
    with pytest.raises(release.Blocked, match='source_or_status'):
        release.inspect_artifact(archive(files), 'phase8-browser-verification', 'b' * 40)
    files.pop(next(iter(files)))
    with pytest.raises(release.Blocked, match='missing_integrated'):
        release.inspect_artifact(archive(files), 'phase8-browser-verification', SOURCE)


@pytest.mark.parametrize('changes', [dict(status='failed'), dict(checks=[]),
    dict(checks=['scenario_passed']), dict(checks=['source_unchanged', 'source_unchanged']),
    dict(checks=[dict(passed=True)]), dict(synthetic_only=False)])
def test_browser_success_cannot_be_fabricated(changes):
    files = browser_files()
    key = next(iter(files))
    value = json.loads(files[key])
    value.update(changes)
    files[key] = json.dumps(value)
    with pytest.raises(release.Blocked):
        release.inspect_artifact(archive(files), 'phase8-browser-verification', SOURCE)


@pytest.mark.parametrize('name', ['../secret', '/absolute', 'C:/secret', 'folder\\secret'])
def test_artifact_zip_paths_never_escape_evidence(name):
    with pytest.raises(release.Blocked, match='unsafe_artifact_path'):
        release.zip_members(archive({name: b'not extracted'}))


def test_ordinary_suite_skips_are_preserved_without_exception_text():
    xml = '<testsuite><testcase classname="Synthetic" name="requires_platform"><skipped>private exception text</skipped></testcase></testsuite>'
    raw = archive({'results.xml': xml})
    report = release.inspect_artifact(raw, 'postgresql-verification', SOURCE)
    assert report['junit'][0]['skipped'] == [dict(classname='Synthetic', name='requires_platform')]
    assert 'private exception text' not in json.dumps(report)


def mandatory_xml(artifact):
    path, identities = release.MANDATORY_JUNIT[artifact]
    root = ET.Element('testsuite')
    for classname, name in identities:
        ET.SubElement(root, 'testcase', classname=classname, name=name)
    return path, root


def inspect_mandatory(artifact, path, root):
    return release.inspect_artifact(archive({path: ET.tostring(root)}), artifact, SOURCE)


@pytest.mark.parametrize('artifact', sorted(release.MANDATORY_JUNIT))
def test_applicable_mandatory_inventory_all_passed(artifact):
    path, root = mandatory_xml(artifact)
    report = inspect_mandatory(artifact, path, root)
    assert report['allowed_platform_skips'] == []


def test_only_exact_ubuntu_junction_platform_skip_is_allowed():
    artifact = 'native-storage-links-ubuntu-24.04'
    path, root = mandatory_xml(artifact)
    ET.SubElement(root[1], 'skipped', type='pytest.skip', message='Windows native junction only')
    report = inspect_mandatory(artifact, path, root)
    assert report['junit'][0]['cases'] == 2
    assert report['allowed_platform_skips'] == [dict(classname=release.WINDOWS_JUNCTION_CASE[0],
        name=release.WINDOWS_JUNCTION_CASE[1], classification='not_applicable_windows_junction_on_ubuntu')]


@pytest.mark.parametrize('artifact,index', [
    ('native-storage-links-ubuntu-24.04', 0), ('native-storage-links-windows-latest', 0),
    ('native-storage-links-windows-latest', 1), ('document-scanner-verification', 0)])
def test_required_native_and_scanner_skips_remain_blocked(artifact, index):
    path, root = mandatory_xml(artifact)
    # Even the otherwise approved reason cannot excuse the wrong test/platform.
    ET.SubElement(root[index], 'skipped', type='pytest.skip', message='Windows native junction only')
    with pytest.raises(release.Blocked, match='mandatory_native_or_scanner_tests_skipped'):
        inspect_mandatory(artifact, path, root)


@pytest.mark.parametrize('attrs', [dict(type='pytest.skip', message='missing permissions'),
    dict(type='pytest.skip', message='Windows native junction only '),
    dict(type='pytest.xfail', message='Windows native junction only'),
    dict(message='Windows native junction only'), dict(type='pytest.skip')])
def test_unexpected_junction_skip_classification_is_rejected(attrs):
    artifact = 'native-storage-links-ubuntu-24.04'
    path, root = mandatory_xml(artifact)
    ET.SubElement(root[1], 'skipped', **attrs)
    with pytest.raises(release.Blocked, match='mandatory_native_or_scanner_tests_skipped'):
        inspect_mandatory(artifact, path, root)


@pytest.mark.parametrize('artifact', sorted(release.MANDATORY_JUNIT))
@pytest.mark.parametrize('mutation', ['missing', 'empty', 'duplicate', 'unexpected', 'failure', 'error', 'parameterized'])
def test_mandatory_coverage_cannot_be_satisfied_by_wrong_or_missing_tests(artifact, mutation):
    path, root = mandatory_xml(artifact)
    if mutation == 'missing':
        root.remove(root[0])
    elif mutation == 'empty':
        root.clear()
    elif mutation == 'duplicate':
        root.append(ET.fromstring(ET.tostring(root[0])))
    elif mutation == 'unexpected':
        root[0].set('classname', 'tests.some_other_test')
    elif mutation == 'parameterized':
        root[0].set('name', root[0].get('name') + '[unexpected]')
    else:
        ET.SubElement(root[0], mutation).text = 'private diagnostic must not escape'
    with pytest.raises(release.Blocked):
        inspect_mandatory(artifact, path, root)


@pytest.mark.parametrize('artifact', sorted(release.MANDATORY_JUNIT))
def test_mandatory_junit_file_must_be_present_at_expected_path(artifact):
    path, root = mandatory_xml(artifact)
    for files in ({}, {'other.xml': ET.tostring(root)}, {path: ET.tostring(root), 'extra.xml': ET.tostring(root)}):
        with pytest.raises(release.Blocked):
            release.inspect_artifact(archive(files), artifact, SOURCE)


def test_failed_junit_blocks_without_exposing_exception():
    raw = archive({'results.xml': '<testsuite><testcase><failure>password=PRIVATE</failure></testcase></testsuite>'})
    with pytest.raises(release.Blocked, match='^artifact_contains_failed_tests$'):
        release.inspect_artifact(raw, 'postgresql-verification', SOURCE)


def test_cross_host_artifact_redirect_strips_bearer_token():
    original = urllib.request.Request('https://api.github.com/repos/example/artifacts/1/zip',
        headers={'Authorization': 'Bearer PRIVATE'})
    redirected = release.SafeRedirect().redirect_request(original, None, 302, '', {}, 'https://artifact.example/download')
    assert not redirected.has_header('Authorization')
    with pytest.raises(release.Blocked, match='insecure_redirect'):
        release.SafeRedirect().redirect_request(original, None, 302, '', {}, 'http://artifact.example/download')


@pytest.mark.parametrize('rule', ['merge_queue', 'required_deployments', 'required_linear_history', 'required_signatures', 'update'])
def test_no_automatic_bypass_of_unimplemented_merge_policies(rule):
    with pytest.raises(release.Blocked, match='different_merge_workflow'):
        release.merge_policy(dict(classic=None, effective_rules=[dict(type=rule)]))


def test_classic_linear_history_and_lock_block_merge():
    for key in ('required_linear_history', 'lock_branch'):
        with pytest.raises(release.Blocked):
            release.merge_policy(dict(classic={key: dict(enabled=True)}, effective_rules=[]))


def test_ruleset_protected_branch_can_have_no_classic_protection(tmp_path):
    class API:
        def repo(self, path, **kwargs):
            return None if path.endswith('/protection') else dict(protected=True, commit=dict(sha=SOURCE))
        def pages(self, path):
            return [dict(type='pull_request')] if '/rules/branches/' in path else []
    snapshot = release.protection(API(), 'main', tmp_path, 'test')
    assert snapshot['classic'] is None
    release.merge_policy(snapshot)


def test_unreadable_protection_is_not_absence(tmp_path):
    api = SimpleNamespace(repo=lambda *a, **kw: None if a[0].endswith('/protection')
        else dict(protected=True, commit=dict(sha=SOURCE)), pages=lambda *a: [])
    with pytest.raises(release.Blocked, match='protection_not_readable'):
        release.protection(api, 'main', tmp_path, 'test')


def test_stale_author_bot_and_dismissed_reviews_do_not_approve(tmp_path):
    rows = []
    api = SimpleNamespace(pages=lambda *a: rows)
    runner = release.Acceptance(api, SOURCE, tmp_path, 1)
    def review(identifier, user, state='APPROVED', sha=SOURCE, kind='User'):
        return dict(id=identifier, user=dict(login=user, type=kind), state=state,
            commit_id=sha, submitted_at='2026-10-23T12:00:00Z', html_url='https://github.com/review')
    rows.extend([review(1, 'author'), review(2, 'other', sha='b'*40), review(3, 'bot', kind='Bot')])
    assert runner.reviews(1, SOURCE, 'author') == []
    rows.append(review(4, 'other'))
    assert len(runner.reviews(1, SOURCE, 'author')) == 1
    rows.append(review(5, 'other', state='DISMISSED'))
    assert runner.reviews(1, SOURCE, 'author') == []
    rows.append(review(6, 'other', state='CHANGES_REQUESTED'))
    with pytest.raises(release.Blocked, match='review_changes_requested'):
        runner.reviews(1, SOURCE, 'author')


def test_dirty_source_stops_before_remote_changes(monkeypatch):
    responses = {('rev-parse', '--show-toplevel'): str(release.ROOT),
        ('rev-parse', 'HEAD'): SOURCE, ('status', '--porcelain'): ' M docs/preserved.md'}
    monkeypatch.setattr(release, 'git', lambda *args: responses[args])
    with pytest.raises(release.Blocked, match='working_tree_not_clean'):
        release.check_source(SOURCE)


def test_failed_ci_preserves_job_metadata_and_never_merges(tmp_path):
    class API:
        def pages(self, path, key=None):
            if '/workflows/' in path:
                return [dict(id=1, run_number=1, run_attempt=1, head_sha=SOURCE, event='push',
                    head_repository=dict(full_name=release.REPO), status='completed', conclusion='failure', html_url='https://github.com/run/1')]
            return []
    runner = release.Acceptance(API(), SOURCE, tmp_path, 1)
    with pytest.raises(release.Blocked, match='ci_not_successful'):
        runner.verify_run('review/test', SOURCE, 'push', SOURCE)
    assert (tmp_path / 'run-1-attempt-1/jobs.json').exists()
    assert not runner.state['merged_into_main']
    assert not runner.state['release_ready']


def test_completed_successful_run_is_reused_without_dispatch(monkeypatch, tmp_path):
    downloads = {name: name.encode() for name in release.ARTIFACTS}
    class API:
        def pages(self, path, key=None):
            if '/workflows/' in path:
                return [dict(id=1, run_number=1, run_attempt=1, head_sha=SOURCE, event='push',
                    head_repository=dict(full_name=release.REPO), status='completed', conclusion='success', html_url='https://github.com/run/1')]
            if path.endswith('/jobs'):
                return [dict(id=i, name=n, status='completed', conclusion='success', html_url='https://github.com/job') for i, n in enumerate(release.JOBS)]
            if path.endswith('/artifacts'):
                return [dict(id=i, name=n, expired=False, workflow_run=dict(head_sha=SOURCE),
                    digest='sha256:'+release.sha256(downloads[n]).hexdigest()) for i, n in enumerate(downloads)]
            raise AssertionError('unexpected API')
        def repo(self, path, **kwargs):
            assert kwargs == dict(binary=True)
            return list(downloads.values())[int(path.split('/')[-2])]
    def inspect(data, name, sha):
        report = dict(name=name, junit=[], browsers=[])
        if name.startswith('runtime-release-'):
            report['release'] = dict(source_commit=sha, artifact_sha256='e'*64)
        return report
    monkeypatch.setattr(release, 'inspect_artifact', inspect)
    runner = release.Acceptance(API(), SOURCE, tmp_path, 1)
    runner.verify_run('review/test', SOURCE, 'push', SOURCE)
    assert runner.state['runs'][0]['artifacts_verified']
    assert not runner.state['release_ready']  # review and final main CI are still missing


@pytest.mark.parametrize('problem', [None, 'no_review', 'review_required', 'final_ci_failed', 'changed_merge_tree'])
@pytest.mark.parametrize('selected_pr', [0, 7])
def test_full_publication_gate_requires_review_and_new_main_source_ci(monkeypatch, tmp_path, problem, selected_pr):
    base, test_merge, final_merge = 'b'*40, 'c'*40, 'd'*40
    calls = []
    pr = dict(number=7, head=dict(sha=SOURCE, repo=dict(full_name=release.REPO),
        ref='review/integrated-release-' + SOURCE[:12]), base=dict(ref='main', sha=base, repo=dict(full_name=release.REPO)), merged=False,
        state='open', mergeable=True, mergeable_state='clean', merge_commit_sha=test_merge,
        user=dict(login='author'), html_url='https://github.com/example/pull/7')
    class API:
        def repo(self, path, **kwargs):
            if path == '':
                return dict(full_name=release.REPO, archived=False, default_branch='main', allow_merge_commit=True)
            if path == '/pulls/7':
                return dict(pr)
            if path.startswith('/git/ref/heads/'):
                return dict(object=dict(sha=SOURCE))
            if path == '/pulls/7/merge':
                assert calls == [('push', SOURCE), ('pull_request', test_merge)]
                assert kwargs == dict(method='PUT', payload=dict(sha=SOURCE, merge_method='merge'))
                calls.append(('merge', final_merge))
                return dict(merged=True, sha=final_merge)
            if path.startswith('/collaborators/'):
                return dict(permission='write')
            if path == '/issues/7/comments':
                assert kwargs['method'] == 'POST'
                return {}
            if path.endswith('/status'):
                return dict(statuses=[], state='pending')
            if path.startswith('/commits/'):
                tree = 'other' if problem == 'changed_merge_tree' and path.endswith(final_merge) else 'same'
                return dict(commit=dict(tree=dict(sha=tree)))
            if path == '/branches/main':
                return dict(commit=dict(sha=final_merge))
            raise AssertionError(path)
        def pages(self, path, key=None):
            if path.startswith('/pulls?'):
                return [pr]
            if path.endswith('/comments'):
                return []
            if '/check-runs?' in path:
                return [dict(id=1, name='verified', status='completed', conclusion='success')] if SOURCE in path else []
            raise AssertionError(path)
        def request(self, path, **kwargs):
            assert path == '/graphql'
            return dict(data=dict(repository=dict(pullRequest=dict(mergeStateStatus='CLEAN',
                reviewDecision='REVIEW_REQUIRED' if problem == 'review_required' else None))))
    monkeypatch.setattr(release, 'check_source', lambda source: None)
    monkeypatch.setattr(release, 'git', lambda *a: base if a == ('rev-parse', 'FETCH_HEAD') else '')
    monkeypatch.setattr(release, 'run', lambda *a, **kw: SimpleNamespace(returncode=0))
    monkeypatch.setattr(release, 'protection', lambda *a: dict(base_sha=base, classic=None, effective_rules=[]))
    runner = release.Acceptance(API(), SOURCE, tmp_path, 1, pull_request=selected_pr)
    monkeypatch.setattr(runner, 'reviews', lambda *a: [] if problem == 'no_review'
        else [dict(id=1, user=dict(login='independent'))])
    def pause(reason):
        raise release.Blocked('waiting_' + reason)
    monkeypatch.setattr(runner, 'pause', pause)
    def verify_run(branch, source, event, tested):
        calls.append((event, tested))
        if source == final_merge and problem == 'final_ci_failed':
            raise release.Blocked('ci_not_successful')
    monkeypatch.setattr(runner, 'verify_run', verify_run)
    if problem:
        with pytest.raises(release.Blocked):
            runner.execute()
        assert not runner.state['release_ready']
        if problem in ('no_review', 'review_required'):
            assert not any(c[0] == 'merge' for c in calls)
        else:
            assert runner.state['merged_into_main']
            assert not runner.state['hosted_ci_verified']
    else:
        runner.execute()
        assert calls == [('push', SOURCE), ('pull_request', test_merge), ('merge', final_merge), ('push', final_merge)]
        assert runner.state['release_ready']
        assert runner.state['final_source_ci_verified']
        assert not runner.state['deployed']


def test_unrecorded_external_merge_cannot_be_treated_as_our_approved_merge(tmp_path):
    with pytest.raises(release.Blocked, match='prior_verified_merge_receipt'):
        release.merged_receipt(SOURCE, 'b'*40, tmp_path / 'github-release-current')


@pytest.mark.parametrize('problem', [None, 'not_selected', 'diverged', 'ref_changed', 'fork', 'closed'])
def test_existing_pr_updates_are_explicit_fast_forward_only(monkeypatch, problem):
    old = 'b'*40
    branch = 'review/integrated-release-' + old[:12]
    pr = dict(state='open', merged=False, head=dict(sha=old, ref=branch, repo=dict(full_name=release.REPO)))
    if problem == 'fork':
        pr['head']['repo']['full_name'] = 'someone/else'
    if problem == 'closed':
        pr['state'] = 'closed'
    ref = dict(object=dict(sha=old))
    calls = []
    def git(*args):
        calls.append(args)
        if args == ('rev-parse', 'FETCH_HEAD'):
            return 'c'*40 if problem == 'ref_changed' else old
        if args[0] == 'push':
            assert args == ('push', 'origin', SOURCE + ':refs/heads/' + branch)
            ref['object']['sha'] = SOURCE
        return ''
    monkeypatch.setattr(release, 'git', git)
    monkeypatch.setattr(release, 'run', lambda *a, **kw: SimpleNamespace(returncode=1 if problem == 'diverged' else 0))
    api = SimpleNamespace(repo=lambda *a, **kw: dict(object=dict(sha=ref['object']['sha'])))
    if problem:
        with pytest.raises(release.Blocked):
            release.publish_review_ref(api, branch, SOURCE, None if problem == 'not_selected' else pr)
        assert not any(c[0] == 'push' for c in calls)
    else:
        release.publish_review_ref(api, branch, SOURCE, pr)
        assert ref['object']['sha'] == SOURCE
