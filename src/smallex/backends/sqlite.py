"""SQLite backend implementation."""

from __future__ import annotations

from typing import ClassVar

from smallex.backends.base import BaseDatabaseBackend


class SQLiteBackend(BaseDatabaseBackend):
    """Backend for local SQLite databases.

    Expected connection options:
        - ``database``: Path to SQLite database file.
    """

    engine_name: ClassVar[str] = "sqlite"
    module_path: ClassVar[str] = "sqlite3"
    connect_attr: ClassVar[str] = "connect"
    required_connection_fields: ClassVar[tuple[str, ...]] = ("database",)
