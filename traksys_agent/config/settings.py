from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Dict, Optional
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False
    )

    # OpenAI Configuration
    openai_api_key: str
    openai_model: str = "gpt-5"
    agent_model_name: str = "TrakSYS-Agent"
    temperature: float = 0.4

    # MCP Server
    mcp_server_path: str
    mssql_connection_string: str

    # NEW: Add the optional MCP configuration fields
    max_rows: int = 1000
    read_only: bool = True

    # API Server
    api_port: int = 8000
    debug: bool = True
    log_level: str = "INFO"

    # Evaluation
    enable_logging: bool = True
    log_directory: str = "logs"

    # Langfuse Configuration
    langfuse_public_key: Optional[str] = None
    langfuse_secret_key: Optional[str] = None
    langfuse_base_url: str = "http://langfuse-web:3000"

    @property
    def mcp_env_vars(self) -> Dict[str, str]:
        """Passes environment variables down to the MCP subprocess."""
        return {
            "MSSQL_CONNECTION_STRING": self.mssql_connection_string,
            "MAX_ROWS": str(self.max_rows),
            "READ_ONLY": str(self.read_only).lower()  # standardizes to 'true'/'false'
        }


# Global settings instance
settings = Settings()