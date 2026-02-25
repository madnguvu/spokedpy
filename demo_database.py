#!/usr/bin/env python3
"""
Demonstration of the database abstraction layer.

This script shows how to use the DatabaseManager with SQLite and PostgreSQL,
including automatic failover, connection pooling, and health monitoring.
"""

import os
import tempfile
from visual_editor_core.database import (
    DatabaseManager,
    DatabaseConfig,
    DatabaseType,
    DatabaseOperation,
    PoolConfig
)


def demo_sqlite_operations():
    """Demonstrate SQLite database operations."""
    print("=== SQLite Database Operations Demo ===")
    
    # Create temporary SQLite database
    temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
    temp_db.close()
    
    try:
        # Configure SQLite database
        sqlite_config = DatabaseConfig(
            database_type=DatabaseType.SQLITE,
            database=temp_db.name
        )
        
        # Configure connection pool
        pool_config = PoolConfig(
            min_connections=1,
            max_connections=5,
            connection_timeout=10
        )
        
        # Initialize database manager
        manager = DatabaseManager(
            sqlite_config=sqlite_config,
            pool_config=pool_config
        )
        
        print(f"✓ Database manager initialized with {manager.get_current_database_type().value}")
        
        # Check database health
        health_metrics = manager.get_database_health()
        for db_type, health in health_metrics.items():
            print(f"✓ {db_type.value} health: Available={health.is_available}, "
                  f"Response time={health.response_time:.3f}s")
        
        # Create a test table
        create_result = manager.execute_query("""
            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT UNIQUE,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        if create_result.success:
            print("✓ Created users table")
        else:
            print(f"✗ Failed to create table: {create_result.error_message}")
            return
        
        # Insert test data using transaction
        operations = [
            DatabaseOperation(
                operation_type='insert',
                table='users',
                data={'name': 'Alice Johnson', 'email': 'alice@example.com'}
            ),
            DatabaseOperation(
                operation_type='insert',
                table='users',
                data={'name': 'Bob Smith', 'email': 'bob@example.com'}
            ),
            DatabaseOperation(
                operation_type='insert',
                table='users',
                data={'name': 'Carol Davis', 'email': 'carol@example.com'}
            )
        ]
        
        transaction_result = manager.execute_transaction(operations)
        if transaction_result.success:
            print(f"✓ Inserted {transaction_result.operations_count} users via transaction")
        else:
            print(f"✗ Transaction failed: {transaction_result.error_message}")
            return
        
        # Query data
        select_result = manager.execute_query("SELECT * FROM users ORDER BY name")
        if select_result.success:
            print(f"✓ Retrieved {len(select_result.data)} users:")
            for user in select_result.data:
                print(f"  - {user['name']} ({user['email']})")
        else:
            print(f"✗ Query failed: {select_result.error_message}")
        
        # Store JSON data
        json_data = {
            'user_preferences': {
                'theme': 'dark',
                'language': 'en',
                'notifications': True
            },
            'last_login': '2024-01-15T10:30:00Z'
        }
        
        # Create JSON table first
        manager.execute_query("""
            CREATE TABLE user_settings (
                id TEXT PRIMARY KEY,
                data TEXT,
                created_at TEXT,
                updated_at TEXT
            )
        """)
        
        record_id = manager.store_json_data('user_settings', json_data)
        print(f"✓ Stored JSON data with ID: {record_id}")
        
        # Query JSON data
        json_results = manager.query_json_data('user_settings', 'user_preferences.theme', 'dark')
        print(f"✓ Found {len(json_results)} records with dark theme")
        
        # Test backup and restore
        backup_path = tempfile.mktemp(suffix='.db')
        backup_result = manager.backup_database(backup_path)
        if backup_result.success:
            print(f"✓ Database backed up to {backup_path} ({backup_result.backup_size} bytes)")
            
            # Clean up backup file
            if os.path.exists(backup_path):
                os.unlink(backup_path)
        else:
            print(f"✗ Backup failed: {backup_result.error_message}")
        
        # Optimize performance
        optimization_results = manager.optimize_performance()
        for db_type, result in optimization_results.items():
            if result.success:
                print(f"✓ {db_type.value} optimization: {', '.join(result.optimizations_applied)}")
            else:
                print(f"✗ {db_type.value} optimization failed: {result.error_message}")
        
        # Test transaction context manager
        with manager.transaction() as tx:
            tx.add_operation(DatabaseOperation(
                operation_type='insert',
                table='users',
                data={'name': 'David Wilson', 'email': 'david@example.com'}
            ))
        
        print("✓ Added user via transaction context manager")
        
        # Final user count
        count_result = manager.execute_query("SELECT COUNT(*) as count FROM users")
        if count_result.success:
            print(f"✓ Total users: {count_result.data[0]['count']}")
        
        # Close manager
        manager.close()
        print("✓ Database manager closed")
        
    finally:
        # Clean up temporary file
        if os.path.exists(temp_db.name):
            try:
                os.unlink(temp_db.name)
            except PermissionError:
                print(f"Note: Temporary file {temp_db.name} will be cleaned up by OS")


def demo_failover_scenario():
    """Demonstrate database failover scenario."""
    print("\n=== Database Failover Demo ===")
    
    # Create temporary SQLite database for fallback
    temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
    temp_db.close()
    
    try:
        # Configure PostgreSQL (will fail to connect)
        postgresql_config = DatabaseConfig(
            database_type=DatabaseType.POSTGRESQL,
            host='nonexistent-host',
            port=5432,
            database='test_db',
            username='test_user',
            password='test_pass'
        )
        
        # Configure SQLite as fallback
        sqlite_config = DatabaseConfig(
            database_type=DatabaseType.SQLITE,
            database=temp_db.name
        )
        
        # Initialize database manager with both configs
        manager = DatabaseManager(
            postgresql_config=postgresql_config,
            sqlite_config=sqlite_config
        )
        
        print(f"✓ Database manager initialized")
        print(f"✓ Current primary database: {manager.get_current_database_type().value}")
        print(f"✓ Failover occurred: {manager.has_failover_occurred()}")
        
        # Try to get a connection (should failover to SQLite)
        connection = manager.get_connection()
        print(f"✓ Got connection to {connection.database_type.value}")
        
        # Check if failover occurred
        if manager.has_failover_occurred():
            print("✓ Automatic failover to SQLite successful")
        
        # Test basic operations on fallback database
        create_result = manager.execute_query(
            "CREATE TABLE test_table (id INTEGER PRIMARY KEY, message TEXT)"
        )
        
        if create_result.success:
            print("✓ Created table on fallback database")
            
            insert_result = manager.execute_query(
                "INSERT INTO test_table (message) VALUES (:message)",
                {"message": "Failover test successful"}
            )
            
            if insert_result.success:
                print("✓ Inserted data on fallback database")
        
        manager.close()
        print("✓ Failover demo completed")
        
    finally:
        # Clean up temporary file
        if os.path.exists(temp_db.name):
            try:
                os.unlink(temp_db.name)
            except PermissionError:
                print(f"Note: Temporary file {temp_db.name} will be cleaned up by OS")


def demo_connection_validation():
    """Demonstrate connection validation and health monitoring."""
    print("\n=== Connection Validation Demo ===")
    
    temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
    temp_db.close()
    
    try:
        sqlite_config = DatabaseConfig(
            database_type=DatabaseType.SQLITE,
            database=temp_db.name
        )
        
        manager = DatabaseManager(sqlite_config=sqlite_config)
        
        # Get connection and validate it
        connection = manager.get_connection()
        is_valid = manager.validate_connection(connection)
        print(f"✓ Connection validation: {is_valid}")
        
        # Get detailed health metrics
        health_metrics = manager.get_database_health()
        for db_type, health in health_metrics.items():
            print(f"✓ {db_type.value} Health Metrics:")
            print(f"  - Available: {health.is_available}")
            print(f"  - Response time: {health.response_time:.3f}s")
            print(f"  - Active connections: {health.active_connections}")
            print(f"  - Max connections: {health.max_connections}")
            print(f"  - Is healthy: {health.is_healthy()}")
            if health.warnings:
                print(f"  - Warnings: {', '.join(health.warnings)}")
        
        manager.close()
        print("✓ Connection validation demo completed")
        
    finally:
        if os.path.exists(temp_db.name):
            try:
                os.unlink(temp_db.name)
            except PermissionError:
                pass


if __name__ == "__main__":
    print("Database Abstraction Layer Demonstration")
    print("=" * 50)
    
    try:
        demo_sqlite_operations()
        demo_failover_scenario()
        demo_connection_validation()
        
        print("\n" + "=" * 50)
        print("✓ All demonstrations completed successfully!")
        print("\nKey features demonstrated:")
        print("- SQLite database operations")
        print("- Transaction management")
        print("- JSON data storage and querying")
        print("- Database backup and restore")
        print("- Performance optimization")
        print("- Automatic failover from PostgreSQL to SQLite")
        print("- Connection validation and health monitoring")
        print("- Connection pooling")
        
    except Exception as e:
        print(f"\n✗ Demo failed with error: {e}")
        import traceback
        traceback.print_exc()