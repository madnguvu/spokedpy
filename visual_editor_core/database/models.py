"""
Data models for the database abstraction layer.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union
from datetime import datetime
from enum import Enum


class DatabaseType(Enum):
    """Supported database types."""
    POSTGRESQL = "postgresql"
    SQLITE = "sqlite"


class ConnectionStatus(Enum):
    """Database connection status."""
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    FAILED = "failed"
    RECONNECTING = "reconnecting"


@dataclass
class DatabaseConfig:
    """Database configuration settings."""
    database_type: DatabaseType
    host: Optional[str] = None
    port: Optional[int] = None
    database: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    connection_string: Optional[str] = None
    pool_size: int = 10
    max_overflow: int = 20
    pool_timeout: int = 30
    pool_recycle: int = 3600
    echo: bool = False
    
    def __post_init__(self):
        """Validate configuration after initialization."""
        if self.database_type == DatabaseType.POSTGRESQL:
            if not self.connection_string and not all([self.host, self.database, self.username]):
                raise ValueError("PostgreSQL requires either connection_string or host/database/username")
        elif self.database_type == DatabaseType.SQLITE:
            if not self.connection_string and not self.database:
                raise ValueError("SQLite requires either connection_string or database path")


@dataclass
class DatabaseConnection:
    """Represents a database connection."""
    connection_id: str
    database_type: DatabaseType
    status: ConnectionStatus
    created_at: datetime
    last_used: datetime
    connection_string: str
    is_primary: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def is_healthy(self) -> bool:
        """Check if connection is healthy."""
        return self.status == ConnectionStatus.CONNECTED
    
    def mark_used(self):
        """Mark connection as recently used."""
        self.last_used = datetime.now()


@dataclass
class QueryResult:
    """Result of a database query."""
    success: bool
    rows_affected: int = 0
    data: List[Dict[str, Any]] = field(default_factory=list)
    error_message: Optional[str] = None
    execution_time: float = 0.0
    query_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TransactionResult:
    """Result of a database transaction."""
    success: bool
    transaction_id: str
    operations_count: int
    rollback_performed: bool = False
    error_message: Optional[str] = None
    execution_time: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class HealthMetrics:
    """Database health metrics."""
    database_type: DatabaseType
    is_available: bool
    response_time: float
    active_connections: int
    max_connections: int
    cpu_usage: Optional[float] = None
    memory_usage: Optional[float] = None
    disk_usage: Optional[float] = None
    last_check: datetime = field(default_factory=datetime.now)
    error_count: int = 0
    warnings: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def is_healthy(self) -> bool:
        """Check if database is healthy based on metrics."""
        return (
            self.is_available and
            self.response_time < 5.0 and  # 5 second threshold
            self.active_connections < self.max_connections * 0.9 and  # 90% threshold
            self.error_count < 10  # Error threshold
        )


@dataclass
class DatabaseOperation:
    """Represents a database operation for transactions."""
    operation_type: str  # 'insert', 'update', 'delete', 'select'
    table: str
    data: Dict[str, Any] = field(default_factory=dict)
    conditions: Dict[str, Any] = field(default_factory=dict)
    query: Optional[str] = None
    parameters: Dict[str, Any] = field(default_factory=dict)
    
    def validate(self) -> bool:
        """Validate the operation."""
        if not self.operation_type or not self.table:
            return False
        
        if self.operation_type in ['insert', 'update'] and not self.data and not self.query:
            return False
            
        return True


@dataclass
class BackupResult:
    """Result of a database backup operation."""
    success: bool
    backup_path: str
    backup_size: int = 0
    backup_time: datetime = field(default_factory=datetime.now)
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RestoreResult:
    """Result of a database restore operation."""
    success: bool
    restore_path: str
    restore_time: datetime = field(default_factory=datetime.now)
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OptimizationResult:
    """Result of a database optimization operation."""
    success: bool
    optimizations_applied: List[str] = field(default_factory=list)
    performance_improvement: Optional[float] = None
    execution_time: float = 0.0
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)