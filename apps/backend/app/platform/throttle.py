from __future__ import annotations

from collections import OrderedDict, deque
from collections.abc import Callable
from dataclasses import dataclass
from math import ceil
from time import monotonic


@dataclass(frozen=True, slots=True)
class ThrottleDecision:
    allowed: bool
    retry_after: int | None = None


@dataclass(slots=True)
class _ThrottleEntry:
    failures: deque[float]
    locked_until: float | None = None


class LoginThrottle:
    def __init__(
        self,
        *,
        clock: Callable[[], float] = monotonic,
        max_failures: int = 5,
        failure_window_seconds: float = 60,
        lockout_seconds: float = 30,
        max_entries: int = 1024,
    ) -> None:
        if min(max_failures, failure_window_seconds, lockout_seconds, max_entries) <= 0:
            raise ValueError("Login throttle limits must be positive")
        self._clock = clock
        self._max_failures = max_failures
        self._failure_window_seconds = failure_window_seconds
        self._lockout_seconds = lockout_seconds
        self._max_entries = max_entries
        self._entries: OrderedDict[tuple[str, str], _ThrottleEntry] = OrderedDict()

    @property
    def entry_count(self) -> int:
        self._trim(self._clock())
        return len(self._entries)

    def check(self, username: str, remote_client_key: str) -> ThrottleDecision:
        now = self._clock()
        self._trim(now)
        key = self._key(username, remote_client_key)
        entry = self._entries.get(key)
        if entry is None:
            return ThrottleDecision(allowed=True)
        self._entries.move_to_end(key)
        if entry.locked_until is not None and entry.locked_until > now:
            return ThrottleDecision(allowed=False, retry_after=ceil(entry.locked_until - now))
        if entry.locked_until is not None:
            entry.locked_until = None
            entry.failures.clear()
        return ThrottleDecision(allowed=True)

    def record_failure(self, username: str, remote_client_key: str) -> None:
        now = self._clock()
        self._trim(now)
        key = self._key(username, remote_client_key)
        entry = self._entries.setdefault(key, _ThrottleEntry(deque()))
        self._entries.move_to_end(key)
        entry.failures.append(now)
        self._discard_expired_failures(entry, now)
        if len(entry.failures) >= self._max_failures:
            entry.locked_until = now + self._lockout_seconds
            entry.failures.clear()
        self._evict_lru()

    def record_success(self, username: str, remote_client_key: str) -> None:
        self._entries.pop(self._key(username, remote_client_key), None)

    def _trim(self, now: float) -> None:
        for key, entry in list(self._entries.items()):
            self._discard_expired_failures(entry, now)
            if entry.locked_until is not None and entry.locked_until <= now:
                entry.locked_until = None
            if not entry.failures and entry.locked_until is None:
                self._entries.pop(key)

    def _discard_expired_failures(self, entry: _ThrottleEntry, now: float) -> None:
        cutoff = now - self._failure_window_seconds
        while entry.failures and entry.failures[0] <= cutoff:
            entry.failures.popleft()

    def _evict_lru(self) -> None:
        while len(self._entries) > self._max_entries:
            self._entries.popitem(last=False)

    @staticmethod
    def _key(username: str, remote_client_key: str) -> tuple[str, str]:
        return username.strip().casefold(), remote_client_key
