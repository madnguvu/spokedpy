#!/usr/bin/env python3
"""
Complete demonstration of the migration system with PostgreSQL and SQLite support.
"""

import os
import tempfile
import logging
from datetime import datetime

from visual_editor_core.database import (
    DatabaseManager,
    DatabaseConfig,
    DatabaseType,
    DatabaseOperation
)
from visual_editor_core.database.migrations.initial_schema import create_initial_schema_migration
from visual_editor_core.database.migrations.add_indexes import create_indexes_migration

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def demo_postgresql_migration():
    """Demonstrate migration system with PostgreSQL."""
    print("\n" + "="*60)
    print("POSTGRESQL MIGRATION SYSTEM DEMO")
    print("="*60)
    
    try:
        # Configure PostgreSQL connection
        postgresql_config = DatabaseConfig(
            database_type=DatabaseType.POSTGRESQL,
            host="localhost",
            port=5432,
            database="visual_editor_core",
            username="postgres",
            password="headbutt"
        )
        
        print("1. Initializing PostgreSQL database manager...")
        db_manager = DatabaseManager(postgresql_config=postgresql_config)
        migration_manager = db_manager.get_migration_manager()
        
        print(f"   Current version: {migration_manager.get_current_version()}")
        print(f"   Current database: {db_manager.get_current_database_type().value}")
        
        # Initialize database with core schema
        print("\n2. Initializing database with core schema...")
        init_result = migration_manager.initialize_database(DatabaseType.POSTGRESQL)
        
        if init_result.success:
            print(f"   ✓ Database initialized successfully")
            print(f"   ✓ Tables created: {', '.join(init_result.tables_created)}")
            print(f"   ✓ Initial version: {init_result.initial_version}")
        else:
            print(f"   ✗ Database initialization failed: {init_result.error_message}")
            return False
        
        # Create and apply initial schema migration
        print("\n3. Creating initial schema migration...")
        initial_migration = create_initial_schema_migration(DatabaseType.POSTGRESQL)
        migration_manager._migrations[initial_migration.id] = initial_migration
        
        print(f"   Migration ID: {initial_migration.id}")
        print(f"   Migration Name: {initial_migration.name}")
        print(f"   Migration Version: {initial_migration.version}")
        print(f"   Up Operations: {len(initial_migration.up_operations)}")
        print(f"   Down Operations: {len(initial_migration.down_operations)}")
        
        # Create and apply indexes migration
        print("\n4. Creating indexes migration...")
        indexes_migration = create_indexes_migration(DatabaseType.POSTGRESQL)
        migration_manager._migrations[indexes_migration.id] = indexes_migration
        
        print(f"   Migration ID: {indexes_migration.id}")
        print(f"   Migration Name: {indexes_migration.name}")
        print(f"   Migration Version: {indexes_migration.version}")
        print(f"   Up Operations: {len(indexes_migration.up_operations)}")
        print(f"   Down Operations: {len(indexes_migration.down_operations)}")
        
        # Apply pending migrations
        print("\n5. Applying pending migrations...")
        pending = migration_manager.get_pending_migrations()
        print(f"   Pending migrations: {len(pending)}")
        
        if pending:
            results = migration_manager.apply_migrations()
            for result in results:
                if result.success:
                    print(f"   ✓ Applied migration {result.migration_id}")
                    print(f"     Operations executed: {result.operations_executed}")
                    print(f"     Execution time: {result.execution_time:.3f}s")
                else:
                    print(f"   ✗ Failed to apply migration {result.migration_id}: {result.error_message}")
        
        # Show migration history
        print("\n6. Migration history:")
        history = migration_manager.get_migration_history()
        for record in history:
            print(f"   - {record.name} (v{record.version}) - {record.status}")
            print(f"     Applied: {record.applied_at}")
            if record.rollback_at:
                print(f"     Rolled back: {record.rollback_at}")
        
        # Test custom migration
        print("\n7. Creating and applying custom migration...")
        custom_operations = [
            DatabaseOperation(
                operation_type="create_table",
                table="demo_table",
                query="""
                CREATE TABLE IF NOT EXISTS demo_table (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    name VARCHAR(255) NOT NULL,
                    description TEXT,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    data JSONB DEFAULT '{}'
                )
                """
            )
        ]
        
        custom_down_operations = [
            DatabaseOperation(
                operation_type="drop_table",
                table="demo_table",
                query="DROP TABLE IF EXISTS demo_table"
            )
        ]
        
        custom_migration_id = migration_manager.create_migration(
            "add_demo_table",
            custom_operations,
            custom_down_operations
        )
        
        print(f"   Created custom migration: {custom_migration_id}")
        
        # Apply custom migration
        custom_results = migration_manager.apply_migrations()
        for result in custom_results:
            if result.success:
                print(f"   ✓ Applied custom migration")
                print(f"     Operations executed: {result.operations_executed}")
            else:
                print(f"   ✗ Failed to apply custom migration: {result.error_message}")
        
        # Test data insertion into demo table
        print("\n8. Testing data operations on demo table...")
        insert_operation = DatabaseOperation(
            operation_type="insert",
            table="demo_table",
            data={
                "name": "Test Record",
                "description": "This is a test record created by the migration demo",
                "data": '{"demo": true, "timestamp": "' + datetime.now().isoformat() + '"}'
            }
        )
        
        transaction_result = db_manager.execute_transaction([insert_operation])
        if transaction_result.success:
            print("   ✓ Test record inserted successfully")
        else:
            print(f"   ✗ Failed to insert test record: {transaction_result.error_message}")
        
        # Query the data back
        query_result = db_manager.execute_query("SELECT * FROM demo_table LIMIT 5")
        if query_result.success:
            print(f"   ✓ Retrieved {len(query_result.data)} records from demo_table")
            for row in query_result.data:
                print(f"     - {row['name']}: {row['description']}")
        else:
            print(f"   ✗ Failed to query demo_table: {query_result.error_message}")
        
        # Test rollback
        print("\n9. Testing migration rollback...")
        current_version = migration_manager.get_current_version()
        print(f"   Current version: {current_version}")
        
        # Rollback to version 1.1.0 (before custom migration)
        rollback_result = migration_manager.rollback_migration("1.1.0")
        if rollback_result.success:
            print(f"   ✓ Rollback successful to version {rollback_result.target_version}")
            print(f"     Operations executed: {rollback_result.operations_executed}")
            print(f"     Execution time: {rollback_result.execution_time:.3f}s")
        else:
            print(f"   ✗ Rollback failed: {rollback_result.error_message}")
        
        # Verify rollback worked
        print("\n10. Verifying rollback...")
        try:
            query_result = db_manager.execute_query("SELECT COUNT(*) as count FROM demo_table")
            if query_result.success:
                print("   ✗ demo_table still exists after rollback")
            else:
                print("   ✓ demo_table was successfully removed by rollback")
        except Exception as e:
            print("   ✓ demo_table was successfully removed by rollback")
        
        # Test backup functionality
        print("\n11. Testing backup functionality...")
        backup_result = migration_manager.backup_before_migration()
        if backup_result.success:
            print(f"   ✓ Backup created: {backup_result.backup_path}")
            print(f"     Backup size: {backup_result.backup_size} bytes")
        else:
            print(f"   ✗ Backup failed: {backup_result.error_message}")
        
        # Test repair functionality
        print("\n12. Testing migration state repair...")
        repair_result = migration_manager.repair_migration_state()
        if repair_result.success:
            print("   ✓ Migration state repair completed")
            if repair_result.issues_found:
                print(f"     Issues found: {len(repair_result.issues_found)}")
                for issue in repair_result.issues_found:
                    print(f"       - {issue}")
            if repair_result.repairs_applied:
                print(f"     Repairs applied: {len(repair_result.repairs_applied)}")
                for repair in repair_result.repairs_applied:
                    print(f"       - {repair}")
            if not repair_result.issues_found and not repair_result.repairs_applied:
                print("     No issues found, migration state is healthy")
        else:
            print(f"   ✗ Migration state repair failed: {repair_result.error_message}")
        
        print("\n✓ PostgreSQL migration demo completed successfully!")
        
        # Cleanup
        db_manager.close()
        return True
        
    except Exception as e:
        print(f"\n✗ PostgreSQL migration demo failed: {e}")
        logger.exception("PostgreSQL migration demo error")
        return False


def demo_sqlite_migration():
    """Demonstrate migration system with SQLite."""
    print("\n" + "="*60)
    print("SQLITE MIGRATION SYSTEM DEMO")
    print("="*60)
    
    # Create temporary SQLite database
    temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
    temp_db.close()
    
    try:
        # Configure SQLite connection
        sqlite_config = DatabaseConfig(
            database_type=DatabaseType.SQLITE,
            database=temp_db.name
        )
        
        print("1. Initializing SQLite database manager...")
        db_manager = DatabaseManager(sqlite_config=sqlite_config)
        migration_manager = db_manager.get_migration_manager()
        
        print(f"   Database path: {temp_db.name}")
        print(f"   Current version: {migration_manager.get_current_version()}")
        print(f"   Current database: {db_manager.get_current_database_type().value}")
        
        # Initialize database with core schema
        print("\n2. Initializing database with core schema...")
        init_result = migration_manager.initialize_database(DatabaseType.SQLITE)
        
        if init_result.success:
            print(f"   ✓ Database initialized successfully")
            print(f"   ✓ Tables created: {', '.join(init_result.tables_created)}")
            print(f"   ✓ Initial version: {init_result.initial_version}")
        else:
            print(f"   ✗ Database initialization failed: {init_result.error_message}")
            return False
        
        # Create and apply initial schema migration
        print("\n3. Creating initial schema migration...")
        initial_migration = create_initial_schema_migration(DatabaseType.SQLITE)
        migration_manager._migrations[initial_migration.id] = initial_migration
        
        print(f"   Migration ID: {initial_migration.id}")
        print(f"   Migration Name: {initial_migration.name}")
        print(f"   Migration Version: {initial_migration.version}")
        print(f"   Up Operations: {len(initial_migration.up_operations)}")
        print(f"   Down Operations: {len(initial_migration.down_operations)}")
        
        # Create and apply indexes migration
        print("\n4. Creating indexes migration...")
        indexes_migration = create_indexes_migration(DatabaseType.SQLITE)
        migration_manager._migrations[indexes_migration.id] = indexes_migration
        
        print(f"   Migration ID: {indexes_migration.id}")
        print(f"   Migration Name: {indexes_migration.name}")
        print(f"   Migration Version: {indexes_migration.version}")
        print(f"   Up Operations: {len(indexes_migration.up_operations)}")
        print(f"   Down Operations: {len(indexes_migration.down_operations)}")
        
        # Apply pending migrations
        print("\n5. Applying pending migrations...")
        pending = migration_manager.get_pending_migrations()
        print(f"   Pending migrations: {len(pending)}")
        
        if pending:
            results = migration_manager.apply_migrations()
            for result in results:
                if result.success:
                    print(f"   ✓ Applied migration {result.migration_id}")
                    print(f"     Operations executed: {result.operations_executed}")
                    print(f"     Execution time: {result.execution_time:.3f}s")
                else:
                    print(f"   ✗ Failed to apply migration {result.migration_id}: {result.error_message}")
        
        # Show migration history
        print("\n6. Migration history:")
        history = migration_manager.get_migration_history()
        for record in history:
            print(f"   - {record.name} (v{record.version}) - {record.status}")
            print(f"     Applied: {record.applied_at}")
            if record.rollback_at:
                print(f"     Rolled back: {record.rollback_at}")
        
        # Test custom migration with SQLite-specific features
        print("\n7. Creating and applying SQLite-specific migration...")
        custom_operations = [
            DatabaseOperation(
                operation_type="create_table",
                table="sqlite_demo_table",
                query="""
                CREATE TABLE IF NOT EXISTS sqlite_demo_table (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    data TEXT DEFAULT '{}'
                )
                """
            )
        ]
        
        custom_down_operations = [
            DatabaseOperation(
                operation_type="drop_table",
                table="sqlite_demo_table",
                query="DROP TABLE IF EXISTS sqlite_demo_table"
            )
        ]
        
        custom_migration_id = migration_manager.create_migration(
            "add_sqlite_demo_table",
            custom_operations,
            custom_down_operations
        )
        
        print(f"   Created custom migration: {custom_migration_id}")
        
        # Apply custom migration
        custom_results = migration_manager.apply_migrations()
        for result in custom_results:
            if result.success:
                print(f"   ✓ Applied custom migration")
                print(f"     Operations executed: {result.operations_executed}")
            else:
                print(f"   ✗ Failed to apply custom migration: {result.error_message}")
        
        # Test data insertion into demo table
        print("\n8. Testing data operations on SQLite demo table...")
        import uuid
        import json
        
        insert_operation = DatabaseOperation(
            operation_type="insert",
            table="sqlite_demo_table",
            data={
                "id": str(uuid.uuid4()),
                "name": "SQLite Test Record",
                "description": "This is a test record created by the SQLite migration demo",
                "data": json.dumps({"demo": True, "timestamp": datetime.now().isoformat()})
            }
        )
        
        transaction_result = db_manager.execute_transaction([insert_operation])
        if transaction_result.success:
            print("   ✓ Test record inserted successfully")
        else:
            print(f"   ✗ Failed to insert test record: {transaction_result.error_message}")
        
        # Query the data back
        query_result = db_manager.execute_query("SELECT * FROM sqlite_demo_table LIMIT 5")
        if query_result.success:
            print(f"   ✓ Retrieved {len(query_result.data)} records from sqlite_demo_table")
            for row in query_result.data:
                print(f"     - {row['name']}: {row['description']}")
        else:
            print(f"   ✗ Failed to query sqlite_demo_table: {query_result.error_message}")
        
        # Test JSON storage functionality
        print("\n9. Testing JSON storage functionality...")
        json_data = {
            "feature": "json_storage",
            "test_data": {
                "numbers": [1, 2, 3, 4, 5],
                "strings": ["hello", "world"],
                "nested": {
                    "key": "value",
                    "timestamp": datetime.now().isoformat()
                }
            }
        }
        
        try:
            json_id = db_manager.store_json_data("json_test_table", json_data)
            print(f"   ✓ JSON data stored with ID: {json_id}")
            
            # Query JSON data back
            json_results = db_manager.query_json_data("json_test_table", "feature", "json_storage")
            print(f"   ✓ Retrieved {len(json_results)} JSON records")
            for result in json_results:
                print(f"     - Record ID: {result['id']}")
                print(f"     - Feature: {result['data']['feature']}")
        except Exception as e:
            print(f"   ✗ JSON storage test failed: {e}")
        
        print("\n✓ SQLite migration demo completed successfully!")
        
        # Cleanup
        db_manager.close()
        return True
        
    except Exception as e:
        print(f"\n✗ SQLite migration demo failed: {e}")
        logger.exception("SQLite migration demo error")
        return False
    finally:
        # Clean up temporary database file
        try:
            if os.path.exists(temp_db.name):
                os.unlink(temp_db.name)
        except Exception as e:
            print(f"Warning: Could not clean up temporary database: {e}")


def demo_failover_scenario():
    """Demonstrate database failover scenario."""
    print("\n" + "="*60)
    print("DATABASE FAILOVER SCENARIO DEMO")
    print("="*60)
    
    # Create temporary SQLite database for fallback
    temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
    temp_db.close()
    
    try:
        # Configure both PostgreSQL and SQLite
        postgresql_config = DatabaseConfig(
            database_type=DatabaseType.POSTGRESQL,
            host="localhost",
            port=5432,
            database="visual_editor_core",
            username="postgres",
            password="headbutt"
        )
        
        sqlite_config = DatabaseConfig(
            database_type=DatabaseType.SQLITE,
            database=temp_db.name
        )
        
        print("1. Initializing database manager with both PostgreSQL and SQLite...")
        db_manager = DatabaseManager(
            postgresql_config=postgresql_config,
            sqlite_config=sqlite_config
        )
        
        print(f"   Primary database: {db_manager.get_current_database_type().value}")
        print(f"   Failover occurred: {db_manager.has_failover_occurred()}")
        
        # Test normal operations
        print("\n2. Testing normal operations on primary database...")
        query_result = db_manager.execute_query("SELECT 1 as test_value")
        if query_result.success:
            print("   ✓ Primary database query successful")
        else:
            print(f"   ✗ Primary database query failed: {query_result.error_message}")
        
        # Force failover to test fallback
        print("\n3. Testing forced failover to SQLite...")
        failover_success = db_manager.force_failover()
        if failover_success:
            print("   ✓ Forced failover to SQLite successful")
            print(f"   Current database: {db_manager.get_current_database_type().value}")
            print(f"   Failover occurred: {db_manager.has_failover_occurred()}")
        else:
            print("   ✗ Forced failover failed")
        
        # Test operations on fallback database
        print("\n4. Testing operations on fallback database...")
        migration_manager = db_manager.get_migration_manager()
        
        # Initialize SQLite database
        init_result = migration_manager.initialize_database(DatabaseType.SQLITE)
        if init_result.success:
            print("   ✓ SQLite fallback database initialized")
        else:
            print(f"   ✗ SQLite initialization failed: {init_result.error_message}")
        
        # Test query on fallback
        query_result = db_manager.execute_query("SELECT 1 as test_value")
        if query_result.success:
            print("   ✓ Fallback database query successful")
        else:
            print(f"   ✗ Fallback database query failed: {query_result.error_message}")
        
        # Test primary recovery
        print("\n5. Testing primary database recovery...")
        recovery_success = db_manager.attempt_primary_recovery()
        if recovery_success:
            print("   ✓ Primary database recovery successful")
            print(f"   Current database: {db_manager.get_current_database_type().value}")
        else:
            print("   ✗ Primary database recovery failed (this is expected if PostgreSQL is still unavailable)")
        
        print("\n✓ Failover scenario demo completed!")
        
        # Cleanup
        db_manager.close()
        return True
        
    except Exception as e:
        print(f"\n✗ Failover scenario demo failed: {e}")
        logger.exception("Failover scenario demo error")
        return False
    finally:
        # Clean up temporary database file
        try:
            if os.path.exists(temp_db.name):
                os.unlink(temp_db.name)
        except Exception as e:
            print(f"Warning: Could not clean up temporary database: {e}")


def main():
    """Run all migration system demos."""
    print("VISUAL EDITOR CORE - MIGRATION SYSTEM DEMONSTRATION")
    print("=" * 80)
    print(f"Timestamp: {datetime.now().isoformat()}")
    print("=" * 80)
    
    results = []
    
    # Run PostgreSQL demo
    results.append(("PostgreSQL Migration Demo", demo_postgresql_migration()))
    
    # Run SQLite demo
    results.append(("SQLite Migration Demo", demo_sqlite_migration()))
    
    # Run failover demo
    results.append(("Database Failover Demo", demo_failover_scenario()))
    
    # Summary
    print("\n" + "="*80)
    print("DEMO SUMMARY")
    print("="*80)
    
    for demo_name, success in results:
        status = "✓ PASSED" if success else "✗ FAILED"
        print(f"{demo_name}: {status}")
    
    all_passed = all(result[1] for result in results)
    
    if all_passed:
        print("\n🎉 ALL DEMOS PASSED! Migration system is working correctly.")
    else:
        print("\n❌ Some demos failed. Please check the output above for details.")
    
    return all_passed


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)