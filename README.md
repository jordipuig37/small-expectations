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

You can define multiple tests in one SQL file with metadata comments:

```sql
-- smallex:test: no_null_emails
-- smallex:message: users.email should never be null
SELECT id, email
FROM users
WHERE email IS NULL;

-- smallex:test: no_duplicate_emails
-- smallex:message: users.email should be unique
SELECT email, COUNT(*) AS duplicates
FROM users
WHERE email IS NOT NULL
GROUP BY email
HAVING COUNT(*) > 1;
```

Metadata markers:

- `-- smallex:test: <name>`: logical test name (used in output as `file.sql::<name>`).
- `-- smallex:message: <message>`: failure message shown in terminal summary and failure details.

Run:

```bash
smallex run
```

A test passes when the query returns zero rows and fails if it returns one or more rows.
The terminal report follows a pytest-like style (session header, per-test `.`/`F`,
failure details, and short summary info).

### Failure rows output

By default, failing rows are not printed or exported.

You can configure this behavior:

```bash
smallex run \
  --failure-rows-mode terminal \
  --failure-rows-limit 5
```

```bash
smallex run \
  --failure-rows-mode csv \
  --failure-rows-csv-limit 10000 \
  --failure-rows-dir .smallex/failures
```

```bash
smallex run \
  --failure-rows-mode both \
  --failure-rows-limit 5 \
  --failure-rows-csv-limit 10000
```

Options:

- `--failure-rows-mode`: `none | terminal | csv | both` (default: `none`)
- `--failure-rows-limit`: top rows shown in terminal per failing test (default: `5`)
- `--failure-rows-csv-limit`: max rows written to CSV per failing test (default: `10000`)
- `--failure-rows-dir`: output directory for CSV files (default: `.smallex/failures`)

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
