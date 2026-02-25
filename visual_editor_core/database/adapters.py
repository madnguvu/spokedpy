"""
Database adapters for PostgreSQL and SQLite.
"""

import sqlite3
import uuid
import time
import os
import shutil
from datetime import datetime
from typing import Any, Dict, List, Optional
from contextlib import contextmanager

try:
    import psycopg2
    import psycopg2.extras
    from psycopg2 import sql
    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False

from .base_adapter import BaseDatabaseAdapter
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
    DatabaseType,
    ConnectionStatus
)
from .exceptions import (
    DatabaseError,
    ConnectionError,
    ValidationError,
    TransactionError,
    HealthCheckError
)


class PostgreSQLAdapter(BaseDatabaseAdapter):
    """PostgreSQL database adapter."""
    
    def __init__(self, config: DatabaseConfig):
        if not PSYCOPG2_AVAILABLE:
            raise ImportError("psycopg2 is required for PostgreSQL support")
        
        super().__init__(config)
        self._connection = None
        self._connection_id = str(uuid.uuid4())
    
    def connect(self) -> DatabaseConnection:
        """Establish PostgreSQL connection."""
        try:
            connection_string = self._build_connection_string()
            self._connection = psycopg2.connect(connection_string)
            self._connection.autocommit = False
            self._is_connected = True
            
            return DatabaseConnection(
                connection_id=self._connection_id,
                database_type=DatabaseType.POSTGRESQL,
                status=ConnectionStatus.CONNECTED,
                created_at=datetime.now(),
                last_used=datetime.now(),
                connection_string=connection_string,
                is_primary=True
            )
        except Exception as e:
            self._is_connected = False
            raise ConnectionError(f"Failed to connect to PostgreSQL: {str(e)}", "postgresql")
    
    def disconnect(self) -> bool:
        """Close PostgreSQL connection."""
        try:
            if self._connection:
                self._connection.close()
                self._connection = None
            self._is_connected = False
            return True
        except Exception as e:
            raise DatabaseError(f"Failed to disconnect from PostgreSQL: {str(e)}")
    
    def is_connected(self) -> bool:
        """Check if PostgreSQL is connected."""
        if not self._connection:
            return False
        
        try:
            # Test connection with a simple query
            with self._connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
            return True
        except Exception:
            self._is_connected = False
            return False
    
    def execute_query(self, query: str, params: Optional[Dict[str, Any]] = None) -> QueryResult:
        """Execute a PostgreSQL query."""
        if not self.is_connected():
            raise ConnectionError("Not connected to PostgreSQL", "postgresql")
        
        start_time = time.time()
        query_id = str(uuid.uuid4())
        
        try:
            with self._connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                if params:
                    # Handle both list and dict parameters
                    if isinstance(params, list):
                        # Positional parameters
                        cursor.execute(query, params)
                    elif isinstance(params, dict):
                        # Named parameters
                        cursor.execute(query, params)
                    else:
                        cursor.execute(query, params)
                else:
                    cursor.execute(query)
                
                # Handle different query types
                if cursor.description:
                    # SELECT query
                    data = [dict(row) for row in cursor.fetchall()]
                    rows_affected = len(data)
                else:
                    # INSERT/UPDATE/DELETE query
                    data = []
                    rows_affected = cursor.rowcount
                
                # Commit the transaction for non-SELECT queries
                if not cursor.description:
                    self._connection.commit()
                
                execution_time = time.time() - start_time
                
                return QueryResult(
                    success=True,
                    rows_affected=rows_affected,
                    data=data,
                    execution_time=execution_time,
                    query_id=query_id
                )
        except Exception as e:
            execution_time = time.time() - start_time
            return QueryResult(
                success=False,
                error_message=str(e),
                execution_time=execution_time,
                query_id=query_id
            )
    
    def execute_transaction(self, operations: List[DatabaseOperation]) -> TransactionResult:
        """Execute a PostgreSQL transaction."""
        if not self.is_connected():
            raise ConnectionError("Not connected to PostgreSQL", "postgresql")
        
        transaction_id = str(uuid.uuid4())
        start_time = time.time()
        rollback_performed = False
        
        try:
            with self._connection:
                with self._connection.cursor() as cursor:
                    for operation in operations:
                        if not operation.validate():
                            raise ValidationError(f"Invalid operation: {operation}")
                        
                        if operation.query:
                            cursor.execute(operation.query, operation.parameters)
                        else:
                            # Build query from operation
                            query = self._build_operation_query(operation)
                            cursor.execute(query, operation.data)
            
            execution_time = time.time() - start_time
            return TransactionResult(
                success=True,
                transaction_id=transaction_id,
                operations_count=len(operations),
                execution_time=execution_time
            )
        except Exception as e:
            try:
                self._connection.rollback()
                rollback_performed = True
            except Exception:
                pass
            
            execution_time = time.time() - start_time
            return TransactionResult(
                success=False,
                transaction_id=transaction_id,
                operations_count=len(operations),
                rollback_performed=rollback_performed,
                error_message=str(e),
                execution_time=execution_time
            )
    
    def validate_connection(self) -> bool:
        """Validate PostgreSQL connection."""
        try:
            return self.is_connected()
        except Exception:
            return False
    
    def get_health_metrics(self) -> HealthMetrics:
        """Get PostgreSQL health metrics."""
        start_time = time.time()
        
        try:
            # Try to connect if not already connected
            if not self.is_connected():
                try:
                    self.connect()
                except Exception:
                    return HealthMetrics(
                        database_type=DatabaseType.POSTGRESQL,
                        is_available=False,
                        response_time=time.time() - start_time,
                        active_connections=0,
                        max_connections=0,
                        error_count=1,
                        warnings=["Cannot connect to database"]
                    )
            
            # Get connection statistics
            stats_query = """
                SELECT 
                    count(*) as active_connections,
                    setting::int as max_connections
                FROM pg_stat_activity, pg_settings 
                WHERE pg_settings.name = 'max_connections'
                GROUP BY setting
            """
            
            result = self.execute_query(stats_query)
            response_time = time.time() - start_time
            
            if result.success and result.data:
                stats = result.data[0]
                return HealthMetrics(
                    database_type=DatabaseType.POSTGRESQL,
                    is_available=True,
                    response_time=response_time,
                    active_connections=stats['active_connections'],
                    max_connections=stats['max_connections']
                )
            else:
                return HealthMetrics(
                    database_type=DatabaseType.POSTGRESQL,
                    is_available=True,
                    response_time=response_time,
                    active_connections=1,
                    max_connections=100,
                    warnings=["Could not retrieve detailed statistics"]
                )
        except Exception as e:
            return HealthMetrics(
                database_type=DatabaseType.POSTGRESQL,
                is_available=False,
                response_time=time.time() - start_time,
                active_connections=0,
                max_connections=0,
                error_count=1,
                warnings=[str(e)]
            )
    
    def backup_database(self, backup_path: str) -> BackupResult:
        """Create PostgreSQL backup using pg_dump."""
        try:
            # This is a simplified implementation
            # In production, you'd use pg_dump command
            return BackupResult(
                success=False,
                backup_path=backup_path,
                error_message="PostgreSQL backup not implemented in this version"
            )
        except Exception as e:
            return BackupResult(
                success=False,
                backup_path=backup_path,
                error_message=str(e)
            )
    
    def restore_database(self, backup_path: str) -> RestoreResult:
        """Restore PostgreSQL database."""
        try:
            return RestoreResult(
                success=False,
                restore_path=backup_path,
                error_message="PostgreSQL restore not implemented in this version"
            )
        except Exception as e:
            return RestoreResult(
                success=False,
                restore_path=backup_path,
                error_message=str(e)
            )
    
    def optimize_performance(self) -> OptimizationResult:
        """Optimize PostgreSQL performance."""
        try:
            optimizations = []
            
            # Run ANALYZE to update statistics
            analyze_result = self.execute_query("ANALYZE")
            if analyze_result.success:
                optimizations.append("Updated table statistics")
            
            return OptimizationResult(
                success=True,
                optimizations_applied=optimizations
            )
        except Exception as e:
            return OptimizationResult(
                success=False,
                error_message=str(e)
            )
    
    def create_tables(self, schema: Dict[str, Any]) -> bool:
        """Create PostgreSQL tables from schema."""
        try:
            for table_name, table_def in schema.items():
                query = f"CREATE TABLE IF NOT EXISTS {table_name} ({table_def})"
                result = self.execute_query(query)
                if not result.success:
                    return False
            return True
        except Exception:
            return False
    
    def drop_tables(self, table_names: List[str]) -> bool:
        """Drop PostgreSQL tables."""
        try:
            for table_name in table_names:
                query = f"DROP TABLE IF EXISTS {table_name} CASCADE"
                result = self.execute_query(query)
                if not result.success:
                    return False
            return True
        except Exception:
            return False
    
    def get_table_info(self, table_name: str) -> Dict[str, Any]:
        """Get PostgreSQL table information."""
        try:
            query = """
                SELECT column_name, data_type, is_nullable, column_default
                FROM information_schema.columns
                WHERE table_name = %s
                ORDER BY ordinal_position
            """
            result = self.execute_query(query, {"table_name": table_name})
            
            if result.success:
                return {
                    "exists": len(result.data) > 0,
                    "columns": result.data
                }
            else:
                return {"exists": False, "columns": []}
        except Exception:
            return {"exists": False, "columns": []}
    
    def get_connection_string(self) -> str:
        """Get PostgreSQL connection string."""
        return self._build_connection_string()
    
    def _build_connection_string(self) -> str:
        """Build PostgreSQL connection string."""
        if self.config.connection_string:
            return self.config.connection_string
        
        parts = []
        if self.config.host:
            parts.append(f"host={self.config.host}")
        if self.config.port:
            parts.append(f"port={self.config.port}")
        if self.config.database:
            parts.append(f"dbname={self.config.database}")
        if self.config.username:
            parts.append(f"user={self.config.username}")
        if self.config.password:
            parts.append(f"password={self.config.password}")
        
        return " ".join(parts)
    
    def _build_operation_query(self, operation: DatabaseOperation) -> str:
        """Build SQL query from operation."""
        if operation.operation_type == "insert":
            columns = ", ".join(operation.data.keys())
            placeholders = ", ".join([f"%({k})s" for k in operation.data.keys()])
            return f"INSERT INTO {operation.table} ({columns}) VALUES ({placeholders})"
        elif operation.operation_type == "update":
            set_clause = ", ".join([f"{k} = %({k})s" for k in operation.data.keys()])
            where_clause = " AND ".join([f"{k} = %({k})s" for k in operation.conditions.keys()])
            return f"UPDATE {operation.table} SET {set_clause} WHERE {where_clause}"
        elif operation.operation_type == "delete":
            where_clause = " AND ".join([f"{k} = %({k})s" for k in operation.conditions.keys()])
            return f"DELETE FROM {operation.table} WHERE {where_clause}"
        else:
            raise ValueError(f"Unsupported operation type: {operation.operation_type}")


class SQLiteAdapter(BaseDatabaseAdapter):
    """SQLite database adapter."""
    
    def __init__(self, config: DatabaseConfig):
        super().__init__(config)
        self._connection = None
        self._connection_id = str(uuid.uuid4())
    
    def connect(self) -> DatabaseConnection:
        """Establish SQLite connection."""
        try:
            database_path = self._get_database_path()
            
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(database_path), exist_ok=True)
            
            self._connection = sqlite3.connect(database_path, check_same_thread=False)
            self._connection.row_factory = sqlite3.Row
            self._is_connected = True
            
            return DatabaseConnection(
                connection_id=self._connection_id,
                database_type=DatabaseType.SQLITE,
                status=ConnectionStatus.CONNECTED,
                created_at=datetime.now(),
                last_used=datetime.now(),
                connection_string=database_path,
                is_primary=False
            )
        except Exception as e:
            self._is_connected = False
            raise ConnectionError(f"Failed to connect to SQLite: {str(e)}", "sqlite")
    
    def disconnect(self) -> bool:
        """Close SQLite connection."""
        try:
            if self._connection:
                self._connection.close()
                self._connection = None
            self._is_connected = False
            return True
        except Exception as e:
            raise DatabaseError(f"Failed to disconnect from SQLite: {str(e)}")
    
    def is_connected(self) -> bool:
        """Check if SQLite is connected."""
        if not self._connection:
            return False
        
        try:
            # Test connection with a simple query
            cursor = self._connection.cursor()
            cursor.execute("SELECT 1")
            cursor.fetchone()
            cursor.close()
            return True
        except Exception:
            self._is_connected = False
            return False
    
    def execute_query(self, query: str, params: Optional[Dict[str, Any]] = None) -> QueryResult:
        """Execute a SQLite query."""
        if not self.is_connected():
            raise ConnectionError("Not connected to SQLite", "sqlite")
        
        start_time = time.time()
        query_id = str(uuid.uuid4())
        
        try:
            cursor = self._connection.cursor()
            
            if params:
                # Handle both list and dict parameters
                if isinstance(params, list):
                    # Positional parameters
                    cursor.execute(query, params)
                elif isinstance(params, dict):
                    # Named parameters
                    if ':' in query:
                        cursor.execute(query, params)
                    else:
                        # Convert dict to list for positional parameters
                        param_list = list(params.values())
                        cursor.execute(query, param_list)
                else:
                    cursor.execute(query, params)
            else:
                cursor.execute(query)
            
            # Handle different query types
            if cursor.description:
                # SELECT query
                rows = cursor.fetchall()
                data = [dict(row) for row in rows]
                rows_affected = len(data)
            else:
                # INSERT/UPDATE/DELETE query
                data = []
                rows_affected = cursor.rowcount
            
            # Commit the transaction for non-SELECT queries
            if not cursor.description:
                self._connection.commit()
            
            cursor.close()
            execution_time = time.time() - start_time
            
            return QueryResult(
                success=True,
                rows_affected=rows_affected,
                data=data,
                execution_time=execution_time,
                query_id=query_id
            )
        except Exception as e:
            execution_time = time.time() - start_time
            return QueryResult(
                success=False,
                error_message=str(e),
                execution_time=execution_time,
                query_id=query_id
            )
    
    def execute_transaction(self, operations: List[DatabaseOperation]) -> TransactionResult:
        """Execute a SQLite transaction."""
        if not self.is_connected():
            raise ConnectionError("Not connected to SQLite", "sqlite")
        
        transaction_id = str(uuid.uuid4())
        start_time = time.time()
        rollback_performed = False
        
        try:
            cursor = self._connection.cursor()
            cursor.execute("BEGIN TRANSACTION")
            
            for operation in operations:
                if not operation.validate():
                    raise ValidationError(f"Invalid operation: {operation}")
                
                if operation.query:
                    if operation.parameters:
                        if isinstance(operation.parameters, list):
                            cursor.execute(operation.query, operation.parameters)
                        else:
                            cursor.execute(operation.query, operation.parameters)
                    else:
                        cursor.execute(operation.query)
                else:
                    # Build query from operation
                    query = self._build_operation_query(operation)
                    cursor.execute(query, operation.data)
            
            cursor.execute("COMMIT")
            cursor.close()
            
            execution_time = time.time() - start_time
            return TransactionResult(
                success=True,
                transaction_id=transaction_id,
                operations_count=len(operations),
                execution_time=execution_time
            )
        except Exception as e:
            try:
                cursor.execute("ROLLBACK")
                rollback_performed = True
            except Exception:
                pass
            finally:
                cursor.close()
            
            execution_time = time.time() - start_time
            return TransactionResult(
                success=False,
                transaction_id=transaction_id,
                operations_count=len(operations),
                rollback_performed=rollback_performed,
                error_message=str(e),
                execution_time=execution_time
            )
    
    def validate_connection(self) -> bool:
        """Validate SQLite connection."""
        try:
            return self.is_connected()
        except Exception:
            return False
    
    def get_health_metrics(self) -> HealthMetrics:
        """Get SQLite health metrics."""
        start_time = time.time()
        
        try:
            # Try to connect if not already connected
            if not self.is_connected():
                try:
                    self.connect()
                except Exception:
                    return HealthMetrics(
                        database_type=DatabaseType.SQLITE,
                        is_available=False,
                        response_time=time.time() - start_time,
                        active_connections=0,
                        max_connections=1,
                        error_count=1,
                        warnings=["Cannot connect to database"]
                    )
            
            # SQLite is single-threaded, so active connections is always 1 when connected
            response_time = time.time() - start_time
            
            return HealthMetrics(
                database_type=DatabaseType.SQLITE,
                is_available=True,
                response_time=response_time,
                active_connections=1,
                max_connections=1
            )
        except Exception as e:
            return HealthMetrics(
                database_type=DatabaseType.SQLITE,
                is_available=False,
                response_time=time.time() - start_time,
                active_connections=0,
                max_connections=1,
                error_count=1,
                warnings=[str(e)]
            )
    
    def backup_database(self, backup_path: str) -> BackupResult:
        """Create SQLite backup."""
        try:
            database_path = self._get_database_path()
            
            # Create backup directory if it doesn't exist
            os.makedirs(os.path.dirname(backup_path), exist_ok=True)
            
            # Copy the database file
            shutil.copy2(database_path, backup_path)
            
            # Get backup size
            backup_size = os.path.getsize(backup_path)
            
            return BackupResult(
                success=True,
                backup_path=backup_path,
                backup_size=backup_size
            )
        except Exception as e:
            return BackupResult(
                success=False,
                backup_path=backup_path,
                error_message=str(e)
            )
    
    def restore_database(self, backup_path: str) -> RestoreResult:
        """Restore SQLite database."""
        try:
            database_path = self._get_database_path()
            
            # Close current connection
            if self._connection:
                self._connection.close()
                self._connection = None
                self._is_connected = False
            
            # Copy backup to database location
            shutil.copy2(backup_path, database_path)
            
            # Reconnect
            self.connect()
            
            return RestoreResult(
                success=True,
                restore_path=backup_path
            )
        except Exception as e:
            return RestoreResult(
                success=False,
                restore_path=backup_path,
                error_message=str(e)
            )
    
    def optimize_performance(self) -> OptimizationResult:
        """Optimize SQLite performance."""
        try:
            optimizations = []
            
            # Run VACUUM to reclaim space
            vacuum_result = self.execute_query("VACUUM")
            if vacuum_result.success:
                optimizations.append("Reclaimed unused space")
            
            # Run ANALYZE to update statistics
            analyze_result = self.execute_query("ANALYZE")
            if analyze_result.success:
                optimizations.append("Updated table statistics")
            
            return OptimizationResult(
                success=True,
                optimizations_applied=optimizations
            )
        except Exception as e:
            return OptimizationResult(
                success=False,
                error_message=str(e)
            )
    
    def create_tables(self, schema: Dict[str, Any]) -> bool:
        """Create SQLite tables from schema."""
        try:
            for table_name, table_def in schema.items():
                query = f"CREATE TABLE IF NOT EXISTS {table_name} ({table_def})"
                result = self.execute_query(query)
                if not result.success:
                    return False
            return True
        except Exception:
            return False
    
    def drop_tables(self, table_names: List[str]) -> bool:
        """Drop SQLite tables."""
        try:
            for table_name in table_names:
                query = f"DROP TABLE IF EXISTS {table_name}"
                result = self.execute_query(query)
                if not result.success:
                    return False
            return True
        except Exception:
            return False
    
    def get_table_info(self, table_name: str) -> Dict[str, Any]:
        """Get SQLite table information."""
        try:
            query = f"PRAGMA table_info({table_name})"
            result = self.execute_query(query)
            
            if result.success:
                return {
                    "exists": len(result.data) > 0,
                    "columns": result.data
                }
            else:
                return {"exists": False, "columns": []}
        except Exception:
            return {"exists": False, "columns": []}
    
    def get_connection_string(self) -> str:
        """Get SQLite connection string."""
        return self._get_database_path()
    
    def _get_database_path(self) -> str:
        """Get SQLite database path."""
        if self.config.connection_string:
            return self.config.connection_string
        
        if self.config.database:
            return self.config.database
        
        # Default path
        return "data/visual_editor.db"
    
    def _build_operation_query(self, operation: DatabaseOperation) -> str:
        """Build SQL query from operation."""
        if operation.operation_type == "insert":
            columns = ", ".join(operation.data.keys())
            placeholders = ", ".join([f":{k}" for k in operation.data.keys()])
            return f"INSERT INTO {operation.table} ({columns}) VALUES ({placeholders})"
        elif operation.operation_type == "update":
            set_clause = ", ".join([f"{k} = :{k}" for k in operation.data.keys()])
            where_clause = " AND ".join([f"{k} = :{k}" for k in operation.conditions.keys()])
            return f"UPDATE {operation.table} SET {set_clause} WHERE {where_clause}"
        elif operation.operation_type == "delete":
            where_clause = " AND ".join([f"{k} = :{k}" for k in operation.conditions.keys()])
            return f"DELETE FROM {operation.table} WHERE {where_clause}"
        else:
            raise ValueError(f"Unsupported operation type: {operation.operation_type}")