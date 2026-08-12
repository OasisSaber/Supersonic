from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


def create_database_engine(database_url: str, *, echo: bool = False) -> AsyncEngine:
    try:
        url = make_url(database_url)
    except ArgumentError as exc:
        raise ValueError("database URL must use postgresql+psycopg") from exc

    if url.drivername != "postgresql+psycopg":
        raise ValueError("database URL must use postgresql+psycopg")

    return create_async_engine(database_url, echo=echo, pool_pre_ping=True)


def create_session_factory(
    engine: AsyncEngine,
) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(
        bind=engine,
        autoflush=False,
        expire_on_commit=False,
    )
