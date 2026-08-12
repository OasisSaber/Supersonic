from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from typing import Protocol


class CredentialStoreError(RuntimeError):
    """A stored password hash cannot be safely interpreted."""

    def __init__(self) -> None:
        super().__init__("Credential store contains an invalid password hash.")


@dataclass(frozen=True, slots=True)
class PasswordVerification:
    verified: bool
    updated_hash: str | None = None


class PasswordHasher(Protocol):
    def hash(self, password: str) -> str: ...

    def verify_and_update(self, password: str, stored_hash: str) -> PasswordVerification: ...

    def dummy_verify(self, password: str) -> None: ...


class ExactOriginPolicy:
    def __init__(self, allowed_origin: str) -> None:
        self._allowed_origin = allowed_origin

    def allows(self, origin: str | None) -> bool:
        return origin == self._allowed_origin


def issue_session_token() -> str:
    return secrets.token_urlsafe(32)


def digest_session_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
