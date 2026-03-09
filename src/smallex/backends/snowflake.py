"""Snowflake backend implementation."""

from __future__ import annotations

from typing import ClassVar
from typing import Mapping

from smallex.backends.base import BaseDatabaseBackend


class SnowflakeBackend(BaseDatabaseBackend):
    """Backend for Snowflake using ``snowflake-connector-python``.

    Expected connection options for password auth (default):
        - ``account``
        - ``user``
        - ``password``
        - ``warehouse``
        - ``database``
        - ``schema``

    Expected connection options for browser auth:
        - ``auth_mode = "browser"``
        - ``account``
        - ``user``
        - ``warehouse``
        - ``database``
        - ``schema``

    The backend maps ``auth_mode = "browser"`` to Snowflake connector
    option ``authenticator = "externalbrowser"``.
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

    browser_required_connection_fields: ClassVar[tuple[str, ...]] = (
        "account",
        "user",
        "warehouse",
        "database",
        "schema",
    )

    def prepare_connection_options(self, options: Mapping[str, object]) -> dict[str, object]:
        """Map normalized auth mode values to Snowflake connector options."""

        prepared = dict(options)
        auth_mode = prepared.pop("auth_mode", None)
        if auth_mode == "browser":
            prepared["authenticator"] = "externalbrowser"
        elif auth_mode is not None and auth_mode != "password":
            raise ValueError(
                "Unsupported auth_mode for snowflake. Supported: browser, password"
            )
        return prepared

    def validate_connection_options(self, options: Mapping[str, object]) -> None:
        """Validate Snowflake fields according to selected auth mode."""

        required = (
            self.browser_required_connection_fields
            if options.get("authenticator") == "externalbrowser"
            else self.required_connection_fields
        )
        missing = [name for name in required if not options.get(name)]
        if missing:
            missing_fields = ", ".join(missing)
            raise ValueError(
                f"Backend '{self.engine_name}' is missing required connection fields: "
                f"{missing_fields}"
            )
