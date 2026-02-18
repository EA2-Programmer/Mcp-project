"""
Configuration management for the TrakSYS MCP Server.

Pydantic BaseSettings reads from the .env file and validates every field
on startup. If a required field is missing or a type is wrong, the server
crashes immediately with a clear message

Usage: from traksys_mcp.setting import settings

"""

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    All runtime configuration loaded from environment / .env file.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
        frozen=False,
    )

    # Database
    MSSQL_CONNECTION_STRING: str
    MSSQL_CONNECTION_TIMEOUT: int = 5
    MSSQL_QUERY_TIMEOUT: int = 30

    # Security
    READ_ONLY: bool = True
    ENABLE_WRITES: bool = False
    MAX_ROWS: int = 1000
    MAX_QUERY_LENGTH: int = 8000

    # Server transport
    SERVER_TRANSPORT: str = "stdio"
    HTTP_BIND_HOST: str = "0.0.0.0"
    HTTP_BIND_PORT: int = 8080

    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "text"

    # Validators
    @field_validator("MSSQL_QUERY_TIMEOUT", "MSSQL_CONNECTION_TIMEOUT", "MAX_ROWS", "MAX_QUERY_LENGTH")
    @classmethod
    def must_be_positive(cls, value: int) -> int:
        if value <= 0:
            raise ValueError(f"Value must be positive, got {value}")
        return value

    @field_validator("LOG_LEVEL")
    @classmethod
    def valid_log_level(cls, value: str) -> str:
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper = value.upper()
        if upper not in allowed:
            raise ValueError(f"LOG_LEVEL must be one of {allowed}, got '{value}'")
        return upper

    @field_validator("SERVER_TRANSPORT")
    @classmethod
    def valid_transport(cls, value: str) -> str:
        allowed = {"stdio", "http"}
        lower = value.lower()
        if lower not in allowed:
            raise ValueError(f"SERVER_TRANSPORT must be 'stdio' or 'http', got '{value}'")
        return lower

    @model_validator(mode="after")
    def writes_require_read_only_false(self) -> "Settings":
        """Guard: ENABLE_WRITES=true is meaningless if READ_ONLY is still true."""
        if self.ENABLE_WRITES and self.READ_ONLY:
            raise ValueError(
                "Conflicting config: ENABLE_WRITES=true but READ_ONLY=true. "
                "Set READ_ONLY=false to allow writes."
            )
        return self


settings = Settings()
