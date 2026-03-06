"""Typing primitives used across small-expectations."""

from __future__ import annotations

from typing import Protocol


class CursorProtocol(Protocol):
    """Minimal DB-API cursor surface required by the runner."""

    def execute(self, query: str) -> object:
        """Execute a SQL statement."""

    def fetchone(self) -> object | None:
        """Fetch one row from the previous statement result."""


class ConnectionProtocol(Protocol):
    """Minimal DB-API connection surface required by the runner."""

    def cursor(self) -> CursorProtocol:
        """Create and return a new cursor object."""

    def close(self) -> None:
        """Close the underlying connection resources."""

