"""Backend registry and factory helpers."""

from __future__ import annotations

from typing import Final

from smallex.backends.base import BaseDatabaseBackend
from smallex.backends.databricks import DatabricksBackend
from smallex.backends.snowflake import SnowflakeBackend
from smallex.backends.sqlite import SQLiteBackend

_BACKENDS: Final[dict[str, type[BaseDatabaseBackend]]] = {
    SQLiteBackend.engine_name: SQLiteBackend,
    SnowflakeBackend.engine_name: SnowflakeBackend,
    DatabricksBackend.engine_name: DatabricksBackend,
}


def get_backend(engine: str) -> BaseDatabaseBackend:
    """Create a backend instance from an engine identifier.

    Args:
        engine: Backend identifier from config.

    Returns:
        BaseDatabaseBackend: A concrete backend instance.

    Raises:
        ValueError: If the engine is unknown.
    """

    backend_cls = _BACKENDS.get(engine.lower())
    if backend_cls is None:
        supported = ", ".join(sorted(_BACKENDS))
        raise ValueError(
            f"Unsupported database engine '{engine}'. Supported: {supported}")
    return backend_cls()
