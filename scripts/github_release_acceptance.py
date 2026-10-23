"""Revision-bound GitHub publication/acceptance; no deployment or credential output.

Uses the normal user's existing GitHub authentication. Never changes protection,
credentials, proxies, local branches or application code. Re-running resumes an
existing exact-source PR; it does not rerun completed successful workflows.
"""
import argparse
from collections import Counter
from hashlib import sha256
from io import BytesIO
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from uuid import uuid4
import xml.etree.ElementTree as ET
import zipfile

from scripts.build_release import verify_bytes

ROOT = Path(__file__).resolve().parent.parent
REPO = 'mignoncharly/kaemmerei'
REMOTE = 'https://github.com/' + REPO + '.git'
WORKFLOW = 'phase1-verification.yml'
LOCAL_ACCEPTED = 'd44f6c9f435d07e5b6720c8ff8c2fd1790528c5f'
JOBS = frozenset(('locked-release (ubuntu-24.04)', 'locked-release (windows-latest)',
    'native-storage-links (ubuntu-24.04)', 'native-storage-links (windows-latest)',
    'release-reproducibility', 'frontend-browser', 'document-scanner',
    'native-postgresql', 'sqlite', 'postgresql'))
ARTIFACTS = frozenset(('runtime-release-ubuntu-24.04', 'runtime-release-windows-latest',
    'native-storage-links-ubuntu-24.04', 'native-storage-links-windows-latest',
    'phase8-browser-verification', 'document-scanner-verification',
    'native-postgresql-verification', 'sqlite-verification', 'postgresql-verification'))
BROWSER_FORMATS = frozenset(('ohvr-browser-verification-v2', 'ohvr-redesign-browser-v1',
    'ohvr-toolbar-browser-v1', 'ohvr-excel-selection-browser-v1'))


class Blocked(Exception):
    """Only fixed, non-secret codes may cross the CLI boundary."""


def require(condition, code):
    if not condition:
        raise Blocked(code)


def run(command, *, data=None, allowed=(0,)):
    env = os.environ.copy()
    env.update(GIT_TERMINAL_PROMPT='0', GCM_INTERACTIVE='Never')
    result = subprocess.run(command, cwd=ROOT, env=env, input=data,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=180)
    require(result.returncode in allowed, 'local_command_failed_exit_' + str(result.returncode))
    return result


def git(*args):
    return run(['git', *args]).stdout.decode('utf-8').strip()


def credentials():
    for key in ('GH_TOKEN', 'GITHUB_TOKEN'):
        if os.environ.get(key):
            return os.environ[key]
    if shutil.which('gh'):
        result = run(['gh', 'auth', 'token', '--hostname', 'github.com'], allowed=(0, 1))
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.decode().strip()
    result = run(['git', 'credential', 'fill'],
        data=b'protocol=https\nhost=github.com\n\n', allowed=(0, 1, 128))
    fields = dict(line.split('=', 1) for line in result.stdout.decode().splitlines() if '=' in line)
    require(bool(fields.get('password')), 'github_authentication_unavailable')
    return fields['password']


class SafeRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        require(urllib.parse.urlsplit(newurl).scheme == 'https', 'insecure_redirect')
        redirected = super().redirect_request(req, fp, code, msg, headers, newurl)
        if urllib.parse.urlsplit(newurl).netloc != urllib.parse.urlsplit(req.full_url).netloc:
            redirected.remove_header('Authorization')
        return redirected


class GitHub:
    def __init__(self, token):
        self.token = token
        self.opener = urllib.request.build_opener(SafeRedirect())

    def request(self, path, method='GET', payload=None, *, binary=False, missing=False):
        require(path.startswith('/') and not path.startswith('//'), 'invalid_api_path')
        request = urllib.request.Request('https://api.github.com' + path, method=method,
            data=None if payload is None else json.dumps(payload).encode(), headers={
                'Authorization': 'Bearer ' + self.token, 'Accept': 'application/vnd.github+json',
                'X-GitHub-Api-Version': '2022-11-28', 'User-Agent': 'OPEN-HERZ-release-acceptance',
                'Content-Type': 'application/json'})
        try:
            with self.opener.open(request, timeout=90) as response:
                limit = 512 * 1024**2 if binary else 16 * 1024**2
                data = response.read(limit + 1)
                require(len(data) <= limit, 'api_response_limit')
                return data if binary else (json.loads(data) if data else None)
        except urllib.error.HTTPError as exc:
            if missing and exc.code == 404:
                return None
            raise Blocked('github_http_' + str(exc.code)) from None
        except (urllib.error.URLError, TimeoutError):
            raise Blocked('github_network_unavailable') from None

    def repo(self, path, **kwargs):
        return self.request('/repos/' + REPO + path, **kwargs)

    def pages(self, path, key=None):
        rows = []
        for page in range(1, 101):
            value = self.repo(path + ('&' if '?' in path else '?') + f'per_page=100&page={page}')
            batch = value[key] if key else value
            require(isinstance(batch, list), 'invalid_api_collection')
            rows.extend(batch)
            if len(batch) < 100:
                return rows
        raise Blocked('api_pagination_limit')


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


def check_source(source):
    require(Path(git('rev-parse', '--show-toplevel')).resolve() == ROOT, 'wrong_git_root')
    require(git('rev-parse', 'HEAD') == source, 'local_source_changed')
    require(not git('status', '--porcelain'), 'working_tree_not_clean')
    require(git('remote', 'get-url', 'origin') == REMOTE, 'unexpected_origin')
    require(git('remote', 'get-url', '--push', 'origin') == REMOTE, 'unexpected_push_origin')
    require(not git('replace', '-l'), 'git_replace_objects_present')
    result = run(['git', 'merge-base', '--is-ancestor', LOCAL_ACCEPTED, source], allowed=(0, 1))
    require(result.returncode == 0, 'candidate_not_descendant_of_local_acceptance')
    # Only this reviewed orchestration and docs were added after local acceptance.
    allowed = {'scripts/github_release_acceptance.py', 'scripts/Invoke-GitHubReleaseAcceptance.ps1',
        'tests/test_github_release_acceptance.py'}
    changed = git('diff', '--name-only', LOCAL_ACCEPTED, source).splitlines()
    require(all(p.startswith('docs/') or p in allowed for p in changed), 'accepted_scope_changed')


def protection(api, base, output, phase):
    branch = api.repo('/branches/' + urllib.parse.quote(base, safe=''))
    classic = api.repo('/branches/' + urllib.parse.quote(base, safe='') + '/protection', missing=True)
    # Effective rules include organization/inherited branch rules. A 403/404 is
    # NOT interpreted as absence; unknown policy must never permit a merge.
    rules = api.pages('/rules/branches/' + urllib.parse.quote(base, safe=''))
    rulesets = api.pages('/rulesets?includes_parents=true')
    require(classic is not None or rules or not branch['protected'], 'protection_not_readable')
    snapshot = dict(base=base, base_sha=branch['commit']['sha'], protected=branch['protected'],
        classic=classic, effective_rules=rules, rulesets=rulesets)
    write_json(output / (phase + '-protection.json'), snapshot)
    return snapshot


def merge_policy(snapshot):
    # These rules require a different, explicitly reviewed integration strategy.
    unsupported = {'merge_queue', 'required_deployments', 'required_linear_history',
                   'required_signatures', 'update'}
    require(not any(r['type'] in unsupported for r in snapshot['effective_rules']),
        'repository_requires_different_merge_workflow')
    classic = snapshot['classic'] or {}
    require(not classic.get('required_linear_history', {}).get('enabled'),
        'repository_requires_linear_history')
    require(not classic.get('lock_branch', {}).get('enabled'), 'main_branch_locked')


def validate_jobs(run_info, jobs):
    require(run_info['status'] == 'completed' and run_info['conclusion'] == 'success', 'ci_not_successful')
    names = Counter(j['name'] for j in jobs)
    require(set(names) == JOBS and all(n == 1 for n in names.values()), 'mandatory_job_inventory_mismatch')
    require(all(j['status'] == 'completed' and j['conclusion'] == 'success' for j in jobs),
        'mandatory_job_not_successful')


def zip_members(data):
    archive = zipfile.ZipFile(BytesIO(data))
    entries = archive.infolist()
    require(len(entries) <= 10000 and sum(i.file_size for i in entries) <= 1024**3,
        'artifact_expansion_limit')
    names = [i.orig_filename for i in entries]
    require(len(names) == len(set(names)), 'duplicate_artifact_paths')
    for name in names:
        path = PurePosixPath(name)
        require(not path.is_absolute() and '..' not in path.parts and '\\' not in name
            and ':' not in name, 'unsafe_artifact_path')
    return archive


def inspect_artifact(data, name, tested_sha):
    """Read ZIP members without extraction; report identifiers/counts, not failure text."""
    archive = zip_members(data)
    report = dict(name=name, sha256=sha256(data).hexdigest(), junit=[], browsers=[])
    for item in archive.infolist():
        if item.filename.endswith('.xml'):
            require(item.file_size <= 32 * 1024**2, 'junit_size_limit')
            root = ET.fromstring(archive.read(item))
            cases = list(root.iter('testcase'))
            failed = sum(c.find('failure') is not None or c.find('error') is not None for c in cases)
            skips = [dict(classname=c.get('classname'), name=(c.get('name') or '').split('[', 1)[0])
                for c in cases if c.find('skipped') is not None]
            require(failed == 0, 'artifact_contains_failed_tests')
            report['junit'].append(dict(path=item.filename, cases=len(cases), failed=failed,
                skipped=skips, sha256=sha256(archive.read(item)).hexdigest()))
        if item.filename.endswith('/result.json') and name == 'phase8-browser-verification':
            result = json.loads(archive.read(item))
            checks = result.get('checks', [])
            require(result.get('status') == 'passed' and result.get('source') == tested_sha,
                'browser_source_or_status_mismatch')
            require(bool(checks) and all(isinstance(c, str) and re.fullmatch('[a-zA-Z0-9_-]+', c) for c in checks)
                and len(checks) == len(set(checks)) and 'source_unchanged' in checks, 'browser_checks_invalid')
            require(result.get('format') in BROWSER_FORMATS and result.get('synthetic_only') is True,
                'unexpected_browser_format')
            report['browsers'].append(dict(path=item.filename, format=result['format'], source=tested_sha, checks=len(checks)))
    if name.startswith('runtime-release-'):
        summary = json.loads(archive.read('release-summary.json'))
        require(summary['source_commit'] == tested_sha, 'release_artifact_source_mismatch')
        manifest = verify_bytes(archive.read('release.zip'), summary['artifact_sha256'])
        require(manifest['source_commit'] == tested_sha, 'release_manifest_source_mismatch')
        report['release'] = summary
    if name.startswith('native-storage-links-') or name == 'document-scanner-verification':
        require(report['junit'] and all(r['cases'] > 0 and not r['skipped'] for r in report['junit']),
            'mandatory_native_or_scanner_tests_skipped')
    if name == 'phase8-browser-verification':
        require(Counter(r['format'] for r in report['browsers']) == Counter(BROWSER_FORMATS),
            'missing_integrated_browser_results')
    else:
        require(bool(report['junit']), 'missing_junit_evidence')
    return report


def merged_receipt(source, merge_sha, output):
    """Resume our recorded merge, not an unrelated merge that bypassed this gate."""
    for path in output.parent.glob('github-release-*/acceptance.json'):
        if path.parent == output:
            continue
        receipt = json.loads(path.read_text(encoding='utf-8'))
        if (receipt.get('source') != source or receipt.get('merge_sha') != merge_sha
                or not receipt.get('review_approved') or not receipt.get('merged_into_main')):
            continue
        hashes = json.loads((path.parent / 'evidence-sha256.json').read_text(encoding='utf-8'))
        for name in ('acceptance.json', 'merge-gates.json', 'before-merge-protection.json'):
            expected = [row['sha256'] for row in hashes if row['path'] == name]
            require(expected == [sha256((path.parent / name).read_bytes()).hexdigest()], 'prior_merge_receipt_integrity')
        return dict(path=str(path.parent), source=source, merge_sha=merge_sha)
    raise Blocked('merged_pr_requires_prior_verified_merge_receipt')


class Acceptance:
    def __init__(self, api, source, output, hours):
        self.api, self.source, self.output = api, source, output
        self.deadline = time.monotonic() + hours * 3600
        self.state = dict(source=source, integrated=True, hosted_ci_verified=False, candidate_ci_verified=False,
            final_source_ci_verified=False,
            review_approved=False, merged_into_main=False, release_ready=False,
            deployed=False, deployment_status='BLOCKED: no approved target; no deployment attempted', runs=[])

    def save(self):
        write_json(self.output / 'acceptance.json', self.state)
        lines = ['# GitHub release acceptance', '', 'Source: `' + self.source + '`', '']
        for key in ('integrated', 'hosted_ci_verified', 'review_approved', 'merged_into_main', 'release_ready', 'deployed'):
            lines.append(f'- {key}: {self.state[key]}')
        lines += ['', 'PR: ' + self.state.get('pr_url', 'not created'),
            'Merge SHA: ' + self.state.get('merge_sha', 'not merged'),
            'Stop code: ' + self.state.get('stop_code', 'none'), '',
            'No deployment authorized. Original local acceptance remains revision-specific.', '']
        for r in self.state['runs']:
            lines.append(f"- {r['event']} / `{r['tested_sha']}`: {r['url']} (attempt {r['attempt']})")
        (self.output / 'RELEASE_ACCEPTANCE.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
        write_json(self.output / 'evidence-sha256.json', [dict(path=p.relative_to(self.output).as_posix(),
            sha256=sha256(p.read_bytes()).hexdigest()) for p in sorted(self.output.rglob('*'))
            if p.is_file() and p.name != 'evidence-sha256.json'])

    def pause(self, reason):
        check_source(self.source)
        require(time.monotonic() < self.deadline, 'waiting_deadline_reached_' + reason)
        print('WAITING: ' + reason, flush=True)
        time.sleep(30)

    def verify_run(self, branch, source, event, tested_sha):
        query = urllib.parse.urlencode(dict(branch=branch, head_sha=source, event=event))
        while True:
            runs = self.api.pages('/actions/workflows/' + WORKFLOW + '/runs?' + query, 'workflow_runs')
            runs = [r for r in runs if r['head_sha'] == source and r['event'] == event
                and r['head_repository']['full_name'] == REPO]
            if not runs:
                self.pause('workflow_discovery')
                continue
            current = max(runs, key=lambda r: (r['run_number'], r['run_attempt']))
            if current['status'] != 'completed':
                self.pause('github_ci')
                continue
            break
        run_id, attempt = current['id'], current['run_attempt']
        folder = self.output / f'run-{run_id}-attempt-{attempt}'
        folder.mkdir(exist_ok=True)
        jobs = self.api.pages(f'/actions/runs/{run_id}/attempts/{attempt}/jobs', 'jobs')
        summary = dict(id=run_id, attempt=attempt, event=event, head_sha=source, tested_sha=tested_sha,
            url=current['html_url'], conclusion=current['conclusion'],
            jobs=[{k: j[k] for k in ('id', 'name', 'status', 'conclusion', 'html_url')} for j in jobs])
        write_json(folder / 'jobs.json', summary)
        self.state['runs'].append(summary)
        self.save()
        # Preserve downloadable diagnostics even for unsuccessful jobs. They are
        # private evidence; never print archive contents or exception messages.
        artifacts = self.api.pages(f'/actions/runs/{run_id}/artifacts', 'artifacts')
        downloaded = []
        for artifact in artifacts:
            require(artifact['name'] in ARTIFACTS, 'unexpected_artifact_name')
            require(not artifact['expired'], 'expired_ci_artifact')
            require(artifact.get('workflow_run', {}).get('head_sha') == source, 'artifact_run_source_mismatch')
            raw = self.api.repo(f"/actions/artifacts/{artifact['id']}/zip", binary=True)
            digest = 'sha256:' + sha256(raw).hexdigest()
            require(artifact.get('digest') == digest, 'github_artifact_digest_mismatch')
            (folder / (str(artifact['id']) + '-' + artifact['name'] + '.zip')).write_bytes(raw)
            downloaded.append((artifact, raw))
        write_json(folder / 'artifact-downloads.json', [dict(id=a['id'], name=a['name'],
            digest=a['digest'], bytes=len(raw)) for a, raw in downloaded])
        validate_jobs(current, jobs)
        require(Counter(a['name'] for a, _ in downloaded) == Counter(ARTIFACTS), 'artifact_inventory_mismatch')
        reports = [inspect_artifact(raw, a['name'], tested_sha) for a, raw in downloaded]
        releases = [r['release'] for r in reports if 'release' in r]
        require(len(releases) == 2 and releases[0] == releases[1], 'cross_platform_release_mismatch')
        write_json(folder / 'validated-artifacts.json', reports)
        summary['artifacts_verified'] = True
        summary['release_sha256'] = releases[0]['artifact_sha256']
        summary['junit_reports'] = [dict(artifact=r['name'], **j) for r in reports for j in r['junit']]
        summary['browser_reports'] = [b for r in reports for b in r['browsers']]
        self.save()
        return summary

    def reviews(self, number, head, author):
        reviews = self.api.pages(f'/pulls/{number}/reviews')
        latest = {}
        for r in sorted(reviews, key=lambda r: r['id']):
            if r['state'] in ('APPROVED', 'CHANGES_REQUESTED', 'DISMISSED'):
                latest[r['user']['login']] = r
        require(not any(r['state'] == 'CHANGES_REQUESTED' for r in latest.values()), 'review_changes_requested')
        approved = [r for login, r in latest.items() if login != author and r['state'] == 'APPROVED'
            and r['commit_id'] == head and r['user']['type'] == 'User']
        write_json(self.output / 'reviews.json', [dict(id=r['id'], user=r['user']['login'],
            state=r['state'], commit=r['commit_id'], submitted_at=r['submitted_at'], url=r['html_url']) for r in reviews])
        return approved

    def execute(self):
        check_source(self.source)
        repository = self.api.repo('')
        require(repository['full_name'] == REPO and not repository['archived'], 'invalid_repository')
        base = repository['default_branch']
        # Existing documented intended production branch is main; a different
        # remote default is a real decision, not permission to publish elsewhere.
        require(base == 'main', 'default_branch_is_not_documented_main')
        policy = protection(self.api, base, self.output, 'initial')
        self.state['base'] = base
        branch = 'review/integrated-release-' + self.source[:12]
        self.state['review_branch'] = branch
        git('fetch', '--no-tags', 'origin', base)
        require(git('rev-parse', 'FETCH_HEAD') == policy['base_sha'], 'main_changed_during_preflight')
        existing = self.api.pages('/pulls?' + urllib.parse.urlencode(dict(state='all', head=REPO.split('/')[0] + ':' + branch, base=base)))
        require(len(existing) <= 1, 'ambiguous_review_pr')
        pr = self.api.repo('/pulls/' + str(existing[0]['number'])) if existing else None
        if not (pr and pr['merged']):
            require(run(['git', 'merge-base', '--is-ancestor', policy['base_sha'], self.source],
                allowed=(0, 1)).returncode == 0, 'main_has_unintegrated_changes')
        ref = self.api.repo('/git/ref/heads/' + branch, missing=True)
        if ref is None:
            git('push', 'origin', self.source + ':refs/heads/' + branch)
        else:
            require(ref['object']['sha'] == self.source, 'review_branch_has_different_source')
        require(self.api.repo('/git/ref/heads/' + branch)['object']['sha'] == self.source, 'published_source_mismatch')
        if pr is None:
            body = (ROOT / 'docs/INTEGRATED_RELEASE_PR.md').read_text(encoding='utf-8')
            title, body = body.split('\n', 1)
            for name in ('FINAL_RELEASE_ACCEPTANCE.md', 'RELEASE_ACCEPTANCE_MANIFEST.json'):
                body = body.replace('(' + name + ')', '(https://github.com/' + REPO + '/blob/' + self.source + '/docs/' + name + ')')
            pr = self.api.repo('/pulls', method='POST', payload=dict(title=title.lstrip('# '),
                body=body + '\n\nExact candidate: `' + self.source + '`. No deployment.\n', head=branch, base=base))
        require(pr['head']['sha'] == self.source and pr['base']['ref'] == base, 'pr_source_mismatch')
        self.state.update(pr_number=pr['number'], pr_url=pr['html_url'])
        self.save()
        print('PR: ' + pr['html_url'], flush=True)
        self.verify_run(branch, self.source, 'push', self.source)
        if not pr['merged']:
            while True:
                pr = self.api.repo('/pulls/' + str(pr['number']))
                require(pr['head']['sha'] == self.source and pr['state'] == 'open', 'pr_changed_or_closed')
                if pr['mergeable'] is None:
                    self.pause('mergeability_calculation')
                    continue
                require(pr['mergeable'], 'pr_has_conflicts')
                require(pr['base']['sha'] == policy['base_sha'], 'main_changed_requires_reconciliation')
                break
            merge_test = pr['merge_commit_sha']
            self.verify_run(branch, self.source, 'pull_request', merge_test)
            self.state['hosted_ci_verified'] = True
            self.state['candidate_ci_verified'] = True
            self.save()
            # PR reviewers receive actual run URLs. No self-approval or protection edits.
            marker = 'OPENHERZ final-source evidence: ' + self.source
            comments = self.api.pages(f"/issues/{pr['number']}/comments")
            if not any(marker in c['body'] for c in comments):
                body = marker + '\n\nAll ten mandatory jobs and artifact/source hashes verified for each run:\n'
                body += '\n'.join('- ' + r['url'] + ' / tested `' + r['tested_sha'] + '`' for r in self.state['runs'])
                body += '\n\nPlease review the code, CI artifacts (including JUnit skips and browser images), and approve this exact head if acceptable. No deployment is included.'
                self.api.repo(f"/issues/{pr['number']}/comments", method='POST', payload=dict(body=body))
            while True:
                check_source(self.source)
                current = self.api.repo('/pulls/' + str(pr['number']))
                require(current['head']['sha'] == self.source and current['base']['sha'] == policy['base_sha'], 'pr_or_base_changed')
                require(not current['merged'] and current['state'] == 'open', 'pr_changed_during_review')
                approved = self.reviews(pr['number'], self.source, pr['user']['login'])
                if approved and current['mergeable_state'] == 'clean':
                    permitted = [r for r in approved if self.api.repo('/collaborators/' +
                        urllib.parse.quote(r['user']['login'], safe='') + '/permission')['permission']
                        in ('write', 'maintain', 'admin')]
                    require(bool(permitted), 'independent_reviewer_requires_write_permission')
                    break
                self.pause('independent_review_and_repository_gates')
            policy_now = protection(self.api, base, self.output, 'before-merge')
            require(policy_now == policy, 'repository_policy_changed')
            merge_policy(policy_now)
            require(self.api.repo('')['allow_merge_commit'], 'merge_commit_not_permitted')
            # No bypass: require GitHub's reviewDecision and all check/status contexts.
            query = '''query($owner:String!,$name:String!,$number:Int!){repository(owner:$owner,name:$name){pullRequest(number:$number){reviewDecision mergeStateStatus}}}'''
            graph = self.api.request('/graphql', method='POST', payload=dict(query=query,
                variables=dict(owner=REPO.split('/')[0], name=REPO.split('/')[1], number=pr['number'])))
            require(not graph.get('errors'), 'review_policy_query_failed')
            decision = graph['data']['repository']['pullRequest']
            require(decision['reviewDecision'] in ('APPROVED', None) and decision['mergeStateStatus'] == 'CLEAN', 'github_review_gate_not_met')
            checks = []
            status_evidence = []
            for sha in (self.source, merge_test):
                current_checks = self.api.pages('/commits/' + sha + '/check-runs?filter=latest', 'check_runs')
                statuses = self.api.repo('/commits/' + sha + '/status')
                require((current_checks or sha != self.source) and all(c['status'] == 'completed' and c['conclusion'] == 'success'
                    for c in current_checks), 'pr_checks_not_successful')
                require(not statuses['statuses'] or statuses['state'] == 'success', 'pr_statuses_not_successful')
                checks.extend(current_checks)
                status_evidence.append(dict(source=sha, state=statuses['state']))
            write_json(self.output / 'merge-gates.json', dict(review=decision, approved_review_ids=[r['id'] for r in approved],
                checks=[dict(id=c['id'], name=c['name'], conclusion=c['conclusion']) for c in checks], statuses=status_evidence))
            self.state['review_approved'] = True
            self.save()
            check_source(self.source)
            merged = self.api.repo(f"/pulls/{pr['number']}/merge", method='PUT',
                payload=dict(sha=self.source, merge_method='merge'))
            require(merged.get('merged') is True, 'github_merge_rejected')
            merge_sha = merged['sha']
        else:
            # Resume a previously merged run only after its actual review is verified.
            require(bool(self.reviews(pr['number'], self.source, pr['user']['login'])), 'merged_pr_without_exact_source_review')
            self.state['prior_merge_receipt'] = merged_receipt(self.source, pr['merge_commit_sha'], self.output)
            self.state['candidate_ci_verified'] = True
            self.state['review_approved'] = True
            merge_sha = pr['merge_commit_sha']
        self.state.update(merged_into_main=True, merge_sha=merge_sha, hosted_ci_verified=False)
        self.save()
        final = self.api.repo('/commits/' + merge_sha)
        candidate = self.api.repo('/commits/' + self.source)
        require(final['commit']['tree']['sha'] == candidate['commit']['tree']['sha'], 'merged_tree_differs_from_candidate')
        self.verify_run(base, merge_sha, 'push', merge_sha)
        require(self.api.repo('/branches/' + base)['commit']['sha'] == merge_sha, 'main_advanced_after_merge')
        check_source(self.source)
        marker = 'OPENHERZ merged-source acceptance: ' + merge_sha
        if not any(marker in c['body'] for c in self.api.pages(f"/issues/{pr['number']}/comments")):
            body = marker + '\n\nReviewed head: `' + self.source + '`. Merged tree matches the reviewed candidate.\n'
            body += '\n'.join('- ' + r['url'] + ' / tested `' + r['tested_sha'] + '`' for r in self.state['runs'])
            body += '\n\nTen mandatory jobs, artifact SHA-256/source manifests and Windows/Linux release equivalence verified. Independent exact-head approval preserved. Local evidence includes JUnit counts/skips and downloaded archives. RELEASE READY applies to the code candidate only; no host or real-data approval, no deployment.'
            self.api.repo(f"/issues/{pr['number']}/comments", method='POST', payload=dict(body=body))
        self.state.update(hosted_ci_verified=True, final_source_ci_verified=True, release_ready=True)
        self.save()
        print('SUCCESS: hosted source CI, independent review and main merge verified. No deployment.', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--expected-source', required=True)
    parser.add_argument('--wait-hours', type=int, default=24, choices=range(1, 49))
    args = parser.parse_args()
    output = ROOT / '.verification' / ('github-release-' + uuid4().hex)
    acceptance = None
    try:
        require(re.fullmatch('[a-f0-9]{40}', args.expected_source) is not None, 'invalid_source')
        require(Path.cwd().resolve() == ROOT, 'wrong_working_directory')
        for path in (output.parent, *output.parent.parents):
            require(not path.is_symlink() and not path.is_junction(), 'linked_evidence_directory')
        output.mkdir(parents=True)
        print('Evidence: ' + str(output), flush=True)
        check_source(args.expected_source)
        acceptance = Acceptance(GitHub(credentials()), args.expected_source, output, args.wait_hours)
        acceptance.save()
        acceptance.execute()
        return 0
    except KeyboardInterrupt:
        code = 'operator_interrupted'
    except Blocked as exc:
        code = str(exc)
    except Exception:
        code = 'unexpected_release_launcher_error'
    if acceptance:
        acceptance.state['stop_code'] = code
        acceptance.save()
    elif output.exists():
        write_json(output / 'blocked.json', dict(source=args.expected_source, stop_code=code, release_ready=False))
    print('BLOCKED: ' + code + '. Evidence retained; no success claimed.', flush=True)
    return 2


if __name__ == '__main__':
    raise SystemExit(main())
