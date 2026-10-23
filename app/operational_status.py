"""Private, local scheduler evidence. No credentials, business IDs or delivery.

Persistent OS locks survive status replacement and are released on process death.
An interrupted running marker deliberately remains unhealthy until a later run.
"""
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from uuid import uuid4

from app.documents import reject_links, verify_private_acl

JOBS = {'scan-pending': 600, 'purge-sessions': 7200,
        'document-reconcile': 90000, 'integration-status': 7200,
        'events-publish': 600, 'backup-create': 50400}


def utcnow():
    return datetime.now(timezone.utc)


def status_root(directory, production=False):
    root = Path(directory)
    if not root.is_absolute() or (os.name == 'nt' and str(root).startswith('\\\\')):
        raise ValueError('Local absolute operational status directory required')
    reject_links(root)
    if not root.is_dir():
        raise ValueError('Provision operational status storage explicitly')
    if production:
        verify_private_acl(root)
    return root


def _write(root, job, data):
    target = root / (job + '.json')
    reject_links(target)
    temporary = root / (uuid4().hex + '.tmp')
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump(data, stream, sort_keys=True)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)


@contextmanager
def tracked_job(directory, job, *, production=False):
    if job not in JOBS:
        raise ValueError('Unsupported operational job')
    root = status_root(directory, production)
    lock = root / (job + '.lock')
    reject_links(lock)
    with lock.open('a+b') as stream:
        stream.seek(0)
        if os.name == 'nt':
            import msvcrt
            if not stream.read(1):
                stream.write(b'0'); stream.flush()
            stream.seek(0)
            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            data = dict(format='ohvr-job-v1', job=job, state='running',
                        started_at=utcnow().isoformat(), finished_at=None)
            _write(root, job, data)
            try:
                yield
            except BaseException:
                data.update(state='failed', finished_at=utcnow().isoformat())
                _write(root, job, data)
                raise
            else:
                data.update(state='success', finished_at=utcnow().isoformat())
                _write(root, job, data)
        finally:
            if os.name == 'nt':
                stream.seek(0); msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream, fcntl.LOCK_UN)


def job_health(directory, *, clock=None, production=False):
    root = status_root(directory, production)
    clock = clock or utcnow()
    result = {}
    for job, maximum in JOBS.items():
        try:
            path = root / (job + '.json')
            reject_links(path)
            if path.stat().st_size > 4096:
                raise ValueError()
            data = json.loads(path.read_text(encoding='utf-8'))
            started = datetime.fromisoformat(data['started_at'])
            finished = datetime.fromisoformat(data['finished_at'])
            age = (clock - finished).total_seconds()
            healthy = (data['format'] == 'ohvr-job-v1' and data['job'] == job
                       and data['state'] == 'success' and started <= finished
                       and 0 <= age <= maximum)
            result[job] = 'ok' if healthy else 'failed_or_stale'
        except Exception:
            result[job] = 'missing_invalid_or_interrupted'
    return result
