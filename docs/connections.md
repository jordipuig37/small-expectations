# Connection Specs

`small-expectations` supports `sqlite`, `snowflake`, and `databricks`.

Connection values are read from:

```toml
[database]
engine = "..."

[database.connection]
# backend-specific connector args
```

All keys under `[database.connection]` are passed directly to the selected Python connector.

## SQLite

Connector module: `sqlite3.connect(...)`

Required keys:

- `database`: path to `.db` file (or `:memory:`)

Minimal example:

```toml
[database]
engine = "sqlite"

[database.connection]
database = "example.db"
```

Common optional keys (passed through):

- `timeout`
- `detect_types`
- `isolation_level`
- `check_same_thread`
- `uri`

URI example:

```toml
[database]
engine = "sqlite"

[database.connection]
database = "file:example.db?mode=ro"
uri = true
```

## Snowflake

Connector module: `snowflake.connector.connect(...)`

Required keys validated by `small-expectations`:

- `account`
- `user`
- `password`
- `warehouse`
- `database`
- `schema`

Minimal example:

```toml
[database]
engine = "snowflake"

[database.connection]
account = "xy12345.eu-west-1"
user = "analytics_user"
password = "your-password"
warehouse = "COMPUTE_WH"
database = "ANALYTICS"
schema = "PUBLIC"
```

Common optional keys (passed through):

- `role`
- `authenticator`
- `session_parameters`
- `client_session_keep_alive`
- `application`

## Databricks

Connector module: `databricks.sql.connect(...)`

Required keys validated by `small-expectations`:

- `server_hostname`
- `http_path`
- `access_token`

Minimal example:

```toml
[database]
engine = "databricks"

[database.connection]
server_hostname = "adb-1234567890123456.7.azuredatabricks.net"
http_path = "/sql/1.0/warehouses/abc123"
access_token = "dapi..."
```

Common optional keys (passed through):

- `catalog`
- `schema`
- `session_configuration`
- `http_headers`

Note: `small-expectations` does not expand environment variables inside TOML values by itself. If you need secret injection, generate the TOML file before running or use your CI/CD secret templating flow.

## Validation errors you may see

Missing required fields are validated before connecting.

Example:

```text
Backend 'snowflake' is missing required connection fields: schema
```

Unknown engine example:

```text
Unsupported database engine 'postgres'. Supported: databricks, snowflake, sqlite
```
