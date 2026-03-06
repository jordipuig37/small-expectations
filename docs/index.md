# small-expectations

`small-expectations` is a lightweight Python library and CLI that runs SQL checks against your database.

A SQL file passes when it returns zero rows, and fails when it returns one or more rows.

## Installation

From PyPI:

```bash
pip install small-expectations
```

From source in this repository:

```bash
pip install .
```

## Quickstart

Create a config file named `smallex.toml`:

```toml
[database]
engine = "sqlite"

[database.connection]
database = "example.db"
```

Add SQL checks under a folder (for example `tests/`):

```sql
SELECT * FROM users WHERE email IS NULL;
```

Run checks:

```bash
smallex run
```

Expected behavior:

- query returns no rows: `PASS`
- query returns at least one row: `FAIL`

## Supported Engines

- `sqlite`
- `snowflake`
- `databricks`
