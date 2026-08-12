from __future__ import annotations

from typing import cast

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.adapters.postgres.unit_of_work import SqlAlchemyPlatformUnitOfWork


class TransactionRecordingSession:
    """A DB-free Session boundary that records transaction-visible effects."""

    def __init__(self) -> None:
        self.committed_writes: list[str] = []
        self.pending_writes: list[str] = []
        self.rollback_count = 0
        self.closed = False

    def write(self, value: str) -> None:
        self.pending_writes.append(value)

    def in_transaction(self) -> bool:
        return bool(self.pending_writes)

    async def commit(self) -> None:
        self.committed_writes.extend(self.pending_writes)
        self.pending_writes.clear()

    async def rollback(self) -> None:
        self.rollback_count += 1
        self.pending_writes.clear()

    async def close(self) -> None:
        self.closed = True


def _unit_of_work_for(
    session: TransactionRecordingSession,
) -> SqlAlchemyPlatformUnitOfWork:
    factory = cast(async_sessionmaker[AsyncSession], lambda: session)
    return SqlAlchemyPlatformUnitOfWork(factory)


async def test_exit_rolls_back_an_uncommitted_write_and_closes_the_session() -> None:
    session = TransactionRecordingSession()

    async with _unit_of_work_for(session):
        session.write("uncommitted")

    assert session.committed_writes == []
    assert session.pending_writes == []
    assert session.rollback_count == 1
    assert session.closed is True


async def test_exit_rolls_back_a_write_started_after_an_explicit_commit() -> None:
    session = TransactionRecordingSession()

    async with _unit_of_work_for(session) as uow:
        session.write("A")
        await uow.commit()
        session.write("B")

    assert session.committed_writes == ["A"]
    assert session.pending_writes == []
    assert session.rollback_count == 1
    assert session.closed is True


async def test_exit_does_not_roll_back_a_committed_transaction_without_new_writes() -> None:
    session = TransactionRecordingSession()

    async with _unit_of_work_for(session) as uow:
        session.write("committed")
        await uow.commit()

    assert session.committed_writes == ["committed"]
    assert session.rollback_count == 0
    assert session.closed is True


async def test_exit_rolls_back_on_exception_and_closes_the_session() -> None:
    session = TransactionRecordingSession()

    with pytest.raises(RuntimeError, match="abort transaction"):
        async with _unit_of_work_for(session):
            session.write("aborted")
            raise RuntimeError("abort transaction")

    assert session.committed_writes == []
    assert session.pending_writes == []
    assert session.rollback_count == 1
    assert session.closed is True


async def test_explicit_rollback_leaves_no_pending_or_committed_write() -> None:
    session = TransactionRecordingSession()

    async with _unit_of_work_for(session) as uow:
        session.write("rolled-back")
        await uow.rollback()

    assert session.committed_writes == []
    assert session.pending_writes == []
    assert session.closed is True


async def test_distinct_unit_of_works_receive_distinct_sessions() -> None:
    first_session = TransactionRecordingSession()
    second_session = TransactionRecordingSession()
    sessions = iter((first_session, second_session))
    factory = cast(async_sessionmaker[AsyncSession], lambda: next(sessions))

    first = SqlAlchemyPlatformUnitOfWork(factory)
    second = SqlAlchemyPlatformUnitOfWork(factory)

    async with first, second:
        assert first._session is first_session
        assert second._session is second_session
        assert first._session is not second._session
