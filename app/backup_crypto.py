"""Native age file encryption and standard Ed25519 detached receipt signatures.

No custom encryption format/primitives. Encryption alone does not authenticate
the backup's sender; the recovery verifier key must come from trusted custody,
not from the backup being verified. Never print key material or tool stderr.
"""
import base64
from datetime import datetime,timedelta
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import stat
import subprocess
from threading import Timer

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey,Ed25519PublicKey

from app.documents import read_private,reject_links

MAX_ARCHIVE=50*1024**3
DOMAIN=b'OPEN.HERZ encrypted backup receipt v1\x00'
RECEIPT_FIELDS=frozenset(('format','created_at','finished_at','schema_head','ciphertext_file',
                         'ciphertext_sha256','ciphertext_bytes','file_count'))


def file_digest(path,*,limit=MAX_ARCHIVE):
    reject_links(path)
    fd=os.open(path,os.O_RDONLY|getattr(os,'O_BINARY',0)|getattr(os,'O_NOFOLLOW',0))
    with os.fdopen(fd,'rb') as stream:
        before=os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_nlink!=1 or before.st_size>limit:
            raise ValueError('Invalid bounded backup input')
        digest=sha256();size=0
        while chunk:=stream.read(1024*1024):
            size+=len(chunk)
            if size>limit:raise ValueError('Backup input exceeds limit')
            digest.update(chunk)
        after=os.fstat(stream.fileno())
        if size!=before.st_size or (before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns):
            raise ValueError('Backup input changed while hashing')
    return digest.hexdigest(),size


def small_file(path,limit=16384):
    if not path.is_absolute() or (os.name=='nt' and str(path).startswith('\\\\')):
        raise ValueError('Explicit local backup configuration path required')
    reject_links(path)
    if path.stat().st_size>limit:raise ValueError('Oversize backup configuration')
    data=read_private(path)
    if len(data)>limit:raise ValueError('Oversize backup configuration')
    return data


def native_keys(path,*,private=False):
    lines=[line.strip() for line in small_file(path,65536).decode('ascii').splitlines()
           if line.strip() and not line.lstrip().startswith('#')]
    if not 1<=len(lines)<=8:raise ValueError('One to eight native age keys required')
    for line in lines:
        if private:
            allowed=re.fullmatch(r'AGE-SECRET-KEY-(?:PQ-)?1[A-Z02-9]{32,4096}',line)
        else:
            allowed=(re.fullmatch(r'age1[02-9ac-hj-np-z]{58}',line) or
                     re.fullmatch(r'age1pq1[02-9ac-hj-np-z]{1000,4096}',line))
        if not allowed:raise ValueError('Only native age identities/recipients are accepted; no plugins, SSH or passphrases')
    return lines


def _tool_env():
    # No database URLs/password/passfile variables enter the encryption process.
    return {name:value for name,value in os.environ.items()
            if name.upper() in ('SYSTEMROOT','WINDIR','TEMP','TMP','PATH','LANG','LC_ALL')}


def validate_age(executable,expected_sha256):
    if (not executable.is_absolute() or (os.name=='nt' and str(executable).startswith('\\\\'))
            or not re.fullmatch('[0-9a-f]{64}',expected_sha256)):
        raise ValueError('An explicit hash-pinned native age executable is required')
    if file_digest(executable,limit=64*1024*1024)[0]!=expected_sha256:
        raise ValueError('Native age executable digest mismatch')
    try:
        result=subprocess.run([str(executable),'--version'],capture_output=True,timeout=10,
                              env=_tool_env(),check=True)
        if result.stdout.strip()!=b'v1.3.2':raise ValueError()
    except Exception:
        raise ValueError('Reviewed age 1.3.2 executable required') from None


def encrypt_stream(executable,recipients,output,writer,*,seconds=1800):
    if not 1<=seconds<=7200:raise ValueError('Bounded encryption deadline required')
    keys=native_keys(recipients)
    args=[str(executable),'--encrypt']
    for key in keys:args.extend(('--recipient',key))  # public values only
    with output.open('xb') as encrypted:
        process=subprocess.Popen(args,stdin=subprocess.PIPE,stdout=encrypted,stderr=subprocess.DEVNULL,env=_tool_env())
        def expire():
            if process.poll() is None:process.kill()
        timer=Timer(seconds,expire);timer.daemon=True;timer.start()
        try:
            writer(process.stdin)
            process.stdin.close()
            if process.wait(timeout=seconds)!=0:raise ValueError('Age encryption did not complete')
            encrypted.flush();os.fsync(encrypted.fileno())
        finally:
            timer.cancel()
            try:
                if process.stdin and not process.stdin.closed:process.stdin.close()
            except (BrokenPipeError,OSError):
                pass  # Process cleanup must still run after a closed pipe.
            finally:
                if process.poll() is None:
                    process.kill();process.wait(timeout=10)


def decrypt_file(executable,identity,encrypted,output,*,seconds=1800,expected=None):
    if not 1<=seconds<=7200:raise ValueError('Bounded decryption deadline required')
    native_keys(identity,private=True)
    reject_links(encrypted)
    fd=os.open(encrypted,os.O_RDONLY|getattr(os,'O_BINARY',0)|getattr(os,'O_NOFOLLOW',0))
    # Hash the exact bytes supplied to the decryptor, not a separate path read.
    # No plaintext is accepted until age exits successfully AND the signed
    # expected digest/size matches this same stream.
    with os.fdopen(fd,'rb') as source,output.open('xb') as decrypted:
        info=os.fstat(source.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_nlink!=1 or info.st_size>MAX_ARCHIVE:
            raise ValueError('Invalid bounded encrypted input')
        process=subprocess.Popen([str(executable),'--decrypt','--identity',str(identity)],
            stdin=subprocess.PIPE,stdout=decrypted,stderr=subprocess.DEVNULL,env=_tool_env())
        def expire():
            if process.poll() is None:process.kill()
        timer=Timer(seconds,expire);timer.daemon=True;timer.start()
        try:
            digest=sha256();size=0
            while chunk:=source.read(1024*1024):
                size+=len(chunk)
                if size>MAX_ARCHIVE:raise ValueError('Encrypted input exceeds limit')
                digest.update(chunk);process.stdin.write(chunk)
            process.stdin.close()
            if process.wait(timeout=seconds)!=0:
                raise ValueError('Age decryption did not authenticate the complete input')
            if expected is not None and (digest.hexdigest(),size)!=expected:
                raise ValueError('Signed ciphertext changed during decryption')
            decrypted.flush();os.fsync(decrypted.fileno())
        finally:
            timer.cancel()
            try:
                if process.stdin and not process.stdin.closed:process.stdin.close()
            except (BrokenPipeError,OSError):pass
            finally:
                if process.poll() is None:process.kill();process.wait(timeout=10)


def canonical(metadata):
    if set(metadata)!=RECEIPT_FIELDS or metadata['format']!='ohvr-backup-v1':
        raise ValueError('Unsupported backup receipt format')
    if not re.fullmatch(r'bundle-[0-9a-f]{32}\.tar\.age',metadata['ciphertext_file']):
        raise ValueError('Unsafe backup artifact name')
    if not re.fullmatch('[0-9a-f]{64}',metadata['ciphertext_sha256']):raise ValueError('Invalid backup digest')
    if (type(metadata['ciphertext_bytes']) is not int or not 1<=metadata['ciphertext_bytes']<=MAX_ARCHIVE
            or type(metadata['file_count']) is not int or not 0<=metadata['file_count']<=100000):
        raise ValueError('Invalid bounded receipt sizes')
    if not re.fullmatch(r'[0-9]{4}_[a-z0-9_]{1,64}',metadata['schema_head']):
        raise ValueError('Invalid backup schema identifier')
    started,finished=(datetime.fromisoformat(metadata[field]) for field in ('created_at','finished_at'))
    if started.utcoffset()!=timedelta(0) or finished.utcoffset()!=timedelta(0) or finished<started:
        raise ValueError('UTC backup timestamps in order required')
    return json.dumps(metadata,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False).encode('ascii')


def signed_receipt(metadata,signing_key):
    key=serialization.load_pem_private_key(small_file(signing_key),password=None)
    if not isinstance(key,Ed25519PrivateKey):raise ValueError('Ed25519 backup signing key required')
    signature=key.sign(DOMAIN+canonical(metadata))
    return dict(metadata=metadata,signature=base64.b64encode(signature).decode('ascii'))


def verify_receipt(receipt_path,verifier_key):
    try:
        receipt=json.loads(small_file(receipt_path))
        if set(receipt)!= {'metadata','signature'}:raise ValueError()
        metadata=receipt['metadata']
        key=serialization.load_pem_public_key(small_file(verifier_key))
        if not isinstance(key,Ed25519PublicKey):raise ValueError()
        key.verify(base64.b64decode(receipt['signature'],validate=True),DOMAIN+canonical(metadata))
        encrypted=receipt_path.parent/metadata['ciphertext_file']
        digest,size=file_digest(encrypted)
        if (digest,size)!=(metadata['ciphertext_sha256'],metadata['ciphertext_bytes']):raise ValueError()
        return metadata,encrypted
    except Exception:
        raise ValueError('Backup signature, format or artifact digest verification failed') from None
