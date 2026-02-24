"""
Configuration management for the TrakSYS MCP Server.

Pydantic BaseSettings reads from the .env file and validates every field
on startup. If a required field is missing or a type is wrong, the server
crashes immediately with a clear message.

Usage: from traksys_mcp.config.setting import settings
"""

import re
import logging
from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    All runtime configuration loaded from environment / .env file.

    Security: MSSQL_CONNECTION_STRING uses SecretStr to prevent accidental
    credential leakage in logs, error messages, or debug output.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
        frozen=True,
    )

    # Database
    MSSQL_CONNECTION_STRING: SecretStr = Field(
        ...,
        description="ODBC connection string for SQL Server. Use Windows Auth or store credentials securely."
    )
    MSSQL_CONNECTION_TIMEOUT: int = Field(
        default=5,
        ge=1,
        le=120,
        description="Connection timeout in seconds (1-120)"
    )
    MSSQL_QUERY_TIMEOUT: int = Field(
        default=30,
        ge=1,
        le=300,
        description="Query execution timeout in seconds (1-300)"
    )

    # Security
    READ_ONLY: bool = Field(
        default=True,
        description="If True, only SELECT queries are allowed"
    )
    ENABLE_WRITES: bool = Field(
        default=False,
        description="Enable write operations — requires READ_ONLY=false"
    )
    MAX_ROWS: int = Field(
        default=1000,
        ge=1,
        le=50000,
        description="Maximum rows returned per query (DoS protection)"
    )
    MAX_QUERY_LENGTH: int = Field(
        default=8000,
        ge=1024,
        le=65535,
        description="Maximum query length in bytes (prevents injection attacks)"
    )

    # Server transport
    SERVER_TRANSPORT: str = Field(
        default="stdio",
        description="Transport mode: 'stdio' for local, 'http' for network"
    )
    HTTP_BIND_HOST: str = Field(
        default="0.0.0.0",
        description="Host to bind when using HTTP transport"
    )
    HTTP_BIND_PORT: int = Field(
        default=8080,
        ge=1,
        le=65535,
        description="Port to bind when using HTTP transport"
    )

    # Logging
    LOG_LEVEL: str = Field(
        default="INFO",
        description="Logging level: DEBUG, INFO, WARNING, ERROR, CRITICAL"
    )
    LOG_FORMAT: str = Field(
        default="text",
        description="Log output format: 'text' or 'json'"
    )

    # Validators
    @field_validator("LOG_LEVEL")
    @classmethod
    def valid_log_level(cls, value: str) -> str:
        """Validate log level against allowed values."""
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper = value.upper()
        if upper not in allowed:
            raise ValueError(f"LOG_LEVEL must be one of {allowed}, got '{value}'")
        return upper

    @field_validator("LOG_FORMAT")
    @classmethod
    def valid_log_format(cls, value: str) -> str:
        """Validate log format against allowed values."""
        allowed = {"json", "text"}
        lower = value.lower()
        if lower not in allowed:
            raise ValueError(f"LOG_FORMAT must be 'json' or 'text', got '{value}'")
        return lower

    @field_validator("SERVER_TRANSPORT")
    @classmethod
    def valid_transport(cls, value: str) -> str:
        """Validate transport mode."""
        allowed = {"stdio", "http"}
        lower = value.lower()
        if lower not in allowed:
            raise ValueError(f"SERVER_TRANSPORT must be 'stdio' or 'http', got '{value}'")
        return lower

    @field_validator("MSSQL_CONNECTION_STRING")
    @classmethod
    def validate_connection_string_format(cls, value: SecretStr) -> SecretStr:
        """
        Validate that connection string has expected format.

        This is a format check only — the actual string remains secret.
        """
        conn_str = value.get_secret_value()
        conn_lower = conn_str.strip().lower()

        valid_starts = (
            "driver={",
            "mssql+pyodbc://",
            "server=",
        )

        if not any(conn_lower.startswith(prefix) for prefix in valid_starts):
            raise ValueError(
                "MSSQL_CONNECTION_STRING must be a valid ODBC/SQLAlchemy connection string. "
                "Examples: 'Driver={ODBC Driver 17};Server=localhost;...'"
                " or 'mssql+pyodbc://user:pass@host/db?driver=...'"
            )

        if re.search(r"(pwd|password)\s*=", conn_lower):
            logging.warning(
                "Connection string contains inline credentials. "
                "Consider using Windows Authentication for better security."
            )

        return value

    @model_validator(mode="after")
    def writes_require_read_only_false(self) -> "Settings":
        """
        Guard: ENABLE_WRITES=true is meaningless if READ_ONLY is still true.

        This prevents accidental data modification in production.
        """
        if self.ENABLE_WRITES and self.READ_ONLY:
            raise ValueError(
                "Conflicting config: ENABLE_WRITES=true but READ_ONLY=true. "
                "Set READ_ONLY=false to allow writes, or keep READ_ONLY=true for safety."
            )
        return self

    def __repr__(self) -> str:
        """
        Safe string representation — never exposes credentials.

        This prevents accidental leakage if settings is printed in:
        - Exception tracebacks
        - Debug logging
        - Interactive Python sessions
        """
        return (
            f"Settings("
            f"MSSQL_CONNECTION_STRING=SecretStr('****'), "
            f"READ_ONLY={self.READ_ONLY}, "
            f"ENABLE_WRITES={self.ENABLE_WRITES}, "
            f"LOG_LEVEL={self.LOG_LEVEL}, "
            f"SERVER_TRANSPORT={self.SERVER_TRANSPORT}, "
            f"...)"
        )

    def __str__(self) -> str:
        """Delegate to __repr__ for consistency."""
        return self.__repr__()


settings = Settings()