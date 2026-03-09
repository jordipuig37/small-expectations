"""Databricks SQL backend implementation."""

from __future__ import annotations

from typing import ClassVar
from typing import Mapping

from smallex.backends.base import BaseDatabaseBackend


class DatabricksBackend(BaseDatabaseBackend):
    """Backend for Databricks SQL using ``databricks-sql-connector``.

    Expected connection options for token auth (default):
        - ``server_hostname``
        - ``http_path``
        - ``access_token``

    Expected connection options for browser auth:
        - ``auth_mode = "browser"``
        - ``server_hostname``
        - ``http_path``

    The backend maps ``auth_mode = "browser"`` to Databricks connector
    option ``auth_type = "databricks-oauth"``.
    """

    engine_name: ClassVar[str] = "databricks"
    module_path: ClassVar[str] = "databricks.sql"
    connect_attr: ClassVar[str] = "connect"
    required_connection_fields: ClassVar[tuple[str, ...]] = (
        "server_hostname",
        "http_path",
        "access_token",
    )

    browser_required_connection_fields: ClassVar[tuple[str, ...]] = (
        "server_hostname",
        "http_path",
    )

    def prepare_connection_options(self, options: Mapping[str, object]) -> dict[str, object]:
        """Map normalized auth mode values to Databricks connector options."""

        prepared = dict(options)
        auth_mode = prepared.pop("auth_mode", None)
        if auth_mode == "browser":
            prepared["auth_type"] = "databricks-oauth"
        elif auth_mode is not None and auth_mode != "token":
            raise ValueError(
                "Unsupported auth_mode for databricks. Supported: browser, token"
            )
        return prepared

    def validate_connection_options(self, options: Mapping[str, object]) -> None:
        """Validate Databricks fields according to selected auth mode."""

        required = (
            self.browser_required_connection_fields
            if options.get("auth_type") == "databricks-oauth"
            else self.required_connection_fields
        )
        missing = [name for name in required if not options.get(name)]
        if missing:
            missing_fields = ", ".join(missing)
            raise ValueError(
                f"Backend '{self.engine_name}' is missing required connection fields: "
                f"{missing_fields}"
            )
