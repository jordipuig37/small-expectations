"""Typing primitives used across small-expectations."""

from __future__ import annotations

from typing import Protocol, Sequence


class CursorProtocol(Protocol):
    """Minimal DB-API cursor surface required by the runner."""

    def execute(self, query: str) -> object:
        """Execute a SQL statement."""

    def fetchone(self) -> Sequence[object] | None:
        """Fetch one row from the previous statement result."""

    @property
    def description(self) -> Sequence[Sequence[object]] | None:
        """Optional DB-API column metadata for the active result set."""


class ConnectionProtocol(Protocol):
    """Minimal DB-API connection surface required by the runner."""

    def cursor(self) -> CursorProtocol:
        """Create and return a new cursor object."""

    def close(self) -> None:
        """Close the underlying connection resources."""
