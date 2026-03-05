"""Command-line interface for small-expectations."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from smallex.runner import run_all


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
    return parser


def _handle_run(config: str, tests_dir: str) -> int:
    """Execute ``smallex run`` and map outcomes to an exit code.

    Args:
        config: Path to TOML config file.
        tests_dir: Directory containing SQL test files.

    Returns:
        int: Process-style exit code.
            - ``0``: success with no failures
            - ``1``: one or more failing SQL checks
            - ``2``: configuration/runtime error
    """

    try:
        results, failed = run_all(Path(config), Path(tests_dir))
    except Exception as exc:  # pragma: no cover - surfaced as CLI error behavior
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    if not results:
        print("No SQL tests found.")
        return 0

    for result in results:
        status = "PASS" if result.passed else "FAIL"
        print(f"[{status}] {result.path}")

    passed = len(results) - failed
    print(f"\nSummary: {passed} passed, {failed} failed, {len(results)} total")
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
        return _handle_run(args.config, args.tests_dir)

    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
