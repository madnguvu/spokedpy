#!/usr/bin/env python3
"""
Demo script for the migration manager and schema versioning system.

This script demonstrates:
1. Database initialization with core schema
2. Creating and applying migrations
3. Migration validation and dependency checking
4. Rollback capabilities
5. Migration history tracking
"""

import os
import tempfile
from datetime import datetime

from visual_editor_core.database import (
    DatabaseManager,
    DatabaseConfig,
    DatabaseType,
    DatabaseOperation
)
from visual_editor_core.database.migrations.initial_schema import create_initial_schema_migration
from visual_editor_core.database.migrations.add_indexes import create_indexes_migration


def main():
    """Run migration system demo."""
    print("=== Visual Editor Core - Migration System Demo ===\n")
    
    # Create temporary database for demo
    temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
    temp_db.close()
    
    try:
        # Configure SQLite database
        sqlite_config = DatabaseConfig(
            database_type=DatabaseType.SQLITE,
            database=temp_db.name
        )
        
        print(f"Using temporary SQLite database: {temp_db.name}")
        
        # Create database manager
        db_manager = DatabaseManager(sqlite_config=sqlite_config)
        print("✓ Database manager created")
        
        # Get migration manager
        migration_manager = db_manager.get_migration_manager()
        print("✓ Migration manager initialized")
        print(f"  Current version: {migration_manager.get_current_version()}")
        
        # 1. Initialize database with core schema
        print("\n1. Initializing database with core schema...")
        init_result = migration_manager.initialize_database(DatabaseType.SQLITE)
        
        if init_result.success:
            print("✓ Database initialization successful")
            print(f"  Tables created: {', '.join(init_result.tables_created)}")
            print(f"  Initial version: {init_result.initial_version}")
        else:
            print(f"✗ Database initialization failed: {init_result.error_message}")
            return
        
        # 2. Create and apply a custom migration
        print("\n2. Creating custom migration...")
        
        # Create operations for a new feature table
        up_operations = [
            DatabaseOperation(
                operation_type="create_table",
                table="feature_flags",
                query="""
                CREATE TABLE IF NOT EXISTS feature_flags (
                    id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
                    name TEXT NOT NULL,
                    description TEXT,
                    is_enabled INTEGER DEFAULT 0,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(tenant_id, name)
                )
                """
            ),
            DatabaseOperation(
                operation_type="create_index",
                table="feature_flags",
                query="CREATE INDEX IF NOT EXISTS idx_feature_flags_tenant_id ON feature_flags(tenant_id)"
            )
        ]
        
        # Create down operations for rollback
        down_operations = [
            DatabaseOperation(
                operation_type="drop_index",
                table="feature_flags",
                query="DROP INDEX IF EXISTS idx_feature_flags_tenant_id"
            ),
            DatabaseOperation(
                operation_type="drop_table",
                table="feature_flags",
                query="DROP TABLE IF EXISTS feature_flags"
            )
        ]
        
        migration_id = migration_manager.create_migration(
            "add_feature_flags",
            up_operations,
            down_operations
        )
        
        print(f"✓ Migration created: {migration_id}")
        
        # 3. Validate migration
        print("\n3. Validating migration...")
        pending_migrations = migration_manager.get_pending_migrations()
        
        if pending_migrations:
            migration = pending_migrations[0]
            validation_result = migration_manager.validate_migration(migration)
            
            if validation_result.is_valid:
                print("✓ Migration validation passed")
                if validation_result.warnings:
                    print(f"  Warnings: {', '.join(validation_result.warnings)}")
            else:
                print("✗ Migration validation failed")
                print(f"  Errors: {', '.join(validation_result.errors)}")
                return
        
        # 4. Apply migrations
        print("\n4. Applying migrations...")
        apply_results = migration_manager.apply_migrations()
        
        for result in apply_results:
            if result.success:
                print(f"✓ Migration {result.migration_id} applied successfully")
                print(f"  Operations executed: {result.operations_executed}")
                print(f"  Execution time: {result.execution_time:.3f}s")
            else:
                print(f"✗ Migration {result.migration_id} failed: {result.error_message}")
        
        # 5. Show migration history
        print("\n5. Migration history:")
        history = migration_manager.get_migration_history()
        
        for record in history:
            status_symbol = "✓" if record.status == "applied" else "✗"
            print(f"  {status_symbol} {record.name} (v{record.version})")
            print(f"    ID: {record.migration_id}")
            print(f"    Applied: {record.applied_at}")
            print(f"    Status: {record.status}")
            if record.execution_time:
                print(f"    Execution time: {record.execution_time:.3f}s")
            print()
        
        # 6. Create another migration to demonstrate rollback
        print("6. Creating second migration for rollback demo...")
        
        second_migration_ops = [
            DatabaseOperation(
                operation_type="create_table",
                table="user_sessions",
                query="""
                CREATE TABLE IF NOT EXISTS user_sessions (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    session_token TEXT NOT NULL UNIQUE,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    expires_at DATETIME NOT NULL,
                    ip_address TEXT,
                    user_agent TEXT
                )
                """
            )
        ]
        
        second_migration_down = [
            DatabaseOperation(
                operation_type="drop_table",
                table="user_sessions",
                query="DROP TABLE IF EXISTS user_sessions"
            )
        ]
        
        second_migration_id = migration_manager.create_migration(
            "add_user_sessions",
            second_migration_ops,
            second_migration_down
        )
        
        # Apply second migration
        apply_results = migration_manager.apply_migrations()
        
        if apply_results and apply_results[0].success:
            print(f"✓ Second migration applied: {second_migration_id}")
            
            current_version = migration_manager.get_current_version()
            print(f"  Current version: {current_version}")
            
            # 7. Demonstrate rollback
            print("\n7. Demonstrating rollback...")
            
            # Find the version to rollback to (first custom migration)
            history = migration_manager.get_migration_history()
            target_version = None
            
            for record in history:
                if record.name == "add_feature_flags":
                    target_version = record.version
                    break
            
            if target_version:
                print(f"Rolling back to version: {target_version}")
                
                rollback_result = migration_manager.rollback_migration(target_version)
                
                if rollback_result.success:
                    print("✓ Rollback successful")
                    print(f"  Operations executed: {rollback_result.operations_executed}")
                    print(f"  Execution time: {rollback_result.execution_time:.3f}s")
                    
                    # Show updated history
                    print("\n  Updated migration history:")
                    updated_history = migration_manager.get_migration_history()
                    
                    for record in updated_history:
                        status_symbol = "✓" if record.status == "applied" else "↶" if record.status == "rolled_back" else "✗"
                        print(f"    {status_symbol} {record.name} (v{record.version}) - {record.status}")
                else:
                    print(f"✗ Rollback failed: {rollback_result.error_message}")
        
        # 8. Demonstrate backup functionality
        print("\n8. Demonstrating backup functionality...")
        backup_result = migration_manager.backup_before_migration()
        
        if backup_result.success:
            print("✓ Backup created successfully")
            print(f"  Backup path: {backup_result.backup_path}")
            print(f"  Backup size: {backup_result.backup_size} bytes")
        else:
            print(f"✗ Backup failed: {backup_result.error_message}")
        
        # 9. Demonstrate repair functionality
        print("\n9. Demonstrating migration state repair...")
        repair_result = migration_manager.repair_migration_state()
        
        if repair_result.success:
            print("✓ Migration state repair completed")
            if repair_result.issues_found:
                print(f"  Issues found: {len(repair_result.issues_found)}")
                for issue in repair_result.issues_found:
                    print(f"    - {issue}")
            else:
                print("  No issues found")
            
            if repair_result.repairs_applied:
                print(f"  Repairs applied: {len(repair_result.repairs_applied)}")
                for repair in repair_result.repairs_applied:
                    print(f"    - {repair}")
        else:
            print(f"✗ Repair failed: {repair_result.error_message}")
        
        # 10. Show final database state
        print("\n10. Final database state:")
        print(f"Current version: {migration_manager.get_current_version()}")
        
        pending = migration_manager.get_pending_migrations()
        print(f"Pending migrations: {len(pending)}")
        
        final_history = migration_manager.get_migration_history()
        applied_count = len([h for h in final_history if h.status == "applied"])
        rolled_back_count = len([h for h in final_history if h.status == "rolled_back"])
        
        print(f"Applied migrations: {applied_count}")
        print(f"Rolled back migrations: {rolled_back_count}")
        
        print("\n=== Demo completed successfully! ===")
        
    except Exception as e:
        print(f"\n✗ Demo failed with error: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        # Clean up
        try:
            db_manager.close()
        except:
            pass
        
        if os.path.exists(temp_db.name):
            os.unlink(temp_db.name)
            print(f"\nCleaned up temporary database: {temp_db.name}")


if __name__ == "__main__":
    main()