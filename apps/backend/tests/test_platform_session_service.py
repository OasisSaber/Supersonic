from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from types import TracebackType
from typing import Self

import pytest

import app.platform.sessions as sessions_module
from app.platform.models import AuditResult, PlatformSession, Role, User
from app.platform.persistence import DatabaseUnavailable, PlatformReadiness
from app.platform.security import CredentialStoreError, PasswordVerification, digest_session_token
from app.platform.sessions import (
    AuditPersistenceFailure,
    CredentialStoreInvalid,
    InvalidCredentials,
    InvalidSession,
    LoginThrottled,
    SessionService,
)
from app.platform.throttle import LoginThrottle

NOW = datetime(2026, 8, 12, 8, tzinfo=UTC)


class FakeUsers:
    def __init__(self, user: User | None) -> None:
        self.user = user
        self.lookups: list[str] = []
        self.updates: list[tuple[str, str, datetime]] = []

    async def get_by_username_norm(self, username_norm: str) -> User | None:
        self.lookups.append(username_norm)
        return self.user

    async def get_by_id(self, user_id: str) -> User | None:
        self.lookups.append(user_id)
        return self.user if self.user is not None and self.user.id == user_id else None

    async def update_password_hash(
        self, user_id: str, password_hash: str, updated_at: datetime
    ) -> bool:
        self.updates.append((user_id, password_hash, updated_at))
        return True


class FakeSessions:
    def __init__(self, calls: list[str], session: PlatformSession | None = None) -> None:
        self.calls = calls
        self.added: list[PlatformSession] = []
        self.session = session
        self.persisted_session = session
        self.pending_session: PlatformSession | None = None
        self.attempted_revokes: list[tuple[str, datetime, str | None]] = []
        self.staged_revokes: list[tuple[str, datetime, str | None]] = []
        self.persisted_revokes: list[tuple[str, datetime, str | None]] = []

    async def add(self, platform_session: PlatformSession) -> None:
        self.calls.append("session.add")
        self.added.append(platform_session)
        self.pending_session = platform_session

    async def get_by_token_digest(self, token_digest: str) -> PlatformSession | None:
        self.calls.append("session.get_by_token_digest")
        return self.session if self.session and self.session.token_digest == token_digest else None

    async def get_by_id(self, platform_session_id: str) -> PlatformSession | None:
        self.calls.append("session.get_by_id")
        return self.session if self.session and self.session.id == platform_session_id else None

    async def revoke(
        self, platform_session_id: str, revoked_at: datetime, reason: str | None
    ) -> bool:
        self.calls.append("session.revoke")
        revoke = (platform_session_id, revoked_at, reason)
        self.attempted_revokes.append(revoke)
        if (
            self.session is None
            or self.session.id != platform_session_id
            or self.session.revoked_at
        ):
            return False
        self.pending_session = replace(self.session, revoked_at=revoked_at, revoke_reason=reason)
        self.staged_revokes.append(revoke)
        return True

    def commit(self) -> None:
        if self.pending_session is not None:
            self.session = self.persisted_session = self.pending_session
        self.persisted_revokes.extend(self.staged_revokes)
        self.pending_session = None
        self.staged_revokes.clear()

    def rollback(self) -> None:
        self.pending_session = None
        self.staged_revokes.clear()


class FakeAudits:
    def __init__(self, calls: list[str], *, inserted: bool = True) -> None:
        self.calls = calls
        self.inserted = inserted
        self.attempted_events: list[object] = []
        self.staged_events: list[object] = []
        self.persisted_events: list[object] = []

    async def append(self, event: object) -> bool:
        self.calls.append("audit.append")
        self.attempted_events.append(event)
        if self.inserted:
            self.staged_events.append(event)
        return self.inserted

    def commit(self) -> None:
        self.persisted_events.extend(self.staged_events)
        self.staged_events.clear()

    def rollback(self) -> None:
        self.staged_events.clear()


class FakeUow:
    def __init__(
        self,
        user: User | None,
        *,
        session: PlatformSession | None = None,
        audit_inserted: bool = True,
        commit_error: Exception | None = None,
    ) -> None:
        self.calls: list[str] = []
        self.users = FakeUsers(user)
        self.platform_sessions = FakeSessions(self.calls, session)
        self.audit_events = FakeAudits(self.calls, inserted=audit_inserted)
        self.commit_error = commit_error
        self.committed = False

    async def __aenter__(self) -> Self:
        self.calls.append("enter")
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if exc_type is not None and not self.committed:
            self.platform_sessions.rollback()
            self.audit_events.rollback()
        self.calls.append("exit")

    async def commit(self) -> None:
        self.calls.append("commit")
        if self.commit_error:
            raise self.commit_error
        self.platform_sessions.commit()
        self.audit_events.commit()
        self.committed = True

    async def rollback(self) -> None:
        self.calls.append("rollback")
        self.platform_sessions.rollback()
        self.audit_events.rollback()


class FakeReadiness:
    def __init__(self) -> None:
        self.calls = 0
        self.error: Exception | None = None

    async def check(self) -> PlatformReadiness:
        self.calls += 1
        if self.error:
            raise self.error
        return PlatformReadiness.READY


class FakeHasher:
    def __init__(self, result: PasswordVerification | None = None) -> None:
        self.result = result or PasswordVerification(True)
        self.verified: list[tuple[str, str]] = []
        self.dummy: list[str] = []
        self.error: Exception | None = None

    def verify_and_update(self, password: str, stored_hash: str) -> PasswordVerification:
        self.verified.append((password, stored_hash))
        if self.error:
            raise self.error
        return self.result

    def dummy_verify(self, password: str) -> None:
        self.dummy.append(password)


def user(*, disabled: bool = False) -> User:
    return User(
        "user-1",
        "alice",
        "Alice",
        "stored-hash",
        Role.OPERATOR,
        NOW if disabled else None,
        NOW,
        NOW,
    )


async def no_failure_delay() -> None:
    return None


def service(
    uow: FakeUow,
    hasher: FakeHasher,
    readiness: FakeReadiness,
    throttle: LoginThrottle | None = None,
    failure_delay: Callable[[], Awaitable[None]] = no_failure_delay,
) -> SessionService:
    return SessionService(
        readiness=readiness,
        uow_factory=lambda: uow,
        password_hasher=hasher,
        throttle=throttle or LoginThrottle(),
        session_ttl=timedelta(hours=8),
        clock=lambda: NOW,
        uuid_factory=lambda: "11111111-1111-4111-8111-111111111111",
        token_factory=lambda: "raw-session-secret",
        failure_delay=failure_delay,
    )


def active_session(*, expired: bool = False, revoked: bool = False) -> PlatformSession:
    return PlatformSession(
        id="session-1",
        user_id="user-1",
        token_digest=digest_session_token("raw-session-secret"),
        created_at=NOW - timedelta(hours=1),
        expires_at=NOW - timedelta(seconds=1) if expired else NOW + timedelta(hours=1),
        revoked_at=NOW if revoked else None,
    )


async def test_login_commits_session_digest_and_sanitized_audit_before_returning_secret() -> None:
    uow = FakeUow(user())
    readiness = FakeReadiness()
    result = await service(uow, FakeHasher(), readiness).login("  ALICE ", "correct", "client-a")

    assert readiness.calls == 1
    assert uow.users.lookups == ["alice"]
    assert uow.calls == ["enter", "session.add", "audit.append", "commit", "exit"]
    assert result.token == "raw-session-secret"
    assert result.user_id == "user-1"
    assert result.role is Role.OPERATOR
    stored = uow.platform_sessions.added[0]
    assert stored.token_digest == digest_session_token(result.token)
    assert stored.expires_at == NOW + timedelta(hours=8)
    event = uow.audit_events.persisted_events[0]
    assert event.action == "auth.login"
    assert event.result is AuditResult.SUCCEEDED
    assert event.parameters == {}
    assert "raw-session-secret" not in repr(event)


@pytest.mark.parametrize("stored_user", [None, user(disabled=True)])
async def test_unknown_and_disabled_users_use_generic_rejection_with_empty_actor(
    stored_user: User | None,
) -> None:
    uow = FakeUow(stored_user)
    hasher = FakeHasher(PasswordVerification(False))
    with pytest.raises(InvalidCredentials, match="Invalid username or password"):
        await service(uow, hasher, FakeReadiness()).login("Alice", "bad-password", "client")

    assert bool(hasher.dummy) is (stored_user is None)
    event = uow.audit_events.persisted_events[0]
    assert event.result is AuditResult.REJECTED
    assert event.actor_user_id is None and event.actor_role is None
    assert event.parameters == {}
    assert all(secret not in repr(event) for secret in ("Alice", "bad-password", "stored-hash"))
    assert uow.calls[-2:] == ["commit", "exit"]


@pytest.mark.parametrize(
    ("stored_user", "verification"),
    [
        (None, PasswordVerification(False)),
        (user(), PasswordVerification(False)),
        (user(disabled=True), PasswordVerification(True)),
    ],
)
async def test_credential_rejections_delay_once_after_audited_transaction(
    stored_user: User | None,
    verification: PasswordVerification,
) -> None:
    uow = FakeUow(stored_user)
    observed_delay_states: list[tuple[str, ...]] = []

    async def record_delay() -> None:
        observed_delay_states.append(tuple(uow.calls))

    with pytest.raises(InvalidCredentials):
        await service(
            uow,
            FakeHasher(verification),
            FakeReadiness(),
            failure_delay=record_delay,
        ).login("alice", "bad-password", "client")

    assert observed_delay_states == [("enter", "audit.append", "commit", "exit")]


async def test_default_credential_rejection_delay_is_250_ms_after_audited_transaction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    uow = FakeUow(None)
    observed_sleep_calls: list[tuple[float, tuple[str, ...]]] = []

    async def capture_sleep(seconds: float) -> None:
        observed_sleep_calls.append((seconds, tuple(uow.calls)))

    monkeypatch.setattr(sessions_module.asyncio, "sleep", capture_sleep)
    subject = SessionService(
        readiness=FakeReadiness(),
        uow_factory=lambda: uow,
        password_hasher=FakeHasher(PasswordVerification(False)),
        throttle=LoginThrottle(),
        session_ttl=timedelta(hours=8),
        clock=lambda: NOW,
        uuid_factory=lambda: "11111111-1111-4111-8111-111111111111",
        token_factory=lambda: "raw-session-secret",
    )

    with pytest.raises(InvalidCredentials):
        await subject.login("alice", "bad-password", "client")

    assert observed_sleep_calls == [(0.25, ("enter", "audit.append", "commit", "exit"))]


async def test_wrong_password_rehashes_only_on_verified_success() -> None:
    rejected_uow = FakeUow(user())
    with pytest.raises(InvalidCredentials):
        await service(
            rejected_uow, FakeHasher(PasswordVerification(False, "must-ignore")), FakeReadiness()
        ).login("alice", "bad", "client")
    assert rejected_uow.users.updates == []

    accepted_uow = FakeUow(user())
    await service(
        accepted_uow, FakeHasher(PasswordVerification(True, "new-hash")), FakeReadiness()
    ).login("alice", "good", "client")
    assert accepted_uow.users.updates == [("user-1", "new-hash", NOW)]


async def test_malformed_hash_maps_to_typed_store_failure_without_secrets() -> None:
    hasher = FakeHasher()
    hasher.error = CredentialStoreError()
    delay_calls: list[tuple[str, ...]] = []

    async def record_delay() -> None:
        delay_calls.append(())

    with pytest.raises(CredentialStoreInvalid) as caught:
        await service(
            FakeUow(user()), hasher, FakeReadiness(), failure_delay=record_delay
        ).login("alice", "secret", "client")
    assert "secret" not in str(caught.value)
    assert delay_calls == []


@pytest.mark.parametrize(
    "audit_inserted, commit_error", [(False, None), (True, DatabaseUnavailable())]
)
async def test_audit_or_commit_failure_returns_no_issued_session(
    audit_inserted: bool, commit_error: Exception | None
) -> None:
    uow = FakeUow(user(), audit_inserted=audit_inserted, commit_error=commit_error)
    expected = DatabaseUnavailable if commit_error else AuditPersistenceFailure
    with pytest.raises(expected):
        await service(uow, FakeHasher(), FakeReadiness()).login("alice", "good", "client")
    assert uow.platform_sessions.persisted_session is None
    assert uow.audit_events.persisted_events == []


async def test_login_readiness_failure_does_not_open_a_uow() -> None:
    uow = FakeUow(user())
    readiness = FakeReadiness()
    readiness.error = DatabaseUnavailable()
    delay_calls: list[tuple[str, ...]] = []

    async def record_delay() -> None:
        delay_calls.append(())

    subject = service(uow, FakeHasher(), readiness, failure_delay=record_delay)
    factory_calls = 0

    def factory() -> FakeUow:
        nonlocal factory_calls
        factory_calls += 1
        return uow

    subject._uow_factory = factory  # type: ignore[assignment]
    with pytest.raises(DatabaseUnavailable):
        await subject.login("alice", "good", "client")
    assert factory_calls == 0
    assert uow.calls == []
    assert delay_calls == []


@pytest.mark.parametrize("stored_user", [None, user()])
@pytest.mark.parametrize(
    "audit_inserted, commit_error", [(False, None), (True, DatabaseUnavailable())]
)
async def test_rejected_login_audit_failures_are_truthful_and_not_persisted(
    stored_user: User | None, audit_inserted: bool, commit_error: Exception | None
) -> None:
    uow = FakeUow(stored_user, audit_inserted=audit_inserted, commit_error=commit_error)
    hasher = FakeHasher(PasswordVerification(False))
    delay_calls: list[tuple[str, ...]] = []

    async def record_delay() -> None:
        delay_calls.append(())

    expected = DatabaseUnavailable if commit_error else AuditPersistenceFailure
    with pytest.raises(expected):
        await service(uow, hasher, FakeReadiness(), failure_delay=record_delay).login(
            "unknown", "bad", "client"
        )
    assert uow.audit_events.persisted_events == []
    assert uow.platform_sessions.persisted_session is None
    assert delay_calls == []


async def test_throttle_blocks_before_readiness_and_resets_after_success() -> None:
    throttle = LoginThrottle(max_failures=1)
    throttle.record_failure("alice", "client")
    readiness = FakeReadiness()
    delay_calls: list[tuple[str, ...]] = []

    async def record_delay() -> None:
        delay_calls.append(())

    with pytest.raises(LoginThrottled) as caught:
        await service(
            FakeUow(user()),
            FakeHasher(),
            readiness,
            throttle,
            failure_delay=record_delay,
        ).login(" ALICE ", "secret", "client")
    assert caught.value.retry_after == 30
    assert readiness.calls == 0

    fresh = LoginThrottle(max_failures=2)
    fresh.record_failure("alice", "client")
    await service(
        FakeUow(user()),
        FakeHasher(),
        FakeReadiness(),
        fresh,
        failure_delay=record_delay,
    ).login("alice", "good", "client")
    assert fresh.entry_count == 0
    assert delay_calls == []


async def test_resolve_uses_current_server_identity_without_writes() -> None:
    current = user()
    uow = FakeUow(current, session=active_session())

    identity = await service(uow, FakeHasher(), FakeReadiness()).resolve("raw-session-secret")

    assert identity.principal.user_id == current.id
    assert identity.principal.role is current.role
    assert identity.principal.session_id == "session-1"
    assert identity.display_name == current.display_name
    assert identity.expires_at == active_session().expires_at
    assert uow.calls == ["enter", "session.get_by_token_digest", "exit"]
    assert uow.users.lookups == ["user-1"]
    assert uow.platform_sessions.persisted_revokes == []


@pytest.mark.parametrize(
    "stored_user, stored_session",
    [
        (None, active_session()),
        (user(disabled=True), active_session()),
        (user(), active_session(expired=True)),
        (user(), active_session(revoked=True)),
        (user(), None),
    ],
)
async def test_resolve_rejects_invalid_current_session_facts(
    stored_user: User | None, stored_session: PlatformSession | None
) -> None:
    uow = FakeUow(stored_user, session=stored_session)
    with pytest.raises(InvalidSession) as caught:
        await service(uow, FakeHasher(), FakeReadiness()).resolve("raw-session-secret")

    assert caught.value.status_code == 401
    assert "raw-session-secret" not in str(caught.value)
    assert uow.platform_sessions.persisted_revokes == []
    assert "commit" not in uow.calls


async def test_logout_revokes_then_audits_without_secret_and_commits_before_success() -> None:
    uow = FakeUow(user(), session=active_session())

    assert await service(uow, FakeHasher(), FakeReadiness()).logout("raw-session-secret") is True

    assert uow.platform_sessions.persisted_revokes == [("session-1", NOW, "logout")]
    event = uow.audit_events.persisted_events[0]
    assert event.action == "auth.logout"
    assert event.result is AuditResult.SUCCEEDED
    assert event.actor_user_id == "user-1"
    assert event.actor_role is Role.OPERATOR
    assert event.actor_platform_session_id == "session-1"
    assert event.parameters == {}
    assert "raw-session-secret" not in repr(event)
    assert uow.calls == [
        "enter",
        "session.get_by_token_digest",
        "session.revoke",
        "audit.append",
        "commit",
        "exit",
    ]


async def test_logout_commit_failure_does_not_report_success() -> None:
    uow = FakeUow(user(), session=active_session(), commit_error=DatabaseUnavailable())
    with pytest.raises(DatabaseUnavailable):
        await service(uow, FakeHasher(), FakeReadiness()).logout("raw-session-secret")
    assert uow.platform_sessions.persisted_session is not None
    assert uow.platform_sessions.persisted_session.revoked_at is None
    assert uow.platform_sessions.persisted_revokes == []
    event = uow.audit_events.attempted_events[0]
    assert event.action == "auth.logout"
    assert event.result is AuditResult.SUCCEEDED
    assert event.actor_user_id == "user-1"
    assert event.actor_role is Role.OPERATOR
    assert event.actor_platform_session_id == "session-1"
    assert event.parameters == {}
    assert "raw-session-secret" not in repr(event)
    assert uow.audit_events.persisted_events == []


async def test_logout_audit_failure_does_not_persist_revoke() -> None:
    uow = FakeUow(user(), session=active_session(), audit_inserted=False)
    with pytest.raises(AuditPersistenceFailure):
        await service(uow, FakeHasher(), FakeReadiness()).logout("raw-session-secret")
    assert uow.platform_sessions.persisted_session is not None
    assert uow.platform_sessions.persisted_session.revoked_at is None
    assert uow.platform_sessions.persisted_revokes == []
    event = uow.audit_events.attempted_events[0]
    assert event.action == "auth.logout"
    assert event.result is AuditResult.SUCCEEDED
    assert event.actor_user_id == "user-1"
    assert event.actor_role is Role.OPERATOR
    assert event.actor_platform_session_id == "session-1"
    assert event.parameters == {}
    assert "raw-session-secret" not in repr(event)
    assert uow.audit_events.persisted_events == []


async def test_internal_revoke_uses_current_actor_and_audits_after_commit() -> None:
    uow = FakeUow(user(), session=active_session())
    assert await service(uow, FakeHasher(), FakeReadiness()).revoke("session-1", "operator_request")
    event = uow.audit_events.persisted_events[0]
    assert event.action == "session.revoke"
    assert event.result is AuditResult.SUCCEEDED
    assert event.actor_user_id == "user-1"
    assert event.actor_platform_session_id == "session-1"
    assert event.actor_role is Role.OPERATOR
    assert event.parameters == {}
    assert uow.platform_sessions.persisted_session is not None
    assert uow.platform_sessions.persisted_session.revoke_reason == "operator_request"
    assert uow.platform_sessions.persisted_revokes == [
        ("session-1", NOW, "operator_request")
    ]


@pytest.mark.parametrize(
    "audit_inserted, commit_error", [(False, None), (True, DatabaseUnavailable())]
)
async def test_internal_revoke_failure_does_not_persist_revoke_or_event(
    audit_inserted: bool, commit_error: Exception | None
) -> None:
    uow = FakeUow(
        user(),
        session=active_session(),
        audit_inserted=audit_inserted,
        commit_error=commit_error,
    )
    expected = DatabaseUnavailable if commit_error else AuditPersistenceFailure
    with pytest.raises(expected):
        await service(uow, FakeHasher(), FakeReadiness()).revoke("session-1", "operator_request")
    assert uow.platform_sessions.persisted_session is not None
    assert uow.platform_sessions.persisted_session.revoked_at is None
    assert uow.platform_sessions.persisted_revokes == []
    event = uow.audit_events.attempted_events[0]
    assert event.action == "session.revoke"
    assert event.result is AuditResult.SUCCEEDED
    assert event.actor_user_id == "user-1"
    assert event.actor_platform_session_id == "session-1"
    assert event.actor_role is Role.OPERATOR
    assert event.parameters == {}
    assert uow.audit_events.persisted_events == []


@pytest.mark.parametrize("reason", ["", "   ", "x" * 65])
async def test_internal_revoke_rejects_blank_or_oversized_reason_before_uow(reason: str) -> None:
    uow = FakeUow(user(), session=active_session())
    with pytest.raises(ValueError, match="revoke reason"):
        await service(uow, FakeHasher(), FakeReadiness()).revoke("session-1", reason)
    assert uow.calls == []


async def test_internal_revoke_requires_current_enabled_user() -> None:
    uow = FakeUow(user(disabled=True), session=active_session())
    with pytest.raises(InvalidSession):
        await service(uow, FakeHasher(), FakeReadiness()).revoke("session-1", "operator_request")
    assert uow.platform_sessions.persisted_session is not None
    assert uow.platform_sessions.persisted_session.revoked_at is None


async def test_login_rejects_naive_clock_before_uow() -> None:
    uow = FakeUow(user())
    subject = service(uow, FakeHasher(), FakeReadiness())
    subject._clock = lambda: NOW.replace(tzinfo=None)  # type: ignore[method-assign]
    with pytest.raises(ValueError, match="aware UTC"):
        await subject.login("alice", "good", "client")
    assert uow.calls == []


async def test_repeated_logout_is_invalid_and_internal_revoke_is_idempotent() -> None:
    logout_uow = FakeUow(user(), session=active_session(revoked=True))
    with pytest.raises(InvalidSession):
        await service(logout_uow, FakeHasher(), FakeReadiness()).logout("raw-session-secret")

    revoke_uow = FakeUow(user(), session=active_session(revoked=True))
    result = await service(revoke_uow, FakeHasher(), FakeReadiness()).revoke(
        "session-1", "operator_request"
    )
    assert result is False
    assert revoke_uow.platform_sessions.persisted_revokes == []
    assert revoke_uow.audit_events.attempted_events == []
    assert "commit" not in revoke_uow.calls
