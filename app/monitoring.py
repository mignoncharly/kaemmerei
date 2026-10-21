"""Read-only local operator checks. Redacted output; exit status drives local action.

Receipts are fully verified including ciphertext hash. No notification transport.
"""
from datetime import datetime, timezone, timedelta
import shutil
from sqlalchemy import text
from app.backup_crypto import verify_receipt
from app.operational_status import job_health


def newest_receipt(directory):
    """Bounded candidate selection; caller MUST verify signature/digest and age.

    Modification time selects only a candidate, never proves successful backup.
    No fallback to an older receipt when the selected artifact is corrupt.
    """
    from app.documents import reject_links
    from pathlib import Path
    import re
    root = Path(directory)
    if not root.is_absolute():
        raise ValueError('Absolute backup directory required')
    reject_links(root)
    candidates = []
    for index, child in enumerate(root.iterdir()):
        if index >= 4096:
            raise ValueError('Backup inventory exceeds monitoring bound; review preservation policy')
        reject_links(child)
        if re.fullmatch('backup-[0-9a-f]{32}', child.name) and child.is_dir():
            receipt = child/'receipt.json'
            reject_links(receipt)
            if receipt.is_file():
                candidates.append((receipt.stat().st_mtime_ns, receipt))
    if not candidates:
        raise ValueError('No completed backup candidate')
    return max(candidates, key=lambda item:(item[0],str(item[1])))[1]


def require_operator(connection):
    if connection.dialect.name == 'postgresql':
        if not connection.scalar(text("SELECT pg_get_userbyid(nspowner)=current_user FROM pg_namespace WHERE nspname='ohvr_security'")):
            raise PermissionError('Explicit schema operator required')


def database_health(engine, *, clock=None):
    clock = clock or datetime.now(timezone.utc)
    with engine.connect() as connection:
        if connection.dialect.name == 'postgresql':
            connection.execute(text('SET TRANSACTION READ ONLY'))
        require_operator(connection)
        counts = {}
        for name, query in {
            'scan_pending': "SELECT count(*) FROM document_jobs WHERE state IN ('pending','retry')",
            'scan_exhausted': "SELECT count(*) FROM document_jobs WHERE state IN ('pending','retry') AND attempts>=5",
            'unpublished_events': 'SELECT count(*) FROM sync_outbox WHERE published_seq IS NULL',
            'expired_tokens': 'SELECT count(*) FROM integration_tokens WHERE is_active=true AND expires_at <= :now',
            'security_denials_15m': "SELECT count(*) FROM security_events WHERE outcome<>'success' AND created_at>=:since",
            'login_attempts_15m': 'SELECT count(*) FROM login_attempts WHERE created_at>=:since',
        }.items():
            counts[name] = connection.scalar(text(query), {'now': clock.replace(tzinfo=None),
                'since': (clock-timedelta(minutes=15)).replace(tzinfo=None)})
        oldest = connection.scalar(text("SELECT min(updated_at) FROM document_jobs WHERE state IN ('pending','retry')"))
        if isinstance(oldest, str):
            oldest = datetime.fromisoformat(oldest)
        counts['oldest_scan_seconds'] = max(0, (clock.replace(tzinfo=None)-oldest).total_seconds()) if oldest else 0
        return counts


def operational_health(engine, storage, status_directory, receipt, verifier, *,
                       reserve_bytes=256*1024**2, maximum_backup_hours=24,
                       security_threshold=100, production=False, clock=None, backup_directory=None):
    if not 1 <= maximum_backup_hours <= 24 or reserve_bytes < 0 or not 1 <= security_threshold <= 100000:
        raise ValueError('Invalid bounded operational thresholds')
    clock = clock or datetime.now(timezone.utc)
    checks = {}; metrics = {}
    try:
        metrics = database_health(engine, clock=clock)
        checks['database'] = True
        checks['scan_queue'] = metrics['scan_exhausted'] == 0 and metrics['oldest_scan_seconds'] <= 600
        checks['event_feed'] = metrics['unpublished_events'] == 0
        checks['security_activity'] = max(metrics['security_denials_15m'], metrics['login_attempts_15m']) < security_threshold
    except Exception:
        checks['database'] = False
    if production:
        try:
            from app.server_security import validate_server_security
            validate_server_security(engine)
            checks['server_security_baseline'] = True
        except Exception:
            checks['server_security_baseline'] = False
    try:
        from app.documents import reject_links
        reject_links(storage)
        metrics['storage_free_bytes'] = shutil.disk_usage(storage).free
        checks['storage_capacity'] = metrics['storage_free_bytes'] >= reserve_bytes
    except Exception:
        checks['storage_capacity'] = False
    try:
        jobs = job_health(status_directory, production=production, clock=clock)
        checks.update({'job_'+key: value == 'ok' for key, value in jobs.items()})
    except Exception:
        checks['job_evidence'] = False
    try:
        if backup_directory is not None:
            receipt = newest_receipt(backup_directory)
        metadata, _ = verify_receipt(receipt, verifier)
        start = datetime.fromisoformat(metadata['created_at'])
        finish = datetime.fromisoformat(metadata['finished_at'])
        age = (clock-start).total_seconds()  # snapshot age, not just completion
        metrics['backup_snapshot_age_seconds'] = age
        checks['backup'] = start <= finish <= clock and 0 <= age <= maximum_backup_hours*3600
    except Exception:
        checks['backup'] = False
    return dict(format='ohvr-health-v1', healthy=all(checks.values()),
                checked_at=clock.isoformat(), checks=checks, metrics=metrics,
                external_delivery=False)
