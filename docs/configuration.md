# Configuration Reference

The CLI reads TOML config from `smallex.toml` by default.

## Schema

```toml
[database]
engine = "sqlite" # sqlite | snowflake | databricks
default_connection = "dev" # optional

[database.connection]
# backend-specific connector args

[database.connections.dev]
# backend-specific connector args

[database.connections.prod]
# backend-specific connector args
```

## `database.engine`

Allowed values:

- `sqlite`
- `snowflake`
- `databricks`

## `database.connection`

A table containing connector arguments. Values are passed directly to the selected connector after required field validation.

See `Connection Specs` for backend-by-backend required and optional fields.

## `database.connections`

Use this table to define multiple named connection environments in a single file:

- `[database.connections.<name>]` for each environment (`dev`, `development`, `prod`, etc.)
- optional `[database].default_connection` to select a default when `--env` is not provided

Selection behavior:

- If `smallex run --env <name>` is used, that named connection is selected.
- If `--env` is omitted and `default_connection` exists, that connection is selected.
- If `--env` is omitted and `default_connection` is missing, `default` is used when present.
- If exactly one named connection exists, it is used automatically.
- If multiple named connections exist without default and without `--env`, the run fails with a config error.

## Legacy compatibility

For backward compatibility, if `[database.connection]` is missing, keys in `[database]` (except `engine` and `module`) are treated as connection options.

Legacy-style SQLite example:

```toml
[database]
engine = "sqlite"
database = "example.db"
```

## File location and CLI override

Default file path:

- `smallex.toml`

Override path with:

```bash
smallex run --config path/to/smallex.toml
```
