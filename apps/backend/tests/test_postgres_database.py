import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from app.adapters.postgres import database
from app.adapters.postgres.database import create_database_engine, create_session_factory


@pytest.mark.parametrize(
    "database_url",
    [
        "postgresql+asyncpg://user:password@db/supersonic",
        "postgresql://user:password@db/supersonic",
        "sqlite+aiosqlite:///supersonic.db",
    ],
)
def test_database_engine_rejects_non_psycopg_postgresql_urls(database_url: str) -> None:
    with pytest.raises(ValueError, match=r"postgresql\+psycopg"):
        create_database_engine(database_url)


async def test_database_engine_is_configured_without_connecting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_options: dict[str, object] = {}
    real_create_async_engine = database.create_async_engine

    def capture_create_async_engine(database_url: str, **options: object) -> AsyncEngine:
        captured_options.update(options)
        return real_create_async_engine(database_url, **options)

    monkeypatch.setattr(database, "create_async_engine", capture_create_async_engine)
    engine = create_database_engine(
        "postgresql+psycopg://user:password@127.0.0.1:1/supersonic_test",
        echo=True,
    )
    try:
        assert isinstance(engine, AsyncEngine)
        assert engine.url.drivername == "postgresql+psycopg"
        assert engine.echo is True
        assert captured_options == {"echo": True, "pool_pre_ping": True}
    finally:
        await engine.dispose()


async def test_session_factory_returns_distinct_sessions_without_connecting() -> None:
    engine = create_database_engine(
        "postgresql+psycopg://user:password@127.0.0.1:1/supersonic_test"
    )
    factory = create_session_factory(engine)

    first = factory()
    second = factory()
    try:
        assert first is not second
        assert first.bind is engine
        assert second.bind is engine
        assert factory.kw["expire_on_commit"] is False
        assert factory.kw["autoflush"] is False
    finally:
        await first.close()
        await second.close()
        await engine.dispose()


def test_database_module_has_no_global_engine_or_session_factory() -> None:
    assert not any(isinstance(value, AsyncEngine) for value in vars(database).values())
    assert not any(isinstance(value, async_sessionmaker) for value in vars(database).values())
