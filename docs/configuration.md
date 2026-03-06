# Configuration

The CLI reads configuration from a TOML file (`smallex.toml` by default).

## Basic format

```toml
[database]
engine = "sqlite"

[database.connection]
database = "example.db"
```

## `database.engine`

Supported values:

- `sqlite`
- `snowflake`
- `databricks`

## `database.connection`

A table of connector keyword arguments passed directly to the selected backend.

### SQLite example

```toml
[database]
engine = "sqlite"

[database.connection]
database = "example.db"
```

### Snowflake example

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

### Databricks example

```toml
[database]
engine = "databricks"

[database.connection]
server_hostname = "adb-1234567890123456.7.azuredatabricks.net"
http_path = "/sql/1.0/warehouses/abc123"
access_token = "dapi..."
```

## Legacy compatibility

If `database.connection` is not present, top-level keys inside `[database]` (except `engine` and `module`) are treated as connection options.
