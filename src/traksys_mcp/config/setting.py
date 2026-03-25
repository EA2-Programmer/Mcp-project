import re
import os
import logging
from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Get the directory where this file is located
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        # This checks the current directory, the src folder, AND the root folder
        env_file=(".env", "src/.env", "../.env", "../../.env"),
        env_file_encoding="utf-8",
        # Set to False to handle Windows environment variable quirks
        case_sensitive=False,
        extra="ignore",
        frozen=True,
    )

    MSSQL_CONNECTION_STRING: SecretStr = Field(
        ...,
        description="ODBC connection string for SQL Server. Use Windows Auth or store credentials securely."
    )
    MSSQL_CONNECTION_TIMEOUT: int = Field(default=5, ge=1, le=120, description="Connection timeout in seconds (1-120)")
    MSSQL_QUERY_TIMEOUT: int = Field(default=30, ge=1, le=300, description="Query execution timeout in seconds (1-300)")

    READ_ONLY: bool = Field(default=True, description="If True, only SELECT queries are allowed")
    ENABLE_WRITES: bool = Field(default=False, description="Enable write operations — requires READ_ONLY=false")
    MAX_ROWS: int = Field(default=1000, ge=1, le=50000, description="Maximum rows returned per query")
    MAX_QUERY_LENGTH: int = Field(default=8000, ge=1024, le=65535, description="Maximum query length in bytes")

    SERVER_TRANSPORT: str = Field(default="stdio", description="Transport mode: 'stdio' for local, 'http' for network")
    HTTP_BIND_HOST: str = Field(default="0.0.0.0", description="Host to bind when using HTTP transport")
    HTTP_BIND_PORT: int = Field(default=8080, ge=1, le=65535, description="Port to bind when using HTTP transport")

    LOG_LEVEL: str = Field(default="INFO", description="Logging level: DEBUG, INFO, WARNING, ERROR, CRITICAL")
    LOG_FORMAT: str = Field(default="text", description="Log output format: 'text' or 'json'")

    LANGFUSE_SECRET_KEY: SecretStr | None = Field(None, description="Langfuse secret key. If not set, tracing is disabled.")
    LANGFUSE_PUBLIC_KEY: str | None = Field(None, description="Langfuse public key.")
    LANGFUSE_BASE_URL: str = Field(
        default="http://localhost:3000",
        description="Langfuse base URL. Local: http://localhost:3000 | EU: https://cloud.langfuse.com | US: https://us.cloud.langfuse.com"
    )
    ENABLE_TRACING: bool = Field(default=False, description="Master used for Langfuse tracing.")

    @field_validator("LOG_LEVEL")
    @classmethod
    def valid_log_level(cls, value: str) -> str:
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper = value.upper()
        if upper not in allowed:
            raise ValueError(f"LOG_LEVEL must be one of {allowed}, got '{value}'")
        return upper

    @field_validator("LOG_FORMAT")
    @classmethod
    def valid_log_format(cls, value: str) -> str:
        allowed = {"json", "text"}
        lower = value.lower()
        if lower not in allowed:
            raise ValueError(f"LOG_FORMAT must be 'json' or 'text', got '{value}'")
        return lower

    @field_validator("SERVER_TRANSPORT")
    @classmethod
    def valid_transport(cls, value: str) -> str:
        allowed = {"stdio", "http"}
        lower = value.lower()
        if lower not in allowed:
            raise ValueError(f"SERVER_TRANSPORT must be 'stdio' or 'http', got '{value}'")
        return lower

    @field_validator("MSSQL_CONNECTION_STRING")
    @classmethod
    def validate_connection_string_format(cls, value: SecretStr) -> SecretStr:
        conn_str = value.get_secret_value()
        conn_lower = conn_str.strip().lower()

        valid_starts = ("driver={", "mssql+pyodbc://", "server=")
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
        if self.ENABLE_WRITES and self.READ_ONLY:
            raise ValueError(
                "Conflicting config: ENABLE_WRITES=true but READ_ONLY=true. "
                "Set READ_ONLY=false to allow writes, or keep READ_ONLY=true for safety."
            )
        return self

    def __repr__(self) -> str:
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
        return self.__repr__()

# Final initialization
settings = Settings()