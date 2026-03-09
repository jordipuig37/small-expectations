from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
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


def _write_env_config(path: Path, dev_db_path: Path, prod_db_path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "[database]",
                'engine = "sqlite"',
                'default_connection = "dev"',
                "",
                "[database.connections.dev]",
                f'database = "{dev_db_path}"',
                "",
                "[database.connections.prod]",
                f'database = "{prod_db_path}"',
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
    assert "test session starts" in out
    assert "collected 1 item" in out
    assert "no_null_emails.sql ." in out
    assert "FAILURES" not in out
    assert "1 passed in " in out


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
    assert "test session starts" in out
    assert "collected 1 item" in out
    assert "no_null_emails.sql F" in out
    assert "FAILURES" in out
    assert "short test summary info" in out
    assert "FAILED " in out
    assert "1 failed in " in out


def test_run_command_returns_error_for_missing_config(capsys: CaptureFixture[str]) -> None:
    exit_code = main(["run", "--config", "missing.toml", "--tests-dir", "tests"])
    err = capsys.readouterr().err

    assert exit_code == 2
    assert "Error:" in err


def test_run_command_help_displays_options(capsys: CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as raised:
        main(["run", "--help"])

    out = capsys.readouterr().out
    assert raised.value.code == 0
    assert "Run SQL expectation tests from .sql files." in out
    assert "--config CONFIG" in out
    assert "--tests-dir TESTS_DIR" in out


def test_run_command_supports_forced_color_output(
    tmp_path: Path, capsys: CaptureFixture[str]
) -> None:
    db_path = tmp_path / "test.db"
    config_path = tmp_path / "smallex.toml"
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    _write_config(config_path, db_path)

    with sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, email TEXT)")
        conn.commit()

    (tests_dir / "no_null_emails.sql").write_text(
        "SELECT * FROM users WHERE email IS NULL;",
        encoding="utf-8",
    )

    exit_code = main(
        [
            "run",
            "--config",
            str(config_path),
            "--tests-dir",
            str(tests_dir),
            "--color",
            "yes",
        ]
    )
    out = capsys.readouterr().out

    assert exit_code == 0
    assert "\x1b[" in out


def test_run_command_supports_message_and_multi_query_blocks(
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
        conn.execute("INSERT INTO users (email) VALUES ('ok@example.com')")
        conn.commit()

    (tests_dir / "users.sql").write_text(
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

    exit_code = main(
        [
            "run",
            "--config",
            str(config_path),
            "--tests-dir",
            str(tests_dir),
            "--failure-rows-mode",
            "terminal",
            "--failure-rows-limit",
            "5",
        ]
    )
    out = capsys.readouterr().out

    assert exit_code == 1
    assert "collected 2 items" in out
    assert "users.sql F." in out
    assert "users.email should never be null" in out
    assert "Sample failing rows" in out


def test_run_command_supports_failure_csv_export(
    tmp_path: Path, capsys: CaptureFixture[str]
) -> None:
    db_path = tmp_path / "test.db"
    config_path = tmp_path / "smallex.toml"
    tests_dir = tmp_path / "tests"
    output_dir = tmp_path / "failures"
    tests_dir.mkdir()
    _write_config(config_path, db_path)

    with sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, email TEXT)")
        conn.execute("INSERT INTO users (email) VALUES (NULL)")
        conn.commit()

    (tests_dir / "users.sql").write_text(
        "SELECT id, email FROM users WHERE email IS NULL;",
        encoding="utf-8",
    )

    exit_code = main(
        [
            "run",
            "--config",
            str(config_path),
            "--tests-dir",
            str(tests_dir),
            "--failure-rows-mode",
            "csv",
            "--failure-rows-dir",
            str(output_dir),
            "--failure-rows-csv-limit",
            "10000",
        ]
    )
    out = capsys.readouterr().out

    assert exit_code == 1
    assert "Failure rows CSV:" in out
    csv_files = list(output_dir.glob("*.csv"))
    assert len(csv_files) == 1
    content = csv_files[0].read_text(encoding="utf-8")
    assert "id,email" in content


def test_run_command_supports_named_connection_environment(
    tmp_path: Path, capsys: CaptureFixture[str]
) -> None:
    dev_db_path = tmp_path / "dev.db"
    prod_db_path = tmp_path / "prod.db"
    config_path = tmp_path / "smallex.toml"
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    _write_env_config(config_path, dev_db_path, prod_db_path)

    with sqlite3.connect(dev_db_path) as conn:
        conn.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, email TEXT)")
        conn.commit()

    with sqlite3.connect(prod_db_path) as conn:
        conn.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, email TEXT)")
        conn.execute("INSERT INTO users (email) VALUES (NULL)")
        conn.commit()

    (tests_dir / "no_null_emails.sql").write_text(
        "SELECT * FROM users WHERE email IS NULL;",
        encoding="utf-8",
    )

    exit_code_default = main(
        ["run", "--config", str(config_path), "--tests-dir", str(tests_dir)]
    )
    out_default = capsys.readouterr().out
    assert exit_code_default == 0
    assert "1 passed in " in out_default

    exit_code_prod = main(
        [
            "run",
            "--config",
            str(config_path),
            "--tests-dir",
            str(tests_dir),
            "--env",
            "prod",
        ]
    )
    out_prod = capsys.readouterr().out
    assert exit_code_prod == 1
    assert "1 failed in " in out_prod
