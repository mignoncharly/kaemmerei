"""Disposable native age keys and standard signature round trips; no real data."""
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import subprocess
from types import SimpleNamespace
from uuid import uuid4

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
import pytest

from app.backup_crypto import (decrypt_file,encrypt_stream,file_digest,native_keys,
    signed_receipt,validate_age,verify_receipt)
from tests.support import scratch_directory


@pytest.fixture
def backup_keys():
    configured=os.getenv('TEST_AGE_BIN')
    expected=os.getenv('TEST_AGE_SHA256')
    if configured:
        executable=Path(configured)
    else:
        executable=Path('.verification/phase9-tools/age-1.3.2/age.exe').resolve()
        provenance=Path('.verification/phase9-age-provenance.json')
        if executable.is_file() and provenance.is_file():
            expected=next(f['sha256'] for f in json.loads(provenance.read_text())['files'] if f['name']=='age.exe')
    if not executable.is_file() or not expected:
        if os.getenv('REQUIRE_BACKUP_ENCRYPTION')=='1':
            pytest.fail('Required actual age encryption tool/provenance unavailable')
        pytest.skip('Native age tool not provisioned; required backup CI sets REQUIRE_BACKUP_ENCRYPTION=1')
    validate_age(executable,expected)
    keygen=executable.with_name('age-keygen.exe' if os.name=='nt' else 'age-keygen')
    with scratch_directory('backup-keys-') as directory:
        root=Path(directory)
        identity,recipients=root/'identity.txt',root/'recipients.txt'
        subprocess.run([str(keygen),'-pq','-o',str(identity)],stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=15,check=True)
        subprocess.run([str(keygen),'-y','-o',str(recipients),str(identity)],stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=15,check=True)
        key=Ed25519PrivateKey.generate()
        signer,verifier=root/'signer.pem',root/'verifier.pem'
        signer.write_bytes(key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()))
        verifier.write_bytes(key.public_key().public_bytes(serialization.Encoding.PEM,serialization.PublicFormat.SubjectPublicKeyInfo))
        yield SimpleNamespace(root=root,executable=executable,sha256=expected,identity=identity,
                              recipients=recipients,signer=signer,verifier=verifier)


def test_actual_native_encryption_signature_and_decryption(backup_keys):
    keys=backup_keys
    artifact=keys.root/('bundle-'+uuid4().hex+'.tar.age')
    payload=b'Synthetic confidential backup content\n'*10000
    encrypt_stream(keys.executable,keys.recipients,artifact,lambda stream:stream.write(payload),seconds=15)
    assert b'Synthetic confidential backup content' not in artifact.read_bytes()
    digest,size=file_digest(artifact)
    now=datetime.now(timezone.utc).isoformat()
    metadata=dict(format='ohvr-backup-v1',created_at=now,finished_at=now,schema_head='0023_human_mfa',
        ciphertext_file=artifact.name,ciphertext_sha256=digest,ciphertext_bytes=size,file_count=1)
    receipt=keys.root/'receipt.json'
    receipt.write_text(json.dumps(signed_receipt(metadata,keys.signer)),encoding='utf-8')
    actual,encrypted=verify_receipt(receipt,keys.verifier)
    assert actual==metadata
    output=keys.root/'restored.bin'
    decrypt_file(keys.executable,keys.identity,encrypted,output,seconds=15)
    assert output.read_bytes()==payload
    with pytest.raises(ValueError,match='changed during decryption'):
        decrypt_file(keys.executable,keys.identity,encrypted,keys.root/'wrong-digest-output',seconds=15,
                     expected=('0'*64,size))
    # An intact encrypted file still needs an independently trusted signer.
    wrong=Ed25519PrivateKey.generate().public_key()
    other=keys.root/'other.pem'
    other.write_bytes(wrong.public_bytes(serialization.Encoding.PEM,serialization.PublicFormat.SubjectPublicKeyInfo))
    with pytest.raises(ValueError,match='signature'):verify_receipt(receipt,other)
    receipt_data=json.loads(receipt.read_text());receipt_data['metadata']['file_count']=2
    receipt.write_text(json.dumps(receipt_data),encoding='utf-8')
    with pytest.raises(ValueError):verify_receipt(receipt,keys.verifier)


def test_truncated_age_input_never_yields_success(backup_keys):
    keys=backup_keys;encrypted=keys.root/'truncated.age'
    encrypt_stream(keys.executable,keys.recipients,encrypted,lambda stream:stream.write(b'x'*200000),seconds=15)
    data=encrypted.read_bytes();encrypted.write_bytes(data[:-20])
    with pytest.raises(ValueError,match='complete input'):
        decrypt_file(keys.executable,keys.identity,encrypted,keys.root/'partial-output',seconds=15)


@pytest.mark.parametrize('line',['age1plugin1not-a-native-recipient','ssh-ed25519 invalid','-','AGE-PLUGIN-EVIL-1DATA'])
def test_interactive_ssh_and_plugin_inputs_are_refused(line):
    with scratch_directory('backup-invalid-') as directory:
        path=Path(directory)/'keys.txt';path.write_text(line,encoding='ascii')
        with pytest.raises(ValueError):native_keys(path)
        with pytest.raises(ValueError):native_keys(path,private=True)
