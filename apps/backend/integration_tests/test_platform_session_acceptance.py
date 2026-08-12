from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import event, select, text

from app.adapters.postgres.database import create_database_engine, create_session_factory
from app.adapters.postgres.orm import AuditEventRow, PlatformSessionRow, UserRow
from app.adapters.postgres.readiness import SqlAlchemyPlatformReadiness
from app.adapters.postgres.unit_of_work import SqlAlchemyPlatformUnitOfWork
from app.adapters.security import PwdlibPasswordHasher
from app.platform.models import Role, User
from app.platform.persistence import MigrationRequired, PlatformReadiness
from app.platform.security import PasswordVerification, digest_session_token
from app.platform.sessions import AuditPersistenceFailure, InvalidSession, SessionService
from app.platform.throttle import LoginThrottle


class Ready:
    async def check(self) -> PlatformReadiness:
        return PlatformReadiness.READY


def _service(
    session_factory,
    *,
    now: datetime,
    token: str = "raw-secret-never-store",
    password_hasher=None,
):
    return SessionService(
        readiness=Ready(),
        uow_factory=lambda: SqlAlchemyPlatformUnitOfWork(session_factory),
        password_hasher=password_hasher or PwdlibPasswordHasher(),
        throttle=LoginThrottle(),
        session_ttl=timedelta(hours=1),
        clock=lambda: now,
        uuid_factory=lambda: str(uuid4()),
        token_factory=lambda: token,
    )


async def _add_user(session_factory, *, password: str, disabled_at=None) -> User:
    now = datetime.now(UTC)
    user = User(
        id=str(uuid4()),
        username_norm=f"operator-{uuid4().hex}",
        display_name="Operator",
        password_hash=PwdlibPasswordHasher().hash(password),
        role=Role.OPERATOR,
        disabled_at=disabled_at,
        created_at=now,
        updated_at=now,
    )
    async with SqlAlchemyPlatformUnitOfWork(session_factory) as uow:
        await uow.users.add(user)
        await uow.commit()
    return user


async def test_login_persists_digest_and_audit_atomically_without_raw_secret(
    migrated_database_url: str,
) -> None:
    engine = create_database_engine(migrated_database_url)
    factory = create_session_factory(engine)
    raw_password = "acceptance-password"
    raw_token = "acceptance-raw-session-secret"
    captured_parameters: list[str] = []

    def capture_parameters(connection, cursor, statement, parameters, context, many) -> None:
        captured_parameters.append(repr(parameters))

    event.listen(engine.sync_engine, "before_cursor_execute", capture_parameters)
    try:
        user = await _add_user(factory, password=raw_password)
        issued = await _service(factory, now=datetime.now(UTC), token=raw_token).login(
            user.username_norm, raw_password, "127.0.0.1"
        )
        async with factory() as session:
            stored_session = (
                await session.execute(select(PlatformSessionRow))
            ).scalar_one()
            audit = (await session.execute(select(AuditEventRow))).scalar_one()
            rendered = repr((stored_session.__dict__, audit.parameters))
        assert issued.token == raw_token
        assert stored_session.token_digest == digest_session_token(raw_token)
        assert audit.action == "auth.login"
        assert audit.actor_platform_session_id == stored_session.id
        assert raw_token not in rendered
        assert raw_password not in rendered
        assert raw_token not in "".join(captured_parameters)
        assert raw_password not in "".join(captured_parameters)
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", capture_parameters)
        await engine.dispose()


async def test_audit_append_failure_rolls_back_login_session(
    migrated_database_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    engine = create_database_engine(migrated_database_url)
    factory = create_session_factory(engine)
    try:
        user = await _add_user(factory, password="acceptance-password")

        async def reject_append(self, event) -> bool:
            return False

        monkeypatch.setattr(
            "app.adapters.postgres.repositories.SqlAlchemyAuditEventRepository.append",
            reject_append,
        )
        with pytest.raises(AuditPersistenceFailure):
            await _service(factory, now=datetime.now(UTC)).login(
                user.username_norm, "acceptance-password", "127.0.0.1"
            )
        async with factory() as session:
            assert (await session.execute(select(PlatformSessionRow))).scalars().all() == []
    finally:
        await engine.dispose()


async def test_resolve_logout_expiry_and_disabled_user_use_current_database_facts(
    migrated_database_url: str,
) -> None:
    engine = create_database_engine(migrated_database_url)
    factory = create_session_factory(engine)
    now = datetime.now(UTC)
    try:
        user = await _add_user(factory, password="acceptance-password")
        service = _service(factory, now=now)
        issued = await service.login(user.username_norm, "acceptance-password", "client")
        assert (await service.resolve(issued.token)).principal.user_id == user.id
        assert await service.logout(issued.token) is True
        with pytest.raises(InvalidSession):
            await service.resolve(issued.token)

        issued_disabled = await _service(factory, now=now, token="disabled-secret").login(
            user.username_norm, "acceptance-password", "other-client"
        )
        async with factory.begin() as session:
            await session.execute(
                UserRow.__table__.update()
                .where(UserRow.id == user.id)
                .values(disabled_at=now)
            )
        with pytest.raises(InvalidSession):
            await service.resolve(issued_disabled.token)

        async with factory.begin() as session:
            await session.execute(
                UserRow.__table__.update()
                .where(UserRow.id == user.id)
                .values(disabled_at=None)
            )
        issued_expired = await _service(factory, now=now, token="expired-secret").login(
            user.username_norm, "acceptance-password", "third-client"
        )
        async with factory.begin() as session:
            await session.execute(
                PlatformSessionRow.__table__.update()
                .where(
                    PlatformSessionRow.token_digest
                    == digest_session_token(issued_expired.token)
                )
                .values(
                    created_at=now - timedelta(hours=2),
                    expires_at=now - timedelta(seconds=1),
                )
            )
        with pytest.raises(InvalidSession):
            await service.resolve(issued_expired.token)
    finally:
        await engine.dispose()


async def test_password_rehash_is_persisted(migrated_database_url: str) -> None:
    class RehashingPasswordHasher:
        def verify_and_update(self, password: str, stored_hash: str) -> PasswordVerification:
            return PasswordVerification(verified=True, updated_hash="replacement-hash")

        def dummy_verify(self, password: str) -> None:
            return None

    engine = create_database_engine(migrated_database_url)
    factory = create_session_factory(engine)
    try:
        user = await _add_user(factory, password="acceptance-password")
        await _service(
            factory,
            now=datetime.now(UTC),
            password_hasher=RehashingPasswordHasher(),
        ).login(user.username_norm, "acceptance-password", "client")
        async with factory() as session:
            row = (await session.execute(select(UserRow).where(UserRow.id == user.id))).scalar_one()
        assert row.password_hash == "replacement-hash"
    finally:
        await engine.dispose()


async def test_readiness_detects_missing_and_mismatched_heads(
    migrated_database_url: str,
) -> None:
    engine = create_database_engine(migrated_database_url)
    try:
        async with engine.begin() as connection:
            current = (
                await connection.execute(text("SELECT version_num FROM alembic_version"))
            ).scalar_one()
        readiness = SqlAlchemyPlatformReadiness(migrated_database_url, engine=engine)
        try:
            async with engine.begin() as connection:
                await connection.execute(text("DELETE FROM alembic_version"))
            with pytest.raises(MigrationRequired):
                await readiness.check()
            async with engine.begin() as connection:
                await connection.execute(
                    text("INSERT INTO alembic_version(version_num) VALUES ('stale-head')")
                )
            with pytest.raises(MigrationRequired):
                await readiness.check()
        finally:
            async with engine.begin() as connection:
                await connection.execute(text("DELETE FROM alembic_version"))
                await connection.execute(
                    text("INSERT INTO alembic_version(version_num) VALUES (:head)"),
                    {"head": current},
                )
    finally:
        await engine.dispose()
