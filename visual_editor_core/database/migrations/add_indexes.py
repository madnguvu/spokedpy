"""
Add database indexes migration - creates performance indexes.
"""

import uuid
from datetime import datetime
from typing import List

from ..models import DatabaseOperation, DatabaseType
from ..migration_manager import Migration


def create_indexes_migration(database_type: DatabaseType) -> Migration:
    """
    Create migration to add database indexes for performance.
    
    Args:
        database_type: Type of database (PostgreSQL or SQLite)
        
    Returns:
        Migration: Indexes migration
    """
    migration_id = str(uuid.uuid4())
    
    # Define up operations (create indexes)
    up_operations = []
    
    if database_type == DatabaseType.POSTGRESQL:
        index_definitions = _get_postgresql_indexes()
    else:
        index_definitions = _get_sqlite_indexes()
    
    for index_name, index_sql in index_definitions.items():
        operation = DatabaseOperation(
            operation_type="create_index",
            table="multiple",  # Indexes span multiple tables
            query=index_sql
        )
        up_operations.append(operation)
    
    # Define down operations (drop indexes)
    down_operations = []
    
    for index_name in index_definitions.keys():
        drop_sql = f"DROP INDEX IF EXISTS {index_name}"
        operation = DatabaseOperation(
            operation_type="drop_index",
            table="multiple",  # Indexes span multiple tables
            query=drop_sql
        )
        down_operations.append(operation)
    
    return Migration(
        id=migration_id,
        name="add_indexes",
        version="1.1.0",
        description="Add performance indexes to core tables",
        up_operations=up_operations,
        down_operations=down_operations,
        dependencies=[]  # Depends on initial schema but we'll handle this in the migration manager
    )


def _get_postgresql_indexes() -> dict:
    """Get PostgreSQL index definitions."""
    return {
        "idx_users_tenant_id": "CREATE INDEX IF NOT EXISTS idx_users_tenant_id ON users(tenant_id)",
        "idx_users_email": "CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)",
        "idx_users_username": "CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)",
        "idx_users_status": "CREATE INDEX IF NOT EXISTS idx_users_status ON users(status)",
        
        "idx_roles_tenant_id": "CREATE INDEX IF NOT EXISTS idx_roles_tenant_id ON roles(tenant_id)",
        "idx_roles_parent_role_id": "CREATE INDEX IF NOT EXISTS idx_roles_parent_role_id ON roles(parent_role_id)",
        
        "idx_user_roles_user_id": "CREATE INDEX IF NOT EXISTS idx_user_roles_user_id ON user_roles(user_id)",
        "idx_user_roles_role_id": "CREATE INDEX IF NOT EXISTS idx_user_roles_role_id ON user_roles(role_id)",
        "idx_user_roles_expires_at": "CREATE INDEX IF NOT EXISTS idx_user_roles_expires_at ON user_roles(expires_at)",
        
        "idx_audit_logs_tenant_id": "CREATE INDEX IF NOT EXISTS idx_audit_logs_tenant_id ON audit_logs(tenant_id)",
        "idx_audit_logs_user_id": "CREATE INDEX IF NOT EXISTS idx_audit_logs_user_id ON audit_logs(user_id)",
        "idx_audit_logs_timestamp": "CREATE INDEX IF NOT EXISTS idx_audit_logs_timestamp ON audit_logs(timestamp)",
        "idx_audit_logs_action": "CREATE INDEX IF NOT EXISTS idx_audit_logs_action ON audit_logs(action)",
        "idx_audit_logs_resource_type": "CREATE INDEX IF NOT EXISTS idx_audit_logs_resource_type ON audit_logs(resource_type)",
        
        "idx_visual_models_tenant_id": "CREATE INDEX IF NOT EXISTS idx_visual_models_tenant_id ON visual_models(tenant_id)",
        "idx_visual_models_owner_id": "CREATE INDEX IF NOT EXISTS idx_visual_models_owner_id ON visual_models(owner_id)",
        "idx_visual_models_status": "CREATE INDEX IF NOT EXISTS idx_visual_models_status ON visual_models(status)",
        "idx_visual_models_created_at": "CREATE INDEX IF NOT EXISTS idx_visual_models_created_at ON visual_models(created_at)",
        "idx_visual_models_updated_at": "CREATE INDEX IF NOT EXISTS idx_visual_models_updated_at ON visual_models(updated_at)",
        
        "idx_execution_records_tenant_id": "CREATE INDEX IF NOT EXISTS idx_execution_records_tenant_id ON execution_records(tenant_id)",
        "idx_execution_records_user_id": "CREATE INDEX IF NOT EXISTS idx_execution_records_user_id ON execution_records(user_id)",
        "idx_execution_records_model_id": "CREATE INDEX IF NOT EXISTS idx_execution_records_model_id ON execution_records(model_id)",
        "idx_execution_records_status": "CREATE INDEX IF NOT EXISTS idx_execution_records_status ON execution_records(status)",
        "idx_execution_records_start_time": "CREATE INDEX IF NOT EXISTS idx_execution_records_start_time ON execution_records(start_time)",
        
        "idx_custom_components_tenant_id": "CREATE INDEX IF NOT EXISTS idx_custom_components_tenant_id ON custom_components(tenant_id)",
        "idx_custom_components_creator_id": "CREATE INDEX IF NOT EXISTS idx_custom_components_creator_id ON custom_components(creator_id)",
        "idx_custom_components_category": "CREATE INDEX IF NOT EXISTS idx_custom_components_category ON custom_components(category)",
        "idx_custom_components_is_shared": "CREATE INDEX IF NOT EXISTS idx_custom_components_is_shared ON custom_components(is_shared)",
        
        "idx_tenants_domain": "CREATE INDEX IF NOT EXISTS idx_tenants_domain ON tenants(domain)",
        "idx_tenants_status": "CREATE INDEX IF NOT EXISTS idx_tenants_status ON tenants(status)"
    }


def _get_sqlite_indexes() -> dict:
    """Get SQLite index definitions."""
    return {
        "idx_users_tenant_id": "CREATE INDEX IF NOT EXISTS idx_users_tenant_id ON users(tenant_id)",
        "idx_users_email": "CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)",
        "idx_users_username": "CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)",
        "idx_users_status": "CREATE INDEX IF NOT EXISTS idx_users_status ON users(status)",
        
        "idx_roles_tenant_id": "CREATE INDEX IF NOT EXISTS idx_roles_tenant_id ON roles(tenant_id)",
        "idx_roles_parent_role_id": "CREATE INDEX IF NOT EXISTS idx_roles_parent_role_id ON roles(parent_role_id)",
        
        "idx_user_roles_user_id": "CREATE INDEX IF NOT EXISTS idx_user_roles_user_id ON user_roles(user_id)",
        "idx_user_roles_role_id": "CREATE INDEX IF NOT EXISTS idx_user_roles_role_id ON user_roles(role_id)",
        "idx_user_roles_expires_at": "CREATE INDEX IF NOT EXISTS idx_user_roles_expires_at ON user_roles(expires_at)",
        
        "idx_audit_logs_tenant_id": "CREATE INDEX IF NOT EXISTS idx_audit_logs_tenant_id ON audit_logs(tenant_id)",
        "idx_audit_logs_user_id": "CREATE INDEX IF NOT EXISTS idx_audit_logs_user_id ON audit_logs(user_id)",
        "idx_audit_logs_timestamp": "CREATE INDEX IF NOT EXISTS idx_audit_logs_timestamp ON audit_logs(timestamp)",
        "idx_audit_logs_action": "CREATE INDEX IF NOT EXISTS idx_audit_logs_action ON audit_logs(action)",
        "idx_audit_logs_resource_type": "CREATE INDEX IF NOT EXISTS idx_audit_logs_resource_type ON audit_logs(resource_type)",
        
        "idx_visual_models_tenant_id": "CREATE INDEX IF NOT EXISTS idx_visual_models_tenant_id ON visual_models(tenant_id)",
        "idx_visual_models_owner_id": "CREATE INDEX IF NOT EXISTS idx_visual_models_owner_id ON visual_models(owner_id)",
        "idx_visual_models_status": "CREATE INDEX IF NOT EXISTS idx_visual_models_status ON visual_models(status)",
        "idx_visual_models_created_at": "CREATE INDEX IF NOT EXISTS idx_visual_models_created_at ON visual_models(created_at)",
        "idx_visual_models_updated_at": "CREATE INDEX IF NOT EXISTS idx_visual_models_updated_at ON visual_models(updated_at)",
        
        "idx_execution_records_tenant_id": "CREATE INDEX IF NOT EXISTS idx_execution_records_tenant_id ON execution_records(tenant_id)",
        "idx_execution_records_user_id": "CREATE INDEX IF NOT EXISTS idx_execution_records_user_id ON execution_records(user_id)",
        "idx_execution_records_model_id": "CREATE INDEX IF NOT EXISTS idx_execution_records_model_id ON execution_records(model_id)",
        "idx_execution_records_status": "CREATE INDEX IF NOT EXISTS idx_execution_records_status ON execution_records(status)",
        "idx_execution_records_start_time": "CREATE INDEX IF NOT EXISTS idx_execution_records_start_time ON execution_records(start_time)",
        
        "idx_custom_components_tenant_id": "CREATE INDEX IF NOT EXISTS idx_custom_components_tenant_id ON custom_components(tenant_id)",
        "idx_custom_components_creator_id": "CREATE INDEX IF NOT EXISTS idx_custom_components_creator_id ON custom_components(creator_id)",
        "idx_custom_components_category": "CREATE INDEX IF NOT EXISTS idx_custom_components_category ON custom_components(category)",
        "idx_custom_components_is_shared": "CREATE INDEX IF NOT EXISTS idx_custom_components_is_shared ON custom_components(is_shared)",
        
        "idx_tenants_domain": "CREATE INDEX IF NOT EXISTS idx_tenants_domain ON tenants(domain)",
        "idx_tenants_status": "CREATE INDEX IF NOT EXISTS idx_tenants_status ON tenants(status)"
    }