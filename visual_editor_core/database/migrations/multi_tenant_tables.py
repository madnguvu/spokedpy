"""
Multi-tenant tables migration - creates additional tables for multi-tenancy support.
"""

import uuid
from datetime import datetime
from typing import List

from ..models import DatabaseOperation, DatabaseType
from ..migration_manager import Migration


def create_multi_tenant_tables_migration(database_type: DatabaseType) -> Migration:
    """
    Create the multi-tenant tables migration.
    
    Args:
        database_type: Type of database (PostgreSQL or SQLite)
        
    Returns:
        Migration: Multi-tenant tables migration
    """
    migration_id = str(uuid.uuid4())
    
    # Define up operations (create tables)
    up_operations = []
    
    if database_type == DatabaseType.POSTGRESQL:
        # PostgreSQL table creation operations
        table_definitions = _get_postgresql_tables()
    else:
        # SQLite table creation operations
        table_definitions = _get_sqlite_tables()
    
    for table_name, table_sql in table_definitions.items():
        operation = DatabaseOperation(
            operation_type="create_table",
            table=table_name,
            query=table_sql
        )
        up_operations.append(operation)
    
    # Define down operations (drop tables in reverse order)
    down_operations = []
    table_names = list(table_definitions.keys())
    table_names.reverse()  # Drop in reverse order to handle foreign keys
    
    for table_name in table_names:
        if database_type == DatabaseType.POSTGRESQL:
            drop_sql = f"DROP TABLE IF EXISTS {table_name} CASCADE"
        else:
            drop_sql = f"DROP TABLE IF EXISTS {table_name}"
        
        operation = DatabaseOperation(
            operation_type="drop_table",
            table=table_name,
            query=drop_sql
        )
        down_operations.append(operation)
    
    return Migration(
        id=migration_id,
        name="multi_tenant_tables",
        version="1.1.0",
        description="Create additional tables for multi-tenancy support",
        up_operations=up_operations,
        down_operations=down_operations,
        dependencies=["initial_schema"]
    )


def _get_postgresql_tables() -> dict:
    """Get PostgreSQL table definitions for multi-tenancy."""
    return {
        "user_tenant_assignments": """
            CREATE TABLE IF NOT EXISTS user_tenant_assignments (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
                permissions JSONB DEFAULT '[]',
                status VARCHAR(20) NOT NULL DEFAULT 'active',
                assigned_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                assigned_by UUID NULL REFERENCES users(id) ON DELETE SET NULL,
                expires_at TIMESTAMP NULL,
                UNIQUE(user_id, tenant_id)
            )
        """,
        
        "tenant_configurations": """
            CREATE TABLE IF NOT EXISTS tenant_configurations (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
                settings JSONB DEFAULT '{}',
                feature_flags JSONB DEFAULT '{}',
                resource_limits JSONB DEFAULT '{}',
                ui_customization JSONB DEFAULT '{}',
                integrations JSONB DEFAULT '{}',
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(tenant_id)
            )
        """,
        
        "tenant_usage_metrics": """
            CREATE TABLE IF NOT EXISTS tenant_usage_metrics (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
                metric_type VARCHAR(255) NOT NULL,
                metric_value BIGINT NOT NULL DEFAULT 0,
                measurement_date DATE NOT NULL DEFAULT CURRENT_DATE,
                period_type VARCHAR(20) NOT NULL DEFAULT 'daily',
                metadata JSONB DEFAULT '{}',
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(tenant_id, metric_type, measurement_date, period_type)
            )
        """,
        
        "tenant_resource_limits": """
            CREATE TABLE IF NOT EXISTS tenant_resource_limits (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
                resource_type VARCHAR(255) NOT NULL,
                limit_value BIGINT NOT NULL,
                current_usage BIGINT DEFAULT 0,
                warning_threshold DECIMAL(5,2) DEFAULT 0.80,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(tenant_id, resource_type)
            )
        """,
        
        "cross_tenant_access_logs": """
            CREATE TABLE IF NOT EXISTS cross_tenant_access_logs (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                attempted_tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
                actual_tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
                access_type VARCHAR(255) NOT NULL,
                blocked BOOLEAN NOT NULL DEFAULT TRUE,
                timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                ip_address INET NULL,
                user_agent TEXT NULL,
                details JSONB DEFAULT '{}'
            )
        """,
        
        "tenant_data_exports": """
            CREATE TABLE IF NOT EXISTS tenant_data_exports (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
                requested_by UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                export_type VARCHAR(50) NOT NULL DEFAULT 'full',
                status VARCHAR(20) NOT NULL DEFAULT 'pending',
                file_path TEXT NULL,
                file_size BIGINT DEFAULT 0,
                requested_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP NULL,
                expires_at TIMESTAMP NULL,
                error_message TEXT NULL,
                metadata JSONB DEFAULT '{}'
            )
        """,
        
        "tenant_data_imports": """
            CREATE TABLE IF NOT EXISTS tenant_data_imports (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
                requested_by UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                import_type VARCHAR(50) NOT NULL DEFAULT 'full',
                status VARCHAR(20) NOT NULL DEFAULT 'pending',
                file_path TEXT NOT NULL,
                file_size BIGINT DEFAULT 0,
                records_imported INTEGER DEFAULT 0,
                records_failed INTEGER DEFAULT 0,
                requested_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP NULL,
                error_message TEXT NULL,
                metadata JSONB DEFAULT '{}'
            )
        """
    }


def _get_sqlite_tables() -> dict:
    """Get SQLite table definitions for multi-tenancy."""
    return {
        "user_tenant_assignments": """
            CREATE TABLE IF NOT EXISTS user_tenant_assignments (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                tenant_id TEXT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
                permissions TEXT DEFAULT '[]',
                status TEXT NOT NULL DEFAULT 'active',
                assigned_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                assigned_by TEXT NULL REFERENCES users(id) ON DELETE SET NULL,
                expires_at DATETIME NULL,
                UNIQUE(user_id, tenant_id)
            )
        """,
        
        "tenant_configurations": """
            CREATE TABLE IF NOT EXISTS tenant_configurations (
                id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
                settings TEXT DEFAULT '{}',
                feature_flags TEXT DEFAULT '{}',
                resource_limits TEXT DEFAULT '{}',
                ui_customization TEXT DEFAULT '{}',
                integrations TEXT DEFAULT '{}',
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(tenant_id)
            )
        """,
        
        "tenant_usage_metrics": """
            CREATE TABLE IF NOT EXISTS tenant_usage_metrics (
                id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
                metric_type TEXT NOT NULL,
                metric_value INTEGER NOT NULL DEFAULT 0,
                measurement_date DATE NOT NULL DEFAULT CURRENT_DATE,
                period_type TEXT NOT NULL DEFAULT 'daily',
                metadata TEXT DEFAULT '{}',
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(tenant_id, metric_type, measurement_date, period_type)
            )
        """,
        
        "tenant_resource_limits": """
            CREATE TABLE IF NOT EXISTS tenant_resource_limits (
                id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
                resource_type TEXT NOT NULL,
                limit_value INTEGER NOT NULL,
                current_usage INTEGER DEFAULT 0,
                warning_threshold REAL DEFAULT 0.80,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(tenant_id, resource_type)
            )
        """,
        
        "cross_tenant_access_logs": """
            CREATE TABLE IF NOT EXISTS cross_tenant_access_logs (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                attempted_tenant_id TEXT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
                actual_tenant_id TEXT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
                access_type TEXT NOT NULL,
                blocked INTEGER NOT NULL DEFAULT 1,
                timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                ip_address TEXT NULL,
                user_agent TEXT NULL,
                details TEXT DEFAULT '{}'
            )
        """,
        
        "tenant_data_exports": """
            CREATE TABLE IF NOT EXISTS tenant_data_exports (
                id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
                requested_by TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                export_type TEXT NOT NULL DEFAULT 'full',
                status TEXT NOT NULL DEFAULT 'pending',
                file_path TEXT NULL,
                file_size INTEGER DEFAULT 0,
                requested_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                completed_at DATETIME NULL,
                expires_at DATETIME NULL,
                error_message TEXT NULL,
                metadata TEXT DEFAULT '{}'
            )
        """,
        
        "tenant_data_imports": """
            CREATE TABLE IF NOT EXISTS tenant_data_imports (
                id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
                requested_by TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                import_type TEXT NOT NULL DEFAULT 'full',
                status TEXT NOT NULL DEFAULT 'pending',
                file_path TEXT NOT NULL,
                file_size INTEGER DEFAULT 0,
                records_imported INTEGER DEFAULT 0,
                records_failed INTEGER DEFAULT 0,
                requested_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                completed_at DATETIME NULL,
                error_message TEXT NULL,
                metadata TEXT DEFAULT '{}'
            )
        """
    }