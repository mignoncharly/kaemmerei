"""Public RFC vectors and disposable keys only; no production MFA material."""
import base64
import json
from pathlib import Path

import pyotp
import pytest
from cryptography.fernet import Fernet

from app.mfa_codec import SeedCipher, matching_step
from tests.support import scratch_directory


def test_seed_encryption_binds_account_and_rejects_tampering():
    with scratch_directory('mfa-codec-') as directory:
        path=Path(directory)/'keys.json'
        path.write_text(json.dumps([Fernet.generate_key().decode()]),encoding='utf-8')
        cipher=SeedCipher(path)
        seed=pyotp.random_base32()
        token=cipher.encrypt(1,seed)
        assert seed not in token and cipher.decrypt(1,token)==seed
        with pytest.raises(ValueError):cipher.decrypt(2,token)
        with pytest.raises(ValueError):cipher.decrypt(1,token[:-8]+'AAAAAAAA')


def test_rotation_preserves_account_binding_and_allows_retiring_old_key():
    with scratch_directory('mfa-codec-') as directory:
        path=Path(directory)/'keys.json'
        old,new=Fernet.generate_key().decode(),Fernet.generate_key().decode()
        path.write_text(json.dumps([old]),encoding='utf-8')
        old_cipher=SeedCipher(path)
        seed=pyotp.random_base32();token=old_cipher.encrypt(1,seed)
        path.write_text(json.dumps([new,old]),encoding='utf-8')
        rotated=SeedCipher(path).rotate(1,token)
        path.write_text(json.dumps([new]),encoding='utf-8')
        assert SeedCipher(path).decrypt(1,rotated)==seed
        with pytest.raises(ValueError):old_cipher.decrypt(1,rotated)


@pytest.mark.parametrize('data',['{}','[]','["invalid"]','x'*1025])
def test_invalid_key_files_fail_closed(data):
    with scratch_directory('mfa-codec-') as directory:
        path=Path(directory)/'keys.json';path.write_text(data,encoding='utf-8')
        with pytest.raises(ValueError):SeedCipher(path)


def test_rfc6238_vector_window_replay_and_strict_digits():
    # RFC 6238 Appendix B SHA1 vector 59s: 94287082 with eight digits.
    seed=base64.b32encode(b'12345678901234567890').decode()
    assert pyotp.TOTP(seed,digits=8).at(59)=='94287082'
    assert matching_step(seed,'287082',-1,timestamp=59)==1
    assert matching_step(seed,'287082',1,timestamp=59) is None
    assert matching_step(seed,'287082',-1,timestamp=90) is None
    for code in ('', '2870820', ' 287082', '\u0661'*6, '28708x'):
        assert matching_step(seed,code,-1,timestamp=59) is None
