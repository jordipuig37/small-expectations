# CLI

## Command

```bash
smallex run [--config PATH] [--tests-dir PATH]
```

## Options

- `--config`: path to TOML config file. Default: `smallex.toml`.
- `--tests-dir`: directory containing `.sql` tests. Default: `tests`.

## Output

For each SQL file, the CLI prints either `PASS` or `FAIL`.

At the end, it prints a summary:

```text
Summary: <passed> passed, <failed> failed, <total> total
```

## Exit codes

- `0`: command succeeded and there were no failed checks
- `1`: one or more checks failed
- `2`: invalid configuration or runtime error
