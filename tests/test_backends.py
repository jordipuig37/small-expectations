from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Callable

import pytest

from smallex.backends import get_backend
from smallex.backends.databricks import DatabricksBackend
from smallex.backends.snowflake import SnowflakeBackend
from smallex.backends.sqlite import SQLiteBackend
from smallex.runner import load_config, run_all
from smallex.types import ConnectionProtocol, CursorProtocol


def test_get_backend_returns_expected_backend_instances() -> None:
    assert isinstance(get_backend("sqlite"), SQLiteBackend)
    assert isinstance(get_backend("snowflake"), SnowflakeBackend)
    assert isinstance(get_backend("databricks"), DatabricksBackend)


def test_get_backend_raises_for_unknown_engine() -> None:
    with pytest.raises(ValueError, match="Unsupported database engine"):
        get_backend("postgres")


def test_snowflake_backend_connects_without_real_driver(
        monkeypatch: pytest.MonkeyPatch
        ) -> None:
    called: dict[str, object] = {}

    class FakeCursorForConnect(CursorProtocol):
        @property
        def description(self) -> tuple[tuple[object, ...], ...] | None:
            return None

        def execute(self, query: str) -> None:
            self.query = query

        def fetchone(self) -> tuple[object, ...] | None:
            return None

    class FakeConnectionForConnect(ConnectionProtocol):
        def cursor(self) -> CursorProtocol:
            return FakeCursorForConnect()

        def close(self) -> None:
            return None

    def fake_connect(**kwargs: object) -> ConnectionProtocol:
        called.update(kwargs)
        return FakeConnectionForConnect()

    def fake_import_module(module_path: str) -> object:
        assert module_path == "snowflake.connector"
        return SimpleNamespace(connect=fake_connect)

    monkeypatch.setattr(
        "smallex.backends.base.importlib.import_module", fake_import_module)

    backend = SnowflakeBackend()
    backend.connect(
        {
            "account": "acme",
            "user": "user",
            "password": "secret",
            "warehouse": "wh",
            "database": "analytics",
            "schema": "public",
        }
    )

    assert called["account"] == "acme"
    assert called["database"] == "analytics"


def test_snowflake_browser_auth_mode_is_rejected() -> None:
    backend = SnowflakeBackend()
    with pytest.raises(
            ValueError, match="Unsupported auth_mode for snowflake"
            ):
        backend.connect(
            {
                "auth_mode": "browser",
                "account": "acme",
                "user": "user",
                "warehouse": "wh",
                "database": "analytics",
                "schema": "public",
            }
        )


def test_databricks_backend_requires_core_fields() -> None:
    backend = DatabricksBackend()
    with pytest.raises(ValueError, match="missing required connection fields"):
        backend.connect({"server_hostname": "host"})


def test_run_all_for_snowflake_uses_backend_with_mocked_driver(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_path = tmp_path / "smallex.toml"
    config_path.write_text(
        "\n".join(
            [
                "[database]",
                'engine = "snowflake"',
                "",
                "[database.connection]",
                'account = "acme"',
                'user = "user"',
                'password = "secret"',
                'warehouse = "wh"',
                'database = "analytics"',
                'schema = "public"',
            ]
        ),
        encoding="utf-8",
    )

    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "check.sql").write_text("SELECT 1", encoding="utf-8")

    class FakeCursor(CursorProtocol):
        def __init__(self) -> None:
            self.query: str = ""

        def execute(self, query: str) -> None:
            self.query = query

        def fetchone(self) -> tuple[object, ...] | None:
            return None

        @property
        def description(self) -> tuple[tuple[object, ...], ...] | None:
            return (("col1",),)

    class FakeConnection(ConnectionProtocol):
        def __init__(self) -> None:
            self.closed = False

        def cursor(self) -> FakeCursor:
            return FakeCursor()

        def close(self) -> None:
            self.closed = True

    fake_connection = FakeConnection()

    def fake_connect(**_: object) -> ConnectionProtocol:
        return fake_connection

    def fake_import_module(module_path: str) -> object:
        assert module_path == "snowflake.connector"
        connect_fn: Callable[..., ConnectionProtocol] = fake_connect
        return SimpleNamespace(connect=connect_fn)

    monkeypatch.setattr(
        "smallex.backends.base.importlib.import_module", fake_import_module)

    results, failed = run_all(config_path, tests_dir)
    assert failed == 0
    assert len(results) == 1
    assert results[0].passed is True
    assert fake_connection.closed is True


def test_load_config_supports_legacy_sqlite_module(tmp_path: Path) -> None:
    config_path = tmp_path / "smallex.toml"
    config_path.write_text(
        "\n".join(
            [
                "[database]",
                'module = "sqlite3"',
                'database = "sample.db"',
            ]
        ),
        encoding="utf-8",
    )

    config = load_config(config_path)
    assert config.engine == "sqlite"
    assert config.connection["database"] == "sample.db"


def test_load_config_selects_default_named_connection(tmp_path: Path) -> None:
    config_path = tmp_path / "smallex.toml"
    config_path.write_text(
        "\n".join(
            [
                "[database]",
                'engine = "sqlite"',
                'default_connection = "development"',
                "",
                "[database.connections.development]",
                'database = "dev.db"',
                "",
                "[database.connections.production]",
                'database = "prod.db"',
            ]
        ),
        encoding="utf-8",
    )

    config = load_config(config_path)
    assert config.engine == "sqlite"
    assert config.connection["database"] == "dev.db"


def test_load_config_selects_named_connection_from_env(tmp_path: Path) -> None:
    config_path = tmp_path / "smallex.toml"
    config_path.write_text(
        "\n".join(
            [
                "[database]",
                'engine = "sqlite"',
                "",
                "[database.connections.dev]",
                'database = "dev.db"',
                "",
                "[database.connections.prod]",
                'database = "prod.db"',
            ]
        ),
        encoding="utf-8",
    )

    config = load_config(config_path, env="prod")
    assert config.engine == "sqlite"
    assert config.connection["database"] == "prod.db"


def test_load_config_requires_env_or_default_when_multiple_named_connections(
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "smallex.toml"
    config_path.write_text(
        "\n".join(
            [
                "[database]",
                'engine = "sqlite"',
                "",
                "[database.connections.dev]",
                'database = "dev.db"',
                "",
                "[database.connections.prod]",
                'database = "prod.db"',
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="defines multiple environments",
    ):
        load_config(config_path)


def test_load_config_raises_for_unknown_named_connection(
        tmp_path: Path
        ) -> None:
    config_path = tmp_path / "smallex.toml"
    config_path.write_text(
        "\n".join(
            [
                "[database]",
                'engine = "sqlite"',
                "",
                "[database.connections.dev]",
                'database = "dev.db"',
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(
            ValueError, match="Unknown database connection environment"
            ):
        load_config(config_path, env="staging")


def test_databricks_browser_auth_mode_is_rejected() -> None:
    backend = DatabricksBackend()
    with pytest.raises(
            ValueError, match="Unsupported auth_mode for databricks"
            ):
        backend.connect(
            {
                "auth_mode": "browser",
                "server_hostname": "dbc.example.com",
                "http_path": "/sql/1.0/warehouses/abc",
            }
        )
