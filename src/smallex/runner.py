"""Core execution pipeline for SQL expectation tests."""

from __future__ import annotations

import sys
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from smallex.backends import get_backend
from smallex.backends.base import DatabaseConfig
from smallex.types import ConnectionProtocol

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover
    import tomli as tomllib


@dataclass
class TestResult:
    """Outcome for one SQL expectation file.

    Attributes:
        path: File path for the SQL script that was executed.
        passed: ``True`` when the query returned zero rows.
        row_count: Number of rows used to determine pass/fail.
            The current runner only needs to know if at least one row exists,
            so this value is either ``0`` or ``1``.
    """

    path: Path
    passed: bool
    row_count: int


def _as_mapping(value: object, *, field_name: str) -> Mapping[str, object]:
    """Validate and cast a TOML table-like object into a mapping.

    Args:
        value: TOML node to validate.
        field_name: Human-readable field name used for error messages.

    Returns:
        Mapping[str, object]: Mapping view of the table.

    Raises:
        ValueError: If ``value`` is not a mapping.
    """

    if not isinstance(value, dict):
        raise ValueError(f"Config {field_name} must be a table.")
    return value


def _parse_database_config(raw_database_cfg: Mapping[str, object]) -> DatabaseConfig:
    """Convert a raw TOML database section into a typed config object.

    Config format:
        [database]
        engine = "sqlite"  # sqlite | snowflake | databricks

        [database.connection]
        database = "example.db"

    Legacy compatibility:
        If ``[database.connection]`` is missing, keys from ``[database]`` other
        than ``engine`` and ``module`` are treated as connection options.
        If ``engine`` is missing and ``module == "sqlite3"``, engine defaults
        to ``sqlite``.

    Args:
        raw_database_cfg: Parsed ``[database]`` TOML section.

    Returns:
        DatabaseConfig: Normalized database configuration.

    Raises:
        ValueError: If required config pieces are missing or invalid.
    """

    engine_raw = raw_database_cfg.get("engine")
    module_raw = raw_database_cfg.get("module")
    engine = engine_raw if isinstance(engine_raw, str) else None
    module = module_raw if isinstance(module_raw, str) else None

    if not engine and module == "sqlite3":
        engine = "sqlite"
    if not engine:
        raise ValueError("Config [database] must include 'engine'.")

    connection_raw = raw_database_cfg.get("connection")
    connection_cfg: Mapping[str, object]
    if connection_raw is None:
        connection_cfg = {}
    else:
        connection_cfg = _as_mapping(connection_raw, field_name="[database.connection]")

    if not connection_cfg:
        excluded = {"engine", "module"}
        connection_cfg = {
            key: value for key, value in raw_database_cfg.items() if key not in excluded
        }

    return DatabaseConfig(engine=engine, connection=dict(connection_cfg))


def load_config(config_path: Path) -> DatabaseConfig:
    """Load and validate CLI config from TOML file.

    Args:
        config_path: Path to the TOML config file.

    Returns:
        DatabaseConfig: Parsed and normalized database settings.

    Raises:
        FileNotFoundError: If ``config_path`` does not exist.
        ValueError: If the TOML contents are missing required sections/fields.
    """

    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with config_path.open("rb") as fh:
        content = tomllib.load(fh)

    database_cfg_raw = content.get("database")
    if database_cfg_raw is None:
        raise ValueError("Config must define a [database] section.")
    database_cfg = _as_mapping(database_cfg_raw, field_name="[database]")
    return _parse_database_config(database_cfg)


def discover_sql_tests(tests_dir: Path) -> list[Path]:
    """Discover SQL test scripts recursively under a directory.

    Args:
        tests_dir: Root directory containing ``.sql`` files.

    Returns:
        list[Path]: Sorted list of discovered SQL script paths.
    """

    if not tests_dir.exists():
        return []
    return sorted(path for path in tests_dir.rglob("*.sql") if path.is_file())


def run_sql_file(connection: ConnectionProtocol, sql_file: Path) -> TestResult:
    """Execute one SQL file and classify pass/fail.

    A script is considered passing if it returns no rows. If at least one row
    is returned, it is considered failed.

    Args:
        connection: Open DB-API-like connection object.
        sql_file: SQL file path to execute.

    Returns:
        TestResult: Pass/fail status for the file.
    """

    query = sql_file.read_text(encoding="utf-8")
    cursor = connection.cursor()
    cursor.execute(query)
    first_row = cursor.fetchone()
    row_count = 0 if first_row is None else 1
    return TestResult(path=sql_file, passed=row_count == 0, row_count=row_count)


def run_all(config_path: Path, tests_dir: Path) -> tuple[list[TestResult], int]:
    """Run all SQL expectations and return results plus failed count.

    Args:
        config_path: Path to CLI config file.
        tests_dir: Directory containing SQL scripts.

    Returns:
        tuple[list[TestResult], int]: A tuple with all results and the number
        of failed tests.
    """

    db_config = load_config(config_path)
    sql_files = discover_sql_tests(tests_dir)
    if not sql_files:
        return [], 0

    backend = get_backend(db_config.engine)
    results: list[TestResult] = []

    with closing(backend.connect(db_config.connection)) as connection:
        for sql_file in sql_files:
            results.append(run_sql_file(connection, sql_file))

    failed = sum(1 for result in results if not result.passed)
    return results, failed
