"""
Base database adapter interface.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from .models import (
    DatabaseConfig,
    DatabaseConnection,
    QueryResult,
    TransactionResult,
    HealthMetrics,
    DatabaseOperation,
    BackupResult,
    RestoreResult,
    OptimizationResult
)


class BaseDatabaseAdapter(ABC):
    """Base class for database adapters."""
    
    def __init__(self, config: DatabaseConfig):
        self.config = config
        self._is_connected = False
    
    @abstractmethod
    def connect(self) -> DatabaseConnection:
        """Establish database connection."""
        pass
    
    @abstractmethod
    def disconnect(self) -> bool:
        """Close database connection."""
        pass
    
    @abstractmethod
    def is_connected(self) -> bool:
        """Check if database is connected."""
        pass
    
    @abstractmethod
    def execute_query(self, query: str, params: Optional[Dict[str, Any]] = None) -> QueryResult:
        """Execute a database query."""
        pass
    
    @abstractmethod
    def execute_transaction(self, operations: List[DatabaseOperation]) -> TransactionResult:
        """Execute a database transaction."""
        pass
    
    @abstractmethod
    def validate_connection(self) -> bool:
        """Validate database connection."""
        pass
    
    @abstractmethod
    def get_health_metrics(self) -> HealthMetrics:
        """Get database health metrics."""
        pass
    
    @abstractmethod
    def backup_database(self, backup_path: str) -> BackupResult:
        """Create database backup."""
        pass
    
    @abstractmethod
    def restore_database(self, backup_path: str) -> RestoreResult:
        """Restore database from backup."""
        pass
    
    @abstractmethod
    def optimize_performance(self) -> OptimizationResult:
        """Optimize database performance."""
        pass
    
    @abstractmethod
    def create_tables(self, schema: Dict[str, Any]) -> bool:
        """Create tables from schema."""
        pass
    
    @abstractmethod
    def drop_tables(self, table_names: List[str]) -> bool:
        """Drop tables."""
        pass
    
    @abstractmethod
    def get_table_info(self, table_name: str) -> Dict[str, Any]:
        """Get table information."""
        pass
    
    @abstractmethod
    def get_connection_string(self) -> str:
        """Get connection string."""
        pass