"""SQL test file parsing utilities."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

TEST_MARKER = "-- smallex:test:"
MESSAGE_MARKER = "-- smallex:message:"


@dataclass(frozen=True)
class SQLTestCase:
    """A single executable SQL expectation parsed from test files.

    Attributes:
        path: Source SQL file path.
        name: Human-readable test name.
        message: Optional failure message authored by the developer.
        query: SQL query text to execute.
    """

    path: Path
    name: str
    message: str | None
    query: str

    @property
    def node_id(self) -> str:
        """Return pytest-like node id for terminal reporting."""

        return f"{self.path}::{self.name}"


def _parse_marker_value(line: str, marker: str) -> str:
    """Extract and normalize marker payload from a comment line."""

    return line[len(marker):].strip()


def _build_default_name(path: Path, case_index: int) -> str:
    """Build deterministic fallback name when marker is not provided."""

    if case_index == 1:
        return path.stem
    return f"{path.stem}_{case_index}"


def _finalize_case(
    *,
    cases: list[SQLTestCase],
    path: Path,
    case_index: int,
    pending_name: str | None,
    pending_message: str | None,
    sql_lines: list[str],
) -> int:
    """Finalize a buffered SQL case if it contains executable SQL."""

    query = "".join(sql_lines).strip()
    if not query:
        return case_index

    case_index += 1
    name = pending_name if pending_name else _build_default_name(
        path, case_index)
    cases.append(SQLTestCase(path=path, name=name,
                 message=pending_message, query=query))
    return case_index


def _split_sql_statements(sql_text: str) -> list[str]:
    """Split SQL text into statements, preserving semicolons when present."""

    statements: list[str] = []
    buffer: list[str] = []
    in_single = False
    in_double = False
    index = 0
    length = len(sql_text)

    while index < length:
        char = sql_text[index]

        if char == "'" and not in_double:
            if in_single and index + 1 < length and sql_text[index + 1] == "'":
                buffer.append("''")
                index += 2
                continue
            in_single = not in_single
            buffer.append(char)
            index += 1
            continue

        if char == '"' and not in_single:
            if in_double and index + 1 < length and sql_text[index + 1] == '"':
                buffer.append('""')
                index += 2
                continue
            in_double = not in_double
            buffer.append(char)
            index += 1
            continue

        if char == ";" and not in_single and not in_double:
            buffer.append(char)
            statement = "".join(buffer).strip()
            if statement:
                statements.append(statement)
            buffer = []
            index += 1
            continue

        buffer.append(char)
        index += 1

    statement = "".join(buffer).strip()
    if statement:
        statements.append(statement)

    return statements


def parse_sql_file(path: Path) -> list[SQLTestCase]:
    """Parse one SQL file into one or more test cases.

    Supported metadata markers:
        ``-- smallex:test: <name>``
        ``-- smallex:message: <message>``

    Marker semantics:
        - ``test`` starts a new logical test block when encountered after SQL.
        - ``message`` attaches to the next finalized test block.
        - files without markers split into one test per SQL statement.

    Args:
        path: SQL file to parse.

    Returns:
        list[SQLTestCase]: Parsed SQL test cases in file order.
    """

    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    cases: list[SQLTestCase] = []
    sql_lines: list[str] = []
    pending_name: str | None = None
    pending_message: str | None = None
    case_index = 0

    has_markers = False

    for line in lines:
        stripped = line.strip()
        if stripped.startswith(TEST_MARKER):
            has_markers = True
            case_index = _finalize_case(
                cases=cases,
                path=path,
                case_index=case_index,
                pending_name=pending_name,
                pending_message=pending_message,
                sql_lines=sql_lines,
            )
            sql_lines = []
            pending_name = _parse_marker_value(stripped, TEST_MARKER) or None
            pending_message = None
            continue

        if stripped.startswith(MESSAGE_MARKER):
            has_markers = True
            pending_message = _parse_marker_value(
                stripped, MESSAGE_MARKER) or None
            continue

        sql_lines.append(line)

    if has_markers:
        _finalize_case(
            cases=cases,
            path=path,
            case_index=case_index,
            pending_name=pending_name,
            pending_message=pending_message,
            sql_lines=sql_lines,
        )
        return cases

    for statement in _split_sql_statements("".join(lines)):
        case_index += 1
        cases.append(
            SQLTestCase(
                path=path,
                name=_build_default_name(path, case_index),
                message=None,
                query=statement,
            )
        )

    return cases


def parse_sql_files(paths: Iterable[Path]) -> list[SQLTestCase]:
    """Parse multiple SQL files into a flat list of SQL test cases."""

    cases: list[SQLTestCase] = []
    for path in paths:
        cases.extend(parse_sql_file(path))
    return cases
