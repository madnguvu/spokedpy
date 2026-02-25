"""
Tests for the database manager and abstraction layer.
"""

import pytest
import tempfile
import os
import time
from datetime import datetime
from unittest.mock import Mock, patch

from visual_editor_core.database import (
    DatabaseManager,
    DatabaseConfig,
    DatabaseType,
    PostgreSQLAdapter,
    SQLiteAdapter,
    ConnectionPool,
    PoolConfig,
    DatabaseOperation,
    DatabaseError,
    ConnectionError,
    FailoverError
)
from visual_editor_core.database.models import ConnectionStatus


class TestDatabaseManager:
    """Test cases for DatabaseManager."""
    
    def setup_method(self):
        """Set up test fixtures."""
        # Create temporary SQLite database
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        
        self.sqlite_config = DatabaseConfig(
            database_type=DatabaseType.SQLITE,
            database=self.temp_db.name
        )
        
        # Mock PostgreSQL config (won't actually connect)
        self.postgresql_config = DatabaseConfig(
            database_type=DatabaseType.POSTGRESQL,
            host='localhost',
            port=5432,
            database='test_db',
            username='test_user',
            password='test_pass'
        )
    
    def teardown_method(self):
        """Clean up test fixtures."""
        import time
        # Give some time for connections to close
        time.sleep(0.1)
        try:
            if os.path.exists(self.temp_db.name):
                os.unlink(self.temp_db.name)
        except PermissionError:
            # File might still be locked, try again after a short delay
            time.sleep(0.5)
            try:
                if os.path.exists(self.temp_db.name):
                    os.unlink(self.temp_db.name)
            except PermissionError:
                # If still locked, just leave it - OS will clean up eventually
                pass
    
    def test_database_manager_initialization_sqlite_only(self):
        """Test DatabaseManager initialization with SQLite only."""
        manager = DatabaseManager(sqlite_config=self.sqlite_config)
        
        assert manager.sqlite_adapter is not None
        assert manager.postgresql_adapter is None
        assert manager.get_current_database_type() == DatabaseType.SQLITE
        
        manager.close()
    
    def test_database_manager_initialization_no_config(self):
        """Test DatabaseManager initialization with no configuration raises error."""
        with pytest.raises(ValueError, match="At least one database configuration"):
            DatabaseManager()
    
    def test_database_manager_get_connection(self):
        """Test getting a database connection."""
        manager = DatabaseManager(sqlite_config=self.sqlite_config)
        
        connection = manager.get_connection()
        assert connection is not None
        assert connection.database_type == DatabaseType.SQLITE
        assert connection.is_healthy()
        
        manager.close()
    
    def test_database_manager_execute_query(self):
        """Test executing a database query."""
        manager = DatabaseManager(sqlite_config=self.sqlite_config)
        
        # Create a test table
        create_result = manager.execute_query(
            "CREATE TABLE test_table (id INTEGER PRIMARY KEY, name TEXT)"
        )
        assert create_result.success
        
        # Insert test data
        insert_result = manager.execute_query(
            "INSERT INTO test_table (name) VALUES (:name)",
            {"name": "test_name"}
        )
        assert insert_result.success
        assert insert_result.rows_affected == 1
        
        # Query test data
        select_result = manager.execute_query("SELECT * FROM test_table")
        assert select_result.success
        assert len(select_result.data) == 1
        assert select_result.data[0]['name'] == 'test_name'
        
        manager.close()
    
    def test_database_manager_execute_transaction(self):
        """Test executing a database transaction."""
        manager = DatabaseManager(sqlite_config=self.sqlite_config)
        
        # Create test table
        manager.execute_query(
            "CREATE TABLE test_table (id INTEGER PRIMARY KEY, name TEXT)"
        )
        
        # Execute transaction with multiple operations
        operations = [
            DatabaseOperation(
                operation_type='insert',
                table='test_table',
                data={'name': 'name1'}
            ),
            DatabaseOperation(
                operation_type='insert',
                table='test_table',
                data={'name': 'name2'}
            )
        ]
        
        result = manager.execute_transaction(operations)
        assert result.success
        assert result.operations_count == 2
        
        # Verify data was inserted
        select_result = manager.execute_query("SELECT COUNT(*) as count FROM test_table")
        assert select_result.success
        assert select_result.data[0]['count'] == 2
        
        manager.close()
    
    def test_database_manager_store_and_query_json_data(self):
        """Test storing and querying JSON data."""
        manager = DatabaseManager(sqlite_config=self.sqlite_config)
        
        # Create JSON table
        manager.execute_query("""
            CREATE TABLE json_table (
                id TEXT PRIMARY KEY,
                data TEXT,
                created_at TEXT,
                updated_at TEXT
            )
        """)
        
        # Store JSON data
        test_data = {'key': 'value', 'number': 42}
        record_id = manager.store_json_data('json_table', test_data)
        
        assert record_id is not None
        
        # Query JSON data
        results = manager.query_json_data('json_table', 'key', 'value')
        assert len(results) == 1
        
        manager.close()
    
    def test_database_manager_health_metrics(self):
        """Test getting database health metrics."""
        manager = DatabaseManager(sqlite_config=self.sqlite_config)
        
        health_metrics = manager.get_database_health()
        
        assert DatabaseType.SQLITE in health_metrics
        sqlite_health = health_metrics[DatabaseType.SQLITE]
        assert sqlite_health.is_available
        assert sqlite_health.database_type == DatabaseType.SQLITE
        
        manager.close()
    
    def test_database_manager_backup_and_restore(self):
        """Test database backup and restore operations."""
        manager = DatabaseManager(sqlite_config=self.sqlite_config)
        
        # Create test data
        manager.execute_query(
            "CREATE TABLE test_table (id INTEGER PRIMARY KEY, name TEXT)"
        )
        manager.execute_query(
            "INSERT INTO test_table (name) VALUES (?)",
            {"name": "test_data"}
        )
        
        # Create backup
        backup_path = tempfile.mktemp(suffix='.db')
        try:
            backup_result = manager.backup_database(backup_path)
            assert backup_result.success
            assert os.path.exists(backup_path)
            
            # Restore from backup
            restore_result = manager.restore_database(backup_path)
            assert restore_result.success
            
            # Verify data is still there
            select_result = manager.execute_query("SELECT * FROM test_table")
            assert select_result.success
            assert len(select_result.data) == 1
            
        finally:
            if os.path.exists(backup_path):
                os.unlink(backup_path)
            manager.close()
    
    def test_database_manager_optimization(self):
        """Test database performance optimization."""
        manager = DatabaseManager(sqlite_config=self.sqlite_config)
        
        optimization_results = manager.optimize_performance()
        
        assert DatabaseType.SQLITE in optimization_results
        sqlite_optimization = optimization_results[DatabaseType.SQLITE]
        assert sqlite_optimization.success
        
        manager.close()
    
    def test_database_manager_transaction_context(self):
        """Test database transaction context manager."""
        manager = DatabaseManager(sqlite_config=self.sqlite_config)
        
        # Create test table
        manager.execute_query(
            "CREATE TABLE test_table (id INTEGER PRIMARY KEY, name TEXT)"
        )
        
        # Use transaction context
        with manager.transaction() as tx:
            tx.add_operation(DatabaseOperation(
                operation_type='insert',
                table='test_table',
                data={'name': 'context_test'}
            ))
        
        # Verify data was inserted
        select_result = manager.execute_query("SELECT * FROM test_table")
        assert select_result.success
        assert len(select_result.data) == 1
        assert select_result.data[0]['name'] == 'context_test'
        
        manager.close()
    
    @patch('visual_editor_core.database.adapters.PSYCOPG2_AVAILABLE', False)
    def test_database_manager_postgresql_unavailable(self):
        """Test behavior when PostgreSQL is not available."""
        # Should work with SQLite only
        manager = DatabaseManager(sqlite_config=self.sqlite_config)
        
        assert manager.sqlite_adapter is not None
        assert manager.postgresql_adapter is None
        assert manager.get_current_database_type() == DatabaseType.SQLITE
        
        manager.close()
    
    def test_database_manager_failover_status(self):
        """Test failover status tracking."""
        manager = DatabaseManager(sqlite_config=self.sqlite_config)
        
        # Initially no failover
        assert not manager.has_failover_occurred()
        
        # Reset failover status
        manager.reset_failover_status()
        assert not manager.has_failover_occurred()
        
        manager.close()


class TestSQLiteAdapter:
    """Test cases for SQLiteAdapter."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        
        self.config = DatabaseConfig(
            database_type=DatabaseType.SQLITE,
            database=self.temp_db.name
        )
    
    def teardown_method(self):
        """Clean up test fixtures."""
        if os.path.exists(self.temp_db.name):
            os.unlink(self.temp_db.name)
    
    def test_sqlite_adapter_connection(self):
        """Test SQLite adapter connection."""
        adapter = SQLiteAdapter(self.config)
        
        connection = adapter.connect()
        assert connection is not None
        assert connection.database_type == DatabaseType.SQLITE
        assert adapter.is_connected()
        
        assert adapter.disconnect()
        assert not adapter.is_connected()
    
    def test_sqlite_adapter_query_execution(self):
        """Test SQLite adapter query execution."""
        adapter = SQLiteAdapter(self.config)
        adapter.connect()
        
        # Create table
        result = adapter.execute_query(
            "CREATE TABLE test (id INTEGER PRIMARY KEY, name TEXT)"
        )
        assert result.success
        
        # Insert data
        result = adapter.execute_query(
            "INSERT INTO test (name) VALUES (?)",
            {"name": "test_name"}
        )
        assert result.success
        assert result.rows_affected == 1
        
        # Select data
        result = adapter.execute_query("SELECT * FROM test")
        assert result.success
        assert len(result.data) == 1
        assert result.data[0]['name'] == 'test_name'
        
        adapter.disconnect()
    
    def test_sqlite_adapter_transaction(self):
        """Test SQLite adapter transaction execution."""
        adapter = SQLiteAdapter(self.config)
        adapter.connect()
        
        # Create table
        adapter.execute_query(
            "CREATE TABLE test (id INTEGER PRIMARY KEY, name TEXT)"
        )
        
        # Execute transaction
        operations = [
            DatabaseOperation(
                operation_type='insert',
                table='test',
                data={'name': 'name1'}
            ),
            DatabaseOperation(
                operation_type='insert',
                table='test',
                data={'name': 'name2'}
            )
        ]
        
        result = adapter.execute_transaction(operations)
        assert result.success
        assert result.operations_count == 2
        
        adapter.disconnect()
    
    def test_sqlite_adapter_health_metrics(self):
        """Test SQLite adapter health metrics."""
        adapter = SQLiteAdapter(self.config)
        adapter.connect()
        
        health = adapter.get_health_metrics()
        assert health.database_type == DatabaseType.SQLITE
        assert health.is_available
        assert health.active_connections == 1
        assert health.max_connections == 1
        
        adapter.disconnect()
    
    def test_sqlite_adapter_backup_restore(self):
        """Test SQLite adapter backup and restore."""
        adapter = SQLiteAdapter(self.config)
        adapter.connect()
        
        # Create test data
        adapter.execute_query(
            "CREATE TABLE test (id INTEGER PRIMARY KEY, name TEXT)"
        )
        adapter.execute_query(
            "INSERT INTO test (name) VALUES (?)",
            {"name": "backup_test"}
        )
        
        # Create backup
        backup_path = tempfile.mktemp(suffix='.db')
        try:
            backup_result = adapter.backup_database(backup_path)
            assert backup_result.success
            assert os.path.exists(backup_path)
            
            # Restore from backup
            restore_result = adapter.restore_database(backup_path)
            assert restore_result.success
            
        finally:
            if os.path.exists(backup_path):
                os.unlink(backup_path)
            adapter.disconnect()


class TestConnectionPool:
    """Test cases for ConnectionPool."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.pool_config = PoolConfig(
            min_connections=1,
            max_connections=3,
            connection_timeout=5,
            performance_monitoring_enabled=True,
            detailed_statistics=True
        )
        self.pool = ConnectionPool(self.pool_config)
        
        # Create temporary SQLite database for testing
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        
        self.sqlite_config = DatabaseConfig(
            database_type=DatabaseType.SQLITE,
            database=self.temp_db.name
        )
        
        # Register SQLite adapter
        self.pool.register_adapter(
            DatabaseType.SQLITE,
            SQLiteAdapter,
            self.sqlite_config
        )
    
    def teardown_method(self):
        """Clean up test fixtures."""
        self.pool.close_all_connections()
        
        # Give some time for connections to close properly
        time.sleep(0.2)
        
        # Try to remove the temp file with retries
        max_retries = 3
        for attempt in range(max_retries):
            try:
                if os.path.exists(self.temp_db.name):
                    os.unlink(self.temp_db.name)
                break
            except PermissionError:
                if attempt < max_retries - 1:
                    time.sleep(0.5)
                else:
                    # If still locked after retries, just leave it - OS will clean up eventually
                    pass
    
    def test_connection_pool_get_connection(self):
        """Test getting connection from pool."""
        connection = self.pool.get_connection(DatabaseType.SQLITE)
        
        assert connection is not None
        assert connection.database_type == DatabaseType.SQLITE
        
        # Return connection
        assert self.pool.return_connection(connection)
    
    def test_connection_pool_statistics(self):
        """Test connection pool statistics."""
        stats = self.pool.get_pool_statistics()
        
        assert stats.pool_size == self.pool_config.max_connections
        assert stats.max_connections == self.pool_config.max_connections
        assert stats.total_connections >= 0
    
    def test_connection_pool_enhanced_statistics(self):
        """Test enhanced connection pool statistics."""
        # Get a connection to generate some activity
        connection = self.pool.get_connection(DatabaseType.SQLITE)
        self.pool.return_connection(connection)
        
        stats = self.pool.get_pool_statistics()
        
        # Check enhanced statistics fields
        assert hasattr(stats, 'pool_efficiency')
        assert hasattr(stats, 'average_connection_age')
        assert hasattr(stats, 'peak_connections')
        assert hasattr(stats, 'connection_failures')
        assert hasattr(stats, 'connection_recoveries')
        assert hasattr(stats, 'health_check_failures')
        assert hasattr(stats, 'stale_connections_cleaned')
        
        assert stats.pool_efficiency >= 0.0
        assert stats.average_connection_age >= 0.0
    
    def test_connection_pool_detailed_performance_metrics(self):
        """Test detailed performance metrics."""
        # Generate some activity
        connection = self.pool.get_connection(DatabaseType.SQLITE)
        self.pool.return_connection(connection)
        
        metrics = self.pool.get_detailed_performance_metrics()
        
        assert 'pool_statistics' in metrics
        assert 'success_rate' in metrics
        assert 'utilization_history' in metrics
        assert 'connection_performance' in metrics
        assert 'failed_connections_count' in metrics
        assert 'performance_trends' in metrics
        
        assert metrics['success_rate'] >= 0.0
        assert metrics['success_rate'] <= 1.0
    
    def test_connection_pool_health_monitoring(self):
        """Test connection pool health monitoring."""
        health_report = self.pool.monitor_connection_health()
        
        assert 'timestamp' in health_report
        assert 'total_connections' in health_report
        assert 'healthy_connections' in health_report
        assert 'unhealthy_connections' in health_report
        assert 'connection_details' in health_report
    
    def test_connection_pool_health_summary(self):
        """Test comprehensive health summary."""
        # Get a connection to generate some activity
        connection = self.pool.get_connection(DatabaseType.SQLITE)
        self.pool.return_connection(connection)
        
        health_summary = self.pool.get_pool_health_summary()
        
        assert 'overall_status' in health_summary
        assert 'health_score' in health_summary
        assert 'total_connections' in health_summary
        assert 'healthy_connections' in health_summary
        assert 'unhealthy_connections' in health_summary
        assert 'pool_utilization' in health_summary
        assert 'recommendations' in health_summary
        
        assert health_summary['overall_status'] in ['excellent', 'good', 'fair', 'poor']
        assert 0.0 <= health_summary['health_score'] <= 1.0
        assert isinstance(health_summary['recommendations'], list)
    
    def test_connection_lifecycle_info(self):
        """Test connection lifecycle information."""
        connection = self.pool.get_connection(DatabaseType.SQLITE)
        
        lifecycle_info = self.pool.get_connection_lifecycle_info(connection.connection_id)
        
        assert lifecycle_info is not None
        assert 'connection_id' in lifecycle_info
        assert 'database_type' in lifecycle_info
        assert 'status' in lifecycle_info
        assert 'created_at' in lifecycle_info
        assert 'last_used' in lifecycle_info
        assert 'age_seconds' in lifecycle_info
        assert 'total_uses' in lifecycle_info
        assert 'performance_score' in lifecycle_info
        assert 'is_healthy' in lifecycle_info
        
        assert lifecycle_info['connection_id'] == connection.connection_id
        assert lifecycle_info['database_type'] == 'sqlite'
        assert lifecycle_info['is_healthy'] is True
        
        self.pool.return_connection(connection)
    
    def test_connection_pool_failure_handling(self):
        """Test connection failure handling and recovery."""
        connection = self.pool.get_connection(DatabaseType.SQLITE)
        original_connection_id = connection.connection_id
        
        # Simulate connection failure
        connection.status = ConnectionStatus.FAILED
        
        # Handle the failure
        recovery_success = self.pool.handle_connection_failure(connection)
        
        # Check that failure was handled
        stats = self.pool.get_pool_statistics()
        assert stats.connection_failures > 0
        
        # The method should attempt to create a replacement
        # (success depends on pool capacity and adapter availability)
        assert isinstance(recovery_success, bool)
    
    def test_connection_pool_resize(self):
        """Test connection pool resizing."""
        # Get initial size
        initial_stats = self.pool.get_pool_statistics()
        initial_max = initial_stats.max_connections
        
        # Resize pool
        new_size = initial_max + 2
        assert self.pool.resize_pool(new_size)
        
        # Check new size
        new_stats = self.pool.get_pool_statistics()
        assert new_stats.max_connections == new_size
    
    def test_connection_pool_optimization(self):
        """Test connection pool performance optimization."""
        optimization_result = self.pool.optimize_pool_performance()
        
        assert 'optimizations_applied' in optimization_result
        assert 'recommendations' in optimization_result
        assert isinstance(optimization_result['optimizations_applied'], list)
        assert isinstance(optimization_result['recommendations'], list)
    
    def test_connection_pool_auto_scaling_config(self):
        """Test auto-scaling configuration."""
        # Test with auto-scaling enabled
        auto_scale_config = PoolConfig(
            min_connections=2,
            max_connections=5,
            auto_scale_enabled=True,
            scale_up_threshold=0.8,
            scale_down_threshold=0.3
        )
        
        auto_pool = ConnectionPool(auto_scale_config)
        auto_pool.register_adapter(DatabaseType.SQLITE, SQLiteAdapter, self.sqlite_config)
        
        try:
            # Test that auto-scaling configuration is preserved
            assert auto_pool.config.auto_scale_enabled is True
            assert auto_pool.config.scale_up_threshold == 0.8
            assert auto_pool.config.scale_down_threshold == 0.3
            
            # Get detailed metrics to verify auto-scaling status
            metrics = auto_pool.get_detailed_performance_metrics()
            assert metrics['auto_scaling_enabled'] is True
            
        finally:
            auto_pool.close_all_connections()
    
    def test_connection_pool_performance_monitoring(self):
        """Test performance monitoring functionality."""
        # Generate some activity to create performance data
        connections = []
        for _ in range(3):
            conn = self.pool.get_connection(DatabaseType.SQLITE)
            connections.append(conn)
        
        # Return connections
        for conn in connections:
            self.pool.return_connection(conn)
        
        # Wait a bit for performance monitoring to capture data
        time.sleep(0.1)
        
        # Check that performance monitoring is working
        metrics = self.pool.get_detailed_performance_metrics()
        assert metrics['performance_trends']['trend'] in ['increasing', 'decreasing', 'stable', 'insufficient_data']
        
        # Check connection performance data
        assert 'connection_performance' in metrics
        if metrics['connection_performance']:
            for conn_id, perf_data in metrics['connection_performance'].items():
                assert 'total_uses' in perf_data
                assert 'performance_score' in perf_data
                assert 'age_seconds' in perf_data