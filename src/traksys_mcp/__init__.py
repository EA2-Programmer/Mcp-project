"""
TrakSYS MCP Server - Main Package
"""

# Import only base exceptions to avoid circular dependencies with services
from .core.exceptions import TrakSYSError, DatabaseError

__version__ = "0.1.0"

__all__ = [
    "TrakSYSError",
    "DatabaseError",
]