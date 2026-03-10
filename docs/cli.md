# CLI Reference

## Main command

```bash
smallex run [options]
```

Other commands:

- `smallex init`: scaffold starter config + sample SQL test
- `smallex validate-config`: validate config and test database connectivity

## Options

- `--config`: path to TOML config file (default: `smallex.toml`)
- `--tests-dir`: root directory to discover `.sql` tests recursively (default: `tests`)
- `--env`: named database connection environment from `[database.connections.<name>]`
- `--color`: `auto | yes | no` (default: `auto`)
- `--failure-rows-mode`: `none | terminal | csv | both` (default: `none`)
- `--failure-rows-limit`: terminal rows per failing test (default: `5`)
- `--failure-rows-csv-limit`: max CSV rows per failing test (default: `10000`)
- `--failure-rows-dir`: CSV output directory (default: `.smallex/failures`)

## What the run does

1. Loads TOML config.
2. Discovers `.sql` files recursively under `--tests-dir`.
3. Parses one or more logical tests per file.
4. Executes each test query.
5. Marks pass when query returns zero rows; fail otherwise.
6. Prints pytest-style summary output.

## Exit codes

- `0`: all tests passed
- `1`: at least one test failed
- `2`: invalid config, invalid CLI args, or runtime error

## Examples

Basic run:

```bash
smallex run
```

Run from non-default config and tests location:

```bash
smallex run --config conf/smallex.toml --tests-dir expectations
```

Run with a specific connection environment:

```bash
smallex run --env dev
```

Initialize a new project:

```bash
smallex init --engine sqlite
```

Validate configuration and connection:

```bash
smallex validate-config --config smallex.toml --env dev
```

Show failing rows in terminal:

```bash
smallex run --failure-rows-mode terminal --failure-rows-limit 10
```

Export failing rows to CSV:

```bash
smallex run --failure-rows-mode csv --failure-rows-dir artifacts/smallex
```
