## Security Best Practices

When using MSSQL MCP Python, follow these security practices:

### 1. Connection Strings
- Never commit connection strings to version control
- Use environment variables or secure configuration management
- Restrict database user permissions to minimum required

### 2. Read-Only Mode
- Keep `READ_ONLY=true` (default) unless write operations are necessary
- Only enable writes with `ENABLE_WRITES=true` in controlled environments
- Use the `ADMIN_CONFIRM` token for write operations

### 3. Network Security
- Use firewall rules to restrict access to the MCP server
- Consider using VPN or private networks for database connections
- Enable TLS/SSL for SQL Server connections when possible

### 4. Query Limits
- Configure appropriate `MSSQL_QUERY_TIMEOUT` values
- Set `MAX_ROWS` to prevent excessive data retrieval
- Monitor query patterns for suspicious activity

### 5. Logging and Monitoring
- Enable structured logging with `LOG_FORMAT=json`
- Monitor logs for blocked queries and security events
- Set up alerts for unusual query patterns
- Use Prometheus metrics to track security-relevant events

### 6. Updates
- Keep dependencies up to date
- Regularly update to the latest version of MSSQL MCP Python
- Subscribe to security advisories for dependencies

## Known Security Features

✅ **SQL Injection Prevention**
- Parameterized queries via pyodbc
- Multi-statement query blocking
- Banned keyword detection

✅ **Sensitive Data Protection**
- Automatic log redaction for passwords and connection strings
- Query hashing for safe logging
- No credentials in response bodies

✅ **Resource Limits**
- Query timeouts (default 30s)
- Row limits (default 50,000 rows)
- Query length limits (50KB)

✅ **Audit Trail**
- Structured logging with request metadata
- Query metrics and statistics
- Client ID tracking
