"""

Custom exception hierarchy for the TrakSYS MCP Server.

All application-specific errors inherit from TrakSYSError, making it
easy to catch any application error at the boundary without masking
unrelated Python exceptions.

Import pattern for other modules:
    from traksys_mcp.exceptions import DatabaseError, QueryTimeoutError
"""


class TrakSYSError(Exception):
    """
    Root exception for all TrakSYS MCP Server errors.

    Catching this catches any application error while leaving
    standard Python exceptions (ValueError, TypeError, etc.) untouched.
    """
    pass


class DatabaseError(TrakSYSError):
    """
    General database operation failure.

    Raised when a query fails for a reason that is not a timeout
    and not a connection issue — e.g. malformed SQL that passes
    validation but fails at the driver level.
    """
    pass


class ConnectionsError(DatabaseError):
    """
    Failed to establish or maintain a database connection.

    Raised by the connection context manager when pyodbc cannot
    connect within the configured timeout.
    """
    pass


class QueryTimeoutError(DatabaseError):
    """
    Query execution exceeded the configured timeout.

    Raised when asyncio.wait_for() cancels a query that runs longer
    than MSSQL_QUERY_TIMEOUT seconds.
    """
    pass


class SecurityError(TrakSYSError):
    """
    SQL query blocked by the security policy engine.

    Raised when a query contains always-banned patterns (xp_cmdshell,
    KILL, SHUTDOWN) or write operations while READ_ONLY=true.
    Tools should return this as an error dict, not let it propagate.
    """
    pass


class ValidationError(TrakSYSError):
    """
    Input validation failure before the query reaches the database.

    Raised for empty SQL, multi-statement queries (semicolons),
    or queries exceeding MAX_ROWS / query length limits.
    Distinct from SecurityError — this is malformed input, not an attack.
    """
    pass