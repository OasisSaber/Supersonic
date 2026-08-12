from __future__ import annotations

from pwdlib import PasswordHash
from pwdlib.exceptions import PwdlibError

from ..platform.security import CredentialStoreError, PasswordVerification


class PwdlibPasswordHasher:
    def __init__(self) -> None:
        self._hasher = PasswordHash.recommended()
        self._dummy_hash = self._hasher.hash("supersonic-platform-dummy-password")

    def hash(self, password: str) -> str:
        return self._hasher.hash(password)

    def verify_and_update(self, password: str, stored_hash: str) -> PasswordVerification:
        try:
            verified, updated_hash = self._hasher.verify_and_update(password, stored_hash)
        except PwdlibError:
            raise CredentialStoreError() from None
        return PasswordVerification(verified=verified, updated_hash=updated_hash)

    def dummy_verify(self, password: str) -> None:
        self._hasher.verify(password, self._dummy_hash)
