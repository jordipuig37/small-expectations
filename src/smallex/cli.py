"""Command-line interface for small-expectations."""

from __future__ import annotations

import argparse
import os
import platform
import shutil
import sys
import time
from pathlib import Path

from smallex import __version__
from smallex.runner import TestResult, load_config, run_all

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
    """Decide whether ANSI colors should be enabled.

    Args:
        mode: Color mode from CLI options.

    Returns:
        bool: ``True`` when color output should be used.
    """

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
    """Build a pytest-like section separator line.

    Args:
        title: Section title text.
        color_enabled: Whether ANSI coloring is enabled.
        title_color: Optional ANSI color for the title text.
        title_bold: Whether title text should be bold.
        line_color: Optional ANSI color for the separator lines.

    Returns:
        str: Formatted section separator.
    """

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


def _display_path(path: Path) -> str:
    """Render a path in a terminal-friendly form.

    Args:
        path: Path to display.

    Returns:
        str: Path relative to current working directory when possible.
    """

    try:
        return str(path.resolve().relative_to(Path.cwd()))
    except ValueError:
        return str(path)


def _safe_connection_details(connection: dict[str, object]) -> str:
    """Render safe connection detail keys without sensitive values."""

    keys = sorted(connection)
    return ", ".join(keys) if keys else "no connection options"


def build_parser() -> argparse.ArgumentParser:
    """Build the top-level command parser.

    Returns:
        argparse.ArgumentParser: Configured parser for the ``smallex`` CLI.
    """

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
    """Print one progress line per SQL test result."""

    for result in results:
        status = "." if result.passed else "F"
        status_color = GREEN if result.passed else RED
        print(
            f"{_display_path(result.path)} "
            f"{_paint(status, status_color, enabled=color_enabled)}"
        )


def _print_failures(results: list[TestResult], *, color_enabled: bool) -> None:
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
        print(_paint(_display_path(result.path), RED, enabled=color_enabled))
        print(
            _paint(
                "Query returned at least one row. Expected: zero rows.",
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
            print(f"{label} {_display_path(result.path)} - Query returned one or more rows")

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


def _handle_run(config: str, tests_dir: str, color: str) -> int:
    """Execute ``smallex run`` and map outcomes to an exit code.

    Args:
        config: Path to TOML config file.
        tests_dir: Directory containing SQL test files.
        color: Color output mode.

    Returns:
        int: Process-style exit code.
            - ``0``: success with no failures
            - ``1``: one or more failing SQL checks
            - ``2``: configuration/runtime error
    """

    started = time.perf_counter()
    color_enabled = _use_color(color)
    config_path = Path(config)
    tests_path = Path(tests_dir)

    try:
        db_config = load_config(config_path)
        results, failed = run_all(config_path, tests_path)
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
    _print_failures(results, color_enabled=color_enabled)
    _print_footer(results, duration, color_enabled=color_enabled)
    return 1 if failed else 0


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint used by both console script and tests.

    Args:
        argv: Optional argument vector, excluding executable name.

    Returns:
        int: Process-style exit code.
    """

    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "run":
        return _handle_run(args.config, args.tests_dir, args.color)

    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
