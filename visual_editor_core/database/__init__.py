"""
Database abstraction layer for Visual Editor Core.

This module provides a unified interface for database operations supporting
both PostgreSQL and SQLite with automatic failover capabilities.
"""

from .database_manager import DatabaseManager
from .multi_tenant_manager import (
    MultiTenantManager,
    TenantInfo,
    TenantContext,
    UsageMetrics,
    TenantConfig,
    ExportResult,
    ImportResult,
    TenantData
)
from .tenant_access_control import (
    TenantAccessController,
    AccessAttempt,
    AccessViolation,
    TenantAccessRule
)
from .migration_manager import (
    MigrationManager,
    Migration,
    MigrationRecord,
    MigrationResult,
    InitializationResult,
    RollbackResult,
    ValidationResult,
    BackupResult as MigrationBackupResult,
    RepairResult
)
from .adapters import PostgreSQLAdapter, SQLiteAdapter
from .connection_pool import ConnectionPool, PoolConfig
from .exceptions import (
    DatabaseError,
    ConnectionError,
    FailoverError,
    ValidationError,
    TransactionError,
    MigrationError,
    MigrationValidationError,
    MigrationRollbackError,
    SchemaVersionError,
    TenantError,
    IsolationError,
    TenantNotFoundError,
    TenantAccessDeniedError,
    TenantResourceLimitError
)
from .models import (
    DatabaseConnection,
    QueryResult,
    TransactionResult,
    HealthMetrics,
    DatabaseConfig,
    DatabaseType,
    ConnectionStatus,
    DatabaseOperation,
    BackupResult,
    RestoreResult,
    OptimizationResult
)

__all__ = [
    'DatabaseManager',
    'MultiTenantManager',
    'TenantInfo',
    'TenantContext',
    'UsageMetrics',
    'TenantConfig',
    'ExportResult',
    'ImportResult',
    'TenantData',
    'TenantAccessController',
    'AccessAttempt',
    'AccessViolation',
    'TenantAccessRule',
    'MigrationManager',
    'Migration',
    'MigrationRecord',
    'MigrationResult',
    'InitializationResult',
    'RollbackResult',
    'ValidationResult',
    'MigrationBackupResult',
    'RepairResult',
    'PostgreSQLAdapter',
    'SQLiteAdapter',
    'ConnectionPool',
    'PoolConfig',
    'DatabaseError',
    'ConnectionError',
    'FailoverError',
    'ValidationError',
    'TransactionError',
    'MigrationError',
    'MigrationValidationError',
    'MigrationRollbackError',
    'SchemaVersionError',
    'TenantError',
    'IsolationError',
    'TenantNotFoundError',
    'TenantAccessDeniedError',
    'TenantResourceLimitError',
    'DatabaseConnection',
    'QueryResult',
    'TransactionResult',
    'HealthMetrics',
    'DatabaseConfig',
    'DatabaseType',
    'ConnectionStatus',
    'DatabaseOperation',
    'BackupResult',
    'RestoreResult',
    'OptimizationResult'
]