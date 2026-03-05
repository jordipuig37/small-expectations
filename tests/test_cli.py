from __future__ import annotations

import sqlite3
from pathlib import Path

from pytest import CaptureFixture

from smallex.cli import main


def _write_config(path: Path, db_path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "[database]",
                'engine = "sqlite"',
                "",
                "[database.connection]",
                f'database = "{db_path}"',
            ]
        ),
        encoding="utf-8",
    )


def test_run_command_passes_when_query_returns_no_rows(
    tmp_path: Path, capsys: CaptureFixture[str]
) -> None:
    db_path = tmp_path / "test.db"
    config_path = tmp_path / "smallex.toml"
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    _write_config(config_path, db_path)

    with sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, email TEXT)")
        conn.execute("INSERT INTO users (email) VALUES ('a@example.com')")
        conn.commit()

    (tests_dir / "no_null_emails.sql").write_text(
        "SELECT * FROM users WHERE email IS NULL;",
        encoding="utf-8",
    )

    exit_code = main(
        ["run", "--config", str(config_path), "--tests-dir", str(tests_dir)]
    )
    out = capsys.readouterr().out

    assert exit_code == 0
    assert "[PASS]" in out
    assert "1 passed, 0 failed, 1 total" in out


def test_run_command_fails_when_query_returns_rows(
    tmp_path: Path, capsys: CaptureFixture[str]
) -> None:
    db_path = tmp_path / "test.db"
    config_path = tmp_path / "smallex.toml"
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    _write_config(config_path, db_path)

    with sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, email TEXT)")
        conn.execute("INSERT INTO users (email) VALUES (NULL)")
        conn.commit()

    (tests_dir / "no_null_emails.sql").write_text(
        "SELECT * FROM users WHERE email IS NULL;",
        encoding="utf-8",
    )

    exit_code = main(
        ["run", "--config", str(config_path), "--tests-dir", str(tests_dir)]
    )
    out = capsys.readouterr().out

    assert exit_code == 1
    assert "[FAIL]" in out
    assert "0 passed, 1 failed, 1 total" in out


def test_run_command_returns_error_for_missing_config(capsys: CaptureFixture[str]) -> None:
    exit_code = main(["run", "--config", "missing.toml", "--tests-dir", "tests"])
    err = capsys.readouterr().err

    assert exit_code == 2
    assert "Error:" in err
