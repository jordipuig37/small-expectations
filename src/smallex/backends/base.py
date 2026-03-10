"""Base interfaces and shared utilities for database backends."""

from __future__ import annotations

import importlib
from abc import ABC
from contextlib import closing
from dataclasses import dataclass
from types import ModuleType
from typing import Callable, ClassVar, Mapping, cast

from smallex.types import ConnectionProtocol


@dataclass(frozen=True)
class DatabaseConfig:
    """Configuration payload used to build a backend connection.

    Attributes:
        engine: Logical backend name (for example: ``sqlite`` or ``snowflake``).
        connection: Keyword arguments passed to the backend connector.
    """

    engine: str
    connection: dict[str, object]


class BaseDatabaseBackend(ABC):
    """Abstract base class for all supported database backends.

    Concrete backends define connector import details and required options.
    They then reuse :meth:`connect` to validate config and open a connection.

    Attributes:
        engine_name: Public engine identifier used in config files.
        module_path: Import path for the connector module.
        connect_attr: Connector function name in the imported module.
        required_connection_fields: Required config keys for the backend.
    """

    engine_name: ClassVar[str] = ""
    module_path: ClassVar[str] = ""
    connect_attr: ClassVar[str] = "connect"
    required_connection_fields: ClassVar[tuple[str, ...]] = ()

    def prepare_connection_options(self, options: Mapping[str, object]) -> dict[str, object]:
        """Transform user config into connector-ready options.

        Subclasses can override this to map normalized values to
        connector-specific keys and to remove framework-level keys that should
        not be passed to the underlying connector.

        Args:
            options: Raw connection mapping from config.

        Returns:
            dict[str, object]: Connector-ready connection options.
        """

        return dict(options)

    def validate_connection_options(self, options: Mapping[str, object]) -> None:
        """Validate connection options before opening a connection.

        Args:
            options: Connection keyword arguments from user config.

        Raises:
            ValueError: If one or more required fields are missing.
        """

        missing = [name for name in self.required_connection_fields if not options.get(name)]
        if missing:
            missing_fields = ", ".join(missing)
            raise ValueError(
                f"Backend '{self.engine_name}' is missing required connection fields: "
                f"{missing_fields}"
            )

    def connect(self, options: Mapping[str, object]) -> ConnectionProtocol:
        """Open a database connection using the backend connector.

        Args:
            options: Connection keyword arguments passed to the connector.

        Returns:
            ConnectionProtocol: A DB-API-like connection object.
        """

        prepared_options = self.prepare_connection_options(options)
        self.validate_connection_options(prepared_options)
        module: ModuleType = importlib.import_module(self.module_path)
        connect_fn = getattr(module, self.connect_attr, None)
        if connect_fn is None or not callable(connect_fn):
            raise AttributeError(
                f"Module '{self.module_path}' does not expose callable '{self.connect_attr}'."
            )
        connector = cast(Callable[..., ConnectionProtocol], connect_fn)
        return connector(**prepared_options)

    def test_connection(
        self,
        connection: ConnectionProtocol,
        options: Mapping[str, object],
    ) -> None:
        """Verify a backend connection is usable."""

        with closing(connection.cursor()) as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
