"""Maintained OTP/encryption primitives; seed material never belongs in logs.

Small Fernet messages only, not bulk backup encryption. Keys are provisioned
separately from database/storage backups. The first key encrypts; old keys may
remain for an explicitly managed rotation/recovery window.
"""
import json
from pathlib import Path
import re
import secrets
import time

import pyotp
from cryptography.fernet import Fernet, MultiFernet

from app.documents import read_private, reject_links


class SeedCipher:
    def __init__(self, path: Path):
        if not path.is_absolute():
            raise ValueError('An absolute private MFA key file is required')
        reject_links(path)
        if path.stat().st_size > 1024:
            raise ValueError('Invalid MFA key file')
        try:
            keys = json.loads(read_private(path))
            if (not isinstance(keys,list) or not 1 <= len(keys) <= 5 or
                    any(not isinstance(key,str) or len(key)!=44 for key in keys)):
                raise ValueError()
            self._cipher = MultiFernet([Fernet(key.encode('ascii')) for key in keys])
        except Exception:
            raise ValueError('Invalid or unreadable private MFA key file') from None

    def encrypt(self, user_id: int, seed: str) -> str:
        if user_id <= 0 or not re.fullmatch(r'[A-Z2-7]{32}',seed):
            raise ValueError('Invalid MFA seed identity')
        return self._cipher.encrypt(f'{user_id}:{seed}'.encode('ascii')).decode('ascii')

    def decrypt(self, user_id: int, ciphertext: str) -> str:
        try:
            if not isinstance(ciphertext,str) or not 100 <= len(ciphertext) <= 512:
                raise ValueError()
            payload = self._cipher.decrypt(ciphertext).decode('ascii')
            account, seed = payload.split(':',1)
            if account != str(user_id) or not re.fullmatch(r'[A-Z2-7]{32}',seed):
                raise ValueError()
            return seed
        except Exception:
            raise ValueError('MFA seed cannot be authenticated for this account') from None

    def rotate(self, user_id: int, ciphertext: str) -> str:
        # Authenticate account binding before returning a newly encrypted token.
        self.decrypt(user_id,ciphertext)
        return self._cipher.rotate(ciphertext).decode('ascii')


def matching_step(seed: str, code: str, last_step: int, *, timestamp=None):
    """Return the matching unreplayed step, not merely an OTP library boolean.

    Persist last_step in the same locked transaction that grants the session.
    All three comparisons are performed, including when a replay is supplied.
    """
    if not re.fullmatch(r'[0-9]{6}',code):
        return None
    current = int(time.time() if timestamp is None else timestamp)//30
    otp = pyotp.TOTP(seed,digits=6,interval=30)
    matches=[]
    for step in (current-1,current,current+1):
        if step >= 0 and secrets.compare_digest(otp.at(step*30),code) and step > last_step:
            matches.append(step)
    return max(matches) if matches else None
