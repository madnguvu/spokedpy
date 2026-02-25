"""
Tests for the migration manager and schema versioning system.
"""

import pytest
import tempfile
import os
import uuid
from datetime import datetime
from unittest.mock import Mock, patch

from visual_editor_core.database import (
    DatabaseManager,
    MigrationManager,
    Migration,
    MigrationResult,
    InitializationResult,
    RollbackResult,
    ValidationResult,
    DatabaseConfig,
    DatabaseType,
    DatabaseOperation
)
from visual_editor_core.database.migrations.initial_schema import create_initial_schema_migration
from visual_editor_core.database.migrations.add_indexes import create_indexes_migration


class TestMigrationManager:
    """Test cases for MigrationManager."""
    
    @pytest.fixture
    def temp_db_path(self):
        """Create temporary database path."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        yield db_path
        # Cleanup - try multiple times on Windows
        import time
        for i in range(5):
            try:
                if os.path.exists(db_path):
                    os.unlink(db_path)
                break
            except PermissionError:
                time.sleep(0.1)
                continue
    
    @pytest.fixture
    def sqlite_config(self, temp_db_path):
        """Create SQLite database configuration."""
        return DatabaseConfig(
            database_type=DatabaseType.SQLITE,
            database=temp_db_path
        )
    
    @pytest.fixture
    def database_manager(self, sqlite_config):
        """Create database manager with SQLite."""
        manager = DatabaseManager(sqlite_config=sqlite_config)
        yield manager
        # Ensure proper cleanup
        try:
            manager.close()
        except:
            pass
    
    @pytest.fixture
    def migration_manager(self, database_manager):
        """Create migration manager."""
        return database_manager.get_migration_manager()
    
    def test_migration_manager_initialization(self, migration_manager):
        """Test migration manager initialization."""
        assert migration_manager is not None
        assert migration_manager.get_current_version() == "0.0.0"
        assert len(migration_manager.get_pending_migrations()) == 0
    
    def test_database_initialization_sqlite(self, migration_manager):
        """Test database initialization with SQLite."""
        result = migration_manager.initialize_database(DatabaseType.SQLITE)
        
        assert result.success is True
        assert result.database_type == DatabaseType.SQLITE
        assert len(result.tables_created) > 0
        assert "tenants" in result.tables_created
        assert "users" in result.tables_created
        assert "roles" in result.tables_created
        assert "audit_logs" in result.tables_created
        assert result.initial_version == "1.0.0"
    
    def test_create_migration(self, migration_manager):
        """Test creating a new migration."""
        operations = [
            DatabaseOperation(
                operation_type="create_table",
                table="test_table",
                query="CREATE TABLE test_table (id INTEGER PRIMARY KEY, name TEXT)"
            )
        ]
        
        migration_id = migration_manager.create_migration(
            "test_migration",
            operations
        )
        
        assert migration_id is not None
        assert len(migration_id) > 0
        
        # Check that migration was added
        pending = migration_manager.get_pending_migrations()
        assert len(pending) == 1
        assert pending[0].name == "test_migration"
    
    def test_migration_validation(self, migration_manager):
        """Test migration validation."""
        # Valid migration
        valid_migration = Migration(
            id=str(uuid.uuid4()),
            name="valid_migration",
            version="1.0.1",
            description="A valid migration",
            up_operations=[
                DatabaseOperation(
                    operation_type="create_table",
                    table="test_table",
                    query="CREATE TABLE test_table (id INTEGER PRIMARY KEY)"
                )
            ],
            down_operations=[
                DatabaseOperation(
                    operation_type="drop_table",
                    table="test_table",
                    query="DROP TABLE test_table"
                )
            ]
        )
        
        result = migration_manager.validate_migration(valid_migration)
        assert result.is_valid is True
        assert len(result.errors) == 0
        
        # Invalid migration (no operations)
        invalid_migration = Migration(
            id=str(uuid.uuid4()),
            name="invalid_migration",
            version="1.0.2",
            description="An invalid migration",
            up_operations=[],  # No operations
            down_operations=[]
        )
        
        result = migration_manager.validate_migration(invalid_migration)
        assert result.is_valid is False
        assert len(result.errors) > 0
    
    def test_apply_migrations(self, migration_manager):
        """Test applying migrations."""
        # Initialize database first
        init_result = migration_manager.initialize_database(DatabaseType.SQLITE)
        assert init_result.success is True
        
        # Create a test migration
        operations = [
            DatabaseOperation(
                operation_type="create_table",
                table="test_table",
                query="CREATE TABLE IF NOT EXISTS test_table (id TEXT PRIMARY KEY, name TEXT)"
            )
        ]
        
        migration_id = migration_manager.create_migration(
            "add_test_table",
            operations,
            down_operations=[
                DatabaseOperation(
                    operation_type="drop_table",
                    table="test_table",
                    query="DROP TABLE IF EXISTS test_table"
                )
            ]
        )
        
        # Apply migrations
        results = migration_manager.apply_migrations()
        
        assert len(results) == 1
        assert results[0].success is True
        assert results[0].migration_id == migration_id
        
        # Check that migration is no longer pending
        pending = migration_manager.get_pending_migrations()
        assert len(pending) == 0
    
    def test_rollback_migration(self, migration_manager):
        """Test rolling back migrations."""
        # Initialize database
        init_result = migration_manager.initialize_database(DatabaseType.SQLITE)
        assert init_result.success is True
        
        # Create and apply a migration
        operations = [
            DatabaseOperation(
                operation_type="create_table",
                table="rollback_test_table",
                query="CREATE TABLE IF NOT EXISTS rollback_test_table (id TEXT PRIMARY KEY, data TEXT)"
            )
        ]
        
        down_operations = [
            DatabaseOperation(
                operation_type="drop_table",
                table="rollback_test_table",
                query="DROP TABLE IF EXISTS rollback_test_table"
            )
        ]
        
        migration_id = migration_manager.create_migration(
            "rollback_test",
            operations,
            down_operations
        )
        
        # Apply migration
        apply_results = migration_manager.apply_migrations()
        assert len(apply_results) == 1
        assert apply_results[0].success is True
        
        current_version = migration_manager.get_current_version()
        
        # Rollback to previous version
        rollback_result = migration_manager.rollback_migration("1.0.0")
        
        assert rollback_result.success is True
        assert rollback_result.target_version == "1.0.0"
        assert rollback_result.operations_executed > 0
    
    def test_migration_history(self, migration_manager):
        """Test migration history tracking."""
        # Initialize database
        init_result = migration_manager.initialize_database(DatabaseType.SQLITE)
        assert init_result.success is True
        
        # Initially no history (except schema migrations table)
        history = migration_manager.get_migration_history()
        initial_count = len(history)
        
        # Create and apply a migration
        operations = [
            DatabaseOperation(
                operation_type="create_table",
                table="history_test_table",
                query="CREATE TABLE IF NOT EXISTS history_test_table (id TEXT PRIMARY KEY)"
            )
        ]
        
        migration_id = migration_manager.create_migration(
            "history_test",
            operations
        )
        
        migration_manager.apply_migrations()
        
        # Check history
        history = migration_manager.get_migration_history()
        assert len(history) == initial_count + 1
        
        # Find our migration in history
        our_migration = next((h for h in history if h.migration_id == migration_id), None)
        assert our_migration is not None
        assert our_migration.name == "history_test"
        assert our_migration.status == "applied"
        assert our_migration.applied_at is not None
    
    def test_backup_before_migration(self, migration_manager):
        """Test backup creation before migration."""
        # Initialize database
        init_result = migration_manager.initialize_database(DatabaseType.SQLITE)
        assert init_result.success is True
        
        # Create backup
        backup_result = migration_manager.backup_before_migration()
        
        # For SQLite, backup should succeed
        assert backup_result.success is True
        assert backup_result.backup_path is not None
        assert len(backup_result.backup_path) > 0
    
    def test_repair_migration_state(self, migration_manager):
        """Test migration state repair."""
        # Initialize database
        init_result = migration_manager.initialize_database(DatabaseType.SQLITE)
        assert init_result.success is True
        
        # Run repair (should find no issues initially)
        repair_result = migration_manager.repair_migration_state()
        
        assert repair_result.success is True
        # May have issues or not, depending on state
        assert isinstance(repair_result.issues_found, list)
        assert isinstance(repair_result.repairs_applied, list)
    
    def test_version_comparison(self, migration_manager):
        """Test version comparison logic."""
        # Test version comparison through migration manager's internal methods
        assert migration_manager._compare_versions("1.0.0", "1.0.1") == -1
        assert migration_manager._compare_versions("1.0.1", "1.0.0") == 1
        assert migration_manager._compare_versions("1.0.0", "1.0.0") == 0
        assert migration_manager._compare_versions("2.0.0", "1.9.9") == 1
        assert migration_manager._compare_versions("1.2.3", "1.2.4") == -1
    
    def test_version_to_tuple(self, migration_manager):
        """Test version string to tuple conversion."""
        assert migration_manager._version_to_tuple("1.2.3") == (1, 2, 3)
        assert migration_manager._version_to_tuple("1.2") == (1, 2, 0)
        assert migration_manager._version_to_tuple("1") == (1, 0, 0)
        assert migration_manager._version_to_tuple("invalid") == (0, 0, 0)
    
    def test_initial_schema_migration_creation(self):
        """Test creating initial schema migration."""
        # Test PostgreSQL migration creation
        pg_migration = create_initial_schema_migration(DatabaseType.POSTGRESQL)
        assert pg_migration.name == "initial_schema"
        assert pg_migration.version == "1.0.0"
        assert len(pg_migration.up_operations) > 0
        assert len(pg_migration.down_operations) > 0
        
        # Test SQLite migration creation
        sqlite_migration = create_initial_schema_migration(DatabaseType.SQLITE)
        assert sqlite_migration.name == "initial_schema"
        assert sqlite_migration.version == "1.0.0"
        assert len(sqlite_migration.up_operations) > 0
        assert len(sqlite_migration.down_operations) > 0
    
    def test_indexes_migration_creation(self):
        """Test creating indexes migration."""
        # Test PostgreSQL indexes migration
        pg_migration = create_indexes_migration(DatabaseType.POSTGRESQL)
        assert pg_migration.name == "add_indexes"
        assert pg_migration.version == "1.1.0"
        assert len(pg_migration.up_operations) > 0
        assert len(pg_migration.down_operations) > 0
        
        # Test SQLite indexes migration
        sqlite_migration = create_indexes_migration(DatabaseType.SQLITE)
        assert sqlite_migration.name == "add_indexes"
        assert sqlite_migration.version == "1.1.0"
        assert len(sqlite_migration.up_operations) > 0
        assert len(sqlite_migration.down_operations) > 0
    
    def test_migration_checksum_validation(self, migration_manager):
        """Test migration checksum validation."""
        migration = Migration(
            id=str(uuid.uuid4()),
            name="checksum_test",
            version="1.0.1",
            description="Test checksum validation",
            up_operations=[
                DatabaseOperation(
                    operation_type="create_table",
                    table="checksum_table",
                    query="CREATE TABLE checksum_table (id INTEGER PRIMARY KEY)"
                )
            ]
        )
        
        # Checksum should be calculated automatically
        assert migration.checksum is not None
        assert len(migration.checksum) == 64  # SHA256 hex length
        
        # Validation should pass
        result = migration_manager.validate_migration(migration)
        assert result.is_valid is True
        
        # Corrupt checksum
        migration.checksum = "invalid_checksum"
        result = migration_manager.validate_migration(migration)
        assert result.is_valid is False
        assert any("checksum mismatch" in error.lower() for error in result.errors)
    
    def test_migration_dependencies(self, migration_manager):
        """Test migration dependency validation."""
        # Create migration with non-existent dependency
        migration = Migration(
            id=str(uuid.uuid4()),
            name="dependent_migration",
            version="1.0.1",
            description="Migration with dependencies",
            up_operations=[
                DatabaseOperation(
                    operation_type="create_table",
                    table="dependent_table",
                    query="CREATE TABLE dependent_table (id INTEGER PRIMARY KEY)"
                )
            ],
            dependencies=["non_existent_migration_id"]
        )
        
        result = migration_manager.validate_migration(migration)
        assert result.is_valid is False
        assert not result.dependencies_satisfied
        assert len(result.missing_dependencies) == 1
        assert "non_existent_migration_id" in result.missing_dependencies


class TestMigrationModels:
    """Test migration data models."""
    
    def test_migration_creation(self):
        """Test Migration model creation and validation."""
        migration = Migration(
            id=str(uuid.uuid4()),
            name="test_migration",
            version="1.0.0",
            description="Test migration",
            up_operations=[
                DatabaseOperation(
                    operation_type="create_table",
                    table="test_table",
                    query="CREATE TABLE test_table (id INTEGER PRIMARY KEY)"
                )
            ]
        )
        
        assert migration.id is not None
        assert migration.name == "test_migration"
        assert migration.checksum is not None
        assert len(migration.validate()) == 0  # No validation errors
    
    def test_migration_validation_errors(self):
        """Test Migration validation with errors."""
        # Migration with missing required fields
        migration = Migration(
            id="",  # Missing ID
            name="",  # Missing name
            version="",  # Missing version
            description="Test",
            up_operations=[]  # No operations
        )
        
        errors = migration.validate()
        assert len(errors) > 0
        assert any("ID is required" in error for error in errors)
        assert any("name is required" in error for error in errors)
        assert any("version is required" in error for error in errors)
        assert any("at least one up operation" in error for error in errors)
    
    def test_database_operation_validation(self):
        """Test DatabaseOperation validation."""
        # Valid operation
        valid_op = DatabaseOperation(
            operation_type="insert",
            table="test_table",
            data={"name": "test"}
        )
        assert valid_op.validate() is True
        
        # Invalid operation (missing table)
        invalid_op = DatabaseOperation(
            operation_type="insert",
            table="",  # Missing table
            data={"name": "test"}
        )
        assert invalid_op.validate() is False
        
        # Invalid operation (missing data for insert)
        invalid_op2 = DatabaseOperation(
            operation_type="insert",
            table="test_table",
            data={}  # No data
        )
        assert invalid_op2.validate() is False


@pytest.mark.integration
class TestMigrationIntegration:
    """Integration tests for migration system."""
    
    @pytest.fixture
    def temp_db_path(self):
        """Create temporary database path."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        yield db_path
        # Cleanup - try multiple times on Windows
        import time
        for i in range(5):
            try:
                if os.path.exists(db_path):
                    os.unlink(db_path)
                break
            except PermissionError:
                time.sleep(0.1)
                continue
    
    @pytest.fixture
    def sqlite_config(self, temp_db_path):
        """Create SQLite database configuration."""
        return DatabaseConfig(
            database_type=DatabaseType.SQLITE,
            database=temp_db_path
        )
    
    def test_full_migration_workflow(self, sqlite_config):
        """Test complete migration workflow from initialization to rollback."""
        # Create database manager and migration manager
        db_manager = DatabaseManager(sqlite_config=sqlite_config)
        migration_manager = db_manager.get_migration_manager()
        
        # 1. Initialize database
        init_result = migration_manager.initialize_database(DatabaseType.SQLITE)
        assert init_result.success is True
        assert migration_manager.get_current_version() == "1.0.0"
        
        # 2. Create and apply first migration
        migration1_ops = [
            DatabaseOperation(
                operation_type="create_table",
                table="workflow_test1",
                query="CREATE TABLE IF NOT EXISTS workflow_test1 (id TEXT PRIMARY KEY, data TEXT)"
            )
        ]
        
        migration1_down = [
            DatabaseOperation(
                operation_type="drop_table",
                table="workflow_test1",
                query="DROP TABLE IF EXISTS workflow_test1"
            )
        ]
        
        migration1_id = migration_manager.create_migration(
            "workflow_test1",
            migration1_ops,
            migration1_down
        )
        
        apply_results = migration_manager.apply_migrations()
        assert len(apply_results) == 1
        assert apply_results[0].success is True
        
        # 3. Create and apply second migration
        migration2_ops = [
            DatabaseOperation(
                operation_type="create_table",
                table="workflow_test2",
                query="CREATE TABLE IF NOT EXISTS workflow_test2 (id TEXT PRIMARY KEY, value INTEGER)"
            )
        ]
        
        migration2_down = [
            DatabaseOperation(
                operation_type="drop_table",
                table="workflow_test2",
                query="DROP TABLE IF EXISTS workflow_test2"
            )
        ]
        
        migration2_id = migration_manager.create_migration(
            "workflow_test2",
            migration2_ops,
            migration2_down
        )
        
        apply_results = migration_manager.apply_migrations()
        assert len(apply_results) == 1
        assert apply_results[0].success is True
        
        # 4. Verify migration history
        history = migration_manager.get_migration_history()
        applied_migrations = [h for h in history if h.status == "applied"]
        assert len(applied_migrations) >= 2
        
        # 5. Test rollback
        current_version = migration_manager.get_current_version()
        
        # Get the version of the first migration we applied
        first_migration_version = None
        for record in history:
            if record.migration_id == migration1_id:
                first_migration_version = record.version
                break
        
        assert first_migration_version is not None
        
        # Rollback to first migration version
        rollback_result = migration_manager.rollback_migration(first_migration_version)
        assert rollback_result.success is True
        
        # 6. Verify rollback worked
        history_after_rollback = migration_manager.get_migration_history()
        rolled_back_migrations = [h for h in history_after_rollback if h.status == "rolled_back"]
        assert len(rolled_back_migrations) >= 1
        
        # Clean up
        db_manager.close()
    
    def test_migration_error_handling(self, sqlite_config):
        """Test migration error handling and recovery."""
        db_manager = DatabaseManager(sqlite_config=sqlite_config)
        migration_manager = db_manager.get_migration_manager()
        
        # Initialize database
        init_result = migration_manager.initialize_database(DatabaseType.SQLITE)
        assert init_result.success is True
        
        # Create migration with invalid SQL
        invalid_ops = [
            DatabaseOperation(
                operation_type="create_table",
                table="invalid_table",
                query="INVALID SQL STATEMENT THAT WILL DEFINITELY FAIL"  # Invalid SQL
            )
        ]
        
        migration_id = migration_manager.create_migration(
            "invalid_migration",
            invalid_ops
        )
        
        # Apply migrations - should fail
        apply_results = migration_manager.apply_migrations()
        assert len(apply_results) == 1
        assert apply_results[0].success is False
        assert apply_results[0].error_message is not None
        
        # Verify migration was not recorded as applied
        history = migration_manager.get_migration_history()
        failed_migration = next((h for h in history if h.migration_id == migration_id), None)
        # Migration should not be in history if it failed during application
        assert failed_migration is None or failed_migration.status != "applied"
        
        # Clean up
        db_manager.close()


if __name__ == "__main__":
    pytest.main([__file__])