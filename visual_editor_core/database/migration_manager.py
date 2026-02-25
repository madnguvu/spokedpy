"""
Migration Manager - Database schema versioning and migration system.
"""

import logging
import os
import uuid
import hashlib
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from pathlib import Path

from .models import (
    DatabaseType,
    DatabaseOperation,
    QueryResult,
    TransactionResult
)
from .exceptions import (
    DatabaseError,
    MigrationError,
    ValidationError
)


@dataclass
class Migration:
    """Represents a database migration."""
    id: str
    name: str
    version: str
    description: str
    up_operations: List[DatabaseOperation] = field(default_factory=list)
    down_operations: List[DatabaseOperation] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    checksum: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    applied_at: Optional[datetime] = None
    rollback_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Calculate checksum after initialization."""
        if not self.checksum:
            self.checksum = self._calculate_checksum()
    
    def _calculate_checksum(self) -> str:
        """Calculate migration checksum for integrity verification."""
        content = f"{self.name}:{self.version}:{self.description}"
        for op in self.up_operations:
            content += f":{op.operation_type}:{op.table}:{str(op.data)}"
        return hashlib.sha256(content.encode()).hexdigest()
    
    def validate(self) -> List[str]:
        """Validate migration structure."""
        errors = []
        
        if not self.id:
            errors.append("Migration ID is required")
        if not self.name:
            errors.append("Migration name is required")
        if not self.version:
            errors.append("Migration version is required")
        if not self.up_operations:
            errors.append("Migration must have at least one up operation")
        
        # Validate operations
        for i, op in enumerate(self.up_operations):
            if not op.validate():
                errors.append(f"Invalid up operation at index {i}")
        
        for i, op in enumerate(self.down_operations):
            if not op.validate():
                errors.append(f"Invalid down operation at index {i}")
        
        return errors


@dataclass
class MigrationRecord:
    """Database record of applied migration."""
    migration_id: str
    name: str
    version: str
    checksum: str
    applied_at: datetime
    rollback_at: Optional[datetime] = None
    execution_time: float = 0.0
    status: str = "applied"  # applied, rolled_back, failed
    error_message: Optional[str] = None


@dataclass
class MigrationResult:
    """Result of migration execution."""
    success: bool
    migration_id: str
    operations_executed: int = 0
    execution_time: float = 0.0
    error_message: Optional[str] = None
    rollback_performed: bool = False


@dataclass
class InitializationResult:
    """Result of database initialization."""
    success: bool
    database_type: DatabaseType
    tables_created: List[str] = field(default_factory=list)
    initial_version: str = "0.0.0"
    error_message: Optional[str] = None


@dataclass
class RollbackResult:
    """Result of migration rollback."""
    success: bool
    migration_id: str
    target_version: str
    operations_executed: int = 0
    execution_time: float = 0.0
    error_message: Optional[str] = None


@dataclass
class ValidationResult:
    """Result of migration validation."""
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    dependencies_satisfied: bool = True
    missing_dependencies: List[str] = field(default_factory=list)


@dataclass
class BackupResult:
    """Result of pre-migration backup."""
    success: bool
    backup_path: str
    backup_size: int = 0
    created_at: datetime = field(default_factory=datetime.now)
    error_message: Optional[str] = None


@dataclass
class RepairResult:
    """Result of migration state repair."""
    success: bool
    issues_found: List[str] = field(default_factory=list)
    repairs_applied: List[str] = field(default_factory=list)
    error_message: Optional[str] = None


class MigrationManager:
    """
    Database migration manager with version tracking and rollback capabilities.
    
    This class handles database schema creation, updates, and version management
    for both PostgreSQL and SQLite databases.
    """
    
    def __init__(self, database_manager):
        """
        Initialize the migration manager.
        
        Args:
            database_manager: DatabaseManager instance
        """
        self.database_manager = database_manager
        self.logger = logging.getLogger(__name__)
        self._migrations: Dict[str, Migration] = {}
        self._migration_history: List[MigrationRecord] = []
        self._current_version = "0.0.0"
        self._migrations_table = "schema_migrations"
        
        # Initialize migration tracking table
        self._ensure_migrations_table()
        
        # Load migration history
        self._load_migration_history()
    
    def initialize_database(self, database_type: DatabaseType) -> InitializationResult:
        """
        Initialize database with core schema.
        
        Args:
            database_type: Type of database to initialize
            
        Returns:
            InitializationResult: Initialization result
        """
        try:
            self.logger.info(f"Initializing {database_type.value} database")
            
            # Create core tables
            core_tables = self._get_core_schema(database_type)
            tables_created = []
            
            for table_name, table_schema in core_tables.items():
                operation = DatabaseOperation(
                    operation_type="create_table",
                    table=table_name,
                    query=table_schema
                )
                
                result = self.database_manager.execute_query(operation.query)
                if result.success:
                    tables_created.append(table_name)
                    self.logger.info(f"Created table: {table_name}")
                else:
                    self.logger.error(f"Failed to create table {table_name}: {result.error_message}")
                    return InitializationResult(
                        success=False,
                        database_type=database_type,
                        error_message=f"Failed to create table {table_name}: {result.error_message}"
                    )
            
            # Set initial version
            self._set_current_version("1.0.0")
            
            return InitializationResult(
                success=True,
                database_type=database_type,
                tables_created=tables_created,
                initial_version="1.0.0"
            )
            
        except Exception as e:
            self.logger.error(f"Database initialization failed: {e}")
            return InitializationResult(
                success=False,
                database_type=database_type,
                error_message=str(e)
            )
    
    def apply_migrations(self, target_version: Optional[str] = None) -> List[MigrationResult]:
        """
        Apply pending migrations up to target version.
        
        Args:
            target_version: Target version to migrate to (latest if None)
            
        Returns:
            List[MigrationResult]: Results of migration executions
        """
        try:
            pending_migrations = self.get_pending_migrations()
            
            if target_version:
                # Filter migrations up to target version
                pending_migrations = [
                    m for m in pending_migrations 
                    if self._compare_versions(m.version, target_version) <= 0
                ]
            
            if not pending_migrations:
                self.logger.info("No pending migrations to apply")
                return []
            
            results = []
            
            for migration in pending_migrations:
                # Validate migration before applying
                validation_result = self.validate_migration(migration)
                if not validation_result.is_valid:
                    error_msg = f"Migration validation failed: {', '.join(validation_result.errors)}"
                    results.append(MigrationResult(
                        success=False,
                        migration_id=migration.id,
                        error_message=error_msg
                    ))
                    break
                
                # Create backup before migration
                backup_result = self.backup_before_migration()
                if not backup_result.success:
                    self.logger.warning(f"Backup failed: {backup_result.error_message}")
                
                # Apply migration
                result = self._apply_migration(migration)
                results.append(result)
                
                if not result.success:
                    self.logger.error(f"Migration {migration.id} failed: {result.error_message}")
                    break
                
                self.logger.info(f"Successfully applied migration {migration.id}")
            
            return results
            
        except Exception as e:
            self.logger.error(f"Migration application failed: {e}")
            return [MigrationResult(
                success=False,
                migration_id="unknown",
                error_message=str(e)
            )]
    
    def rollback_migration(self, target_version: str) -> RollbackResult:
        """
        Rollback migrations to target version.
        
        Args:
            target_version: Target version to rollback to
            
        Returns:
            RollbackResult: Rollback operation result
        """
        try:
            current_version = self.get_current_version()
            
            if self._compare_versions(target_version, current_version) >= 0:
                return RollbackResult(
                    success=False,
                    migration_id="",
                    target_version=target_version,
                    error_message="Target version must be lower than current version"
                )
            
            # Get migrations to rollback (in reverse order)
            migrations_to_rollback = [
                record for record in reversed(self._migration_history)
                if (self._compare_versions(record.version, target_version) > 0 and 
                    record.status == "applied")
            ]
            
            if not migrations_to_rollback:
                return RollbackResult(
                    success=True,
                    migration_id="",
                    target_version=target_version,
                    operations_executed=0
                )
            
            # Create backup before rollback
            backup_result = self.backup_before_migration()
            if not backup_result.success:
                self.logger.warning(f"Backup failed: {backup_result.error_message}")
            
            operations_executed = 0
            start_time = datetime.now()
            
            for record in migrations_to_rollback:
                migration = self._migrations.get(record.migration_id)
                if not migration:
                    self.logger.warning(f"Migration {record.migration_id} not found for rollback")
                    continue
                
                # Execute down operations
                for operation in migration.down_operations:
                    if operation.query:
                        result = self.database_manager.execute_query(operation.query, operation.parameters)
                    else:
                        query = self._build_operation_query(operation)
                        result = self.database_manager.execute_query(query, operation.data)
                    
                    if not result.success:
                        execution_time = (datetime.now() - start_time).total_seconds()
                        return RollbackResult(
                            success=False,
                            migration_id=migration.id,
                            target_version=target_version,
                            operations_executed=operations_executed,
                            execution_time=execution_time,
                            error_message=f"Rollback failed: {result.error_message}"
                        )
                    
                    operations_executed += 1
                
                # Update migration record
                self._update_migration_record(record.migration_id, "rolled_back")
                self.logger.info(f"Rolled back migration {migration.id}")
            
            # Update current version
            self._set_current_version(target_version)
            
            execution_time = (datetime.now() - start_time).total_seconds()
            
            return RollbackResult(
                success=True,
                migration_id=migrations_to_rollback[0].migration_id if migrations_to_rollback else "",
                target_version=target_version,
                operations_executed=operations_executed,
                execution_time=execution_time
            )
            
        except Exception as e:
            self.logger.error(f"Migration rollback failed: {e}")
            return RollbackResult(
                success=False,
                migration_id="",
                target_version=target_version,
                error_message=str(e)
            )
    
    def get_current_version(self) -> str:
        """
        Get current database schema version.
        
        Returns:
            str: Current version
        """
        return self._current_version
    
    def get_pending_migrations(self) -> List[Migration]:
        """
        Get list of pending migrations.
        
        Returns:
            List[Migration]: Pending migrations sorted by version
        """
        applied_migration_ids = {record.migration_id for record in self._migration_history 
                               if record.status == "applied"}
        
        pending = [
            migration for migration in self._migrations.values()
            if migration.id not in applied_migration_ids
        ]
        
        # Sort by version
        return sorted(pending, key=lambda m: self._version_to_tuple(m.version))
    
    def create_migration(self, 
                        migration_name: str, 
                        operations: List[DatabaseOperation],
                        down_operations: Optional[List[DatabaseOperation]] = None,
                        dependencies: Optional[List[str]] = None) -> str:
        """
        Create a new migration.
        
        Args:
            migration_name: Name of the migration
            operations: List of up operations
            down_operations: List of down operations (optional)
            dependencies: List of migration dependencies (optional)
            
        Returns:
            str: Migration ID
        """
        migration_id = str(uuid.uuid4())
        version = self._generate_next_version()
        
        migration = Migration(
            id=migration_id,
            name=migration_name,
            version=version,
            description=f"Migration: {migration_name}",
            up_operations=operations,
            down_operations=down_operations or [],
            dependencies=dependencies or []
        )
        
        self._migrations[migration_id] = migration
        self.logger.info(f"Created migration {migration_id}: {migration_name}")
        
        return migration_id
    
    def validate_migration(self, migration: Migration) -> ValidationResult:
        """
        Validate a migration.
        
        Args:
            migration: Migration to validate
            
        Returns:
            ValidationResult: Validation result
        """
        errors = migration.validate()
        warnings = []
        missing_dependencies = []
        
        # Check dependencies
        for dep_id in migration.dependencies:
            if dep_id not in self._migrations:
                missing_dependencies.append(dep_id)
                errors.append(f"Missing dependency: {dep_id}")
        
        # Check for potential issues
        if not migration.down_operations:
            warnings.append("Migration has no down operations - rollback will not be possible")
        
        # Validate checksum integrity
        expected_checksum = migration._calculate_checksum()
        if migration.checksum != expected_checksum:
            errors.append("Migration checksum mismatch - migration may be corrupted")
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            dependencies_satisfied=len(missing_dependencies) == 0,
            missing_dependencies=missing_dependencies
        )
    
    def backup_before_migration(self) -> BackupResult:
        """
        Create backup before migration.
        
        Returns:
            BackupResult: Backup operation result
        """
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = f"backups/pre_migration_{timestamp}.backup"
            
            # Ensure backup directory exists
            os.makedirs(os.path.dirname(backup_path), exist_ok=True)
            
            # Use database manager's backup functionality
            db_backup_result = self.database_manager.backup_database(backup_path)
            
            if db_backup_result.success:
                return BackupResult(
                    success=True,
                    backup_path=backup_path,
                    backup_size=db_backup_result.backup_size
                )
            else:
                return BackupResult(
                    success=False,
                    backup_path=backup_path,
                    error_message=db_backup_result.error_message
                )
                
        except Exception as e:
            return BackupResult(
                success=False,
                backup_path="",
                error_message=str(e)
            )
    
    def get_migration_history(self) -> List[MigrationRecord]:
        """
        Get migration history.
        
        Returns:
            List[MigrationRecord]: Migration history
        """
        return self._migration_history.copy()
    
    def repair_migration_state(self) -> RepairResult:
        """
        Repair migration state inconsistencies.
        
        Returns:
            RepairResult: Repair operation result
        """
        try:
            issues_found = []
            repairs_applied = []
            
            # Check for orphaned migration records
            for record in self._migration_history:
                if record.migration_id not in self._migrations:
                    issues_found.append(f"Orphaned migration record: {record.migration_id}")
            
            # Check for missing migration records
            applied_ids = {record.migration_id for record in self._migration_history}
            for migration_id, migration in self._migrations.items():
                if migration_id not in applied_ids and migration.applied_at:
                    issues_found.append(f"Missing migration record: {migration_id}")
                    
                    # Create missing record
                    record = MigrationRecord(
                        migration_id=migration_id,
                        name=migration.name,
                        version=migration.version,
                        checksum=migration.checksum,
                        applied_at=migration.applied_at
                    )
                    self._migration_history.append(record)
                    repairs_applied.append(f"Created missing record for {migration_id}")
            
            # Verify checksums
            for record in self._migration_history:
                migration = self._migrations.get(record.migration_id)
                if migration and migration.checksum != record.checksum:
                    issues_found.append(f"Checksum mismatch for migration {record.migration_id}")
            
            return RepairResult(
                success=True,
                issues_found=issues_found,
                repairs_applied=repairs_applied
            )
            
        except Exception as e:
            return RepairResult(
                success=False,
                error_message=str(e)
            )
    
    def _ensure_migrations_table(self):
        """Ensure migration tracking table exists."""
        try:
            # Get current database type
            db_type = self.database_manager.get_current_database_type()
            
            if db_type == DatabaseType.POSTGRESQL:
                create_table_sql = f"""
                CREATE TABLE IF NOT EXISTS {self._migrations_table} (
                    migration_id VARCHAR(36) PRIMARY KEY,
                    name VARCHAR(255) NOT NULL,
                    version VARCHAR(50) NOT NULL,
                    checksum VARCHAR(64) NOT NULL,
                    applied_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    rollback_at TIMESTAMP NULL,
                    execution_time FLOAT DEFAULT 0.0,
                    status VARCHAR(20) DEFAULT 'applied',
                    error_message TEXT NULL
                )
                """
            else:  # SQLite
                create_table_sql = f"""
                CREATE TABLE IF NOT EXISTS {self._migrations_table} (
                    migration_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    version TEXT NOT NULL,
                    checksum TEXT NOT NULL,
                    applied_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    rollback_at DATETIME NULL,
                    execution_time REAL DEFAULT 0.0,
                    status TEXT DEFAULT 'applied',
                    error_message TEXT NULL
                )
                """
            
            result = self.database_manager.execute_query(create_table_sql)
            if not result.success:
                raise DatabaseError(f"Failed to create migrations table: {result.error_message}")
                
        except Exception as e:
            self.logger.error(f"Failed to ensure migrations table: {e}")
            raise
    
    def _load_migration_history(self):
        """Load migration history from database."""
        try:
            query = f"SELECT * FROM {self._migrations_table} ORDER BY applied_at"
            result = self.database_manager.execute_query(query)
            
            if result.success:
                self._migration_history = []
                for row in result.data:
                    record = MigrationRecord(
                        migration_id=row['migration_id'],
                        name=row['name'],
                        version=row['version'],
                        checksum=row['checksum'],
                        applied_at=row['applied_at'],
                        rollback_at=row.get('rollback_at'),
                        execution_time=row.get('execution_time', 0.0),
                        status=row.get('status', 'applied'),
                        error_message=row.get('error_message')
                    )
                    self._migration_history.append(record)
                
                # Update current version from latest applied migration
                if self._migration_history:
                    latest_applied = max(
                        (r for r in self._migration_history if r.status == 'applied'),
                        key=lambda r: self._version_to_tuple(r.version),
                        default=None
                    )
                    if latest_applied:
                        self._current_version = latest_applied.version
                        
        except Exception as e:
            self.logger.warning(f"Failed to load migration history: {e}")
            self._migration_history = []
    
    def _apply_migration(self, migration: Migration) -> MigrationResult:
        """Apply a single migration."""
        start_time = datetime.now()
        operations_executed = 0
        
        try:
            # Execute up operations in a transaction
            db_operations = []
            for operation in migration.up_operations:
                if operation.query:
                    # For operations with direct queries, execute them individually
                    result = self.database_manager.execute_query(operation.query, operation.parameters)
                    if not result.success:
                        execution_time = (datetime.now() - start_time).total_seconds()
                        return MigrationResult(
                            success=False,
                            migration_id=migration.id,
                            operations_executed=operations_executed,
                            execution_time=execution_time,
                            error_message=result.error_message
                        )
                else:
                    # For operations without direct queries, add to transaction
                    db_operations.append(operation)
                
                operations_executed += 1
            
            # Execute any remaining operations in a transaction
            if db_operations:
                transaction_result = self.database_manager.execute_transaction(db_operations)
                if not transaction_result.success:
                    execution_time = (datetime.now() - start_time).total_seconds()
                    return MigrationResult(
                        success=False,
                        migration_id=migration.id,
                        operations_executed=operations_executed,
                        execution_time=execution_time,
                        error_message=transaction_result.error_message
                    )
            
            # Record migration as applied
            self._record_migration_applied(migration, start_time)
            
            # Update current version
            if self._compare_versions(migration.version, self._current_version) > 0:
                self._current_version = migration.version
            
            execution_time = (datetime.now() - start_time).total_seconds()
            
            return MigrationResult(
                success=True,
                migration_id=migration.id,
                operations_executed=operations_executed,
                execution_time=execution_time
            )
                
        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            return MigrationResult(
                success=False,
                migration_id=migration.id,
                operations_executed=operations_executed,
                execution_time=execution_time,
                error_message=str(e)
            )
    
    def _record_migration_applied(self, migration: Migration, start_time: datetime):
        """Record migration as applied in database."""
        execution_time = (datetime.now() - start_time).total_seconds()
        
        # Use appropriate parameter syntax based on database type
        db_type = self.database_manager.get_current_database_type()
        
        if db_type == DatabaseType.POSTGRESQL:
            insert_query = f"""
            INSERT INTO {self._migrations_table} 
            (migration_id, name, version, checksum, applied_at, execution_time, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """
        else:  # SQLite
            insert_query = f"""
            INSERT INTO {self._migrations_table} 
            (migration_id, name, version, checksum, applied_at, execution_time, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """
        
        params = [
            migration.id,
            migration.name,
            migration.version,
            migration.checksum,
            datetime.now().isoformat(),
            execution_time,
            'applied'
        ]
        
        result = self.database_manager.execute_query(insert_query, params)
        if result.success:
            # Add to local history
            record = MigrationRecord(
                migration_id=migration.id,
                name=migration.name,
                version=migration.version,
                checksum=migration.checksum,
                applied_at=datetime.now(),
                execution_time=execution_time,
                status='applied'
            )
            self._migration_history.append(record)
            self.logger.info(f"Recorded migration {migration.id} as applied")
        else:
            self.logger.error(f"Failed to record migration {migration.id}: {result.error_message}")
            raise DatabaseError(f"Failed to record migration: {result.error_message}")
    
    def _update_migration_record(self, migration_id: str, status: str):
        """Update migration record status."""
        db_type = self.database_manager.get_current_database_type()
        
        if db_type == DatabaseType.POSTGRESQL:
            update_query = f"""
            UPDATE {self._migrations_table} 
            SET status = %s, rollback_at = %s
            WHERE migration_id = %s
            """
        else:  # SQLite
            update_query = f"""
            UPDATE {self._migrations_table} 
            SET status = ?, rollback_at = ?
            WHERE migration_id = ?
            """
        
        params = [
            status,
            datetime.now().isoformat() if status == 'rolled_back' else None,
            migration_id
        ]
        
        result = self.database_manager.execute_query(update_query, params)
        if result.success:
            # Update local history
            for record in self._migration_history:
                if record.migration_id == migration_id:
                    record.status = status
                    if status == 'rolled_back':
                        record.rollback_at = datetime.now()
                    break
            self.logger.info(f"Updated migration {migration_id} status to {status}")
        else:
            self.logger.error(f"Failed to update migration {migration_id}: {result.error_message}")
            raise DatabaseError(f"Failed to update migration record: {result.error_message}")
    
    def _set_current_version(self, version: str):
        """Set current database version."""
        self._current_version = version
    
    def _generate_next_version(self) -> str:
        """Generate next version number."""
        # Simple version increment (major.minor.patch)
        parts = self._current_version.split('.')
        if len(parts) != 3:
            return "1.0.1"
        
        try:
            major, minor, patch = map(int, parts)
            return f"{major}.{minor}.{patch + 1}"
        except ValueError:
            return "1.0.1"
    
    def _compare_versions(self, version1: str, version2: str) -> int:
        """Compare two version strings. Returns -1, 0, or 1."""
        v1_tuple = self._version_to_tuple(version1)
        v2_tuple = self._version_to_tuple(version2)
        
        if v1_tuple < v2_tuple:
            return -1
        elif v1_tuple > v2_tuple:
            return 1
        else:
            return 0
    
    def _version_to_tuple(self, version: str) -> Tuple[int, int, int]:
        """Convert version string to tuple for comparison."""
        try:
            parts = version.split('.')
            if len(parts) >= 3:
                return (int(parts[0]), int(parts[1]), int(parts[2]))
            elif len(parts) == 2:
                return (int(parts[0]), int(parts[1]), 0)
            elif len(parts) == 1:
                return (int(parts[0]), 0, 0)
            else:
                return (0, 0, 0)
        except ValueError:
            return (0, 0, 0)
    
    def _build_operation_query(self, operation: DatabaseOperation) -> str:
        """Build SQL query from operation."""
        if operation.operation_type == "create_table":
            return operation.query  # Table creation queries are provided directly
        elif operation.operation_type == "insert":
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
    
    def _get_core_schema(self, database_type: DatabaseType) -> Dict[str, str]:
        """Get core database schema for the specified database type."""
        if database_type == DatabaseType.POSTGRESQL:
            return self._get_postgresql_core_schema()
        else:
            return self._get_sqlite_core_schema()
    
    def _get_postgresql_core_schema(self) -> Dict[str, str]:
        """Get PostgreSQL core schema definitions."""
        return {
            "tenants": """
                CREATE TABLE IF NOT EXISTS tenants (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    name VARCHAR(255) NOT NULL,
                    domain VARCHAR(255) UNIQUE NOT NULL,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    status VARCHAR(20) NOT NULL DEFAULT 'active',
                    configuration JSONB DEFAULT '{}',
                    resource_limits JSONB DEFAULT '{}',
                    billing_info JSONB DEFAULT '{}'
                )
            """,
            
            "users": """
                CREATE TABLE IF NOT EXISTS users (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
                    username VARCHAR(255) NOT NULL,
                    email VARCHAR(255) NOT NULL,
                    password_hash VARCHAR(255) NOT NULL,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    last_login TIMESTAMP NULL,
                    status VARCHAR(20) NOT NULL DEFAULT 'active',
                    profile JSONB DEFAULT '{}',
                    preferences JSONB DEFAULT '{}',
                    UNIQUE(tenant_id, username),
                    UNIQUE(tenant_id, email)
                )
            """,
            
            "roles": """
                CREATE TABLE IF NOT EXISTS roles (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
                    name VARCHAR(255) NOT NULL,
                    description TEXT,
                    permissions JSONB DEFAULT '[]',
                    parent_role_id UUID NULL REFERENCES roles(id) ON DELETE SET NULL,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(tenant_id, name)
                )
            """,
            
            "user_roles": """
                CREATE TABLE IF NOT EXISTS user_roles (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    role_id UUID NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
                    assigned_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    expires_at TIMESTAMP NULL,
                    assigned_by UUID NULL REFERENCES users(id) ON DELETE SET NULL,
                    UNIQUE(user_id, role_id)
                )
            """,
            
            "audit_logs": """
                CREATE TABLE IF NOT EXISTS audit_logs (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
                    user_id UUID NULL REFERENCES users(id) ON DELETE SET NULL,
                    action VARCHAR(255) NOT NULL,
                    resource_type VARCHAR(255) NOT NULL,
                    resource_id VARCHAR(255) NULL,
                    timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    ip_address INET NULL,
                    user_agent TEXT NULL,
                    details JSONB DEFAULT '{}',
                    signature VARCHAR(255) NOT NULL
                )
            """,
            
            "visual_models": """
                CREATE TABLE IF NOT EXISTS visual_models (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
                    owner_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    name VARCHAR(255) NOT NULL,
                    description TEXT,
                    model_data JSONB NOT NULL DEFAULT '{}',
                    version INTEGER NOT NULL DEFAULT 1,
                    parent_version_id UUID NULL REFERENCES visual_models(id) ON DELETE SET NULL,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    status VARCHAR(20) NOT NULL DEFAULT 'draft',
                    tags TEXT[] DEFAULT '{}',
                    metadata JSONB DEFAULT '{}'
                )
            """,
            
            "execution_records": """
                CREATE TABLE IF NOT EXISTS execution_records (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
                    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    model_id UUID NOT NULL REFERENCES visual_models(id) ON DELETE CASCADE,
                    execution_data JSONB NOT NULL DEFAULT '{}',
                    start_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    end_time TIMESTAMP NULL,
                    status VARCHAR(20) NOT NULL DEFAULT 'running',
                    output TEXT,
                    error_message TEXT NULL,
                    performance_metrics JSONB DEFAULT '{}'
                )
            """,
            
            "custom_components": """
                CREATE TABLE IF NOT EXISTS custom_components (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
                    creator_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    name VARCHAR(255) NOT NULL,
                    description TEXT,
                    component_data JSONB NOT NULL DEFAULT '{}',
                    category VARCHAR(255) NOT NULL,
                    tags TEXT[] DEFAULT '{}',
                    usage_count INTEGER DEFAULT 0,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    is_shared BOOLEAN DEFAULT FALSE
                )
            """
        }
    
    def _get_sqlite_core_schema(self) -> Dict[str, str]:
        """Get SQLite core schema definitions."""
        return {
            "tenants": """
                CREATE TABLE IF NOT EXISTS tenants (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    domain TEXT UNIQUE NOT NULL,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    status TEXT NOT NULL DEFAULT 'active',
                    configuration TEXT DEFAULT '{}',
                    resource_limits TEXT DEFAULT '{}',
                    billing_info TEXT DEFAULT '{}'
                )
            """,
            
            "users": """
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
                    username TEXT NOT NULL,
                    email TEXT NOT NULL,
                    password_hash TEXT NOT NULL,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    last_login DATETIME NULL,
                    status TEXT NOT NULL DEFAULT 'active',
                    profile TEXT DEFAULT '{}',
                    preferences TEXT DEFAULT '{}',
                    UNIQUE(tenant_id, username),
                    UNIQUE(tenant_id, email)
                )
            """,
            
            "roles": """
                CREATE TABLE IF NOT EXISTS roles (
                    id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
                    name TEXT NOT NULL,
                    description TEXT,
                    permissions TEXT DEFAULT '[]',
                    parent_role_id TEXT NULL REFERENCES roles(id) ON DELETE SET NULL,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(tenant_id, name)
                )
            """,
            
            "user_roles": """
                CREATE TABLE IF NOT EXISTS user_roles (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    role_id TEXT NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
                    assigned_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    expires_at DATETIME NULL,
                    assigned_by TEXT NULL REFERENCES users(id) ON DELETE SET NULL,
                    UNIQUE(user_id, role_id)
                )
            """,
            
            "audit_logs": """
                CREATE TABLE IF NOT EXISTS audit_logs (
                    id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
                    user_id TEXT NULL REFERENCES users(id) ON DELETE SET NULL,
                    action TEXT NOT NULL,
                    resource_type TEXT NOT NULL,
                    resource_id TEXT NULL,
                    timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    ip_address TEXT NULL,
                    user_agent TEXT NULL,
                    details TEXT DEFAULT '{}',
                    signature TEXT NOT NULL
                )
            """,
            
            "visual_models": """
                CREATE TABLE IF NOT EXISTS visual_models (
                    id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
                    owner_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    name TEXT NOT NULL,
                    description TEXT,
                    model_data TEXT NOT NULL DEFAULT '{}',
                    version INTEGER NOT NULL DEFAULT 1,
                    parent_version_id TEXT NULL REFERENCES visual_models(id) ON DELETE SET NULL,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    status TEXT NOT NULL DEFAULT 'draft',
                    tags TEXT DEFAULT '',
                    metadata TEXT DEFAULT '{}'
                )
            """,
            
            "execution_records": """
                CREATE TABLE IF NOT EXISTS execution_records (
                    id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
                    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    model_id TEXT NOT NULL REFERENCES visual_models(id) ON DELETE CASCADE,
                    execution_data TEXT NOT NULL DEFAULT '{}',
                    start_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    end_time DATETIME NULL,
                    status TEXT NOT NULL DEFAULT 'running',
                    output TEXT,
                    error_message TEXT NULL,
                    performance_metrics TEXT DEFAULT '{}'
                )
            """,
            
            "custom_components": """
                CREATE TABLE IF NOT EXISTS custom_components (
                    id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
                    creator_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    name TEXT NOT NULL,
                    description TEXT,
                    component_data TEXT NOT NULL DEFAULT '{}',
                    category TEXT NOT NULL,
                    tags TEXT DEFAULT '',
                    usage_count INTEGER DEFAULT 0,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    is_shared INTEGER DEFAULT 0
                )
            """
        }