"""
Database Manager - Unified interface for database operations with failover support.
"""

import logging
import time
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from contextlib import contextmanager

from .models import (
    DatabaseConfig,
    DatabaseConnection,
    QueryResult,
    TransactionResult,
    HealthMetrics,
    DatabaseOperation,
    BackupResult,
    RestoreResult,
    OptimizationResult,
    DatabaseType
)
from .adapters import PostgreSQLAdapter, SQLiteAdapter
from .connection_pool import ConnectionPool, PoolConfig
from .exceptions import (
    DatabaseError,
    ConnectionError,
    FailoverError,
    ValidationError,
    TransactionError
)
from .transaction_manager import TransactionManager, IsolationLevel
from .transaction_wrapper import TransactionWrapper
from .deadlock_detector import DeadlockDetector
from .transaction_monitor import TransactionMonitor


class DatabaseManager:
    """
    Unified database manager supporting PostgreSQL and SQLite with automatic failover.
    
    This class provides a single interface for all database operations while managing
    connections to both PostgreSQL (primary) and SQLite (fallback) databases.
    """
    
    def __init__(self, 
                 postgresql_config: Optional[DatabaseConfig] = None,
                 sqlite_config: Optional[DatabaseConfig] = None,
                 pool_config: Optional[PoolConfig] = None):
        """
        Initialize the database manager.
        
        Args:
            postgresql_config: Configuration for PostgreSQL database
            sqlite_config: Configuration for SQLite database  
            pool_config: Configuration for connection pool
        """
        self.logger = logging.getLogger(__name__)
        
        # Validate that at least one database is configured
        if not postgresql_config and not sqlite_config:
            raise ValueError("At least one database configuration (PostgreSQL or SQLite) must be provided")
        
        self.postgresql_config = postgresql_config
        self.sqlite_config = sqlite_config
        self.pool_config = pool_config or PoolConfig()
        
        # Initialize connection pool
        self.connection_pool = ConnectionPool(self.pool_config)
        
        # Initialize adapters
        self.postgresql_adapter = None
        self.sqlite_adapter = None
        
        if self.postgresql_config:
            self.postgresql_adapter = PostgreSQLAdapter(self.postgresql_config)
            self.connection_pool.register_adapter(
                DatabaseType.POSTGRESQL, 
                PostgreSQLAdapter, 
                self.postgresql_config
            )
        
        if self.sqlite_config:
            self.sqlite_adapter = SQLiteAdapter(self.sqlite_config)
            self.connection_pool.register_adapter(
                DatabaseType.SQLITE,
                SQLiteAdapter,
                self.sqlite_config
            )
        
        # Track current primary database
        self._current_primary = DatabaseType.POSTGRESQL if self.postgresql_adapter else DatabaseType.SQLITE
        self._failover_occurred = False
        self._last_health_check = {}
        
        # Initialize migration manager (will be set after database initialization)
        self._migration_manager = None
        
        # Initialize multi-tenant manager
        self._multi_tenant_manager = None
        
        # Initialize transaction management components
        self.transaction_manager = TransactionManager(self)
        self.transaction_wrapper = TransactionWrapper(self, self.transaction_manager)
        self.deadlock_detector = DeadlockDetector()
        self.transaction_monitor = TransactionMonitor()
        
        # Start monitoring components
        self.deadlock_detector.start_monitoring()
        self.transaction_monitor.start_monitoring()
        
        # Initialize databases
        self._initialize_databases()
    
    def get_connection(self, tenant_id: Optional[str] = None) -> DatabaseConnection:
        """
        Get a database connection from the pool.
        
        Args:
            tenant_id: Optional tenant ID for multi-tenant support
            
        Returns:
            DatabaseConnection: Active database connection
            
        Raises:
            ConnectionError: If no database connection is available
        """
        try:
            # Try primary database first
            connection = self.connection_pool.get_connection(self._current_primary)
            if connection and self._validate_connection(connection):
                return connection
        except Exception as e:
            self.logger.warning(f"Failed to get connection from primary database: {e}")
        
        # Try failover if primary failed
        if self._current_primary == DatabaseType.POSTGRESQL and self.sqlite_adapter:
            try:
                self.logger.info("Attempting failover to SQLite")
                connection = self.connection_pool.get_connection(DatabaseType.SQLITE)
                if connection and self._validate_connection(connection):
                    self._current_primary = DatabaseType.SQLITE
                    self._failover_occurred = True
                    self.logger.info("Successfully failed over to SQLite")
                    return connection
            except Exception as e:
                self.logger.error(f"Failover to SQLite failed: {e}")
        
        raise ConnectionError("No database connections available", str(self._current_primary))
    
    def execute_query(self, 
                     query: str, 
                     params: Optional[Dict[str, Any]] = None, 
                     tenant_id: Optional[str] = None) -> QueryResult:
        """
        Execute a database query.
        
        Args:
            query: SQL query to execute
            params: Query parameters
            tenant_id: Optional tenant ID for multi-tenant support
            
        Returns:
            QueryResult: Query execution result
        """
        connection = None
        try:
            connection = self.get_connection(tenant_id)
            adapter = self._get_adapter(connection.database_type)
            
            # Add tenant scoping if provided
            if tenant_id:
                query = self._add_tenant_scoping(query, tenant_id)
            
            result = adapter.execute_query(query, params)
            
            # Return connection to pool
            self.connection_pool.return_connection(connection)
            
            return result
            
        except Exception as e:
            if connection:
                self.connection_pool.close_connection(connection)
            
            self.logger.error(f"Query execution failed: {e}")
            return QueryResult(
                success=False,
                error_message=str(e)
            )
    
    def execute_transaction(self, 
                          operations: List[DatabaseOperation], 
                          tenant_id: Optional[str] = None) -> TransactionResult:
        """
        Execute a database transaction.
        
        Args:
            operations: List of database operations to execute
            tenant_id: Optional tenant ID for multi-tenant support
            
        Returns:
            TransactionResult: Transaction execution result
        """
        connection = None
        try:
            connection = self.get_connection(tenant_id)
            adapter = self._get_adapter(connection.database_type)
            
            # Add tenant scoping to operations if provided
            if tenant_id:
                operations = self._add_tenant_scoping_to_operations(operations, tenant_id)
            
            result = adapter.execute_transaction(operations)
            
            # Return connection to pool
            self.connection_pool.return_connection(connection)
            
            return result
            
        except Exception as e:
            if connection:
                self.connection_pool.close_connection(connection)
            
            self.logger.error(f"Transaction execution failed: {e}")
            return TransactionResult(
                success=False,
                transaction_id=str(uuid.uuid4()),
                operations_count=len(operations),
                error_message=str(e)
            )
    
    def store_json_data(self, 
                       table: str, 
                       data: Dict[str, Any], 
                       tenant_id: Optional[str] = None) -> str:
        """
        Store JSON data in the database.
        
        Args:
            table: Table name to store data
            data: JSON data to store
            tenant_id: Optional tenant ID for multi-tenant support
            
        Returns:
            str: ID of the stored record
        """
        import json
        
        record_id = str(uuid.uuid4())
        
        # Add metadata
        data_with_metadata = {
            'id': record_id,
            'data': json.dumps(data),  # Convert dict to JSON string
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat()
        }
        
        if tenant_id:
            data_with_metadata['tenant_id'] = tenant_id
        
        operation = DatabaseOperation(
            operation_type='insert',
            table=table,
            data=data_with_metadata
        )
        
        result = self.execute_transaction([operation], tenant_id)
        
        if result.success:
            return record_id
        else:
            raise DatabaseError(f"Failed to store JSON data: {result.error_message}")
    
    def query_json_data(self, 
                       table: str, 
                       json_path: str, 
                       value: Any, 
                       tenant_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Query JSON data from the database.
        
        Args:
            table: Table name to query
            json_path: JSON path to search
            value: Value to search for
            tenant_id: Optional tenant ID for multi-tenant support
            
        Returns:
            List[Dict[str, Any]]: Query results
        """
        import json
        
        # For SQLite, we'll do a simple text search in the JSON data
        # The data is stored as a JSON string, so we need to search within that JSON
        query = f"SELECT * FROM {table} WHERE data LIKE :search_pattern"
        
        # Create search pattern that looks for the key-value pair within the JSON string
        if isinstance(value, str):
            search_pattern = f'%"{json_path}": "{value}"%'
        else:
            search_pattern = f'%"{json_path}": {value}%'
        
        params = {"search_pattern": search_pattern}
        
        result = self.execute_query(query, params, tenant_id)
        
        if result.success:
            # Parse JSON data back to dict
            parsed_results = []
            for row in result.data:
                try:
                    row_copy = dict(row)
                    if 'data' in row_copy:
                        row_copy['data'] = json.loads(row_copy['data'])
                    parsed_results.append(row_copy)
                except json.JSONDecodeError:
                    # If JSON parsing fails, keep original data
                    parsed_results.append(dict(row))
            return parsed_results
        else:
            raise DatabaseError(f"Failed to query JSON data: {result.error_message}")
    
    def backup_database(self, backup_path: str, tenant_id: Optional[str] = None) -> BackupResult:
        """
        Create a database backup.
        
        Args:
            backup_path: Path to store the backup
            tenant_id: Optional tenant ID for multi-tenant support
            
        Returns:
            BackupResult: Backup operation result
        """
        try:
            adapter = self._get_adapter(self._current_primary)
            return adapter.backup_database(backup_path)
        except Exception as e:
            self.logger.error(f"Database backup failed: {e}")
            return BackupResult(
                success=False,
                backup_path=backup_path,
                error_message=str(e)
            )
    
    def restore_database(self, backup_path: str, tenant_id: Optional[str] = None) -> RestoreResult:
        """
        Restore database from backup.
        
        Args:
            backup_path: Path to the backup file
            tenant_id: Optional tenant ID for multi-tenant support
            
        Returns:
            RestoreResult: Restore operation result
        """
        try:
            adapter = self._get_adapter(self._current_primary)
            return adapter.restore_database(backup_path)
        except Exception as e:
            self.logger.error(f"Database restore failed: {e}")
            return RestoreResult(
                success=False,
                restore_path=backup_path,
                error_message=str(e)
            )
    
    def get_database_health(self) -> Dict[DatabaseType, HealthMetrics]:
        """
        Get health metrics for all configured databases.
        
        Returns:
            Dict[DatabaseType, HealthMetrics]: Health metrics by database type
        """
        health_metrics = {}
        
        if self.postgresql_adapter:
            try:
                health_metrics[DatabaseType.POSTGRESQL] = self.postgresql_adapter.get_health_metrics()
            except Exception as e:
                self.logger.error(f"Failed to get PostgreSQL health metrics: {e}")
                health_metrics[DatabaseType.POSTGRESQL] = HealthMetrics(
                    database_type=DatabaseType.POSTGRESQL,
                    is_available=False,
                    response_time=0.0,
                    active_connections=0,
                    max_connections=0,
                    error_count=1,
                    warnings=[str(e)]
                )
        
        if self.sqlite_adapter:
            try:
                health_metrics[DatabaseType.SQLITE] = self.sqlite_adapter.get_health_metrics()
            except Exception as e:
                self.logger.error(f"Failed to get SQLite health metrics: {e}")
                health_metrics[DatabaseType.SQLITE] = HealthMetrics(
                    database_type=DatabaseType.SQLITE,
                    is_available=False,
                    response_time=0.0,
                    active_connections=0,
                    max_connections=1,
                    error_count=1,
                    warnings=[str(e)]
                )
        
        self._last_health_check = health_metrics
        return health_metrics
    
    def optimize_performance(self) -> Dict[DatabaseType, OptimizationResult]:
        """
        Optimize database performance.
        
        Returns:
            Dict[DatabaseType, OptimizationResult]: Optimization results by database type
        """
        optimization_results = {}
        
        if self.postgresql_adapter:
            try:
                optimization_results[DatabaseType.POSTGRESQL] = self.postgresql_adapter.optimize_performance()
            except Exception as e:
                self.logger.error(f"PostgreSQL optimization failed: {e}")
                optimization_results[DatabaseType.POSTGRESQL] = OptimizationResult(
                    success=False,
                    error_message=str(e)
                )
        
        if self.sqlite_adapter:
            try:
                optimization_results[DatabaseType.SQLITE] = self.sqlite_adapter.optimize_performance()
            except Exception as e:
                self.logger.error(f"SQLite optimization failed: {e}")
                optimization_results[DatabaseType.SQLITE] = OptimizationResult(
                    success=False,
                    error_message=str(e)
                )
        
        return optimization_results
    
    def validate_connection(self, connection: DatabaseConnection) -> bool:
        """
        Validate a database connection.
        
        Args:
            connection: Database connection to validate
            
        Returns:
            bool: True if connection is valid
        """
        return self._validate_connection(connection)
    
    def get_current_database_type(self) -> DatabaseType:
        """
        Get the current primary database type.
        
        Returns:
            DatabaseType: Current primary database type
        """
        return self._current_primary
    
    def has_failover_occurred(self) -> bool:
        """
        Check if failover has occurred.
        
        Returns:
            bool: True if failover has occurred
        """
        return self._failover_occurred
    
    def reset_failover_status(self):
        """Reset failover status."""
        self._failover_occurred = False
    
    def force_failover(self) -> bool:
        """
        Force failover to backup database.
        
        Returns:
            bool: True if failover was successful
        """
        if self._current_primary == DatabaseType.POSTGRESQL and self.sqlite_adapter:
            try:
                # Test SQLite connection
                connection = self.connection_pool.get_connection(DatabaseType.SQLITE)
                if connection and self._validate_connection(connection):
                    self.connection_pool.return_connection(connection)
                    self._current_primary = DatabaseType.SQLITE
                    self._failover_occurred = True
                    self.logger.info("Forced failover to SQLite successful")
                    return True
            except Exception as e:
                self.logger.error(f"Forced failover failed: {e}")
        
        return False
    
    def attempt_primary_recovery(self) -> bool:
        """
        Attempt to recover primary database connection.
        
        Returns:
            bool: True if primary database is recovered
        """
        if self._current_primary == DatabaseType.SQLITE and self.postgresql_adapter:
            try:
                # Test PostgreSQL connection
                connection = self.connection_pool.get_connection(DatabaseType.POSTGRESQL)
                if connection and self._validate_connection(connection):
                    self.connection_pool.return_connection(connection)
                    self._current_primary = DatabaseType.POSTGRESQL
                    self.logger.info("Primary database recovery successful")
                    return True
            except Exception as e:
                self.logger.debug(f"Primary database recovery failed: {e}")
        
        return False
    
    @contextmanager
    def transaction(self, tenant_id: Optional[str] = None):
        """
        Context manager for database transactions.
        
        Args:
            tenant_id: Optional tenant ID for multi-tenant support
        """
        operations = []
        
        class TransactionContext:
            def __init__(self, operations_list):
                self.operations = operations_list
            
            def add_operation(self, operation: DatabaseOperation):
                self.operations.append(operation)
        
        context = TransactionContext(operations)
        
        try:
            yield context
            
            # Execute all operations in a transaction
            if operations:
                result = self.execute_transaction(operations, tenant_id)
                if not result.success:
                    raise TransactionError(f"Transaction failed: {result.error_message}")
        except Exception as e:
            self.logger.error(f"Transaction context failed: {e}")
            raise
    
    def get_migration_manager(self):
        """
        Get the migration manager instance.
        
        Returns:
            MigrationManager: Migration manager instance
        """
        if not self._migration_manager:
            # Import here to avoid circular imports
            from .migration_manager import MigrationManager
            self._migration_manager = MigrationManager(self)
        
        return self._migration_manager
    
    def get_multi_tenant_manager(self):
        """
        Get the multi-tenant manager instance.
        
        Returns:
            MultiTenantManager: Multi-tenant manager instance
        """
        if not self._multi_tenant_manager:
            # Import here to avoid circular imports
            from .multi_tenant_manager import MultiTenantManager
            self._multi_tenant_manager = MultiTenantManager(self)
        
        return self._multi_tenant_manager
    
    def get_transaction_manager(self) -> TransactionManager:
        """
        Get the transaction manager instance.
        
        Returns:
            TransactionManager: Transaction manager instance
        """
        return self.transaction_manager
    
    def get_transaction_wrapper(self) -> TransactionWrapper:
        """
        Get the transaction wrapper instance.
        
        Returns:
            TransactionWrapper: Transaction wrapper instance
        """
        return self.transaction_wrapper
    
    def get_deadlock_detector(self) -> DeadlockDetector:
        """
        Get the deadlock detector instance.
        
        Returns:
            DeadlockDetector: Deadlock detector instance
        """
        return self.deadlock_detector
    
    def get_transaction_monitor(self) -> TransactionMonitor:
        """
        Get the transaction monitor instance.
        
        Returns:
            TransactionMonitor: Transaction monitor instance
        """
        return self.transaction_monitor
    
    def execute_with_transaction_management(self,
                                          operations: List[DatabaseOperation],
                                          isolation_level: IsolationLevel = IsolationLevel.READ_COMMITTED,
                                          timeout: Optional[int] = None,
                                          tenant_id: Optional[str] = None) -> TransactionResult:
        """
        Execute operations with full transaction management features.
        
        Args:
            operations: List of database operations to execute
            isolation_level: Transaction isolation level
            timeout: Transaction timeout in seconds
            tenant_id: Optional tenant ID for multi-tenant support
            
        Returns:
            TransactionResult: Result of the transaction execution
        """
        try:
            with self.transaction_manager.transaction(
                connection=self.get_connection(tenant_id),
                isolation_level=isolation_level,
                timeout=timeout,
                tenant_id=tenant_id
            ) as context:
                # Add all operations to the transaction
                for operation in operations:
                    context.add_operation(operation)
                
                # Transaction will auto-commit when context exits
                return TransactionResult(
                    success=True,
                    transaction_id=context.transaction_id,
                    operations_count=len(operations),
                    execution_time=context.get_duration()
                )
        
        except Exception as e:
            return TransactionResult(
                success=False,
                transaction_id=str(uuid.uuid4()),
                operations_count=len(operations),
                rollback_performed=True,
                error_message=str(e)
            )
    
    def get_transaction_statistics(self) -> Dict[str, Any]:
        """
        Get comprehensive transaction statistics.
        
        Returns:
            Dict containing transaction statistics
        """
        stats = {}
        
        # Transaction manager stats
        if hasattr(self, 'transaction_manager'):
            stats['transaction_manager'] = self.transaction_manager.get_transaction_metrics()
        
        # Deadlock detector stats
        if hasattr(self, 'deadlock_detector'):
            stats['deadlock_detector'] = self.deadlock_detector.get_deadlock_statistics()
        
        # Transaction monitor stats
        if hasattr(self, 'transaction_monitor'):
            stats['performance_monitor'] = self.transaction_monitor.get_performance_summary()
        
        return stats
    
    def get_transaction_health_check(self) -> Dict[str, Any]:
        """
        Get transaction system health check.
        
        Returns:
            Dict containing health check results
        """
        health_check = {}
        
        if hasattr(self, 'transaction_monitor'):
            health_check = self.transaction_monitor.get_health_check()
        
        return health_check
    
    def close(self):
        """Close all database connections and cleanup resources."""
        try:
            # Stop monitoring components
            if hasattr(self, 'deadlock_detector'):
                self.deadlock_detector.stop_monitoring()
            
            if hasattr(self, 'transaction_monitor'):
                self.transaction_monitor.stop_monitoring()
            
            if hasattr(self, 'transaction_manager'):
                self.transaction_manager.shutdown()
            
            # Close connection pool
            self.connection_pool.close_all_connections()
            self.logger.info("Database manager closed successfully")
        except Exception as e:
            self.logger.error(f"Error closing database manager: {e}")
    
    def _initialize_databases(self):
        """Initialize database connections and perform health checks."""
        health_metrics = self.get_database_health()
        
        # Check if primary database is available
        if self.postgresql_adapter:
            pg_health = health_metrics.get(DatabaseType.POSTGRESQL)
            if not pg_health or not pg_health.is_available:
                self.logger.warning("PostgreSQL is not available, will use SQLite if configured")
                if self.sqlite_adapter:
                    self._current_primary = DatabaseType.SQLITE
        
        # Ensure at least one database is available
        available_databases = [
            db_type for db_type, health in health_metrics.items() 
            if health.is_available
        ]
        
        if not available_databases:
            raise ConnectionError("No databases are available", "none")
        
        self.logger.info(f"Database manager initialized with primary: {self._current_primary}")
    
    def _get_adapter(self, database_type: DatabaseType):
        """Get the appropriate database adapter."""
        if database_type == DatabaseType.POSTGRESQL:
            return self.postgresql_adapter
        elif database_type == DatabaseType.SQLITE:
            return self.sqlite_adapter
        else:
            raise ValueError(f"Unsupported database type: {database_type}")
    
    def _validate_connection(self, connection: DatabaseConnection) -> bool:
        """Validate a database connection."""
        try:
            adapter = self._get_adapter(connection.database_type)
            return adapter.validate_connection()
        except Exception:
            return False
    
    def _add_tenant_scoping(self, query: str, tenant_id: str) -> str:
        """Add tenant scoping to a query."""
        # This is a simplified implementation
        # In production, you'd need more sophisticated query parsing
        if "WHERE" in query.upper():
            return query + f" AND tenant_id = '{tenant_id}'"
        else:
            return query + f" WHERE tenant_id = '{tenant_id}'"
    
    def _add_tenant_scoping_to_operations(self, 
                                        operations: List[DatabaseOperation], 
                                        tenant_id: str) -> List[DatabaseOperation]:
        """Add tenant scoping to database operations."""
        scoped_operations = []
        
        for operation in operations:
            scoped_operation = DatabaseOperation(
                operation_type=operation.operation_type,
                table=operation.table,
                data={**operation.data, 'tenant_id': tenant_id} if operation.data else {'tenant_id': tenant_id},
                conditions={**operation.conditions, 'tenant_id': tenant_id} if operation.conditions else {'tenant_id': tenant_id},
                query=operation.query,
                parameters={**operation.parameters, 'tenant_id': tenant_id} if operation.parameters else {'tenant_id': tenant_id}
            )
            scoped_operations.append(scoped_operation)
        
        return scoped_operations