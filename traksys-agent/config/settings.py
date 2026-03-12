from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Dict, Optional
import os
from pathlib import Path

# Get the directory where this file is located
BASE_DIR = Path(__file__).resolve().parent.parent

class Settings(BaseSettings):
    # Pydantic Settings configuration
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False
    )

    # OpenAI Configuration
    openai_api_key: str
    openai_model: str = "gpt-5-mini"  # The REAL model for the brain
    agent_model_name: str = "TrakSYS-Agent" # The DISPLAY name for OpenWebUI
    
    temperature: float = 0.7
    # max_tokens: int = 2000

    # MCP Server
    mcp_server_path: str = r"C:\Kdg\year 3\LAB\Lab project\src\traksys_mcp\server.py"

    # Database connection (passed to MCP)
    mssql_connection_string: str = "Driver={ODBC Driver 17 for SQL Server};Server=localhost;Database=EBR_Template;Trusted_Connection=yes;"

    # API Server
    api_port: int = 8000
    debug: bool = True
    log_level: str = "INFO"

    # Evaluation
    enable_logging: bool = True
    log_directory: str = "logs"

    @property
    def mcp_env_vars(self) -> Dict[str, str]:
        return {
            "MSSQL_CONNECTION_STRING": self.mssql_connection_string
        }

# Global settings instance
settings = Settings()
