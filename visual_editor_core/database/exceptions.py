"""
Database-specific exceptions for the Visual Editor Core.
"""

from typing import Optional, Any, Dict


class DatabaseError(Exception):
    """Base exception for all database-related errors."""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.details = details or {}


class ConnectionError(DatabaseError):
    """Raised when database connection fails."""
    
    def __init__(self, message: str, database_type: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, details)
        self.database_type = database_type


class FailoverError(DatabaseError):
    """Raised when database failover fails."""
    
    def __init__(self, message: str, primary_error: Exception, fallback_error: Exception):
        super().__init__(message)
        self.primary_error = primary_error
        self.fallback_error = fallback_error


class ValidationError(DatabaseError):
    """Raised when database validation fails."""
    pass


class TransactionError(DatabaseError):
    """Raised when database transaction fails."""
    
    def __init__(self, message: str, rollback_successful: bool = False, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, details)
        self.rollback_successful = rollback_successful


class HealthCheckError(DatabaseError):
    """Raised when database health check fails."""
    
    def __init__(self, message: str, database_type: str, health_metrics: Optional[Dict[str, Any]] = None):
        super().__init__(message, health_metrics)
        self.database_type = database_type


class MigrationError(DatabaseError):
    """Raised when database migration fails."""
    
    def __init__(self, message: str, migration_id: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, details)
        self.migration_id = migration_id


class MigrationValidationError(MigrationError):
    """Raised when migration validation fails."""
    
    def __init__(self, message: str, migration_id: str, validation_errors: list, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, migration_id, details)
        self.validation_errors = validation_errors


class MigrationRollbackError(MigrationError):
    """Raised when migration rollback fails."""
    
    def __init__(self, message: str, migration_id: str, target_version: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, migration_id, details)
        self.target_version = target_version


class SchemaVersionError(DatabaseError):
    """Raised when schema version conflicts occur."""
    
    def __init__(self, message: str, current_version: str, expected_version: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, details)
        self.current_version = current_version
        self.expected_version = expected_version


class TenantError(DatabaseError):
    """Base exception for tenant-related errors."""
    
    def __init__(self, message: str, tenant_id: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, details)
        self.tenant_id = tenant_id


class IsolationError(TenantError):
    """Raised when tenant isolation is violated."""
    
    def __init__(self, message: str, tenant_id: Optional[str] = None, attempted_tenant_id: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, tenant_id, details)
        self.attempted_tenant_id = attempted_tenant_id


class TenantNotFoundError(TenantError):
    """Raised when a tenant is not found."""
    pass


class TenantAccessDeniedError(TenantError):
    """Raised when access to a tenant is denied."""
    
    def __init__(self, message: str, tenant_id: str, user_id: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, tenant_id, details)
        self.user_id = user_id


class TenantResourceLimitError(TenantError):
    """Raised when tenant resource limits are exceeded."""
    
    def __init__(self, message: str, tenant_id: str, resource_type: str, limit: int, current_usage: int, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, tenant_id, details)
        self.resource_type = resource_type
        self.limit = limit
        self.current_usage = current_usage