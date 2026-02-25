"""
Initial schema migration - creates core tables.
"""

import uuid
from datetime import datetime
from typing import List

from ..models import DatabaseOperation, DatabaseType
from ..migration_manager import Migration


def create_initial_schema_migration(database_type: DatabaseType) -> Migration:
    """
    Create the initial schema migration for core tables.
    
    Args:
        database_type: Type of database (PostgreSQL or SQLite)
        
    Returns:
        Migration: Initial schema migration
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
        name="initial_schema",
        version="1.0.0",
        description="Create initial database schema with core tables",
        up_operations=up_operations,
        down_operations=down_operations,
        dependencies=[]
    )


def _get_postgresql_tables() -> dict:
    """Get PostgreSQL table definitions."""
    return {
        "tenants": """
            CREATE TABLE IF NOT EXISTS tenants (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                name VARCHAR(255) NOT NULL,
                domain VARCHAR(255) UNIQUE NOT NULL,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                status VARCHAR(20) NOT NULL DEFAULT 'active',
                configuration JSONB DEFAULT '{}',
                resource_limits JSONB DEFAULT '{}',
                billing_info JSONB DEFAULT '{}'
            )
        """,
        
        "users": """
            CREATE TABLE IF NOT EXISTS users (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
                username VARCHAR(255) NOT NULL,
                email VARCHAR(255) NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                last_login TIMESTAMP NULL,
                status VARCHAR(20) NOT NULL DEFAULT 'active',
                profile JSONB DEFAULT '{}',
                preferences JSONB DEFAULT '{}',
                UNIQUE(tenant_id, username),
                UNIQUE(tenant_id, email)
            )
        """,
        
        "roles": """
            CREATE TABLE IF NOT EXISTS roles (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
                name VARCHAR(255) NOT NULL,
                description TEXT,
                permissions JSONB DEFAULT '[]',
                parent_role_id UUID NULL REFERENCES roles(id) ON DELETE SET NULL,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(tenant_id, name)
            )
        """,
        
        "user_roles": """
            CREATE TABLE IF NOT EXISTS user_roles (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                role_id UUID NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
                assigned_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP NULL,
                assigned_by UUID NULL REFERENCES users(id) ON DELETE SET NULL,
                UNIQUE(user_id, role_id)
            )
        """,
        
        "audit_logs": """
            CREATE TABLE IF NOT EXISTS audit_logs (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
                user_id UUID NULL REFERENCES users(id) ON DELETE SET NULL,
                action VARCHAR(255) NOT NULL,
                resource_type VARCHAR(255) NOT NULL,
                resource_id VARCHAR(255) NULL,
                timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                ip_address INET NULL,
                user_agent TEXT NULL,
                details JSONB DEFAULT '{}',
                signature VARCHAR(255) NOT NULL
            )
        """,
        
        "visual_models": """
            CREATE TABLE IF NOT EXISTS visual_models (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
                owner_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                name VARCHAR(255) NOT NULL,
                description TEXT,
                model_data JSONB NOT NULL DEFAULT '{}',
                version INTEGER NOT NULL DEFAULT 1,
                parent_version_id UUID NULL REFERENCES visual_models(id) ON DELETE SET NULL,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                status VARCHAR(20) NOT NULL DEFAULT 'draft',
                tags TEXT[] DEFAULT '{}',
                metadata JSONB DEFAULT '{}'
            )
        """,
        
        "execution_records": """
            CREATE TABLE IF NOT EXISTS execution_records (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
                user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                model_id UUID NOT NULL REFERENCES visual_models(id) ON DELETE CASCADE,
                execution_data JSONB NOT NULL DEFAULT '{}',
                start_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                end_time TIMESTAMP NULL,
                status VARCHAR(20) NOT NULL DEFAULT 'running',
                output TEXT,
                error_message TEXT NULL,
                performance_metrics JSONB DEFAULT '{}'
            )
        """,
        
        "custom_components": """
            CREATE TABLE IF NOT EXISTS custom_components (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
                creator_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                name VARCHAR(255) NOT NULL,
                description TEXT,
                component_data JSONB NOT NULL DEFAULT '{}',
                category VARCHAR(255) NOT NULL,
                tags TEXT[] DEFAULT '{}',
                usage_count INTEGER DEFAULT 0,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                is_shared BOOLEAN DEFAULT FALSE
            )
        """
    }


def _get_sqlite_tables() -> dict:
    """Get SQLite table definitions."""
    return {
        "tenants": """
            CREATE TABLE IF NOT EXISTS tenants (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                domain TEXT UNIQUE NOT NULL,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                status TEXT NOT NULL DEFAULT 'active',
                configuration TEXT DEFAULT '{}',
                resource_limits TEXT DEFAULT '{}',
                billing_info TEXT DEFAULT '{}'
            )
        """,
        
        "users": """
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
                username TEXT NOT NULL,
                email TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                last_login DATETIME NULL,
                status TEXT NOT NULL DEFAULT 'active',
                profile TEXT DEFAULT '{}',
                preferences TEXT DEFAULT '{}',
                UNIQUE(tenant_id, username),
                UNIQUE(tenant_id, email)
            )
        """,
        
        "roles": """
            CREATE TABLE IF NOT EXISTS roles (
                id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
                name TEXT NOT NULL,
                description TEXT,
                permissions TEXT DEFAULT '[]',
                parent_role_id TEXT NULL REFERENCES roles(id) ON DELETE SET NULL,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(tenant_id, name)
            )
        """,
        
        "user_roles": """
            CREATE TABLE IF NOT EXISTS user_roles (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                role_id TEXT NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
                assigned_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                expires_at DATETIME NULL,
                assigned_by TEXT NULL REFERENCES users(id) ON DELETE SET NULL,
                UNIQUE(user_id, role_id)
            )
        """,
        
        "audit_logs": """
            CREATE TABLE IF NOT EXISTS audit_logs (
                id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
                user_id TEXT NULL REFERENCES users(id) ON DELETE SET NULL,
                action TEXT NOT NULL,
                resource_type TEXT NOT NULL,
                resource_id TEXT NULL,
                timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                ip_address TEXT NULL,
                user_agent TEXT NULL,
                details TEXT DEFAULT '{}',
                signature TEXT NOT NULL
            )
        """,
        
        "visual_models": """
            CREATE TABLE IF NOT EXISTS visual_models (
                id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
                owner_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                name TEXT NOT NULL,
                description TEXT,
                model_data TEXT NOT NULL DEFAULT '{}',
                version INTEGER NOT NULL DEFAULT 1,
                parent_version_id TEXT NULL REFERENCES visual_models(id) ON DELETE SET NULL,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                status TEXT NOT NULL DEFAULT 'draft',
                tags TEXT DEFAULT '',
                metadata TEXT DEFAULT '{}'
            )
        """,
        
        "execution_records": """
            CREATE TABLE IF NOT EXISTS execution_records (
                id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
                user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                model_id TEXT NOT NULL REFERENCES visual_models(id) ON DELETE CASCADE,
                execution_data TEXT NOT NULL DEFAULT '{}',
                start_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                end_time DATETIME NULL,
                status TEXT NOT NULL DEFAULT 'running',
                output TEXT,
                error_message TEXT NULL,
                performance_metrics TEXT DEFAULT '{}'
            )
        """,
        
        "custom_components": """
            CREATE TABLE IF NOT EXISTS custom_components (
                id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
                creator_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                name TEXT NOT NULL,
                description TEXT,
                component_data TEXT NOT NULL DEFAULT '{}',
                category TEXT NOT NULL,
                tags TEXT DEFAULT '',
                usage_count INTEGER DEFAULT 0,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                is_shared INTEGER DEFAULT 0
            )
        """
    }