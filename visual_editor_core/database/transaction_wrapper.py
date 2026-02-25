"""
Transaction wrapper providing transaction-aware database operations.
"""

import logging
import time
import uuid
from contextlib import contextmanager
from typing import Any, Dict, List, Optional, Union, Callable
from datetime import datetime

from .models import DatabaseOperation, QueryResult, TransactionResult
from .transaction_manager import TransactionManager, TransactionContext, IsolationLevel
from .transaction_models import (
    TransactionConfig,
    TransactionType,
    TransactionPriority,
    TransactionBatch,
    TransactionStatistics
)
from .exceptions import TransactionError, DatabaseError


class TransactionWrapper:
    """
    High-level wrapper for transaction-aware database operations.
    
    This class provides convenient methods for executing database operations
    within transactions, with automatic rollback, retry logic, and performance monitoring.
    """
    
    def __init__(self, database_manager, transaction_manager: Optional[TransactionManager] = None):
        self.database_manager = database_manager
        self.transaction_manager = transaction_manager or TransactionManager(database_manager)
        self.logger = logging.getLogger(__name__)
        
        # Default configuration
        self.default_config = TransactionConfig()
    
    @contextmanager
    def auto_transaction(self,
                        config: Optional[TransactionConfig] = None,
                        tenant_id: Optional[str] = None):
        """
        Context manager for automatic transaction management.
        
        Args:
            config: Transaction configuration
            tenant_id: Tenant ID for multi-tenant support
        """
        config = config or self.default_config
        
        isolation_level = IsolationLevel.READ_COMMITTED
        if config.isolation_level == "READ_UNCOMMITTED":
            isolation_level = IsolationLevel.READ_UNCOMMITTED
        elif config.isolation_level == "REPEATABLE_READ":
            isolation_level = IsolationLevel.REPEATABLE_READ
        elif config.isolation_level == "SERIALIZABLE":
            isolation_level = IsolationLevel.SERIALIZABLE
        
        with self.transaction_manager.transaction(
            isolation_level=isolation_level,
            timeout=config.timeout,
            readonly=config.readonly,
            tenant_id=tenant_id
        ) as context:
            yield TransactionOperations(context, self.database_manager, config)
    
    def execute_batch(self,
                     batch: TransactionBatch,
                     tenant_id: Optional[str] = None) -> TransactionResult:
        """
        Execute a batch of operations in a single transaction.
        
        Args:
            batch: Transaction batch to execute
            tenant_id: Tenant ID for multi-tenant support
            
        Returns:
            TransactionResult: Result of the batch execution
        """
        # Validate batch
        validation_errors = batch.validate()
        if validation_errors:
            return TransactionResult(
                success=False,
                transaction_id=batch.batch_id,
                operations_count=len(batch.operations),
                error_message=f"Batch validation failed: {'; '.join(validation_errors)}"
            )
        
        start_time = time.time()
        
        try:
            with self.auto_transaction(batch.config, tenant_id) as tx_ops:
                # Execute all operations
                for operation in batch.operations:
                    tx_ops.add_operation(operation)
                
                # Transaction will auto-commit when context exits
                execution_time = time.time() - start_time
                
                return TransactionResult(
                    success=True,
                    transaction_id=batch.batch_id,
                    operations_count=len(batch.operations),
                    execution_time=execution_time
                )
        
        except Exception as e:
            execution_time = time.time() - start_time
            return TransactionResult(
                success=False,
                transaction_id=batch.batch_id,
                operations_count=len(batch.operations),
                rollback_performed=True,
                error_message=str(e),
                execution_time=execution_time
            )
    
    def execute_with_savepoints(self,
                               operations: List[DatabaseOperation],
                               savepoint_names: Optional[List[str]] = None,
                               config: Optional[TransactionConfig] = None,
                               tenant_id: Optional[str] = None) -> TransactionResult:
        """
        Execute operations with savepoints for granular rollback control.
        
        Args:
            operations: List of database operations
            savepoint_names: Optional names for savepoints (one per operation)
            config: Transaction configuration
            tenant_id: Tenant ID for multi-tenant support
            
        Returns:
            TransactionResult: Result of the execution
        """
        config = config or self.default_config
        transaction_id = str(uuid.uuid4())
        start_time = time.time()
        
        if savepoint_names and len(savepoint_names) != len(operations):
            return TransactionResult(
                success=False,
                transaction_id=transaction_id,
                operations_count=len(operations),
                error_message="Number of savepoint names must match number of operations"
            )
        
        try:
            with self.auto_transaction(config, tenant_id) as tx_ops:
                for i, operation in enumerate(operations):
                    savepoint_name = savepoint_names[i] if savepoint_names else f"op_{i}"
                    
                    # Create savepoint before operation
                    with tx_ops.savepoint(savepoint_name):
                        tx_ops.add_operation(operation)
                
                execution_time = time.time() - start_time
                
                return TransactionResult(
                    success=True,
                    transaction_id=transaction_id,
                    operations_count=len(operations),
                    execution_time=execution_time
                )
        
        except Exception as e:
            execution_time = time.time() - start_time
            return TransactionResult(
                success=False,
                transaction_id=transaction_id,
                operations_count=len(operations),
                rollback_performed=True,
                error_message=str(e),
                execution_time=execution_time
            )
    
    def execute_with_retry(self,
                          operation_func: Callable,
                          config: Optional[TransactionConfig] = None,
                          tenant_id: Optional[str] = None) -> Any:
        """
        Execute a function with automatic retry on transient failures.
        
        Args:
            operation_func: Function to execute (should accept TransactionOperations)
            config: Transaction configuration
            tenant_id: Tenant ID for multi-tenant support
            
        Returns:
            Result of the operation function
        """
        config = config or self.default_config
        
        def retry_operation():
            with self.auto_transaction(config, tenant_id) as tx_ops:
                return operation_func(tx_ops)
        
        return self.transaction_manager.execute_with_retry(
            retry_operation,
            max_retries=config.max_retry_attempts,
            retry_delay=config.retry_delay
        )
    
    def bulk_insert(self,
                   table: str,
                   records: List[Dict[str, Any]],
                   batch_size: int = 1000,
                   config: Optional[TransactionConfig] = None,
                   tenant_id: Optional[str] = None) -> TransactionResult:
        """
        Perform bulk insert with batching and transaction management.
        
        Args:
            table: Table name
            records: List of records to insert
            batch_size: Number of records per batch
            config: Transaction configuration
            tenant_id: Tenant ID for multi-tenant support
            
        Returns:
            TransactionResult: Result of the bulk insert
        """
        config = config or self.default_config
        config.transaction_type = TransactionType.BULK_OPERATION
        config.batch_size = batch_size
        
        transaction_id = str(uuid.uuid4())
        start_time = time.time()
        total_inserted = 0
        
        try:
            # Process records in batches
            for i in range(0, len(records), batch_size):
                batch_records = records[i:i + batch_size]
                
                with self.auto_transaction(config, tenant_id) as tx_ops:
                    for record in batch_records:
                        operation = DatabaseOperation(
                            operation_type="insert",
                            table=table,
                            data=record
                        )
                        tx_ops.add_operation(operation)
                    
                    total_inserted += len(batch_records)
                    self.logger.debug(f"Inserted batch of {len(batch_records)} records")
            
            execution_time = time.time() - start_time
            
            return TransactionResult(
                success=True,
                transaction_id=transaction_id,
                operations_count=total_inserted,
                execution_time=execution_time
            )
        
        except Exception as e:
            execution_time = time.time() - start_time
            return TransactionResult(
                success=False,
                transaction_id=transaction_id,
                operations_count=total_inserted,
                rollback_performed=True,
                error_message=str(e),
                execution_time=execution_time
            )
    
    def bulk_update(self,
                   table: str,
                   updates: List[Dict[str, Any]],
                   condition_columns: List[str],
                   batch_size: int = 1000,
                   config: Optional[TransactionConfig] = None,
                   tenant_id: Optional[str] = None) -> TransactionResult:
        """
        Perform bulk update with batching and transaction management.
        
        Args:
            table: Table name
            updates: List of update records
            condition_columns: Columns to use for WHERE conditions
            batch_size: Number of records per batch
            config: Transaction configuration
            tenant_id: Tenant ID for multi-tenant support
            
        Returns:
            TransactionResult: Result of the bulk update
        """
        config = config or self.default_config
        config.transaction_type = TransactionType.BULK_OPERATION
        config.batch_size = batch_size
        
        transaction_id = str(uuid.uuid4())
        start_time = time.time()
        total_updated = 0
        
        try:
            # Process updates in batches
            for i in range(0, len(updates), batch_size):
                batch_updates = updates[i:i + batch_size]
                
                with self.auto_transaction(config, tenant_id) as tx_ops:
                    for update_record in batch_updates:
                        # Split record into data and conditions
                        conditions = {col: update_record[col] for col in condition_columns if col in update_record}
                        data = {k: v for k, v in update_record.items() if k not in condition_columns}
                        
                        operation = DatabaseOperation(
                            operation_type="update",
                            table=table,
                            data=data,
                            conditions=conditions
                        )
                        tx_ops.add_operation(operation)
                    
                    total_updated += len(batch_updates)
                    self.logger.debug(f"Updated batch of {len(batch_updates)} records")
            
            execution_time = time.time() - start_time
            
            return TransactionResult(
                success=True,
                transaction_id=transaction_id,
                operations_count=total_updated,
                execution_time=execution_time
            )
        
        except Exception as e:
            execution_time = time.time() - start_time
            return TransactionResult(
                success=False,
                transaction_id=transaction_id,
                operations_count=total_updated,
                rollback_performed=True,
                error_message=str(e),
                execution_time=execution_time
            )
    
    def execute_read_only(self,
                         query: str,
                         params: Optional[Dict[str, Any]] = None,
                         tenant_id: Optional[str] = None) -> QueryResult:
        """
        Execute a read-only query with optimized transaction settings.
        
        Args:
            query: SQL query to execute
            params: Query parameters
            tenant_id: Tenant ID for multi-tenant support
            
        Returns:
            QueryResult: Query result
        """
        config = TransactionConfig(
            readonly=True,
            isolation_level="READ_COMMITTED",
            timeout=60  # Shorter timeout for read operations
        )
        
        try:
            with self.auto_transaction(config, tenant_id) as tx_ops:
                return tx_ops.execute_query(query, params)
        
        except Exception as e:
            return QueryResult(
                success=False,
                error_message=str(e)
            )
    
    def get_transaction_statistics(self) -> Dict[str, Any]:
        """Get comprehensive transaction statistics."""
        return self.transaction_manager.get_transaction_metrics()
    
    def get_active_transactions(self) -> List[Dict[str, Any]]:
        """Get information about currently active transactions."""
        return self.transaction_manager.get_active_transactions()


class TransactionOperations:
    """
    Operations available within a transaction context.
    """
    
    def __init__(self, context: TransactionContext, database_manager, config: TransactionConfig):
        self.context = context
        self.database_manager = database_manager
        self.config = config
        self.logger = logging.getLogger(__name__)
    
    def add_operation(self, operation: DatabaseOperation):
        """Add an operation to the current transaction."""
        self.context.add_operation(operation)
    
    def execute_query(self, query: str, params: Optional[Dict[str, Any]] = None) -> QueryResult:
        """Execute a query within the current transaction."""
        try:
            result = self.database_manager.execute_query(query, params)
            
            # Track the operation
            operation = DatabaseOperation(
                operation_type="select" if query.strip().upper().startswith("SELECT") else "other",
                table="unknown",
                query=query,
                parameters=params or {}
            )
            self.add_operation(operation)
            
            return result
        
        except Exception as e:
            self.logger.error(f"Query execution failed in transaction {self.context.transaction_id}: {e}")
            raise
    
    def insert(self, table: str, data: Dict[str, Any]) -> bool:
        """Insert a record within the current transaction."""
        operation = DatabaseOperation(
            operation_type="insert",
            table=table,
            data=data
        )
        self.add_operation(operation)
        return True
    
    def update(self, table: str, data: Dict[str, Any], conditions: Dict[str, Any]) -> bool:
        """Update records within the current transaction."""
        operation = DatabaseOperation(
            operation_type="update",
            table=table,
            data=data,
            conditions=conditions
        )
        self.add_operation(operation)
        return True
    
    def delete(self, table: str, conditions: Dict[str, Any]) -> bool:
        """Delete records within the current transaction."""
        operation = DatabaseOperation(
            operation_type="delete",
            table=table,
            conditions=conditions
        )
        self.add_operation(operation)
        return True
    
    @contextmanager
    def savepoint(self, name: str):
        """Create a savepoint within the current transaction."""
        savepoint_id = self.context.create_savepoint(name)
        
        try:
            yield savepoint_id
        except Exception as e:
            # Rollback to savepoint on error
            self.context.rollback_to_savepoint(savepoint_id)
            self.logger.info(f"Rolled back to savepoint {name} due to error: {e}")
            raise
    
    def add_callback(self, event: str, callback: Callable):
        """Add a callback for transaction events."""
        self.context.add_callback(event, callback)
    
    def get_statistics(self) -> TransactionStatistics:
        """Get statistics for the current transaction."""
        return TransactionStatistics(
            transaction_id=self.context.transaction_id,
            start_time=self.context.start_time,
            operations_executed=len(self.context.operations),
            savepoint_count=len(self.context.savepoints),
            success=self.context.state.value == "active"
        )