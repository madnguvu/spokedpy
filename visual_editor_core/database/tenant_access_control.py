"""
Tenant Access Control - Implements cross-tenant access prevention and monitoring.
"""

import logging
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field
from contextlib import contextmanager
import threading
import time

from .models import DatabaseOperation, QueryResult, TransactionResult
from .exceptions import (
    DatabaseError,
    IsolationError,
    TenantAccessDeniedError,
    TenantNotFoundError
)


@dataclass
class AccessAttempt:
    """Represents an access attempt that needs validation."""
    user_id: str
    requested_tenant_id: str
    actual_tenant_id: str
    operation_type: str
    resource_type: str
    resource_id: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    
    def is_cross_tenant(self) -> bool:
        """Check if this is a cross-tenant access attempt."""
        return self.requested_tenant_id != self.actual_tenant_id


@dataclass
class AccessViolation:
    """Represents a detected access violation."""
    user_id: str
    attempted_tenant_id: str
    actual_tenant_id: str
    violation_type: str
    severity: str  # low, medium, high, critical
    blocked: bool
    timestamp: datetime = field(default_factory=datetime.now)
    details: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging."""
        return {
            'user_id': self.user_id,
            'attempted_tenant_id': self.attempted_tenant_id,
            'actual_tenant_id': self.actual_tenant_id,
            'violation_type': self.violation_type,
            'severity': self.severity,
            'blocked': self.blocked,
            'timestamp': self.timestamp.isoformat(),
            'details': self.details
        }


@dataclass
class TenantAccessRule:
    """Defines access rules for tenant operations."""
    tenant_id: str
    resource_type: str
    allowed_operations: Set[str]
    restrictions: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    def allows_operation(self, operation: str) -> bool:
        """Check if operation is allowed."""
        return operation in self.allowed_operations


class DatabaseConstraintEnforcer:
    """Enforces tenant isolation at the database level."""
    
    def __init__(self, database_manager):
        self.database_manager = database_manager
        self.logger = logging.getLogger(__name__)
        self._constraint_cache: Dict[str, List[str]] = {}
    
    def create_tenant_constraints(self, tenant_id: str) -> bool:
        """Create database-level constraints for a tenant."""
        try:
            # Create row-level security policies for PostgreSQL
            if self.database_manager.get_current_database_type().value == "postgresql":
                self._create_postgresql_constraints(tenant_id)
            else:
                self._create_sqlite_constraints(tenant_id)
            
            self.logger.info(f"Created database constraints for tenant: {tenant_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to create constraints for tenant {tenant_id}: {e}")
            return False
    
    def validate_query_constraints(self, query: str, tenant_id: str) -> Tuple[bool, List[str]]:
        """Validate that a query respects tenant constraints."""
        violations = []
        
        try:
            # Parse query to check for potential violations
            query_upper = query.upper()
            
            # Check for attempts to access other tenants' data
            if "TENANT_ID" in query_upper:
                # Look for hardcoded tenant IDs that don't match
                if f"'{tenant_id}'" not in query and f'"{tenant_id}"' not in query:
                    # Check if query contains other tenant IDs
                    import re
                    tenant_id_pattern = r"['\"]([a-f0-9-]{36})['\"]"
                    matches = re.findall(tenant_id_pattern, query)
                    
                    for match in matches:
                        if match != tenant_id:
                            violations.append(f"Attempt to access tenant {match} from tenant {tenant_id}")
            
            # Check for attempts to bypass tenant scoping
            dangerous_patterns = [
                "DROP TABLE",
                "TRUNCATE TABLE", 
                "DELETE FROM.*WITHOUT.*TENANT_ID",
                "UPDATE.*WITHOUT.*TENANT_ID"
            ]
            
            for pattern in dangerous_patterns:
                if re.search(pattern, query_upper):
                    violations.append(f"Potentially dangerous operation detected: {pattern}")
            
            return len(violations) == 0, violations
            
        except Exception as e:
            self.logger.error(f"Error validating query constraints: {e}")
            return False, [f"Query validation error: {str(e)}"]
    
    def _create_postgresql_constraints(self, tenant_id: str):
        """Create PostgreSQL-specific constraints."""
        # Enable row-level security on tenant-aware tables
        tenant_tables = [
            'visual_models', 'custom_components', 'execution_records',
            'audit_logs', 'tenant_configurations', 'user_tenant_assignments'
        ]
        
        operations = []
        
        for table in tenant_tables:
            # Enable RLS
            operations.append(DatabaseOperation(
                operation_type="execute",
                table=table,
                query=f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"
            ))
            
            # Create policy for tenant isolation
            policy_name = f"{table}_tenant_isolation"
            policy_query = f"""
                CREATE POLICY {policy_name} ON {table}
                USING (tenant_id = current_setting('app.current_tenant_id'))
                WITH CHECK (tenant_id = current_setting('app.current_tenant_id'))
            """
            
            operations.append(DatabaseOperation(
                operation_type="execute",
                table=table,
                query=policy_query
            ))
        
        # Execute all constraint operations
        result = self.database_manager.execute_transaction(operations)
        if not result.success:
            raise DatabaseError(f"Failed to create PostgreSQL constraints: {result.error_message}")
    
    def _create_sqlite_constraints(self, tenant_id: str):
        """Create SQLite-specific constraints (using triggers)."""
        # SQLite doesn't have RLS, so we use triggers for enforcement
        tenant_tables = [
            'visual_models', 'custom_components', 'execution_records',
            'audit_logs', 'tenant_configurations', 'user_tenant_assignments'
        ]
        
        operations = []
        
        for table in tenant_tables:
            # Create trigger to prevent cross-tenant access on INSERT
            trigger_name = f"{table}_tenant_insert_check"
            trigger_query = f"""
                CREATE TRIGGER IF NOT EXISTS {trigger_name}
                BEFORE INSERT ON {table}
                FOR EACH ROW
                WHEN NEW.tenant_id != '{tenant_id}'
                BEGIN
                    SELECT RAISE(ABORT, 'Cross-tenant access denied');
                END
            """
            
            operations.append(DatabaseOperation(
                operation_type="execute",
                table=table,
                query=trigger_query
            ))
            
            # Create trigger to prevent cross-tenant access on UPDATE
            update_trigger_name = f"{table}_tenant_update_check"
            update_trigger_query = f"""
                CREATE TRIGGER IF NOT EXISTS {update_trigger_name}
                BEFORE UPDATE ON {table}
                FOR EACH ROW
                WHEN OLD.tenant_id != '{tenant_id}' OR NEW.tenant_id != '{tenant_id}'
                BEGIN
                    SELECT RAISE(ABORT, 'Cross-tenant access denied');
                END
            """
            
            operations.append(DatabaseOperation(
                operation_type="execute",
                table=table,
                query=update_trigger_query
            ))
        
        # Execute all constraint operations
        result = self.database_manager.execute_transaction(operations)
        if not result.success:
            raise DatabaseError(f"Failed to create SQLite constraints: {result.error_message}")


class ApplicationLevelValidator:
    """Validates tenant access at the application level."""
    
    def __init__(self, database_manager):
        self.database_manager = database_manager
        self.logger = logging.getLogger(__name__)
        self._validation_cache: Dict[str, Tuple[bool, datetime]] = {}
        self._cache_ttl = timedelta(minutes=5)
    
    def validate_tenant_operation(self, 
                                user_id: str, 
                                tenant_id: str, 
                                operation: str, 
                                resource_type: str,
                                resource_id: Optional[str] = None) -> Tuple[bool, Optional[str]]:
        """
        Validate a tenant operation at the application level.
        
        Args:
            user_id: ID of the user performing the operation
            tenant_id: ID of the tenant being accessed
            operation: Type of operation (read, write, delete, etc.)
            resource_type: Type of resource being accessed
            resource_id: Optional specific resource ID
            
        Returns:
            Tuple[bool, Optional[str]]: (is_valid, error_message)
        """
        try:
            # Check cache first
            cache_key = f"{user_id}:{tenant_id}:{operation}:{resource_type}"
            if cache_key in self._validation_cache:
                cached_result, cached_time = self._validation_cache[cache_key]
                if datetime.now() - cached_time < self._cache_ttl:
                    return cached_result, None if cached_result else "Access denied (cached)"
            
            # Validate user has access to tenant
            if not self._validate_user_tenant_access(user_id, tenant_id):
                error_msg = f"User {user_id} does not have access to tenant {tenant_id}"
                self._validation_cache[cache_key] = (False, datetime.now())
                return False, error_msg
            
            # Validate operation is allowed for resource type
            if not self._validate_operation_allowed(user_id, tenant_id, operation, resource_type):
                error_msg = f"Operation {operation} not allowed on {resource_type} for user {user_id}"
                self._validation_cache[cache_key] = (False, datetime.now())
                return False, error_msg
            
            # Validate resource-specific access if resource_id provided
            if resource_id and not self._validate_resource_access(user_id, tenant_id, resource_type, resource_id):
                error_msg = f"Access denied to {resource_type} {resource_id}"
                self._validation_cache[cache_key] = (False, datetime.now())
                return False, error_msg
            
            # Cache successful validation
            self._validation_cache[cache_key] = (True, datetime.now())
            return True, None
            
        except Exception as e:
            self.logger.error(f"Error validating tenant operation: {e}")
            return False, f"Validation error: {str(e)}"
    
    def validate_data_access(self, 
                           user_id: str, 
                           tenant_id: str, 
                           data: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Validate that data access respects tenant boundaries.
        
        Args:
            user_id: ID of the user
            tenant_id: ID of the tenant
            data: Data being accessed
            
        Returns:
            Tuple[bool, List[str]]: (is_valid, list_of_violations)
        """
        violations = []
        
        try:
            # Check if data contains tenant_id field
            if 'tenant_id' in data:
                data_tenant_id = data['tenant_id']
                if data_tenant_id != tenant_id:
                    violations.append(f"Data belongs to tenant {data_tenant_id}, not {tenant_id}")
            
            # Check for references to other tenants
            for key, value in data.items():
                if isinstance(value, str) and key.endswith('_id'):
                    # Check if this might be a tenant ID reference
                    if self._looks_like_tenant_id(value) and value != tenant_id:
                        if not self._validate_cross_tenant_reference(user_id, tenant_id, value):
                            violations.append(f"Unauthorized reference to tenant {value} in field {key}")
            
            return len(violations) == 0, violations
            
        except Exception as e:
            self.logger.error(f"Error validating data access: {e}")
            return False, [f"Data validation error: {str(e)}"]
    
    def _validate_user_tenant_access(self, user_id: str, tenant_id: str) -> bool:
        """Validate that user has access to tenant."""
        query = """
        SELECT COUNT(*) as count 
        FROM user_tenant_assignments 
        WHERE user_id = :user_id AND tenant_id = :tenant_id AND status = 'active'
        """
        
        result = self.database_manager.execute_query(query, {
            'user_id': user_id,
            'tenant_id': tenant_id
        })
        
        return result.success and result.data and result.data[0]['count'] > 0
    
    def _validate_operation_allowed(self, user_id: str, tenant_id: str, operation: str, resource_type: str) -> bool:
        """Validate that operation is allowed for the resource type."""
        # Get user roles and permissions
        query = """
        SELECT r.permissions 
        FROM user_roles ur
        JOIN roles r ON ur.role_id = r.id
        WHERE ur.user_id = :user_id AND r.tenant_id = :tenant_id
        AND (ur.expires_at IS NULL OR ur.expires_at > :now)
        """
        
        result = self.database_manager.execute_query(query, {
            'user_id': user_id,
            'tenant_id': tenant_id,
            'now': datetime.now().isoformat()
        }, tenant_id)
        
        if not result.success or not result.data:
            return False
        
        # Check if any role allows the operation
        required_permission = f"{resource_type}:{operation}"
        
        for row in result.data:
            permissions = row.get('permissions', [])
            if isinstance(permissions, str):
                import json
                try:
                    permissions = json.loads(permissions)
                except:
                    permissions = []
            
            if required_permission in permissions or f"{resource_type}:*" in permissions:
                return True
        
        return False
    
    def _validate_resource_access(self, user_id: str, tenant_id: str, resource_type: str, resource_id: str) -> bool:
        """Validate access to a specific resource."""
        # Map resource types to tables
        table_mapping = {
            'visual_model': 'visual_models',
            'custom_component': 'custom_components',
            'execution_record': 'execution_records'
        }
        
        table_name = table_mapping.get(resource_type)
        if not table_name:
            return True  # Unknown resource type, allow by default
        
        # Check if resource exists and belongs to tenant
        query = f"""
        SELECT COUNT(*) as count 
        FROM {table_name} 
        WHERE id = :resource_id AND tenant_id = :tenant_id
        """
        
        result = self.database_manager.execute_query(query, {
            'resource_id': resource_id,
            'tenant_id': tenant_id
        }, tenant_id)
        
        return result.success and result.data and result.data[0]['count'] > 0
    
    def _looks_like_tenant_id(self, value: str) -> bool:
        """Check if a string looks like a tenant ID (UUID format)."""
        import re
        uuid_pattern = r'^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$'
        return bool(re.match(uuid_pattern, value, re.IGNORECASE))
    
    def _validate_cross_tenant_reference(self, user_id: str, tenant_id: str, referenced_tenant_id: str) -> bool:
        """Validate if cross-tenant reference is allowed."""
        # For now, cross-tenant references are not allowed
        # This could be extended to support specific cases like shared resources
        return False


class TenantContextValidator:
    """Validates and enforces tenant context throughout operations."""
    
    def __init__(self, database_manager):
        self.database_manager = database_manager
        self.logger = logging.getLogger(__name__)
        self._context_stack = threading.local()
    
    @contextmanager
    def tenant_context(self, user_id: str, tenant_id: str):
        """Context manager for tenant operations."""
        if not hasattr(self._context_stack, 'contexts'):
            self._context_stack.contexts = []
        
        # Validate tenant context
        if not self._validate_tenant_context(user_id, tenant_id):
            raise TenantAccessDeniedError(
                f"Access denied to tenant {tenant_id} for user {user_id}",
                tenant_id,
                user_id
            )
        
        # Push context
        context = {'user_id': user_id, 'tenant_id': tenant_id, 'timestamp': datetime.now()}
        self._context_stack.contexts.append(context)
        
        try:
            yield context
        finally:
            # Pop context
            if self._context_stack.contexts:
                self._context_stack.contexts.pop()
    
    def get_current_tenant_context(self) -> Optional[Dict[str, Any]]:
        """Get the current tenant context."""
        if hasattr(self._context_stack, 'contexts') and self._context_stack.contexts:
            return self._context_stack.contexts[-1]
        return None
    
    def validate_context_consistency(self, operation_tenant_id: str) -> bool:
        """Validate that operation tenant matches current context."""
        current_context = self.get_current_tenant_context()
        if not current_context:
            return False
        
        return current_context['tenant_id'] == operation_tenant_id
    
    def _validate_tenant_context(self, user_id: str, tenant_id: str) -> bool:
        """Validate that user can access tenant."""
        query = """
        SELECT COUNT(*) as count 
        FROM user_tenant_assignments 
        WHERE user_id = :user_id AND tenant_id = :tenant_id AND status = 'active'
        """
        
        result = self.database_manager.execute_query(query, {
            'user_id': user_id,
            'tenant_id': tenant_id
        })
        
        return result.success and result.data and result.data[0]['count'] > 0


class AccessViolationMonitor:
    """Monitors and alerts on access violations."""
    
    def __init__(self, database_manager):
        self.database_manager = database_manager
        self.logger = logging.getLogger(__name__)
        self._violation_counts: Dict[str, int] = {}
        self._alert_thresholds = {
            'cross_tenant_access': 5,
            'permission_denied': 10,
            'data_breach_attempt': 1
        }
        self._monitoring_active = True
        self._monitor_thread = None
    
    def start_monitoring(self):
        """Start the violation monitoring system."""
        if self._monitor_thread is None or not self._monitor_thread.is_alive():
            self._monitoring_active = True
            self._monitor_thread = threading.Thread(target=self._monitor_violations, daemon=True)
            self._monitor_thread.start()
            self.logger.info("Access violation monitoring started")
    
    def stop_monitoring(self):
        """Stop the violation monitoring system."""
        self._monitoring_active = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5)
        self.logger.info("Access violation monitoring stopped")
    
    def log_access_violation(self, violation: AccessViolation):
        """Log an access violation."""
        try:
            # Store violation in database
            violation_data = {
                'id': str(uuid.uuid4()),
                'user_id': violation.user_id,
                'attempted_tenant_id': violation.attempted_tenant_id,
                'actual_tenant_id': violation.actual_tenant_id,
                'access_type': violation.violation_type,
                'blocked': violation.blocked,
                'timestamp': violation.timestamp.isoformat(),
                'ip_address': violation.details.get('ip_address'),
                'user_agent': violation.details.get('user_agent'),
                'details': violation.details
            }
            
            operation = DatabaseOperation(
                operation_type='insert',
                table='cross_tenant_access_logs',
                data=violation_data
            )
            
            result = self.database_manager.execute_transaction([operation])
            
            if result.success:
                self.logger.warning(f"Access violation logged: {violation.violation_type} by user {violation.user_id}")
                
                # Update violation counts
                key = f"{violation.user_id}:{violation.violation_type}"
                self._violation_counts[key] = self._violation_counts.get(key, 0) + 1
                
                # Check if alert threshold reached
                self._check_alert_thresholds(violation)
            else:
                self.logger.error(f"Failed to log access violation: {result.error_message}")
                
        except Exception as e:
            self.logger.error(f"Error logging access violation: {e}")
    
    def get_violation_summary(self, tenant_id: Optional[str] = None, 
                            time_range: Optional[timedelta] = None) -> Dict[str, Any]:
        """Get summary of access violations."""
        try:
            query = "SELECT * FROM cross_tenant_access_logs"
            params = {}
            conditions = []
            
            if tenant_id:
                conditions.append("(attempted_tenant_id = :tenant_id OR actual_tenant_id = :tenant_id)")
                params['tenant_id'] = tenant_id
            
            if time_range:
                since = datetime.now() - time_range
                conditions.append("timestamp >= :since")
                params['since'] = since.isoformat()
            
            if conditions:
                query += " WHERE " + " AND ".join(conditions)
            
            query += " ORDER BY timestamp DESC"
            
            result = self.database_manager.execute_query(query, params)
            
            if result.success:
                violations = result.data
                
                # Summarize violations
                summary = {
                    'total_violations': len(violations),
                    'blocked_violations': len([v for v in violations if v.get('blocked', True)]),
                    'violation_types': {},
                    'top_violators': {},
                    'recent_violations': violations[:10]  # Last 10 violations
                }
                
                # Count by type
                for violation in violations:
                    vtype = violation.get('access_type', 'unknown')
                    summary['violation_types'][vtype] = summary['violation_types'].get(vtype, 0) + 1
                
                # Count by user
                for violation in violations:
                    user_id = violation.get('user_id', 'unknown')
                    summary['top_violators'][user_id] = summary['top_violators'].get(user_id, 0) + 1
                
                return summary
            else:
                return {'error': result.error_message}
                
        except Exception as e:
            self.logger.error(f"Error getting violation summary: {e}")
            return {'error': str(e)}
    
    def _monitor_violations(self):
        """Background monitoring of violations."""
        while self._monitoring_active:
            try:
                # Check for recent violations that might indicate an attack
                recent_violations = self._get_recent_violations()
                
                # Analyze patterns
                self._analyze_violation_patterns(recent_violations)
                
                # Sleep before next check
                time.sleep(60)  # Check every minute
                
            except Exception as e:
                self.logger.error(f"Error in violation monitoring: {e}")
                time.sleep(60)
    
    def _get_recent_violations(self) -> List[Dict[str, Any]]:
        """Get recent violations for analysis."""
        since = datetime.now() - timedelta(minutes=10)
        query = """
        SELECT * FROM cross_tenant_access_logs 
        WHERE timestamp >= :since 
        ORDER BY timestamp DESC
        """
        
        result = self.database_manager.execute_query(query, {
            'since': since.isoformat()
        })
        
        return result.data if result.success else []
    
    def _analyze_violation_patterns(self, violations: List[Dict[str, Any]]):
        """Analyze violation patterns for potential attacks."""
        if not violations:
            return
        
        # Group by user
        user_violations = {}
        for violation in violations:
            user_id = violation.get('user_id', 'unknown')
            if user_id not in user_violations:
                user_violations[user_id] = []
            user_violations[user_id].append(violation)
        
        # Check for suspicious patterns
        for user_id, user_viols in user_violations.items():
            if len(user_viols) >= 5:  # 5 or more violations in 10 minutes
                self.logger.critical(f"Potential attack detected: User {user_id} has {len(user_viols)} violations in 10 minutes")
                # Could trigger additional security measures here
    
    def _check_alert_thresholds(self, violation: AccessViolation):
        """Check if violation counts exceed alert thresholds."""
        key = f"{violation.user_id}:{violation.violation_type}"
        count = self._violation_counts.get(key, 0)
        threshold = self._alert_thresholds.get(violation.violation_type, 999)
        
        if count >= threshold:
            self.logger.critical(f"Alert threshold exceeded: {violation.violation_type} by user {violation.user_id} ({count} violations)")
            # Could trigger additional alerting mechanisms here


class TenantAccessController:
    """
    Main controller for tenant access control and cross-tenant access prevention.
    """
    
    def __init__(self, database_manager):
        """
        Initialize the tenant access controller.
        
        Args:
            database_manager: Database manager instance
        """
        self.database_manager = database_manager
        self.logger = logging.getLogger(__name__)
        
        # Initialize components
        self.constraint_enforcer = DatabaseConstraintEnforcer(database_manager)
        self.app_validator = ApplicationLevelValidator(database_manager)
        self.context_validator = TenantContextValidator(database_manager)
        self.violation_monitor = AccessViolationMonitor(database_manager)
        
        # Start monitoring
        self.violation_monitor.start_monitoring()
        
        self.logger.info("Tenant access controller initialized")
    
    def validate_tenant_access(self, 
                             user_id: str, 
                             tenant_id: str, 
                             operation: str, 
                             resource_type: str,
                             resource_id: Optional[str] = None,
                             data: Optional[Dict[str, Any]] = None) -> Tuple[bool, Optional[str]]:
        """
        Comprehensive tenant access validation.
        
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
        try:
            # Application-level validation
            is_valid, error_msg = self.app_validator.validate_tenant_operation(
                user_id, tenant_id, operation, resource_type, resource_id
            )
            
            if not is_valid:
                # Log violation
                violation = AccessViolation(
                    user_id=user_id,
                    attempted_tenant_id=tenant_id,
                    actual_tenant_id=tenant_id,  # Same in this case
                    violation_type='permission_denied',
                    severity='medium',
                    blocked=True,
                    details={'operation': operation, 'resource_type': resource_type, 'error': error_msg}
                )
                self.violation_monitor.log_access_violation(violation)
                return False, error_msg
            
            # Data validation if provided
            if data:
                data_valid, violations = self.app_validator.validate_data_access(user_id, tenant_id, data)
                if not data_valid:
                    error_msg = f"Data access violations: {', '.join(violations)}"
                    
                    # Log violation
                    violation = AccessViolation(
                        user_id=user_id,
                        attempted_tenant_id=tenant_id,
                        actual_tenant_id=tenant_id,
                        violation_type='data_breach_attempt',
                        severity='high',
                        blocked=True,
                        details={'violations': violations, 'operation': operation}
                    )
                    self.violation_monitor.log_access_violation(violation)
                    return False, error_msg
            
            return True, None
            
        except Exception as e:
            self.logger.error(f"Error validating tenant access: {e}")
            return False, f"Access validation error: {str(e)}"
    
    def create_tenant_constraints(self, tenant_id: str) -> bool:
        """Create database-level constraints for a tenant."""
        return self.constraint_enforcer.create_tenant_constraints(tenant_id)
    
    def validate_query_safety(self, query: str, tenant_id: str) -> Tuple[bool, List[str]]:
        """Validate that a query is safe for tenant execution."""
        return self.constraint_enforcer.validate_query_constraints(query, tenant_id)
    
    @contextmanager
    def tenant_operation_context(self, user_id: str, tenant_id: str):
        """Context manager for tenant operations."""
        with self.context_validator.tenant_context(user_id, tenant_id) as context:
            yield context
    
    def get_violation_summary(self, tenant_id: Optional[str] = None) -> Dict[str, Any]:
        """Get access violation summary."""
        return self.violation_monitor.get_violation_summary(tenant_id)
    
    def shutdown(self):
        """Shutdown the access controller."""
        self.violation_monitor.stop_monitoring()
        self.logger.info("Tenant access controller shutdown")