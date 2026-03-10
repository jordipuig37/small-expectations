# Quickstart

Get from zero to first passing check in under 5 minutes.

## 1. Install

```bash
pip install small-expectations
```

## 2. Create config

Fast path:

```bash
smallex init --engine sqlite
```

Or create `smallex.toml` manually:

Create `smallex.toml`:

```toml
[database]
engine = "sqlite"

[database.connection]
database = "example.db"
```

## 3. Add a SQL check

Create `tests/01_no_null_emails.sql`:

```sql
SELECT *
FROM users
WHERE email IS NULL;
```

Rule of thumb:

- returns `0` rows => pass
- returns `>= 1` row => fail

## 4. Run

```bash
smallex run
```

You will see a pytest-style report with:

- test session header
- per-test progress (`.` for pass, `F` for fail)
- optional failure details
- final summary and proper exit code

## 5. Next steps

- For production usage patterns, go to `Advanced Guide`.
- For backend connection settings, go to `Connection Specs`.
- For all CLI options, go to `CLI Reference`.
