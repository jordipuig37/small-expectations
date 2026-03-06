# small-expectations

Simple SQL-based expectations runner.

## Install

```bash
pip install .
```

## Usage

Create `smallex.toml`:

```toml
[database]
engine = "sqlite"

[database.connection]
database = "example.db"
```

Supported engines:

- `sqlite`
- `snowflake`
- `databricks`

Example `snowflake` config:

```toml
[database]
engine = "snowflake"

[database.connection]
account = "my-account"
user = "my-user"
password = "my-password"
warehouse = "my-warehouse"
database = "my-database"
schema = "public"
```

Example `databricks` config:

```toml
[database]
engine = "databricks"

[database.connection]
server_hostname = "adb-1234567890123456.7.azuredatabricks.net"
http_path = "/sql/1.0/warehouses/abc123"
access_token = "dapi..."
```

Add SQL files under `tests/`:

```sql
SELECT * FROM users WHERE email IS NULL;
```

Run:

```bash
smallex run
```

A test passes when the query returns zero rows and fails if it returns one or more rows.

## Testing

The test suite includes:

- CLI + SQLite integration tests using a temporary local database.
- Backend unit tests that mock Snowflake and Databricks connectors so no real cloud connections are required.

## Documentation

This repository uses MkDocs + Material.

Run docs locally:

```bash
pip install ".[docs]"
mkdocs serve
```

Build static docs:

```bash
mkdocs build
```

GitHub Pages is deployed automatically from `.github/workflows/docs.yml` on pushes to `main`.
