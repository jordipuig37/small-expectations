"""Command-line interface for small-expectations."""

from __future__ import annotations

import argparse
import os
import platform
import shutil
import sys
import time
from contextlib import closing
from pathlib import Path

from smallex import __version__
from smallex.backends import get_backend
from smallex.runner import (
    FailureRowsConfig,
    FailureRowsMode,
    TestResult,
    load_config,
    run_all,
)

MIN_SEPARATOR_WIDTH = 40
RESET = "\033[0m"
RED = "\033[31m"
GREEN = "\033[32m"
BLUE = "\033[34m"
WHITE = "\033[37m"
CYAN = "\033[36m"
BOLD = "\033[1m"
SUPPORTED_ENGINES = ("sqlite", "snowflake", "databricks")


class ColorMode:
    """Supported values for the ``--color`` option."""

    AUTO = "auto"
    YES = "yes"
    NO = "no"


def _use_color(mode: str) -> bool:
    """Decide whether ANSI colors should be enabled."""

    if mode == ColorMode.YES:
        return True
    if mode == ColorMode.NO:
        return False
    return sys.stdout.isatty() and "NO_COLOR" not in os.environ


def _paint(
    text: str,
    color: str | None = None,
    *,
    enabled: bool,
    bold: bool = False,
) -> str:
    """Wrap text in ANSI style escapes when enabled."""

    if not enabled:
        return text

    prefixes: list[str] = []
    if bold:
        prefixes.append(BOLD)
    if color is not None:
        prefixes.append(color)
    if not prefixes:
        return text
    return f"{''.join(prefixes)}{text}{RESET}"


def _terminal_width() -> int:
    """Return terminal width with a safe minimum."""

    width = shutil.get_terminal_size(fallback=(80, 24)).columns
    return max(MIN_SEPARATOR_WIDTH, width)


def _section(
    title: str,
    *,
    color_enabled: bool = False,
    title_color: str | None = CYAN,
    title_bold: bool = False,
    line_color: str | None = None,
) -> str:
    """Build a pytest-like section separator line."""

    width = _terminal_width()
    plain_padded = f" {title} "
    styled_title = _paint(
        title,
        title_color,
        enabled=color_enabled,
        bold=title_bold,
    )
    styled_padded = f" {styled_title} "
    if len(plain_padded) >= width:
        return styled_padded

    side = (width - len(plain_padded)) // 2
    left = "=" * side
    right = "=" * (width - len(plain_padded) - side)
    if line_color is not None:
        left = _paint(left, line_color, enabled=color_enabled)
        right = _paint(right, line_color, enabled=color_enabled)
    return f"{left}{styled_padded}{right}"


def _safe_connection_details(connection: dict[str, object]) -> str:
    """Render safe connection detail keys without sensitive values."""

    safe_values = [
        f"{key}: {str(connection[key])}"
        for key in ("account", "database", "schema", "user", "role")
        if key in connection and connection[key] is not None
    ]
    return ", ".join(safe_values) if safe_values else "no connection options"


def _display_path(path: Path) -> str:
    """Render a path in a terminal-friendly form."""

    try:
        return str(path.resolve().relative_to(Path.cwd()))
    except ValueError:
        return str(path)


def build_parser() -> argparse.ArgumentParser:
    """Build the top-level command parser."""

    parser = argparse.ArgumentParser(prog="smallex")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser(
        "run",
        help="Run SQL tests.",
        description=(
            "Run SQL expectation tests from .sql files. "
            "A test passes when the query returns zero rows."
        ),
    )
    run_parser.add_argument(
        "--config",
        default="smallex.toml",
        help="Path to TOML config file (default: smallex.toml).",
    )
    run_parser.add_argument(
        "--tests-dir",
        default="tests",
        help="Directory containing .sql tests (default: tests).",
    )
    run_parser.add_argument(
        "--env",
        help=(
            "Named database connection environment from "
            "[database.connections.<name>] (for example: dev, prod)."
        ),
    )
    run_parser.add_argument(
        "--color",
        choices=[ColorMode.AUTO, ColorMode.YES, ColorMode.NO],
        default=ColorMode.AUTO,
        help="Color output mode: auto, yes, or no (default: auto).",
    )
    run_parser.add_argument(
        "--failure-rows-mode",
        choices=[
            FailureRowsMode.NONE,
            FailureRowsMode.TERMINAL,
            FailureRowsMode.CSV,
            FailureRowsMode.BOTH,
        ],
        default=FailureRowsMode.NONE,
        help="Failure row output mode: none, terminal, csv, or both.",
    )
    run_parser.add_argument(
        "--failure-rows-limit",
        type=int,
        default=5,
        help="Rows to show in terminal per failing test (default: 5).",
    )
    run_parser.add_argument(
        "--failure-rows-csv-limit",
        type=int,
        default=10_000,
        help="Rows to write to CSV per failing test (default: 10000).",
    )
    run_parser.add_argument(
        "--failure-rows-dir",
        default=".smallex/failures",
        help="Directory for failure CSV outputs (default: .smallex/failures).",
    )
    run_parser.add_argument(
        "target",
        nargs="?",
        help=(
            "Optional selector: <script>[.<test>] or path/to/script(.sql). "
            "If omitted, all tests run."
        ),
    )

    init_parser = subparsers.add_parser(
        "init",
        help="Create starter config and sample SQL test files.",
    )
    init_parser.add_argument(
        "--engine",
        choices=SUPPORTED_ENGINES,
        default="sqlite",
        help="Database engine for starter config (default: sqlite).",
    )
    init_parser.add_argument(
        "--config",
        default="smallex.toml",
        help="Path for generated TOML config (default: smallex.toml).",
    )
    init_parser.add_argument(
        "--tests-dir",
        default="tests",
        help="Directory where starter SQL test will be created (default: tests).",  # noqa: E501
    )
    init_parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing generated files.",
    )

    validate_parser = subparsers.add_parser(
        "validate-config",
        help="Validate config and attempt a database connection.",
    )
    validate_parser.add_argument(
        "--config",
        default="smallex.toml",
        help="Path to TOML config file (default: smallex.toml).",
    )
    validate_parser.add_argument(
        "--env",
        help=(
            "Named database connection environment from "
            "[database.connections.<name>] (for example: dev, prod)."
        ),
    )
    return parser


def _starter_connection_block(engine: str) -> list[str]:
    if engine == "sqlite":
        return ['database = "example.db"']
    if engine == "snowflake":
        return [
            'auth_mode = "password"',
            'account = "your-account"',
            'user = "your-user"',
            'password = "your-password"',
            'warehouse = "your-warehouse"',
            'database = "your-database"',
            'schema = "public"',
        ]
    return [
        'auth_mode = "token"',
        'server_hostname = "adb-1234567890123456.7.azuredatabricks.net"',
        'http_path = "/sql/1.0/warehouses/your-warehouse-id"',
        'access_token = "your-access-token"',
    ]


def _build_starter_config(engine: str) -> str:
    lines = [
        "[database]",
        f'engine = "{engine}"',
        'default_connection = "dev"',
        "",
        "[database.connections.dev]",
        *_starter_connection_block(engine),
    ]
    return "\n".join(lines) + "\n"


def _build_starter_test_sql() -> str:
    return "\n".join(
        [
            "-- smallex:test: no_null_emails",
            "-- smallex:message: users.email should never be null",
            "SELECT id, email",
            "FROM users",
            "WHERE email IS NULL;",
            "",
        ]
    )


def _connection_error_hint(exc: BaseException) -> str | None:
    status = _http_status_from_exception(exc)
    if status == 404:
        return "Account or host not found (HTTP 404). Verify the account/hostname values."  # noqa: E501
    if status in {401, 403}:
        return f"Authentication failed (HTTP {status}). Check the user/password/token values."  # noqa: E501
    if status is not None:
        return f"Backend returned HTTP {status} while validating the connection."  # noqa: E501
    return None


def _http_status_from_exception(exc: BaseException) -> int | None:
    seen: set[int] = set()
    queue: list[BaseException | None] = [exc]
    while queue:
        current = queue.pop(0)
        if current is None:
            continue
        key = id(current)
        if key in seen:
            continue
        seen.add(key)

        status = getattr(current, "status_code", None)
        if isinstance(status, int):
            return status

        response = getattr(current, "response", None)
        if response is not None:
            response_status = getattr(response, "status_code", None)
            if isinstance(response_status, int):
                return response_status

        cause = getattr(current, "__cause__", None)
        context = getattr(current, "__context__", None)
        if isinstance(cause, BaseException):
            queue.append(cause)
        if isinstance(context, BaseException):
            queue.append(context)
    return None


def _write_if_allowed(path: Path, content: str, *, force: bool) -> None:
    if path.exists() and not force:
        raise FileExistsError(
            f"File already exists: {path}. Use --force to overwrite."
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _diagnostic_hint(exc: Exception) -> str:
    if isinstance(exc, ModuleNotFoundError):
        return (
            "Connector package is not installed for this engine. "
            "Install optional dependencies for your backend."
        )

    message = str(exc).lower()
    if any(token in message for token in ("password", "auth", "token", "login")):  # noqa: E501
        return "Authentication failed. Check user/password/token/auth_mode values."  # noqa: E501
    if any(token in message for token in ("timeout", "timed out", "network", "dns", "host")):  # noqa: E501
        return "Network connectivity issue. Check hostname, firewall, VPN, and DNS."  # noqa: E501
    if any(token in message for token in ("warehouse", "schema", "database", "catalog")):  # noqa: E501
        return "Object resolution issue. Check database/schema/warehouse and permissions."  # noqa: E501
    return "Review connection settings and backend-specific required fields."


def _print_header(
    collected: int,
    *,
    color_enabled: bool,
    engine_name: str,
    connection_details: str,
) -> None:
    """Print pytest-like session header lines."""

    print(_section("test session starts",
          color_enabled=color_enabled, title_bold=True))
    print(
        f"platform {platform.system().lower()} -- Python "
        f"{platform.python_version()}, smallex-{__version__}"
    )
    print(f"database: {engine_name} ({connection_details})")
    print(f"rootdir: {Path.cwd()}")
    label = "item" if collected == 1 else "items"
    print(_paint(f"collected {collected} {label}",
          enabled=color_enabled, bold=True))
    print()


def _print_test_progress(
        results: list[TestResult],
        *,
        color_enabled: bool
        ) -> None:
    """Print pytest-like progress grouped by SQL file."""

    grouped: dict[str, list[TestResult]] = {}
    for result in results:
        key = _display_path(result.path)
        grouped.setdefault(key, []).append(result)

    for path, file_results in grouped.items():
        colored_symbols = "".join(
            _paint("." if result.passed else "F",
                   GREEN if result.passed else RED, enabled=color_enabled)
            for result in file_results
        )
        print(f"{path} {colored_symbols}")


def _print_failures(
    results: list[TestResult],
    *,
    color_enabled: bool,
    failure_rows_cfg: FailureRowsConfig,
) -> None:
    """Print pytest-like failure details for failed SQL checks."""

    failed = [result for result in results if not result.passed]
    if not failed:
        return

    print()
    print(
        _section(
            "FAILURES",
            color_enabled=color_enabled,
            title_color=WHITE,
            title_bold=True,
        )
    )
    for result in failed:
        print("_" * _terminal_width())
        print(_paint(result.node_id, RED, enabled=color_enabled))
        if result.error_message:
            print(
                _paint(f"SQL error: {result.error_message}",
                       RED,
                       enabled=color_enabled)
                )
            continue
        if result.message:
            print(_paint(f"Message: {result.message}",
                  RED, enabled=color_enabled))
        else:
            print(
                _paint(
                    "Message: Query returned at least one row. Expected: "
                    "zero rows.",
                    RED,
                    enabled=color_enabled,
                )
            )
        if failure_rows_cfg.terminal_enabled() and result.sample_rows:
            _print_failure_rows(result, color_enabled=color_enabled)
        if result.csv_path is not None:
            print(
                _paint(
                    f"Failure rows CSV: {result.csv_path}",
                    RED,
                    enabled=color_enabled)
                )


def _print_failure_rows(result: TestResult, *, color_enabled: bool) -> None:
    """Print failing sample rows with a single header and raw row values."""

    print(_paint("Sample failing rows:", RED, enabled=color_enabled))
    header_columns = list(result.columns)
    max_row_len = max((len(row) for row in result.sample_rows), default=0)
    max_cols = max(len(header_columns), max_row_len)
    if len(header_columns) < max_cols:
        header_columns.extend(
            f"column_{index + 1}"
            for index in range(len(header_columns), max_cols)
        )
    column_widths = [len(header_columns[index]) for index in range(max_cols)]
    repr_rows: list[list[str]] = []
    for row in result.sample_rows:
        row_repr = [repr(value) for value in row]
        if len(row_repr) < max_cols:
            row_repr.extend("" for _ in range(max_cols - len(row_repr)))
        for index, value in enumerate(row_repr):
            if index >= len(column_widths):
                column_widths.extend([0] * (index + 1 - len(column_widths)))
            column_widths[index] = max(column_widths[index], len(value))
        repr_rows.append(row_repr)
    header_line = "  " + " | ".join(
        header_columns[index].ljust(column_widths[index])
        for index in range(max_cols)
    )
    print(_paint(header_line, RED, enabled=color_enabled))
    for row_repr in repr_rows:
        line = "  " + " | ".join(
            row_repr[index].ljust(column_widths[index])
            for index in range(max_cols)
        )
        print(_paint(line, RED, enabled=color_enabled))
    if result.has_more_rows:
        print(
            _paint(
                "  ... more rows exist (showing first "
                f"{len(result.sample_rows)})",
                RED,
                enabled=color_enabled,
            )
        )


def _print_footer(
    results: list[TestResult], duration_seconds: float, *, color_enabled: bool
) -> None:
    """Print short summary info and final status line."""

    failed = [result for result in results if not result.passed]
    passed = len(results) - len(failed)

    if failed:
        print()
        print(
            _section(
                "short test summary info",
                color_enabled=color_enabled,
                title_color=BLUE,
                title_bold=True,
            )
        )
        for result in failed:
            label = _paint("FAILED", RED, enabled=color_enabled)
            if result.error_message:
                detail = f"SQL error: {result.error_message}"
            else:
                detail = result.message if result.message \
                    else "Query returned one or more rows"
            print(f"{label} {result.node_id} - {detail}")

    status_parts: list[str] = []
    if failed:
        status_parts.append(f"{len(failed)} failed")
    if passed:
        status_parts.append(f"{passed} passed")
    if not status_parts:
        status_parts.append("no tests ran")

    summary = f"{', '.join(status_parts)} in {duration_seconds:.2f}s"
    summary_color = GREEN if not failed else RED
    print(
        _section(
            summary,
            color_enabled=color_enabled,
            title_color=summary_color,
            line_color=summary_color,
        )
    )


def _build_failure_rows_config(args: argparse.Namespace) -> FailureRowsConfig:
    """Build validated failure-row reporting configuration from CLI args."""

    if args.failure_rows_limit < 1:
        raise ValueError("--failure-rows-limit must be >= 1")
    if args.failure_rows_csv_limit < 1:
        raise ValueError("--failure-rows-csv-limit must be >= 1")
    return FailureRowsConfig(
        mode=args.failure_rows_mode,
        terminal_limit=args.failure_rows_limit,
        csv_limit=args.failure_rows_csv_limit,
        csv_dir=Path(args.failure_rows_dir),
    )


def _handle_run(
        config: str,
        tests_dir: str,
        color: str,
        args: argparse.Namespace
        ) -> int:
    """Execute ``smallex run`` and map outcomes to an exit code."""

    started = time.perf_counter()
    color_enabled = _use_color(color)
    config_path = Path(config)
    tests_path = Path(tests_dir)

    try:
        db_config = load_config(config_path, env=args.env)
        failure_rows_cfg = _build_failure_rows_config(args)
        results, failed = run_all(
            config_path,
            tests_path,
            env=args.env,
            failure_rows=failure_rows_cfg,
            selector=args.target,
        )
    except Exception as exc:  # pragma: no cover - surfaced as CLI error
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    _print_header(
        collected=len(results),
        color_enabled=color_enabled,
        engine_name=db_config.engine,
        connection_details=_safe_connection_details(db_config.connection),
    )
    if results:
        _print_test_progress(results, color_enabled=color_enabled)
    duration = time.perf_counter() - started
    _print_failures(results, color_enabled=color_enabled,
                    failure_rows_cfg=failure_rows_cfg)
    _print_footer(results, duration, color_enabled=color_enabled)
    return 1 if failed else 0


def _handle_init(
        engine: str,
        config: str,
        tests_dir: str,
        *,
        force: bool
        ) -> int:
    config_path = Path(config)
    tests_path = Path(tests_dir)
    sample_test_path = tests_path / "01_no_null_emails.sql"

    try:
        _write_if_allowed(
            config_path, _build_starter_config(engine), force=force)
        _write_if_allowed(sample_test_path,
                          _build_starter_test_sql(), force=force)
    except Exception as exc:  # pragma: no cover - surfaced as CLI error
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    print(f"Created config: {config_path}")
    print(f"Created sample test: {sample_test_path}")
    print("Next step: run `smallex validate-config` then `smallex run`.")
    return 0


def _handle_validate_config(config: str, env: str | None) -> int:
    config_path = Path(config)
    db_config = None
    try:
        db_config = load_config(config_path, env=env)
        backend = get_backend(db_config.engine)
        with closing(backend.connect(db_config.connection)) as connection:
            backend.test_connection(connection, db_config.connection)
    except Exception as exc:  # pragma: no cover - surfaced as CLI error
        print("Config validation: FAILED", file=sys.stderr)
        print(
            f"Engine: {db_config.engine if db_config is not None else 'unknown'}",  # noqa: E501
            file=sys.stderr,
        )
        print(
            "Connection keys: "
            + (
                _safe_connection_details(db_config.connection)
                if db_config is not None
                else "unknown"
            ),
            file=sys.stderr,
        )
        if env is not None:
            print(f"Environment: {env}", file=sys.stderr)
        connection_hint = _connection_error_hint(exc)
        if connection_hint is not None:
            print(connection_hint, file=sys.stderr)
        print(f"Error: {exc}", file=sys.stderr)
        print(f"Hint: {_diagnostic_hint(exc)}", file=sys.stderr)
        return 2

    print("Config validation: OK")
    print(f"Engine: {db_config.engine}")
    if env is not None:
        print(f"Environment: {env}")
    print(f"Connection keys: {_safe_connection_details(db_config.connection)}")
    return 0


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint used by both console script and tests."""

    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "run":
        return _handle_run(args.config, args.tests_dir, args.color, args)
    if args.command == "init":
        return _handle_init(
            args.engine, args.config, args.tests_dir, force=args.force
        )
    if args.command == "validate-config":
        return _handle_validate_config(args.config, args.env)

    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
