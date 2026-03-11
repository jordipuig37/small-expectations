from __future__ import annotations

from pathlib import Path

from smallex.sqltests import parse_sql_file


def test_parse_sql_file_without_markers_returns_single_case(
        tmp_path: Path
        ) -> None:
    sql_path = tmp_path / "simple.sql"
    sql_path.write_text("SELECT 1;", encoding="utf-8")

    cases = parse_sql_file(sql_path)

    assert len(cases) == 1
    assert cases[0].name == "simple"
    assert cases[0].message is None
    assert cases[0].query == "SELECT 1;"


def test_parse_sql_file_with_markers_returns_multiple_cases(
        tmp_path: Path
        ) -> None:
    sql_path = tmp_path / "users.sql"
    sql_path.write_text(
        "\n".join(
            [
                "-- smallex:test: no_null_emails",
                "-- smallex:message: users.email should never be null",
                "SELECT id, email FROM users WHERE email IS NULL;",
                "",
                "-- smallex:test: no_blank_emails",
                "-- smallex:message: users.email should never be blank",
                "SELECT id, email FROM users WHERE email = '';",
            ]
        ),
        encoding="utf-8",
    )

    cases = parse_sql_file(sql_path)

    assert len(cases) == 2
    assert cases[0].name == "no_null_emails"
    assert cases[0].message == "users.email should never be null"
    assert "IS NULL" in cases[0].query
    assert cases[1].name == "no_blank_emails"
    assert cases[1].message == "users.email should never be blank"
    assert "email = ''" in cases[1].query


def test_parse_sql_file_without_markers_splits_statements(
        tmp_path: Path
        ) -> None:
    sql_path = tmp_path / "multi.sql"
    sql_path.write_text(
        "\n".join(
            [
                "SELECT 1;",
                "",
                "SELECT 2;",
            ]
        ),
        encoding="utf-8",
    )

    cases = parse_sql_file(sql_path)

    assert len(cases) == 2
    assert cases[0].name == "multi"
    assert cases[0].query == "SELECT 1;"
    assert cases[1].name == "multi_2"
    assert cases[1].query == "SELECT 2;"
