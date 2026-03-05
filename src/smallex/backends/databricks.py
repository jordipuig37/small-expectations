"""Databricks SQL backend implementation."""

from __future__ import annotations

from typing import ClassVar

from smallex.backends.base import BaseDatabaseBackend


class DatabricksBackend(BaseDatabaseBackend):
    """Backend for Databricks SQL using ``databricks-sql-connector``.

    Expected connection options:
        - ``server_hostname``
        - ``http_path``
        - ``access_token``
    """

    engine_name: ClassVar[str] = "databricks"
    module_path: ClassVar[str] = "databricks.sql"
    connect_attr: ClassVar[str] = "connect"
    required_connection_fields: ClassVar[tuple[str, ...]] = (
        "server_hostname",
        "http_path",
        "access_token",
    )
