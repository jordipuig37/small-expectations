"""Snowflake backend implementation."""

from __future__ import annotations

from typing import ClassVar

from smallex.backends.base import BaseDatabaseBackend


class SnowflakeBackend(BaseDatabaseBackend):
    """Backend for Snowflake using ``snowflake-connector-python``.

    Expected connection options:
        - ``account``
        - ``user``
        - ``password``
        - ``warehouse``
        - ``database``
        - ``schema``
    """

    engine_name: ClassVar[str] = "snowflake"
    module_path: ClassVar[str] = "snowflake.connector"
    connect_attr: ClassVar[str] = "connect"
    required_connection_fields: ClassVar[tuple[str, ...]] = (
        "account",
        "user",
        "password",
        "warehouse",
        "database",
        "schema",
    )
