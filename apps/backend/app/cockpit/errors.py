from __future__ import annotations


class CommandRejected(ValueError):
    """A domain-safe command failure that can be mapped to an HTTP response."""

    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
