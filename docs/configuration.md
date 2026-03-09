# Configuration Reference

The CLI reads TOML config from `smallex.toml` by default.

## Schema

```toml
[database]
engine = "sqlite" # sqlite | snowflake | databricks

[database.connection]
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
