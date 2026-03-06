"""Command-line interface for small-expectations."""

from __future__ import annotations

import argparse
import os
import platform
import shutil
import sys
import time
from pathlib import Path
from typing import Sequence

from smallex import __version__
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

    keys = sorted(connection)
    # [ ] render only the account, database, schema, user and role, and instead
    # of returning the keys, return the values
    return ", ".join(keys) if keys else "no connection options"


def _display_path(path: Path) -> str:
    """Render a path in a terminal-friendly form."""

    try:
        return str(path.resolve().relative_to(Path.cwd()))
    except ValueError:
        return str(path)


def _format_row(columns: Sequence[str], row: Sequence[object]) -> str:
    """Render one result row as compact key=value entries."""

    pairs: list[str] = []
    for index, value in enumerate(row):
        key = columns[index] if index < len(columns) else f"column_{index + 1}"
        pairs.append(f"{key}={value!r}")
    return ", ".join(pairs)


def build_parser() -> argparse.ArgumentParser:
    """Build the top-level command parser."""

    parser = argparse.ArgumentParser(prog="smallex")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Run SQL tests.")
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
    return parser


def _print_header(
    collected: int,
    *,
    color_enabled: bool,
    engine_name: str,
    connection_details: str,
) -> None:
    """Print pytest-like session header lines."""

    print(_section("test session starts", color_enabled=color_enabled, title_bold=True))
    print(
        f"platform {platform.system().lower()} -- Python {platform.python_version()}, "
        f"smallex-{__version__}"
    )
    print(f"database: {engine_name} ({connection_details})")
    print(f"rootdir: {Path.cwd()}")
    label = "item" if collected == 1 else "items"
    print(_paint(f"collected {collected} {label}", enabled=color_enabled, bold=True))
    print()


def _print_test_progress(results: list[TestResult], *, color_enabled: bool) -> None:
    """Print pytest-like progress grouped by SQL file."""

    grouped: dict[str, list[TestResult]] = {}
    for result in results:
        key = _display_path(result.path)
        grouped.setdefault(key, []).append(result)

    for path, file_results in grouped.items():
        colored_symbols = "".join(
            _paint("." if result.passed else "F", GREEN if result.passed else RED, enabled=color_enabled)
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
        if result.message:
            print(_paint(f"Message: {result.message}", RED, enabled=color_enabled))
        else:
            print(
                _paint(
                    "Message: Query returned at least one row. Expected: zero rows.",
                    RED,
                    enabled=color_enabled,
                )
            )
        if failure_rows_cfg.terminal_enabled() and result.sample_rows:
            print(
                _paint(
                    f"Sample failing rows (showing up to {failure_rows_cfg.terminal_limit}):",
                    RED,
                    enabled=color_enabled,
                )
            )
            for row in result.sample_rows:
                print(_paint(f"  - {_format_row(result.columns, row)}", RED, enabled=color_enabled))
            if result.has_more_rows:
                print(
                    _paint(
                        f"  ... more rows exist (showing first {len(result.sample_rows)})",
                        RED,
                        enabled=color_enabled,
                    )
                )
        if result.csv_path is not None:
            print(_paint(f"Failure rows CSV: {result.csv_path}", RED, enabled=color_enabled))


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
            detail = result.message if result.message else "Query returned one or more rows"
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


def _handle_run(config: str, tests_dir: str, color: str, args: argparse.Namespace) -> int:
    """Execute ``smallex run`` and map outcomes to an exit code."""

    started = time.perf_counter()
    color_enabled = _use_color(color)
    config_path = Path(config)
    tests_path = Path(tests_dir)

    try:
        db_config = load_config(config_path)
        failure_rows_cfg = _build_failure_rows_config(args)
        results, failed = run_all(
            config_path,
            tests_path,
            failure_rows=failure_rows_cfg,
        )
    except Exception as exc:  # pragma: no cover - surfaced as CLI error behavior
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
    _print_failures(results, color_enabled=color_enabled, failure_rows_cfg=failure_rows_cfg)
    _print_footer(results, duration, color_enabled=color_enabled)
    return 1 if failed else 0


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint used by both console script and tests."""

    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "run":
        return _handle_run(args.config, args.tests_dir, args.color, args)

    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
