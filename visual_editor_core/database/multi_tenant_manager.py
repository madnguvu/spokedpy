"""
Multi-Tenant Manager - Manages tenant isolation and data segregation.
"""

import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field

from .models import DatabaseOperation, QueryResult, TransactionResult
from .exceptions import (
    DatabaseError,
    ValidationError,
    TenantError,
    IsolationError
)
from .tenant_access_control import TenantAccessController


@dataclass
class TenantInfo:
    """Information about a tenant."""
    name: str
    domain: str
    configuration: Dict[str, Any] = field(default_factory=dict)
    resource_limits: Dict[str, int] = field(default_factory=dict)
    billing_info: Dict[str, Any] = field(default_factory=dict)
    status: str = "active"  # active, suspended, deleted
    
    def validate(self) -> List[str]:
        """Validate tenant information."""
        errors = []
        
        if not self.name or not self.name.strip():
            errors.append("Tenant name is required")
        
        if not self.domain or not self.domain.strip():
            errors.append("Tenant domain is required")
        
        if self.status not in ["active", "suspended", "deleted"]:
            errors.append("Invalid tenant status")
        
        return errors


@dataclass
class TenantContext:
    """Context information for a tenant."""
    tenant_id: str
    user_id: str
    permissions: List[str] = field(default_factory=list)
    resource_usage: Dict[str, int] = field(default_factory=dict)
    session_id: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    
    def has_permission(self, permission: str) -> bool:
        """Check if context has a specific permission."""
        return permission in self.permissions


@dataclass
class UsageMetrics:
    """Usage metrics for a tenant."""
    tenant_id: str
    storage_used: int = 0
    queries_executed: int = 0
    active_connections: int = 0
    models_created: int = 0
    executions_performed: int = 0
    last_activity: Optional[datetime] = None
    period_start: datetime = field(default_factory=datetime.now)
    period_end: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary."""
        return {
            'tenant_id': self.tenant_id,
            'storage_used': self.storage_used,
            'queries_executed': self.queries_executed,
            'active_connections': self.active_connections,
            'models_created': self.models_created,
            'executions_performed': self.executions_performed,
            'last_activity': self.last_activity.isoformat() if self.last_activity else None,
            'period_start': self.period_start.isoformat(),
            'period_end': self.period_end.isoformat()
        }


@dataclass
class TenantConfig:
    """Configuration for a tenant."""
    tenant_id: str
    settings: Dict[str, Any] = field(default_factory=dict)
    feature_flags: Dict[str, bool] = field(default_factory=dict)
    resource_limits: Dict[str, int] = field(default_factory=dict)
    ui_customization: Dict[str, Any] = field(default_factory=dict)
    integrations: Dict[str, Any] = field(default_factory=dict)
    
    def get_setting(self, key: str, default: Any = None) -> Any:
        """Get a configuration setting."""
        return self.settings.get(key, default)
    
    def set_setting(self, key: str, value: Any):
        """Set a configuration setting."""
        self.settings[key] = value
    
    def is_feature_enabled(self, feature: str) -> bool:
        """Check if a feature is enabled."""
        return self.feature_flags.get(feature, False)


@dataclass
class ExportResult:
    """Result of tenant data export."""
    success: bool
    export_path: str
    tenant_id: str
    export_size: int = 0
    exported_tables: List[str] = field(default_factory=list)
    export_time: datetime = field(default_factory=datetime.now)
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ImportResult:
    """Result of tenant data import."""
    success: bool
    import_path: str
    tenant_id: str
    imported_records: int = 0
    imported_tables: List[str] = field(default_factory=list)
    import_time: datetime = field(default_factory=datetime.now)
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TenantData:
    """Tenant data for import/export."""
    tenant_info: TenantInfo
    visual_models: List[Dict[str, Any]] = field(default_factory=list)
    custom_components: List[Dict[str, Any]] = field(default_factory=list)
    execution_history: List[Dict[str, Any]] = field(default_factory=list)
    configurations: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


class TenantRegistry:
    """Registry for managing tenant information."""
    
    def __init__(self, database_manager):
        self.database_manager = database_manager
        self.logger = logging.getLogger(__name__)
        self._tenant_cache: Dict[str, TenantInfo] = {}
        self._cache_expiry: Dict[str, datetime] = {}
    
    def register_tenant(self, tenant_info: TenantInfo) -> str:
        """Register a new tenant."""
        # Validate tenant info
        errors = tenant_info.validate()
        if errors:
            raise ValidationError(f"Invalid tenant info: {', '.join(errors)}")
        
        tenant_id = str(uuid.uuid4())
        
        # Store tenant in database
        tenant_data = {
            'id': tenant_id,
            'name': tenant_info.name,
            'domain': tenant_info.domain,
            'configuration': tenant_info.configuration,
            'resource_limits': tenant_info.resource_limits,
            'billing_info': tenant_info.billing_info,
            'status': tenant_info.status,
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat()
        }
        
        operation = DatabaseOperation(
            operation_type='insert',
            table='tenants',
            data=tenant_data
        )
        
        result = self.database_manager.execute_transaction([operation])
        
        if not result.success:
            raise DatabaseError(f"Failed to register tenant: {result.error_message}")
        
        # Cache the tenant info
        self._tenant_cache[tenant_id] = tenant_info
        self._cache_expiry[tenant_id] = datetime.now()
        
        self.logger.info(f"Registered new tenant: {tenant_id} ({tenant_info.name})")
        return tenant_id
    
    def get_tenant(self, tenant_id: str) -> Optional[TenantInfo]:
        """Get tenant information."""
        # Check cache first
        if tenant_id in self._tenant_cache:
            cache_time = self._cache_expiry.get(tenant_id)
            if cache_time and (datetime.now() - cache_time).seconds < 300:  # 5 minute cache
                return self._tenant_cache[tenant_id]
        
        # Query database
        query = "SELECT * FROM tenants WHERE id = :tenant_id"
        result = self.database_manager.execute_query(query, {'tenant_id': tenant_id})
        
        if result.success and result.data:
            tenant_data = result.data[0]
            tenant_info = TenantInfo(
                name=tenant_data['name'],
                domain=tenant_data['domain'],
                configuration=tenant_data.get('configuration', {}),
                resource_limits=tenant_data.get('resource_limits', {}),
                billing_info=tenant_data.get('billing_info', {}),
                status=tenant_data.get('status', 'active')
            )
            
            # Update cache
            self._tenant_cache[tenant_id] = tenant_info
            self._cache_expiry[tenant_id] = datetime.now()
            
            return tenant_info
        
        return None
    
    def update_tenant(self, tenant_id: str, tenant_info: TenantInfo) -> bool:
        """Update tenant information."""
        # Validate tenant info
        errors = tenant_info.validate()
        if errors:
            raise ValidationError(f"Invalid tenant info: {', '.join(errors)}")
        
        tenant_data = {
            'name': tenant_info.name,
            'domain': tenant_info.domain,
            'configuration': tenant_info.configuration,
            'resource_limits': tenant_info.resource_limits,
            'billing_info': tenant_info.billing_info,
            'status': tenant_info.status,
            'updated_at': datetime.now().isoformat()
        }
        
        operation = DatabaseOperation(
            operation_type='update',
            table='tenants',
            data=tenant_data,
            conditions={'id': tenant_id}
        )
        
        result = self.database_manager.execute_transaction([operation])
        
        if result.success:
            # Update cache
            self._tenant_cache[tenant_id] = tenant_info
            self._cache_expiry[tenant_id] = datetime.now()
            self.logger.info(f"Updated tenant: {tenant_id}")
            return True
        else:
            self.logger.error(f"Failed to update tenant {tenant_id}: {result.error_message}")
            return False
    
    def delete_tenant(self, tenant_id: str) -> bool:
        """Delete a tenant (soft delete)."""
        operation = DatabaseOperation(
            operation_type='update',
            table='tenants',
            data={'status': 'deleted', 'updated_at': datetime.now().isoformat()},
            conditions={'id': tenant_id}
        )
        
        result = self.database_manager.execute_transaction([operation])
        
        if result.success:
            # Remove from cache
            self._tenant_cache.pop(tenant_id, None)
            self._cache_expiry.pop(tenant_id, None)
            self.logger.info(f"Deleted tenant: {tenant_id}")
            return True
        else:
            self.logger.error(f"Failed to delete tenant {tenant_id}: {result.error_message}")
            return False
    
    def list_tenants(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """List all tenants."""
        query = "SELECT * FROM tenants"
        params = {}
        
        if status:
            query += " WHERE status = :status"
            params['status'] = status
        
        result = self.database_manager.execute_query(query, params)
        
        if result.success:
            return result.data
        else:
            self.logger.error(f"Failed to list tenants: {result.error_message}")
            return []


class IsolationEnforcer:
    """Enforces tenant isolation at the database level."""
    
    def __init__(self, database_manager):
        self.database_manager = database_manager
        self.logger = logging.getLogger(__name__)
        self._tenant_aware_tables = {
            'visual_models', 'custom_components', 'execution_history',
            'audit_logs', 'user_sessions', 'configurations', 'patterns',
            'capability_assessments', 'enhancements', 'learning_metrics'
        }
    
    def enforce_tenant_scoping(self, query: str, tenant_id: str) -> str:
        """Add tenant scoping to a query."""
        if not tenant_id:
            raise IsolationError("Tenant ID is required for tenant-aware operations")
        
        # Parse query to identify table names
        query_upper = query.upper()
        
        # Check if this is a tenant-aware query
        needs_scoping = any(table in query_upper for table in 
                          [t.upper() for t in self._tenant_aware_tables])
        
        if not needs_scoping:
            return query
        
        # Add tenant scoping
        if "WHERE" in query_upper:
            # Add tenant condition to existing WHERE clause
            scoped_query = query + f" AND tenant_id = '{tenant_id}'"
        else:
            # Add WHERE clause with tenant condition
            # Find the position to insert WHERE clause
            if "ORDER BY" in query_upper:
                order_pos = query_upper.find("ORDER BY")
                scoped_query = query[:order_pos] + f" WHERE tenant_id = '{tenant_id}' " + query[order_pos:]
            elif "GROUP BY" in query_upper:
                group_pos = query_upper.find("GROUP BY")
                scoped_query = query[:group_pos] + f" WHERE tenant_id = '{tenant_id}' " + query[group_pos:]
            elif "LIMIT" in query_upper:
                limit_pos = query_upper.find("LIMIT")
                scoped_query = query[:limit_pos] + f" WHERE tenant_id = '{tenant_id}' " + query[limit_pos:]
            else:
                scoped_query = query + f" WHERE tenant_id = '{tenant_id}'"
        
        return scoped_query
    
    def validate_tenant_access(self, user_id: str, tenant_id: str) -> bool:
        """Validate that a user has access to a tenant."""
        query = """
        SELECT COUNT(*) as count 
        FROM user_tenant_assignments 
        WHERE user_id = :user_id AND tenant_id = :tenant_id AND status = 'active'
        """
        
        result = self.database_manager.execute_query(query, {
            'user_id': user_id,
            'tenant_id': tenant_id
        })
        
        if result.success and result.data:
            return result.data[0]['count'] > 0
        
        return False
    
    def prevent_cross_tenant_access(self, operations: List[DatabaseOperation], tenant_id: str) -> List[DatabaseOperation]:
        """Ensure operations are scoped to the correct tenant."""
        scoped_operations = []
        
        for operation in operations:
            # Check if this table requires tenant scoping
            if operation.table in self._tenant_aware_tables:
                # Add tenant_id to data and conditions
                scoped_operation = DatabaseOperation(
                    operation_type=operation.operation_type,
                    table=operation.table,
                    data={**operation.data, 'tenant_id': tenant_id} if operation.data else {'tenant_id': tenant_id},
                    conditions={**operation.conditions, 'tenant_id': tenant_id} if operation.conditions else {'tenant_id': tenant_id},
                    query=operation.query,
                    parameters={**operation.parameters, 'tenant_id': tenant_id} if operation.parameters else {'tenant_id': tenant_id}
                )
                scoped_operations.append(scoped_operation)
            else:
                # Non-tenant-aware table, use as-is
                scoped_operations.append(operation)
        
        return scoped_operations
    
    def audit_cross_tenant_attempt(self, user_id: str, attempted_tenant_id: str, actual_tenant_id: str):
        """Log cross-tenant access attempts."""
        audit_data = {
            'id': str(uuid.uuid4()),
            'tenant_id': actual_tenant_id,
            'user_id': user_id,
            'action': 'cross_tenant_access_attempt',
            'resource_type': 'tenant',
            'resource_id': attempted_tenant_id,
            'timestamp': datetime.now().isoformat(),
            'details': {
                'attempted_tenant': attempted_tenant_id,
                'actual_tenant': actual_tenant_id,
                'severity': 'high'
            }
        }
        
        operation = DatabaseOperation(
            operation_type='insert',
            table='audit_logs',
            data=audit_data
        )
        
        try:
            self.database_manager.execute_transaction([operation])
            self.logger.warning(f"Cross-tenant access attempt by user {user_id}: {attempted_tenant_id} -> {actual_tenant_id}")
        except Exception as e:
            self.logger.error(f"Failed to audit cross-tenant access attempt: {e}")


class TenantConfigManager:
    """Manages tenant-specific configurations."""
    
    def __init__(self, database_manager):
        self.database_manager = database_manager
        self.logger = logging.getLogger(__name__)
        self._config_cache: Dict[str, TenantConfig] = {}
    
    def get_tenant_configuration(self, tenant_id: str) -> TenantConfig:
        """Get tenant configuration."""
        # Check cache first
        if tenant_id in self._config_cache:
            return self._config_cache[tenant_id]
        
        # Query database
        query = "SELECT * FROM tenant_configurations WHERE tenant_id = :tenant_id"
        result = self.database_manager.execute_query(query, {'tenant_id': tenant_id}, tenant_id)
        
        if result.success and result.data:
            config_data = result.data[0]
            config = TenantConfig(
                tenant_id=tenant_id,
                settings=config_data.get('settings', {}),
                feature_flags=config_data.get('feature_flags', {}),
                resource_limits=config_data.get('resource_limits', {}),
                ui_customization=config_data.get('ui_customization', {}),
                integrations=config_data.get('integrations', {})
            )
        else:
            # Create default configuration
            config = TenantConfig(tenant_id=tenant_id)
            self._create_default_configuration(tenant_id, config)
        
        # Cache the configuration
        self._config_cache[tenant_id] = config
        return config
    
    def update_tenant_configuration(self, tenant_id: str, config: TenantConfig) -> bool:
        """Update tenant configuration."""
        config_data = {
            'tenant_id': tenant_id,
            'settings': config.settings,
            'feature_flags': config.feature_flags,
            'resource_limits': config.resource_limits,
            'ui_customization': config.ui_customization,
            'integrations': config.integrations,
            'updated_at': datetime.now().isoformat()
        }
        
        # Try update first, then insert if not exists
        update_operation = DatabaseOperation(
            operation_type='update',
            table='tenant_configurations',
            data=config_data,
            conditions={'tenant_id': tenant_id}
        )
        
        result = self.database_manager.execute_transaction([update_operation], tenant_id)
        
        if not result.success:
            # Try insert
            config_data['created_at'] = datetime.now().isoformat()
            insert_operation = DatabaseOperation(
                operation_type='insert',
                table='tenant_configurations',
                data=config_data
            )
            
            result = self.database_manager.execute_transaction([insert_operation], tenant_id)
        
        if result.success:
            # Update cache
            self._config_cache[tenant_id] = config
            self.logger.info(f"Updated configuration for tenant: {tenant_id}")
            return True
        else:
            self.logger.error(f"Failed to update configuration for tenant {tenant_id}: {result.error_message}")
            return False
    
    def _create_default_configuration(self, tenant_id: str, config: TenantConfig):
        """Create default configuration for a tenant."""
        # Set default settings
        config.settings = {
            'theme': 'light',
            'language': 'en',
            'timezone': 'UTC',
            'auto_save': True,
            'debug_mode': False
        }
        
        # Set default feature flags
        config.feature_flags = {
            'visual_debugging': True,
            'code_generation': True,
            'pattern_recognition': True,
            'adaptive_learning': True,
            'collaboration': True
        }
        
        # Set default resource limits
        config.resource_limits = {
            'max_models': 1000,
            'max_executions_per_hour': 10000,
            'max_storage_mb': 10240,  # 10GB
            'max_concurrent_users': 100
        }
        
        # Save to database
        self.update_tenant_configuration(tenant_id, config)


class MultiTenantManager:
    """
    Multi-Tenant Manager - Manages tenant isolation and data segregation.
    
    This class provides complete data isolation between tenants, manages tenant
    configurations, and ensures secure multi-tenant operations.
    """
    
    def __init__(self, database_manager):
        """
        Initialize the multi-tenant manager.
        
        Args:
            database_manager: Database manager instance
        """
        self.database_manager = database_manager
        self.logger = logging.getLogger(__name__)
        
        # Initialize components
        self.tenant_registry = TenantRegistry(database_manager)
        self.isolation_enforcer = IsolationEnforcer(database_manager)
        self.tenant_config_manager = TenantConfigManager(database_manager)
        self.access_controller = TenantAccessController(database_manager)
        
        # Active tenant contexts
        self._active_contexts: Dict[str, TenantContext] = {}
        
        self.logger.info("Multi-tenant manager initialized")
    
    def create_tenant(self, tenant_info: TenantInfo) -> str:
        """
        Create a new tenant.
        
        Args:
            tenant_info: Information about the tenant
            
        Returns:
            str: Tenant ID
            
        Raises:
            ValidationError: If tenant info is invalid
            DatabaseError: If tenant creation fails
        """
        try:
            tenant_id = self.tenant_registry.register_tenant(tenant_info)
            
            # Create default configuration
            default_config = TenantConfig(tenant_id=tenant_id)
            self.tenant_config_manager.update_tenant_configuration(tenant_id, default_config)
            
            # Initialize tenant-specific tables/schemas if needed
            self._initialize_tenant_resources(tenant_id)
            
            self.logger.info(f"Created tenant: {tenant_id} ({tenant_info.name})")
            return tenant_id
            
        except Exception as e:
            self.logger.error(f"Failed to create tenant: {e}")
            raise
    
    def delete_tenant(self, tenant_id: str) -> bool:
        """
        Delete a tenant and clean up all associated data.
        
        Args:
            tenant_id: ID of the tenant to delete
            
        Returns:
            bool: True if deletion was successful
        """
        try:
            # First, mark tenant as deleted
            tenant_info = self.tenant_registry.get_tenant(tenant_id)
            if not tenant_info:
                self.logger.warning(f"Tenant not found: {tenant_id}")
                return False
            
            tenant_info.status = "deleted"
            self.tenant_registry.update_tenant(tenant_id, tenant_info)
            
            # Clean up tenant data
            self._cleanup_tenant_data(tenant_id)
            
            # Remove from active contexts
            self._active_contexts.pop(tenant_id, None)
            
            self.logger.info(f"Deleted tenant: {tenant_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to delete tenant {tenant_id}: {e}")
            return False
    
    def get_tenant_context(self, user_id: str) -> Optional[TenantContext]:
        """
        Get tenant context for a user.
        
        Args:
            user_id: ID of the user
            
        Returns:
            TenantContext: Tenant context or None if not found
        """
        # Query user's tenant assignment
        query = """
        SELECT tenant_id, permissions 
        FROM user_tenant_assignments 
        WHERE user_id = :user_id AND status = 'active'
        """
        
        result = self.database_manager.execute_query(query, {'user_id': user_id})
        
        if result.success and result.data:
            assignment = result.data[0]
            tenant_id = assignment['tenant_id']
            
            # Create or get existing context
            context_key = f"{user_id}:{tenant_id}"
            if context_key not in self._active_contexts:
                context = TenantContext(
                    tenant_id=tenant_id,
                    user_id=user_id,
                    permissions=assignment.get('permissions', []),
                    session_id=str(uuid.uuid4())
                )
                self._active_contexts[context_key] = context
            
            return self._active_contexts[context_key]
        
        return None
    
    def enforce_tenant_isolation(self, query: str, tenant_id: str) -> str:
        """
        Enforce tenant isolation by modifying queries.
        
        Args:
            query: SQL query to modify
            tenant_id: ID of the tenant
            
        Returns:
            str: Modified query with tenant scoping
        """
        return self.isolation_enforcer.enforce_tenant_scoping(query, tenant_id)
    
    def get_tenant_usage_metrics(self, tenant_id: str) -> UsageMetrics:
        """
        Get usage metrics for a tenant.
        
        Args:
            tenant_id: ID of the tenant
            
        Returns:
            UsageMetrics: Usage metrics for the tenant
        """
        metrics = UsageMetrics(tenant_id=tenant_id)
        
        try:
            # Get storage usage
            storage_query = """
            SELECT COUNT(*) as model_count, 
                   SUM(LENGTH(model_data)) as storage_used
            FROM visual_models 
            WHERE tenant_id = :tenant_id
            """
            
            result = self.database_manager.execute_query(storage_query, {'tenant_id': tenant_id}, tenant_id)
            if result.success and result.data:
                data = result.data[0]
                metrics.models_created = data.get('model_count', 0)
                metrics.storage_used = data.get('storage_used', 0)
            
            # Get execution count
            execution_query = """
            SELECT COUNT(*) as execution_count,
                   MAX(start_time) as last_activity
            FROM execution_history 
            WHERE tenant_id = :tenant_id
            """
            
            result = self.database_manager.execute_query(execution_query, {'tenant_id': tenant_id}, tenant_id)
            if result.success and result.data:
                data = result.data[0]
                metrics.executions_performed = data.get('execution_count', 0)
                if data.get('last_activity'):
                    metrics.last_activity = datetime.fromisoformat(data['last_activity'])
            
            # Get active connections (simplified)
            metrics.active_connections = len([ctx for ctx in self._active_contexts.values() 
                                            if ctx.tenant_id == tenant_id])
            
        except Exception as e:
            self.logger.error(f"Failed to get usage metrics for tenant {tenant_id}: {e}")
        
        return metrics
    
    def export_tenant_data(self, tenant_id: str) -> ExportResult:
        """
        Export all data for a tenant.
        
        Args:
            tenant_id: ID of the tenant
            
        Returns:
            ExportResult: Result of the export operation
        """
        import json
        import os
        from datetime import datetime
        
        export_path = f"tenant_export_{tenant_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        try:
            # Get tenant info
            tenant_info = self.tenant_registry.get_tenant(tenant_id)
            if not tenant_info:
                return ExportResult(
                    success=False,
                    export_path=export_path,
                    tenant_id=tenant_id,
                    error_message="Tenant not found"
                )
            
            export_data = {
                'tenant_info': {
                    'name': tenant_info.name,
                    'domain': tenant_info.domain,
                    'configuration': tenant_info.configuration,
                    'resource_limits': tenant_info.resource_limits,
                    'billing_info': tenant_info.billing_info,
                    'status': tenant_info.status
                },
                'visual_models': [],
                'custom_components': [],
                'execution_history': [],
                'configurations': {},
                'export_metadata': {
                    'export_time': datetime.now().isoformat(),
                    'tenant_id': tenant_id,
                    'version': '1.0'
                }
            }
            
            # Export visual models
            models_query = "SELECT * FROM visual_models WHERE tenant_id = :tenant_id"
            result = self.database_manager.execute_query(models_query, {'tenant_id': tenant_id}, tenant_id)
            if result.success:
                export_data['visual_models'] = result.data
            
            # Export custom components
            components_query = "SELECT * FROM custom_components WHERE tenant_id = :tenant_id"
            result = self.database_manager.execute_query(components_query, {'tenant_id': tenant_id}, tenant_id)
            if result.success:
                export_data['custom_components'] = result.data
            
            # Export execution history (last 1000 records)
            history_query = """
            SELECT * FROM execution_history 
            WHERE tenant_id = :tenant_id 
            ORDER BY start_time DESC 
            LIMIT 1000
            """
            result = self.database_manager.execute_query(history_query, {'tenant_id': tenant_id}, tenant_id)
            if result.success:
                export_data['execution_history'] = result.data
            
            # Export configurations
            config = self.tenant_config_manager.get_tenant_configuration(tenant_id)
            export_data['configurations'] = {
                'settings': config.settings,
                'feature_flags': config.feature_flags,
                'resource_limits': config.resource_limits,
                'ui_customization': config.ui_customization,
                'integrations': config.integrations
            }
            
            # Write to file
            with open(export_path, 'w') as f:
                json.dump(export_data, f, indent=2, default=str)
            
            export_size = os.path.getsize(export_path)
            
            return ExportResult(
                success=True,
                export_path=export_path,
                tenant_id=tenant_id,
                export_size=export_size,
                exported_tables=['visual_models', 'custom_components', 'execution_history', 'configurations']
            )
            
        except Exception as e:
            self.logger.error(f"Failed to export tenant data for {tenant_id}: {e}")
            return ExportResult(
                success=False,
                export_path=export_path,
                tenant_id=tenant_id,
                error_message=str(e)
            )
    
    def import_tenant_data(self, tenant_id: str, data: TenantData) -> ImportResult:
        """
        Import data for a tenant.
        
        Args:
            tenant_id: ID of the tenant
            data: Tenant data to import
            
        Returns:
            ImportResult: Result of the import operation
        """
        try:
            imported_records = 0
            imported_tables = []
            
            # Import visual models
            if data.visual_models:
                operations = []
                for model in data.visual_models:
                    model['tenant_id'] = tenant_id  # Ensure correct tenant
                    model['id'] = str(uuid.uuid4())  # Generate new ID
                    operations.append(DatabaseOperation(
                        operation_type='insert',
                        table='visual_models',
                        data=model
                    ))
                
                result = self.database_manager.execute_transaction(operations, tenant_id)
                if result.success:
                    imported_records += len(data.visual_models)
                    imported_tables.append('visual_models')
            
            # Import custom components
            if data.custom_components:
                operations = []
                for component in data.custom_components:
                    component['tenant_id'] = tenant_id  # Ensure correct tenant
                    component['id'] = str(uuid.uuid4())  # Generate new ID
                    operations.append(DatabaseOperation(
                        operation_type='insert',
                        table='custom_components',
                        data=component
                    ))
                
                result = self.database_manager.execute_transaction(operations, tenant_id)
                if result.success:
                    imported_records += len(data.custom_components)
                    imported_tables.append('custom_components')
            
            # Import configurations
            if data.configurations:
                config = TenantConfig(
                    tenant_id=tenant_id,
                    settings=data.configurations.get('settings', {}),
                    feature_flags=data.configurations.get('feature_flags', {}),
                    resource_limits=data.configurations.get('resource_limits', {}),
                    ui_customization=data.configurations.get('ui_customization', {}),
                    integrations=data.configurations.get('integrations', {})
                )
                
                if self.tenant_config_manager.update_tenant_configuration(tenant_id, config):
                    imported_tables.append('configurations')
            
            return ImportResult(
                success=True,
                import_path="",
                tenant_id=tenant_id,
                imported_records=imported_records,
                imported_tables=imported_tables
            )
            
        except Exception as e:
            self.logger.error(f"Failed to import tenant data for {tenant_id}: {e}")
            return ImportResult(
                success=False,
                import_path="",
                tenant_id=tenant_id,
                error_message=str(e)
            )
    
    def validate_tenant_access(self, user_id: str, tenant_id: str) -> bool:
        """
        Validate that a user has access to a tenant.
        
        Args:
            user_id: ID of the user
            tenant_id: ID of the tenant
            
        Returns:
            bool: True if user has access
        """
        return self.isolation_enforcer.validate_tenant_access(user_id, tenant_id)
    
    def get_tenant_configuration(self, tenant_id: str) -> TenantConfig:
        """
        Get configuration for a tenant.
        
        Args:
            tenant_id: ID of the tenant
            
        Returns:
            TenantConfig: Tenant configuration
        """
        return self.tenant_config_manager.get_tenant_configuration(tenant_id)
    
    def update_tenant_configuration(self, tenant_id: str, config: TenantConfig) -> bool:
        """
        Update configuration for a tenant.
        
        Args:
            tenant_id: ID of the tenant
            config: New configuration
            
        Returns:
            bool: True if update was successful
        """
        return self.tenant_config_manager.update_tenant_configuration(tenant_id, config)
    
    def validate_tenant_access(self, 
                             user_id: str, 
                             tenant_id: str, 
                             operation: str, 
                             resource_type: str,
                             resource_id: Optional[str] = None,
                             data: Optional[Dict[str, Any]] = None) -> Tuple[bool, Optional[str]]:
        """
        Validate tenant access with cross-tenant prevention.
        
        Args:
            user_id: ID of the user
            tenant_id: ID of the tenant
            operation: Operation being performed
            resource_type: Type of resource
            resource_id: Optional resource ID
            data: Optional data being accessed
            
        Returns:
            Tuple[bool, Optional[str]]: (is_allowed, error_message)
        """
        return self.access_controller.validate_tenant_access(
            user_id, tenant_id, operation, resource_type, resource_id, data
        )
    
    def create_tenant_database_constraints(self, tenant_id: str) -> bool:
        """
        Create database-level constraints for tenant isolation.
        
        Args:
            tenant_id: ID of the tenant
            
        Returns:
            bool: True if constraints were created successfully
        """
        return self.access_controller.create_tenant_constraints(tenant_id)
    
    def validate_query_safety(self, query: str, tenant_id: str) -> Tuple[bool, List[str]]:
        """
        Validate that a query is safe for tenant execution.
        
        Args:
            query: SQL query to validate
            tenant_id: ID of the tenant
            
        Returns:
            Tuple[bool, List[str]]: (is_safe, list_of_violations)
        """
        return self.access_controller.validate_query_safety(query, tenant_id)
    
    def get_access_violation_summary(self, tenant_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get summary of access violations.
        
        Args:
            tenant_id: Optional tenant ID to filter by
            
        Returns:
            Dict[str, Any]: Violation summary
        """
        return self.access_controller.get_violation_summary(tenant_id)
    
    def tenant_operation_context(self, user_id: str, tenant_id: str):
        """
        Context manager for tenant operations with access control.
        
        Args:
            user_id: ID of the user
            tenant_id: ID of the tenant
            
        Returns:
            Context manager for tenant operations
        """
        return self.access_controller.tenant_operation_context(user_id, tenant_id)
    
    def _initialize_tenant_resources(self, tenant_id: str):
        """Initialize resources for a new tenant."""
        try:
            # Create database-level constraints for tenant isolation
            if not self.access_controller.create_tenant_constraints(tenant_id):
                self.logger.warning(f"Failed to create database constraints for tenant: {tenant_id}")
            
            # Create tenant-specific indexes if needed
            # This is a placeholder for any tenant-specific initialization
            self.logger.info(f"Initialized resources for tenant: {tenant_id}")
        except Exception as e:
            self.logger.error(f"Failed to initialize resources for tenant {tenant_id}: {e}")
    
    def _cleanup_tenant_data(self, tenant_id: str):
        """Clean up all data for a deleted tenant."""
        try:
            # List of tables to clean up
            tables_to_cleanup = [
                'visual_models',
                'custom_components', 
                'execution_history',
                'audit_logs',
                'tenant_configurations',
                'user_tenant_assignments'
            ]
            
            operations = []
            for table in tables_to_cleanup:
                operations.append(DatabaseOperation(
                    operation_type='delete',
                    table=table,
                    conditions={'tenant_id': tenant_id}
                ))
            
            # Execute cleanup in transaction
            result = self.database_manager.execute_transaction(operations)
            
            if result.success:
                self.logger.info(f"Cleaned up data for tenant: {tenant_id}")
            else:
                self.logger.error(f"Failed to cleanup data for tenant {tenant_id}: {result.error_message}")
                
        except Exception as e:
            self.logger.error(f"Error during tenant cleanup {tenant_id}: {e}")
    
    def shutdown(self):
        """Shutdown the multi-tenant manager and cleanup resources."""
        try:
            # Shutdown access controller
            self.access_controller.shutdown()
            
            # Clear active contexts
            self._active_contexts.clear()
            
            self.logger.info("Multi-tenant manager shutdown completed")
        except Exception as e:
            self.logger.error(f"Error during multi-tenant manager shutdown: {e}")