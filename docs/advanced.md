# Advanced Guide

This page covers features you will use in team workflows and CI.

## Recommended project layout

```text
.
├── smallex.toml
└── tests/
    ├── 01_no_null_emails.sql
    └── 02_business_rules.sql
```

Run from repository root:

```bash
smallex run
```

## Multiple tests inside one SQL file

You can declare multiple logical checks in a single file using metadata comments.

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

Behavior:

- `-- smallex:test:` starts a new logical test block
- `-- smallex:message:` adds custom failure text to that test
- if no `test` marker exists, the whole file becomes one test

## Useful command variants

Use custom config path:

```bash
smallex run --config config/smallex.prod.toml
```

Use custom tests directory:

```bash
smallex run --tests-dir expectations
```

Control color output:

```bash
smallex run --color auto
smallex run --color yes
smallex run --color no
```

## Failure rows output (debugging failed checks)

By default, failing rows are not printed/exported.

Show top failing rows in terminal:

```bash
smallex run \
  --failure-rows-mode terminal \
  --failure-rows-limit 5
```

Export failing rows to CSV files:

```bash
smallex run \
  --failure-rows-mode csv \
  --failure-rows-csv-limit 10000 \
  --failure-rows-dir .smallex/failures
```

Do both:

```bash
smallex run \
  --failure-rows-mode both \
  --failure-rows-limit 5 \
  --failure-rows-csv-limit 10000
```

CSV naming pattern:

- `<sql_file_stem>__<test_name>.csv`

## Exit codes for automation

- `0`: all checks passed
- `1`: one or more checks failed
- `2`: configuration/runtime error

This allows straightforward CI integration.

## CI example

```bash
smallex run --config smallex.toml --tests-dir tests
```

Fail your pipeline when exit code is non-zero.

## Common rollout practices for data teams

- Keep checks near the data project code (`tests/` or `expectations/`).
- Start with high-signal rules (nulls, uniqueness, referential integrity).
- Use custom `--smallex:message` values as runbook hints for fast triage.
- Use CSV export mode in CI to preserve evidence for failed checks.
