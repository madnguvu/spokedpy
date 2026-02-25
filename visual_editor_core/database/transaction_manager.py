"""
Transaction Management System for Visual Editor Core Database Layer.

This module provides comprehensive transaction management with:
- Automatic rollback on failures
- Nested transaction support (savepoints)
- Transaction performance monitoring
- Deadlock detection and handling
- Transaction-aware database operations
"""

import logging
import threading
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Callable, Union
from enum import Enum

from .models import (
    DatabaseConnection,
    DatabaseOperation,
    TransactionResult,
    DatabaseType
)
from .exceptions import (
    TransactionError,
    DatabaseError,
    ValidationError
)


class TransactionState(Enum):
    """Transaction state enumeration."""
    ACTIVE = "active"
    COMMITTED = "committed"
    ROLLED_BACK = "rolled_back"
    FAILED = "failed"
    PREPARING = "preparing"
    PREPARED = "prepared"


class IsolationLevel(Enum):
    """Transaction isolation levels."""
    READ_UNCOMMITTED = "read_uncommitted"
    READ_COMMITTED = "read_committed"
    REPEATABLE_READ = "repeatable_read"
    SERIALIZABLE = "serializable"


@dataclass
class SavepointInfo:
    """Information about a transaction savepoint."""
    savepoint_id: str
    name: str
    created_at: datetime
    operations_count: int
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TransactionMetrics:
    """Transaction performance metrics."""
    transaction_id: str
    start_time: datetime
    end_time: Optional[datetime] = None
    duration: Optional[float] = None
    operations_count: int = 0
    rollback_count: int = 0
    savepoint_count: int = 0
    deadlock_count: int = 0
    retry_count: int = 0
    isolation_level: Optional[IsolationLevel] = None
    connection_id: str = ""
    database_type: Optional[DatabaseType] = None
    success: bool = False
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DeadlockInfo:
    """Information about a detected deadlock."""
    deadlock_id: str
    detected_at: datetime
    transaction_ids: List[str]
    victim_transaction_id: str
    resolution_strategy: str
    resolution_time: float
    metadata: Dict[str, Any] = field(default_factory=dict)


class TransactionContext:
    """Context for managing a database transaction."""
    
    def __init__(self, 
                 transaction_id: str,
                 connection: DatabaseConnection,
                 isolation_level: IsolationLevel = IsolationLevel.READ_COMMITTED,
                 timeout: Optional[int] = None,
                 readonly: bool = False):
        self.transaction_id = transaction_id
        self.connection = connection
        self.isolation_level = isolation_level
        self.timeout = timeout
        self.readonly = readonly
        self.state = TransactionState.ACTIVE
        self.start_time = datetime.now()
        self.end_time: Optional[datetime] = None
        self.operations: List[DatabaseOperation] = []
        self.savepoints: Dict[str, SavepointInfo] = {}
        self.parent_transaction: Optional['TransactionContext'] = None
        self.child_transactions: List['TransactionContext'] = []
        self.metrics = TransactionMetrics(
            transaction_id=transaction_id,
            start_time=self.start_time,
            connection_id=connection.connection_id,
            database_type=connection.database_type,
            isolation_level=isolation_level
        )
        self.lock = threading.RLock()
        self.callbacks: Dict[str, List[Callable]] = {
            'before_commit': [],
            'after_commit': [],
            'before_rollback': [],
            'after_rollback': []
        }
    
    def add_operation(self, operation: DatabaseOperation):
        """Add an operation to the transaction."""
        with self.lock:
            if self.state != TransactionState.ACTIVE:
                raise TransactionError(f"Cannot add operation to {self.state.value} transaction")
            
            self.operations.append(operation)
            self.metrics.operations_count += 1
    
    def create_savepoint(self, name: str) -> str:
        """Create a savepoint within the transaction."""
        with self.lock:
            if self.state != TransactionState.ACTIVE:
                raise TransactionError(f"Cannot create savepoint in {self.state.value} transaction")
            
            savepoint_id = f"sp_{uuid.uuid4().hex[:8]}"
            savepoint = SavepointInfo(
                savepoint_id=savepoint_id,
                name=name,
                created_at=datetime.now(),
                operations_count=len(self.operations)
            )
            
            self.savepoints[savepoint_id] = savepoint
            self.metrics.savepoint_count += 1
            
            return savepoint_id
    
    def rollback_to_savepoint(self, savepoint_id: str):
        """Rollback to a specific savepoint."""
        with self.lock:
            if savepoint_id not in self.savepoints:
                raise TransactionError(f"Savepoint {savepoint_id} not found")
            
            savepoint = self.savepoints[savepoint_id]
            
            # Remove operations after the savepoint
            self.operations = self.operations[:savepoint.operations_count]
            
            # Remove savepoints created after this one
            savepoints_to_remove = [
                sp_id for sp_id, sp in self.savepoints.items()
                if sp.created_at > savepoint.created_at
            ]
            
            for sp_id in savepoints_to_remove:
                del self.savepoints[sp_id]
            
            self.metrics.rollback_count += 1
    
    def add_callback(self, event: str, callback: Callable):
        """Add a callback for transaction events."""
        if event in self.callbacks:
            self.callbacks[event].append(callback)
    
    def execute_callbacks(self, event: str):
        """Execute callbacks for a specific event."""
        for callback in self.callbacks.get(event, []):
            try:
                callback(self)
            except Exception as e:
                logging.warning(f"Transaction callback failed: {e}")
    
    def is_expired(self) -> bool:
        """Check if transaction has expired."""
        if not self.timeout:
            return False
        
        elapsed = (datetime.now() - self.start_time).total_seconds()
        return elapsed > self.timeout
    
    def get_duration(self) -> float:
        """Get transaction duration in seconds."""
        end_time = self.end_time or datetime.now()
        return (end_time - self.start_time).total_seconds()


class TransactionManager:
    """
    Comprehensive transaction manager with advanced features.
    
    Features:
    - Automatic rollback on failures
    - Nested transaction support with savepoints
    - Transaction performance monitoring
    - Deadlock detection and resolution
    - Transaction timeout handling
    - Connection-aware transaction management
    """
    
    def __init__(self, database_manager=None):
        self.database_manager = database_manager
        self.logger = logging.getLogger(__name__)
        
        # Transaction tracking
        self.active_transactions: Dict[str, TransactionContext] = {}
        self.transaction_history: List[TransactionMetrics] = []
        self.deadlock_history: List[DeadlockInfo] = []
        
        # Thread safety
        self.lock = threading.RLock()
        
        # Configuration
        self.default_timeout = 300  # 5 minutes
        self.deadlock_detection_enabled = True
        self.deadlock_detection_interval = 1.0  # seconds
        self.max_retry_attempts = 3
        self.retry_delay = 0.1  # seconds
        
        # Performance monitoring
        self.performance_metrics = {
            'total_transactions': 0,
            'successful_transactions': 0,
            'failed_transactions': 0,
            'rolled_back_transactions': 0,
            'deadlocks_detected': 0,
            'deadlocks_resolved': 0,
            'average_transaction_time': 0.0,
            'longest_transaction_time': 0.0,
            'total_savepoints_created': 0,
            'total_rollbacks_to_savepoint': 0
        }
        
        # Start background monitoring
        self._monitoring_enabled = True
        self._monitoring_thread = threading.Thread(target=self._monitor_transactions, daemon=True)
        self._monitoring_thread.start()
    
    @contextmanager
    def transaction(self,
                   connection: Optional[DatabaseConnection] = None,
                   isolation_level: IsolationLevel = IsolationLevel.READ_COMMITTED,
                   timeout: Optional[int] = None,
                   readonly: bool = False,
                   tenant_id: Optional[str] = None):
        """
        Context manager for database transactions.
        
        Args:
            connection: Database connection to use
            isolation_level: Transaction isolation level
            timeout: Transaction timeout in seconds
            readonly: Whether transaction is read-only
            tenant_id: Tenant ID for multi-tenant support
        """
        if not connection and self.database_manager:
            connection = self.database_manager.get_connection(tenant_id)
        
        if not connection:
            raise TransactionError("No database connection available")
        
        transaction_id = str(uuid.uuid4())
        timeout = timeout or self.default_timeout
        
        # Create transaction context
        context = TransactionContext(
            transaction_id=transaction_id,
            connection=connection,
            isolation_level=isolation_level,
            timeout=timeout,
            readonly=readonly
        )
        
        with self.lock:
            self.active_transactions[transaction_id] = context
            self.performance_metrics['total_transactions'] += 1
        
        try:
            # Begin transaction
            self._begin_transaction(context)
            
            yield context
            
            # Commit transaction
            self._commit_transaction(context)
            
        except Exception as e:
            # Rollback transaction
            self._rollback_transaction(context, str(e))
            raise
        
        finally:
            # Cleanup
            with self.lock:
                if transaction_id in self.active_transactions:
                    del self.active_transactions[transaction_id]
                
                # Store metrics
                context.end_time = datetime.now()
                context.metrics.end_time = context.end_time
                context.metrics.duration = context.get_duration()
                self.transaction_history.append(context.metrics)
                
                # Update performance metrics
                self._update_performance_metrics(context)
    
    @contextmanager
    def nested_transaction(self,
                          parent_context: TransactionContext,
                          savepoint_name: Optional[str] = None):
        """
        Context manager for nested transactions using savepoints.
        
        Args:
            parent_context: Parent transaction context
            savepoint_name: Optional name for the savepoint
        """
        if parent_context.state != TransactionState.ACTIVE:
            raise TransactionError("Parent transaction is not active")
        
        savepoint_name = savepoint_name or f"nested_{uuid.uuid4().hex[:8]}"
        
        # Create savepoint
        savepoint_id = parent_context.create_savepoint(savepoint_name)
        
        try:
            # Create nested transaction context
            nested_context = TransactionContext(
                transaction_id=f"{parent_context.transaction_id}_nested_{savepoint_id}",
                connection=parent_context.connection,
                isolation_level=parent_context.isolation_level,
                timeout=parent_context.timeout,
                readonly=parent_context.readonly
            )
            
            nested_context.parent_transaction = parent_context
            parent_context.child_transactions.append(nested_context)
            
            yield nested_context
            
            # Merge operations into parent
            parent_context.operations.extend(nested_context.operations)
            
        except Exception as e:
            # Rollback to savepoint
            parent_context.rollback_to_savepoint(savepoint_id)
            self.logger.info(f"Rolled back to savepoint {savepoint_name}: {e}")
            raise
    
    def execute_with_retry(self,
                          operation: Callable,
                          max_retries: Optional[int] = None,
                          retry_delay: Optional[float] = None) -> Any:
        """
        Execute an operation with automatic retry on deadlock.
        
        Args:
            operation: Operation to execute
            max_retries: Maximum number of retry attempts
            retry_delay: Delay between retries in seconds
            
        Returns:
            Result of the operation
        """
        max_retries = max_retries or self.max_retry_attempts
        retry_delay = retry_delay or self.retry_delay
        
        last_exception = None
        
        for attempt in range(max_retries + 1):
            try:
                return operation()
            
            except Exception as e:
                last_exception = e
                
                # Check if this is a deadlock or retryable error
                if self._is_retryable_error(e) and attempt < max_retries:
                    self.logger.warning(f"Retryable error on attempt {attempt + 1}: {e}")
                    time.sleep(retry_delay * (2 ** attempt))  # Exponential backoff
                    continue
                else:
                    break
        
        raise last_exception
    
    def detect_deadlocks(self) -> List[DeadlockInfo]:
        """
        Detect deadlocks among active transactions.
        
        Returns:
            List of detected deadlocks
        """
        deadlocks = []
        
        with self.lock:
            # Simple deadlock detection based on transaction wait times
            # In a production system, you'd implement more sophisticated detection
            current_time = datetime.now()
            long_running_transactions = []
            
            for context in self.active_transactions.values():
                duration = (current_time - context.start_time).total_seconds()
                if duration > 30:  # Transactions running longer than 30 seconds
                    long_running_transactions.append(context)
            
            # If we have multiple long-running transactions, check for potential deadlocks
            if len(long_running_transactions) > 1:
                # This is a simplified deadlock detection
                # Real implementation would analyze lock dependencies
                deadlock_id = str(uuid.uuid4())
                transaction_ids = [ctx.transaction_id for ctx in long_running_transactions]
                victim_id = transaction_ids[0]  # Choose first as victim
                
                deadlock_info = DeadlockInfo(
                    deadlock_id=deadlock_id,
                    detected_at=current_time,
                    transaction_ids=transaction_ids,
                    victim_transaction_id=victim_id,
                    resolution_strategy="abort_victim",
                    resolution_time=0.0
                )
                
                deadlocks.append(deadlock_info)
        
        return deadlocks
    
    def resolve_deadlock(self, deadlock_info: DeadlockInfo) -> bool:
        """
        Resolve a detected deadlock.
        
        Args:
            deadlock_info: Information about the deadlock
            
        Returns:
            True if deadlock was resolved successfully
        """
        try:
            start_time = time.time()
            
            # Abort the victim transaction
            victim_id = deadlock_info.victim_transaction_id
            
            with self.lock:
                if victim_id in self.active_transactions:
                    victim_context = self.active_transactions[victim_id]
                    self._rollback_transaction(victim_context, "Deadlock victim")
                    
                    # Update metrics
                    victim_context.metrics.deadlock_count += 1
                    self.performance_metrics['deadlocks_resolved'] += 1
                    
                    # Record resolution time
                    deadlock_info.resolution_time = time.time() - start_time
                    self.deadlock_history.append(deadlock_info)
                    
                    self.logger.info(f"Resolved deadlock {deadlock_info.deadlock_id} by aborting transaction {victim_id}")
                    return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Failed to resolve deadlock {deadlock_info.deadlock_id}: {e}")
            return False
    
    def get_transaction_metrics(self) -> Dict[str, Any]:
        """
        Get comprehensive transaction metrics.
        
        Returns:
            Dictionary containing transaction metrics
        """
        with self.lock:
            active_count = len(self.active_transactions)
            
            # Calculate average transaction time
            if self.transaction_history:
                total_time = sum(
                    metrics.duration for metrics in self.transaction_history 
                    if metrics.duration is not None
                )
                avg_time = total_time / len(self.transaction_history)
                
                longest_time = max(
                    metrics.duration for metrics in self.transaction_history 
                    if metrics.duration is not None
                )
            else:
                avg_time = 0.0
                longest_time = 0.0
            
            return {
                'active_transactions': active_count,
                'total_transactions': self.performance_metrics['total_transactions'],
                'successful_transactions': self.performance_metrics['successful_transactions'],
                'failed_transactions': self.performance_metrics['failed_transactions'],
                'rolled_back_transactions': self.performance_metrics['rolled_back_transactions'],
                'deadlocks_detected': self.performance_metrics['deadlocks_detected'],
                'deadlocks_resolved': self.performance_metrics['deadlocks_resolved'],
                'average_transaction_time': avg_time,
                'longest_transaction_time': longest_time,
                'total_savepoints_created': self.performance_metrics['total_savepoints_created'],
                'total_rollbacks_to_savepoint': self.performance_metrics['total_rollbacks_to_savepoint'],
                'transaction_history_size': len(self.transaction_history),
                'deadlock_history_size': len(self.deadlock_history)
            }
    
    def get_active_transactions(self) -> List[Dict[str, Any]]:
        """
        Get information about active transactions.
        
        Returns:
            List of active transaction information
        """
        with self.lock:
            active_info = []
            
            for context in self.active_transactions.values():
                info = {
                    'transaction_id': context.transaction_id,
                    'state': context.state.value,
                    'start_time': context.start_time.isoformat(),
                    'duration': context.get_duration(),
                    'operations_count': len(context.operations),
                    'savepoints_count': len(context.savepoints),
                    'isolation_level': context.isolation_level.value,
                    'readonly': context.readonly,
                    'connection_id': context.connection.connection_id,
                    'database_type': context.connection.database_type.value,
                    'is_expired': context.is_expired()
                }
                active_info.append(info)
            
            return active_info
    
    def cleanup_expired_transactions(self) -> int:
        """
        Cleanup expired transactions.
        
        Returns:
            Number of transactions cleaned up
        """
        expired_transactions = []
        
        with self.lock:
            for transaction_id, context in self.active_transactions.items():
                if context.is_expired():
                    expired_transactions.append((transaction_id, context))
        
        # Rollback expired transactions
        cleaned_count = 0
        for transaction_id, context in expired_transactions:
            try:
                self._rollback_transaction(context, "Transaction expired")
                with self.lock:
                    if transaction_id in self.active_transactions:
                        del self.active_transactions[transaction_id]
                cleaned_count += 1
                self.logger.info(f"Cleaned up expired transaction {transaction_id}")
            except Exception as e:
                self.logger.error(f"Failed to cleanup expired transaction {transaction_id}: {e}")
        
        return cleaned_count
    
    def shutdown(self):
        """Shutdown the transaction manager."""
        self._monitoring_enabled = False
        
        # Rollback all active transactions
        with self.lock:
            for context in list(self.active_transactions.values()):
                try:
                    self._rollback_transaction(context, "System shutdown")
                except Exception as e:
                    self.logger.error(f"Failed to rollback transaction during shutdown: {e}")
            
            self.active_transactions.clear()
        
        # Wait for monitoring thread to finish
        if self._monitoring_thread.is_alive():
            self._monitoring_thread.join(timeout=5)
    
    def _begin_transaction(self, context: TransactionContext):
        """Begin a database transaction."""
        try:
            # Set isolation level if supported
            if context.connection.database_type == DatabaseType.POSTGRESQL:
                isolation_map = {
                    IsolationLevel.READ_UNCOMMITTED: "READ UNCOMMITTED",
                    IsolationLevel.READ_COMMITTED: "READ COMMITTED",
                    IsolationLevel.REPEATABLE_READ: "REPEATABLE READ",
                    IsolationLevel.SERIALIZABLE: "SERIALIZABLE"
                }
                isolation_sql = isolation_map.get(context.isolation_level, "READ COMMITTED")
                
                # Execute BEGIN with isolation level
                if self.database_manager:
                    self.database_manager.execute_query(
                        f"BEGIN ISOLATION LEVEL {isolation_sql}",
                        tenant_id=None
                    )
            else:
                # SQLite - just begin transaction
                if self.database_manager:
                    self.database_manager.execute_query("BEGIN", tenant_id=None)
            
            context.state = TransactionState.ACTIVE
            self.logger.debug(f"Started transaction {context.transaction_id}")
            
        except Exception as e:
            context.state = TransactionState.FAILED
            raise TransactionError(f"Failed to begin transaction: {e}")
    
    def _commit_transaction(self, context: TransactionContext):
        """Commit a database transaction."""
        try:
            # Execute before_commit callbacks
            context.execute_callbacks('before_commit')
            
            # Commit all child transactions first
            for child in context.child_transactions:
                if child.state == TransactionState.ACTIVE:
                    self._commit_transaction(child)
            
            # Commit the transaction
            if self.database_manager:
                self.database_manager.execute_query("COMMIT", tenant_id=None)
            
            context.state = TransactionState.COMMITTED
            context.metrics.success = True
            
            # Execute after_commit callbacks
            context.execute_callbacks('after_commit')
            
            # Update performance metrics
            self.performance_metrics['successful_transactions'] += 1
            
            self.logger.debug(f"Committed transaction {context.transaction_id}")
            
        except Exception as e:
            context.state = TransactionState.FAILED
            context.metrics.error_message = str(e)
            self.performance_metrics['failed_transactions'] += 1
            raise TransactionError(f"Failed to commit transaction: {e}")
    
    def _rollback_transaction(self, context: TransactionContext, reason: str):
        """Rollback a database transaction."""
        try:
            # Execute before_rollback callbacks
            context.execute_callbacks('before_rollback')
            
            # Rollback all child transactions first
            for child in context.child_transactions:
                if child.state == TransactionState.ACTIVE:
                    self._rollback_transaction(child, reason)
            
            # Rollback the transaction
            if self.database_manager:
                self.database_manager.execute_query("ROLLBACK", tenant_id=None)
            
            context.state = TransactionState.ROLLED_BACK
            context.metrics.error_message = reason
            context.metrics.rollback_count += 1
            
            # Execute after_rollback callbacks
            context.execute_callbacks('after_rollback')
            
            # Update performance metrics
            self.performance_metrics['rolled_back_transactions'] += 1
            
            self.logger.debug(f"Rolled back transaction {context.transaction_id}: {reason}")
            
        except Exception as e:
            context.state = TransactionState.FAILED
            self.logger.error(f"Failed to rollback transaction {context.transaction_id}: {e}")
    
    def _update_performance_metrics(self, context: TransactionContext):
        """Update performance metrics based on transaction context."""
        if context.metrics.duration:
            if context.metrics.duration > self.performance_metrics['longest_transaction_time']:
                self.performance_metrics['longest_transaction_time'] = context.metrics.duration
        
        self.performance_metrics['total_savepoints_created'] += context.metrics.savepoint_count
        self.performance_metrics['total_rollbacks_to_savepoint'] += context.metrics.rollback_count
        
        if context.metrics.deadlock_count > 0:
            self.performance_metrics['deadlocks_detected'] += context.metrics.deadlock_count
    
    def _is_retryable_error(self, error: Exception) -> bool:
        """Check if an error is retryable (e.g., deadlock)."""
        error_str = str(error).lower()
        retryable_patterns = [
            'deadlock',
            'lock timeout',
            'serialization failure',
            'could not serialize access'
        ]
        
        return any(pattern in error_str for pattern in retryable_patterns)
    
    def _monitor_transactions(self):
        """Background thread for monitoring transactions."""
        while self._monitoring_enabled:
            try:
                # Cleanup expired transactions
                self.cleanup_expired_transactions()
                
                # Detect deadlocks if enabled
                if self.deadlock_detection_enabled:
                    deadlocks = self.detect_deadlocks()
                    for deadlock in deadlocks:
                        self.resolve_deadlock(deadlock)
                
                # Sleep before next check
                time.sleep(self.deadlock_detection_interval)
                
            except Exception as e:
                self.logger.error(f"Error in transaction monitoring: {e}")
                time.sleep(5)  # Wait longer on error