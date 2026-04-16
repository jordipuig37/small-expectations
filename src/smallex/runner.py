"""Core execution pipeline for SQL expectation tests."""

from __future__ import annotations

import csv
import sys
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

from smallex.backends import get_backend
from smallex.backends.base import DatabaseConfig
from smallex.sqltests import SQLTestCase, parse_sql_files
from smallex.types import ConnectionProtocol, CursorProtocol

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover
    import tomli as tomllib


class FailureRowsMode:
    """Supported modes for failure row reporting."""

    NONE = "none"
    TERMINAL = "terminal"
    CSV = "csv"
    BOTH = "both"


@dataclass(frozen=True)
class FailureRowsConfig:
    """Configuration controlling how failing rows are collected and reported.

    Attributes:
        mode: One of ``none``, ``terminal``, ``csv``, or ``both``.
        terminal_limit: Number of rows to display per failing test in terminal.
        csv_limit: Maximum number of rows to persist per failing test in CSV.
        csv_dir: Target directory for CSV outputs.
    """

    mode: str = FailureRowsMode.NONE
    terminal_limit: int = 5
    csv_limit: int = 10_000
    csv_dir: Path = Path(".smallex/failures")

    def terminal_enabled(self) -> bool:
        """Return whether terminal row previews should be produced."""

        return self.mode in {FailureRowsMode.TERMINAL, FailureRowsMode.BOTH}

    def csv_enabled(self) -> bool:
        """Return whether CSV failure exports should be produced."""

        return self.mode in {FailureRowsMode.CSV, FailureRowsMode.BOTH}


@dataclass
class TestResult:
    """Outcome for one SQL expectation.

    Attributes:
        case: Source SQL test case metadata.
        passed: ``True`` when query returns zero rows.
        row_count: Number of rows fetched for this failure context.
        has_more_rows: ``True`` when rows exist beyond configured fetch limits.
        columns: Result column names for failing query rows.
        sample_rows: Sample rows for terminal reporting.
        csv_path: Generated CSV path when export is enabled.
        error_message: SQL error message when query execution fails.
    """

    case: SQLTestCase
    passed: bool
    row_count: int
    has_more_rows: bool
    columns: list[str]
    sample_rows: list[tuple[object, ...]]
    csv_path: Path | None
    error_message: str | None = None

    @property
    def message(self) -> str | None:
        """Return user-authored message associated with this test case."""

        return self.case.message

    @property
    def path(self) -> Path:
        """Return source path for compatibility with existing callers."""

        return self.case.path

    @property
    def node_id(self) -> str:
        """Return pytest-like node id for terminal reporting."""

        return self.case.node_id


def _as_mapping(value: object, *, field_name: str) -> Mapping[str, object]:
    """Validate and cast a TOML table-like object into a mapping."""

    if not isinstance(value, dict):
        raise ValueError(f"Config {field_name} must be a table.")
    return value


def _parse_database_config(
    raw_database_cfg: Mapping[str, object],
    *,
    env: str | None = None,
) -> DatabaseConfig:
    """Convert a raw TOML database section into a typed config object."""

    engine_raw = raw_database_cfg.get("engine")
    module_raw = raw_database_cfg.get("module")
    engine = engine_raw if isinstance(engine_raw, str) else None
    module = module_raw if isinstance(module_raw, str) else None

    if not engine and module == "sqlite3":
        engine = "sqlite"
    if not engine:
        raise ValueError("Config [database] must include 'engine'.")

    connections_raw = raw_database_cfg.get("connections")
    default_connection_raw = raw_database_cfg.get("default_connection")
    default_connection = (
        default_connection_raw if isinstance(
            default_connection_raw, str) else None
    )

    connection_cfg: Mapping[str, object] = {}
    if connections_raw is not None:
        connections_cfg = _as_mapping(
            connections_raw,
            field_name="[database.connections]",
        )
        if env is not None:
            selected_name = env
        elif default_connection is not None:
            selected_name = default_connection
        elif "default" in connections_cfg:
            selected_name = "default"
        else:
            selected_name = None

        if selected_name is not None:
            selected_connection = connections_cfg.get(selected_name)
            if selected_connection is None:
                raise ValueError(
                    "Unknown database connection environment "
                    f"'{selected_name}'. Available: "
                    f"{', '.join(sorted(connections_cfg))}"
                )
            connection_cfg = _as_mapping(
                selected_connection,
                field_name=f"[database.connections.{selected_name}]",
            )
        elif connections_cfg:
            if len(connections_cfg) == 1:
                only_name = next(iter(connections_cfg))
                selected_connection = connections_cfg[only_name]
                connection_cfg = _as_mapping(
                    selected_connection,
                    field_name=f"[database.connections.{only_name}]",
                )
            else:
                raise ValueError(
                    "Config [database.connections] defines multiple "
                    "environments. Provide --env or set "
                    "[database].default_connection."
                )

    if not connection_cfg:
        connection_raw = raw_database_cfg.get("connection")
        if connection_raw is None:
            connection_cfg = {}
        else:
            connection_cfg = _as_mapping(
                connection_raw, field_name="[database.connection]")

    if not connection_cfg:
        excluded = {"engine", "module", "connections", "default_connection"}
        connection_cfg = {
            key: value for key, value in raw_database_cfg.items()
            if key not in excluded
        }

    return DatabaseConfig(engine=engine, connection=dict(connection_cfg))


def load_config(config_path: Path, env: str | None = None) -> DatabaseConfig:
    """Load and validate CLI config from TOML file."""

    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with config_path.open("rb") as fh:
        content = tomllib.load(fh)

    database_cfg_raw = content.get("database")
    if database_cfg_raw is None:
        raise ValueError("Config must define a [database] section.")
    database_cfg = _as_mapping(database_cfg_raw, field_name="[database]")
    return _parse_database_config(database_cfg, env=env)


def discover_sql_tests(tests_dir: Path) -> list[Path]:
    """Discover SQL test scripts recursively under a directory."""

    if not tests_dir.exists():
        return []
    return sorted(path for path in tests_dir.rglob("*.sql") if path.is_file())


def discover_sql_cases(tests_dir: Path) -> list[SQLTestCase]:
    """Discover SQL files and parse all SQL test cases."""

    files = discover_sql_tests(tests_dir)
    return parse_sql_files(files)


def _parse_selector(selector: str) -> tuple[str | None, str | None]:
    """Parse CLI selector into script and optional test components."""

    selector = selector.strip()
    if not selector:
        return None, None
    if selector.endswith(".sql"):
        return selector, None
    if "." in selector:
        script_part, test_part = selector.rsplit(".", 1)
        if script_part:
            return script_part, test_part or None
    return selector, None


def _matches_script_target(
    case: SQLTestCase,
    tests_dir: Path,
    script_part: str,
) -> bool:
    script_normalized = script_part.replace("\\", "/")
    script_no_suffix = (
        script_normalized[:-4]
        if script_normalized.endswith(".sql")
        else script_normalized
    )

    try:
        rel_path = case.path.resolve().relative_to(tests_dir.resolve())
    except ValueError:
        rel_path = case.path

    rel_posix = rel_path.as_posix()
    rel_no_suffix = (
        rel_path.with_suffix("").as_posix()
        if rel_path.suffix
        else rel_posix
    )

    if rel_posix == script_normalized:
        return True
    if rel_posix == f"{script_no_suffix}.sql":
        return True
    if rel_no_suffix == script_no_suffix:
        return True
    if case.path.name == script_normalized:
        return True
    if case.path.stem == script_no_suffix:
        return True
    return False


def _filter_cases_by_selector(
    cases: list[SQLTestCase],
    tests_dir: Path,
    selector: str,
) -> list[SQLTestCase]:
    script_part, test_part = _parse_selector(selector)
    if script_part is None:
        return cases

    filtered: list[SQLTestCase] = []
    for case in cases:
        if not _matches_script_target(case, tests_dir, script_part):
            continue
        if test_part is not None and case.name != test_part:
            continue
        filtered.append(case)

    if not filtered:
        if test_part is None:
            raise ValueError(
                f"No tests matched script selector '{selector}'."
            )
        raise ValueError(
            f"No tests matched selector '{selector}'."
        )

    return filtered


def _normalize_row(row: Sequence[object]) -> tuple[object, ...]:
    """Normalize DB-API row representation into a tuple."""

    return tuple(row)


def _get_column_names(cursor: CursorProtocol, row_width: int) -> list[str]:
    """Extract result-set column names from cursor metadata."""

    description = cursor.description
    if description is None:
        return [f"column_{index}" for index in range(1, row_width + 1)]

    names: list[str] = []
    for index, col in enumerate(description, start=1):
        if not col:
            names.append(f"column_{index}")
            continue
        name = col[0]
        names.append(str(name) if name else f"column_{index}")
    return names


def _safe_test_name(name: str) -> str:
    """Sanitize test names for filesystem usage in CSV exports."""

    lowered = name.lower()
    cleaned = "".join(ch if ch.isalnum() or ch in {
                      "-", "_"} else "_" for ch in lowered)
    collapsed = "_".join(part for part in cleaned.split("_") if part)
    return collapsed or "test"


def _csv_path_for_case(case: SQLTestCase, csv_dir: Path) -> Path:
    """Build deterministic CSV output path for a failing test case."""

    stem = case.path.stem
    safe_name = _safe_test_name(case.name)
    return csv_dir / f"{stem}__{safe_name}.csv"


def _write_rows_csv(
        path: Path,
        columns: Sequence[str],
        rows: Sequence[Sequence[object]]
) -> None:
    """Write rows and columns to a CSV file."""

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(columns)
        for row in rows:
            writer.writerow(row)


def _row_fetch_limit(config: FailureRowsConfig) -> int:
    """Compute maximum number of rows to fetch for failure reporting."""

    if config.mode == FailureRowsMode.NONE:
        return 1

    limits: list[int] = [1]
    if config.terminal_enabled():
        limits.append(config.terminal_limit)
    if config.csv_enabled():
        limits.append(config.csv_limit)
    return max(limits)


def _collect_failure_rows(
    cursor: CursorProtocol,
    first_row: Sequence[object],
    *,
    limit: int,
) -> tuple[list[tuple[object, ...]], bool]:
    """Collect rows for failed query diagnostics up to the given limit.

    Returns:
        tuple[list[tuple[object, ...]], bool]: Collected rows and a flag
        indicating whether more rows exist beyond ``limit``.
    """

    rows: list[tuple[object, ...]] = [_normalize_row(first_row)]
    while len(rows) < limit:
        next_row = cursor.fetchone()
        if next_row is None:
            return rows, False
        rows.append(_normalize_row(next_row))

    extra_row = cursor.fetchone()
    return rows, extra_row is not None


def run_sql_case(
    connection: ConnectionProtocol,
    case: SQLTestCase,
    *,
    failure_rows: FailureRowsConfig,
) -> TestResult:
    """Execute one SQL test case and classify pass/fail with diagnostics."""

    cursor = connection.cursor()
    try:
        cursor.execute(case.query)
    except Exception as exc:  # pragma: no cover - backend-specific SQL error
        error_message = str(exc).strip()
        if not error_message:
            error_message = exc.__class__.__name__
        return TestResult(
            case=case,
            passed=False,
            row_count=0,
            has_more_rows=False,
            columns=[],
            sample_rows=[],
            csv_path=None,
            error_message=error_message,
        )
    first_row = cursor.fetchone()
    if first_row is None:
        return TestResult(
            case=case,
            passed=True,
            row_count=0,
            has_more_rows=False,
            columns=[],
            sample_rows=[],
            csv_path=None,
        )

    fetch_limit = _row_fetch_limit(failure_rows)
    collected_rows, has_more_rows = _collect_failure_rows(
        cursor,
        first_row,
        limit=fetch_limit,
    )

    columns = _get_column_names(cursor, len(collected_rows[0]))
    sample_rows = (
        collected_rows[: failure_rows.terminal_limit]
        if failure_rows.terminal_enabled()
        else []
    )

    csv_path: Path | None = None
    if failure_rows.csv_enabled():
        csv_rows = collected_rows[: failure_rows.csv_limit]
        csv_path = _csv_path_for_case(case, failure_rows.csv_dir)
        _write_rows_csv(csv_path, columns, csv_rows)

    return TestResult(
        case=case,
        passed=False,
        row_count=len(collected_rows),
        has_more_rows=has_more_rows,
        columns=columns,
        sample_rows=sample_rows,
        csv_path=csv_path,
    )


def run_all(
    config_path: Path,
    tests_dir: Path,
    *,
    env: str | None = None,
    failure_rows: FailureRowsConfig | None = None,
    selector: str | None = None,
) -> tuple[list[TestResult], int]:
    """Run all SQL expectations and return results plus failed count."""

    db_config = load_config(config_path, env=env)
    cases = discover_sql_cases(tests_dir)
    if selector:
        cases = _filter_cases_by_selector(cases, tests_dir, selector)
    if not cases:
        return [], 0

    reporting_cfg = failure_rows if failure_rows is not None \
        else FailureRowsConfig()
    backend = get_backend(db_config.engine)
    results: list[TestResult] = []

    with closing(backend.connect(db_config.connection)) as connection:
        for case in cases:
            results.append(
                run_sql_case(connection, case, failure_rows=reporting_cfg)
            )

    failed = sum(1 for result in results if not result.passed)
    return results, failed
