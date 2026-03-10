"""Snowflake backend implementation."""

from __future__ import annotations

from contextlib import closing
from typing import ClassVar
from typing import Mapping

from smallex.backends.base import BaseDatabaseBackend
from smallex.types import ConnectionProtocol, CursorProtocol


class SnowflakeBackend(BaseDatabaseBackend):
    """Backend for Snowflake using ``snowflake-connector-python``.

    Expected connection options for password auth (default):
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

    def prepare_connection_options(self, options: Mapping[str, object]) -> dict[str, object]:
        """Map normalized auth mode values to Snowflake connector options."""

        prepared = dict(options)
        auth_mode = prepared.pop("auth_mode", None)
        if auth_mode is not None and auth_mode != "password":
            raise ValueError(
                "Unsupported auth_mode for snowflake. Supported: password"
            )
        return prepared

    def validate_connection_options(self, options: Mapping[str, object]) -> None:
        """Validate Snowflake fields according to selected auth mode."""

        missing = [
            name for name in self.required_connection_fields if not options.get(name)
        ]
        if missing:
            missing_fields = ", ".join(missing)
            raise ValueError(
                f"Backend '{self.engine_name}' is missing required connection fields: "
                f"{missing_fields}"
            )

    def test_connection(
        self,
        connection: ConnectionProtocol,
        options: Mapping[str, object],
    ) -> None:
        """Verify Snowflake-specific connection details after connecting."""

        super().test_connection(connection, options)
        with closing(connection.cursor()) as cursor:
            self._validate_session(cursor, options)

    def _validate_session(self, cursor: CursorProtocol, options: Mapping[str, object]) -> None:
        """Run USE statements for configured database, schema, warehouse, and role."""

        for key, statement in (
            ("warehouse", "USE WAREHOUSE"),
            ("database", "USE DATABASE"),
            ("schema", "USE SCHEMA"),
            ("role", "USE ROLE"),
        ):
            value = options.get(key)
            identifier = self._normalize_identifier(value)
            if identifier is None:
                continue
            cursor.execute(f"{statement} {identifier}")

    @staticmethod
    def _normalize_identifier(value: object | None) -> str | None:
        """Ensure identifier is a non-empty string wrapped in quotes."""

        if value is None:
            return None
        as_str = str(value).strip()
        if not as_str:
            return None
        escaped = as_str.replace('"', '""')
        return f'"{escaped}"'
