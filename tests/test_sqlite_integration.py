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


def test_run_command_with_sql_folder_fixture(
    tmp_path: Path, capsys: CaptureFixture[str]
) -> None:
    db_path = tmp_path / "sample.db"
    config_path = tmp_path / "smallex.toml"
    _write_config(config_path, db_path)

    with sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, email TEXT)")
        conn.execute("INSERT INTO users (email) VALUES ('alice@example.com')")
        conn.execute("INSERT INTO users (email) VALUES ('bob@example.com')")
        conn.execute("INSERT INTO users (email) VALUES (NULL)")
        conn.commit()

    sql_dir = Path(__file__).parent / "sql"
    exit_code = main(
        ["run", "--config", str(config_path), "--tests-dir", str(sql_dir)]
    )
    out = capsys.readouterr().out

    assert exit_code == 1
    assert "test session starts" in out
    assert "collected 2 items" in out
    assert "01_no_empty_emails.sql ." in out
    assert "02_no_null_emails.sql F" in out
    assert "FAILURES" in out
    assert "short test summary info" in out
    assert "FAILED " in out
    assert "1 failed, 1 passed in " in out
