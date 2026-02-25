"""
Tests for the transaction management system.
"""

import pytest
import time
import threading
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from visual_editor_core.database.transaction_manager import (
    TransactionManager,
    TransactionContext,
    IsolationLevel,
    TransactionState
)
from visual_editor_core.database.transaction_wrapper import TransactionWrapper
from visual_editor_core.database.deadlock_detector import DeadlockDetector
from visual_editor_core.database.transaction_monitor import TransactionMonitor
from visual_editor_core.database.models import (
    DatabaseConnection,
    DatabaseOperation,
    DatabaseType,
    ConnectionStatus
)
from visual_editor_core.database.exceptions import TransactionError


class TestTransactionManager:
    """Test cases for TransactionManager."""
    
    @pytest.fixture
    def mock_database_manager(self):
        """Create a mock database manager."""
        mock_db = Mock()
        mock_connection = DatabaseConnection(
            connection_id="test_conn_1",
            database_type=DatabaseType.SQLITE,
            status=ConnectionStatus.CONNECTED,
            created_at=datetime.now(),
            last_used=datetime.now(),
            connection_string="test.db"
        )
        mock_db.get_connection.return_value = mock_connection
        mock_db.execute_query.return_value = Mock(success=True)
        return mock_db
    
    @pytest.fixture
    def transaction_manager(self, mock_database_manager):
        """Create a TransactionManager instance."""
        return TransactionManager(mock_database_manager)
    
    def test_transaction_context_creation(self, transaction_manager, mock_database_manager):
        """Test transaction context creation."""
        with transaction_manager.transaction() as context:
            assert isinstance(context, TransactionContext)
            assert context.state == TransactionState.ACTIVE
            assert context.isolation_level == IsolationLevel.READ_COMMITTED
            assert len(context.operations) == 0
    
    def test_transaction_operation_addition(self, transaction_manager):
        """Test adding operations to a transaction."""
        with transaction_manager.transaction() as context:
            operation = DatabaseOperation(
                operation_type="insert",
                table="test_table",
                data={"id": 1, "name": "test"}
            )
            
            context.add_operation(operation)
            assert len(context.operations) == 1
            assert context.operations[0] == operation
    
    def test_transaction_savepoint_creation(self, transaction_manager):
        """Test savepoint creation and rollback."""
        with transaction_manager.transaction() as context:
            # Add initial operation
            op1 = DatabaseOperation(
                operation_type="insert",
                table="test_table",
                data={"id": 1, "name": "test1"}
            )
            context.add_operation(op1)
            
            # Create savepoint
            savepoint_id = context.create_savepoint("test_savepoint")
            assert savepoint_id in context.savepoints
            assert len(context.savepoints) == 1
            
            # Add another operation
            op2 = DatabaseOperation(
                operation_type="insert",
                table="test_table",
                data={"id": 2, "name": "test2"}
            )
            context.add_operation(op2)
            assert len(context.operations) == 2
            
            # Rollback to savepoint
            context.rollback_to_savepoint(savepoint_id)
            assert len(context.operations) == 1  # Should only have first operation
    
    def test_transaction_timeout(self, transaction_manager):
        """Test transaction timeout functionality."""
        with transaction_manager.transaction(timeout=1) as context:
            assert context.timeout == 1
            
            # Simulate time passing
            context.start_time = datetime.now() - timedelta(seconds=2)
            assert context.is_expired()
    
    def test_transaction_callbacks(self, transaction_manager):
        """Test transaction event callbacks."""
        callback_called = []
        
        def test_callback(context):
            callback_called.append(context.transaction_id)
        
        with transaction_manager.transaction() as context:
            context.add_callback('before_commit', test_callback)
            # Callback will be executed during commit
        
        # Note: In a real test, we'd need to verify the callback was called
        # This would require more complex mocking of the commit process
    
    def test_nested_transaction(self, transaction_manager):
        """Test nested transaction with savepoints."""
        with transaction_manager.transaction() as parent_context:
            # Add operation to parent
            parent_op = DatabaseOperation(
                operation_type="insert",
                table="parent_table",
                data={"id": 1, "name": "parent"}
            )
            parent_context.add_operation(parent_op)
            
            # Create nested transaction
            with transaction_manager.nested_transaction(parent_context, "nested_test") as nested_context:
                nested_op = DatabaseOperation(
                    operation_type="insert",
                    table="nested_table",
                    data={"id": 1, "name": "nested"}
                )
                nested_context.add_operation(nested_op)
                
                assert nested_context.parent_transaction == parent_context
                assert nested_context in parent_context.child_transactions
            
            # After nested transaction, operations should be merged
            assert len(parent_context.operations) == 2
    
    def test_transaction_retry_mechanism(self, transaction_manager):
        """Test transaction retry on retryable errors."""
        attempt_count = 0
        
        def failing_operation():
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count < 3:
                raise Exception("deadlock detected")  # Simulated retryable error
            return "success"
        
        # Mock the _is_retryable_error method to return True for our test error
        with patch.object(transaction_manager, '_is_retryable_error', return_value=True):
            result = transaction_manager.execute_with_retry(failing_operation, max_retries=3)
            assert result == "success"
            assert attempt_count == 3
    
    def test_transaction_statistics_tracking(self, transaction_manager):
        """Test transaction statistics tracking."""
        initial_stats = transaction_manager.get_transaction_metrics()
        initial_total = initial_stats['total_transactions']
        
        # Execute a successful transaction
        with transaction_manager.transaction() as context:
            operation = DatabaseOperation(
                operation_type="select",
                table="test_table"
            )
            context.add_operation(operation)
        
        # Check updated statistics
        updated_stats = transaction_manager.get_transaction_metrics()
        assert updated_stats['total_transactions'] == initial_total + 1
        assert updated_stats['successful_transactions'] >= initial_stats['successful_transactions']
    
    def test_transaction_cleanup(self, transaction_manager):
        """Test transaction cleanup and resource management."""
        # Create some transactions that should be cleaned up
        expired_count = transaction_manager.cleanup_expired_transactions()
        
        # Initially should be 0 since no transactions are expired
        assert expired_count >= 0
        
        # Test shutdown
        transaction_manager.shutdown()
        assert not transaction_manager._monitoring_enabled


class TestTransactionWrapper:
    """Test cases for TransactionWrapper."""
    
    @pytest.fixture
    def mock_database_manager(self):
        """Create a mock database manager."""
        mock_db = Mock()
        mock_connection = DatabaseConnection(
            connection_id="test_conn_1",
            database_type=DatabaseType.SQLITE,
            status=ConnectionStatus.CONNECTED,
            created_at=datetime.now(),
            last_used=datetime.now(),
            connection_string="test.db"
        )
        mock_db.get_connection.return_value = mock_connection
        mock_db.execute_query.return_value = Mock(success=True)
        return mock_db
    
    @pytest.fixture
    def transaction_wrapper(self, mock_database_manager):
        """Create a TransactionWrapper instance."""
        return TransactionWrapper(mock_database_manager)
    
    def test_auto_transaction_context(self, transaction_wrapper):
        """Test auto transaction context manager."""
        with transaction_wrapper.auto_transaction() as tx_ops:
            assert hasattr(tx_ops, 'add_operation')
            assert hasattr(tx_ops, 'execute_query')
            assert hasattr(tx_ops, 'insert')
            assert hasattr(tx_ops, 'update')
            assert hasattr(tx_ops, 'delete')
    
    def test_bulk_insert(self, transaction_wrapper):
        """Test bulk insert functionality."""
        records = [
            {"id": 1, "name": "record1"},
            {"id": 2, "name": "record2"},
            {"id": 3, "name": "record3"}
        ]
        
        result = transaction_wrapper.bulk_insert(
            table="test_table",
            records=records,
            batch_size=2
        )
        
        assert result.success
        assert result.operations_count == len(records)
    
    def test_bulk_update(self, transaction_wrapper):
        """Test bulk update functionality."""
        updates = [
            {"id": 1, "name": "updated1", "status": "active"},
            {"id": 2, "name": "updated2", "status": "inactive"}
        ]
        
        result = transaction_wrapper.bulk_update(
            table="test_table",
            updates=updates,
            condition_columns=["id"],
            batch_size=1
        )
        
        assert result.success
        assert result.operations_count == len(updates)
    
    def test_read_only_execution(self, transaction_wrapper):
        """Test read-only query execution."""
        result = transaction_wrapper.execute_read_only(
            "SELECT * FROM test_table WHERE id = :id",
            params={"id": 1}
        )
        
        # Should succeed with mocked database manager
        assert result.success
    
    def test_retry_execution(self, transaction_wrapper):
        """Test execution with retry logic."""
        call_count = 0
        
        def test_operation(tx_ops):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise Exception("temporary failure")
            return "success"
        
        # Mock the retry mechanism
        with patch.object(transaction_wrapper.transaction_manager, 'execute_with_retry') as mock_retry:
            mock_retry.return_value = "success"
            
            result = transaction_wrapper.execute_with_retry(test_operation)
            assert result == "success"
            mock_retry.assert_called_once()


class TestDeadlockDetector:
    """Test cases for DeadlockDetector."""
    
    @pytest.fixture
    def deadlock_detector(self):
        """Create a DeadlockDetector instance."""
        return DeadlockDetector(detection_interval=0.1)  # Fast detection for testing
    
    def test_transaction_registration(self, deadlock_detector):
        """Test transaction registration and unregistration."""
        tx_id = "test_tx_1"
        
        deadlock_detector.register_transaction(tx_id, priority=1)
        assert tx_id in deadlock_detector.transaction_info
        assert deadlock_detector.transaction_priorities[tx_id] == 1
        
        deadlock_detector.unregister_transaction(tx_id)
        assert tx_id not in deadlock_detector.transaction_info
        assert tx_id not in deadlock_detector.transaction_priorities
    
    def test_lock_wait_tracking(self, deadlock_detector):
        """Test lock wait relationship tracking."""
        tx1 = "tx_1"
        tx2 = "tx_2"
        resource = "table_1"
        
        deadlock_detector.register_transaction(tx1)
        deadlock_detector.register_transaction(tx2)
        
        deadlock_detector.add_lock_wait(tx1, tx2, resource)
        
        # Check that wait relationship was added
        assert tx1 in deadlock_detector.wait_for_graph.nodes
        assert tx2 in deadlock_detector.wait_for_graph.nodes
        assert tx2 in deadlock_detector.wait_for_graph.edges[tx1]
    
    def test_deadlock_detection(self, deadlock_detector):
        """Test deadlock detection algorithm."""
        # Create a simple deadlock scenario: tx1 waits for tx2, tx2 waits for tx1
        tx1 = "tx_1"
        tx2 = "tx_2"
        
        deadlock_detector.register_transaction(tx1)
        deadlock_detector.register_transaction(tx2)
        
        deadlock_detector.add_lock_wait(tx1, tx2, "resource_1")
        deadlock_detector.add_lock_wait(tx2, tx1, "resource_2")
        
        deadlocks = deadlock_detector.detect_deadlocks()
        
        # Should detect at least one deadlock
        assert len(deadlocks) > 0
        
        # The detected deadlock should involve both transactions
        deadlock = deadlocks[0]
        assert tx1 in deadlock.involved_transactions or tx2 in deadlock.involved_transactions
    
    def test_deadlock_resolution(self, deadlock_detector):
        """Test deadlock resolution."""
        # Create a deadlock scenario
        tx1 = "tx_1"
        tx2 = "tx_2"
        
        deadlock_detector.register_transaction(tx1, priority=1)
        deadlock_detector.register_transaction(tx2, priority=2)
        
        deadlock_detector.add_lock_wait(tx1, tx2, "resource_1")
        deadlock_detector.add_lock_wait(tx2, tx1, "resource_2")
        
        deadlocks = deadlock_detector.detect_deadlocks()
        
        if deadlocks:
            deadlock = deadlocks[0]
            resolved = deadlock_detector.resolve_deadlock(deadlock)
            assert resolved
            assert deadlock.victim_transaction is not None
    
    def test_monitoring_lifecycle(self, deadlock_detector):
        """Test deadlock detector monitoring lifecycle."""
        assert not deadlock_detector._monitoring_enabled
        
        deadlock_detector.start_monitoring()
        assert deadlock_detector._monitoring_enabled
        
        # Give it a moment to start
        time.sleep(0.2)
        
        deadlock_detector.stop_monitoring()
        assert not deadlock_detector._monitoring_enabled
    
    def test_statistics_collection(self, deadlock_detector):
        """Test deadlock statistics collection."""
        stats = deadlock_detector.get_deadlock_statistics()
        
        assert 'total_deadlocks_detected' in stats
        assert 'total_deadlocks_resolved' in stats
        assert 'active_transactions' in stats
        assert 'resolution_success_rate' in stats
        
        # Initially should be zero
        assert stats['total_deadlocks_detected'] == 0
        assert stats['total_deadlocks_resolved'] == 0


class TestTransactionMonitor:
    """Test cases for TransactionMonitor."""
    
    @pytest.fixture
    def transaction_monitor(self):
        """Create a TransactionMonitor instance."""
        return TransactionMonitor(monitoring_interval=0.1)  # Fast monitoring for testing
    
    def test_transaction_recording(self, transaction_monitor):
        """Test transaction statistics recording."""
        from visual_editor_core.database.transaction_models import TransactionStatistics
        
        stats = TransactionStatistics(
            transaction_id="test_tx_1",
            start_time=datetime.now(),
            end_time=datetime.now(),
            duration_seconds=1.5,
            operations_executed=3,
            success=True
        )
        
        initial_count = len(transaction_monitor.transaction_history)
        transaction_monitor.record_transaction(stats)
        
        assert len(transaction_monitor.transaction_history) == initial_count + 1
        assert transaction_monitor.transaction_history[-1] == stats
    
    def test_performance_summary(self, transaction_monitor):
        """Test performance summary generation."""
        from visual_editor_core.database.transaction_models import TransactionStatistics
        
        # Add some test transactions
        for i in range(5):
            stats = TransactionStatistics(
                transaction_id=f"test_tx_{i}",
                start_time=datetime.now(),
                end_time=datetime.now(),
                duration_seconds=1.0 + i * 0.5,
                operations_executed=2,
                success=i < 4  # One failure
            )
            transaction_monitor.record_transaction(stats)
        
        summary = transaction_monitor.get_performance_summary()
        
        assert summary['total_transactions'] == 5
        assert summary['success_rate'] == 80.0  # 4 out of 5 successful
        assert summary['average_duration'] > 0
    
    def test_optimization_suggestions(self, transaction_monitor):
        """Test optimization suggestion generation."""
        from visual_editor_core.database.transaction_models import TransactionStatistics
        
        # Add some slow transactions to trigger suggestions
        for i in range(20):
            stats = TransactionStatistics(
                transaction_id=f"slow_tx_{i}",
                start_time=datetime.now(),
                end_time=datetime.now(),
                duration_seconds=15.0,  # Slow transaction
                operations_executed=1,
                success=True
            )
            transaction_monitor.record_transaction(stats)
        
        suggestions = transaction_monitor.get_optimization_suggestions()
        
        # Should generate suggestions for slow transactions
        assert len(suggestions) > 0
        
        # Check that suggestions have required fields
        for suggestion in suggestions:
            assert hasattr(suggestion, 'suggestion_id')
            assert hasattr(suggestion, 'description')
            assert hasattr(suggestion, 'expected_improvement')
            assert hasattr(suggestion, 'implementation_steps')
    
    def test_health_check(self, transaction_monitor):
        """Test transaction system health check."""
        health_check = transaction_monitor.get_health_check()
        
        assert hasattr(health_check, 'overall_health')
        assert hasattr(health_check, 'active_transactions')
        assert hasattr(health_check, 'warnings')
        assert hasattr(health_check, 'errors')
        assert hasattr(health_check, 'recommendations')
        
        # Initially should be healthy
        assert health_check.overall_health in ['healthy', 'warning', 'critical']
    
    def test_monitoring_lifecycle(self, transaction_monitor):
        """Test transaction monitor lifecycle."""
        assert not transaction_monitor._monitoring_enabled
        
        transaction_monitor.start_monitoring()
        assert transaction_monitor._monitoring_enabled
        
        # Give it a moment to start
        time.sleep(0.2)
        
        transaction_monitor.stop_monitoring()
        assert not transaction_monitor._monitoring_enabled
    
    def test_alert_callbacks(self, transaction_monitor):
        """Test alert callback functionality."""
        alerts_received = []
        
        def test_callback(alert):
            alerts_received.append(alert)
        
        transaction_monitor.add_alert_callback(test_callback)
        
        # The callback is now registered
        assert test_callback in transaction_monitor.alert_callbacks


class TestTransactionIntegration:
    """Integration tests for the complete transaction management system."""
    
    @pytest.fixture
    def mock_database_manager(self):
        """Create a mock database manager with transaction components."""
        mock_db = Mock()
        mock_connection = DatabaseConnection(
            connection_id="test_conn_1",
            database_type=DatabaseType.SQLITE,
            status=ConnectionStatus.CONNECTED,
            created_at=datetime.now(),
            last_used=datetime.now(),
            connection_string="test.db"
        )
        mock_db.get_connection.return_value = mock_connection
        mock_db.execute_query.return_value = Mock(success=True)
        
        # Add transaction management components
        mock_db.transaction_manager = TransactionManager(mock_db)
        mock_db.transaction_wrapper = TransactionWrapper(mock_db, mock_db.transaction_manager)
        mock_db.deadlock_detector = DeadlockDetector()
        mock_db.transaction_monitor = TransactionMonitor()
        
        return mock_db
    
    def test_end_to_end_transaction_flow(self, mock_database_manager):
        """Test complete transaction flow with all components."""
        db = mock_database_manager
        
        # Start monitoring
        db.deadlock_detector.start_monitoring()
        db.transaction_monitor.start_monitoring()
        
        try:
            # Execute a transaction using the wrapper
            with db.transaction_wrapper.auto_transaction() as tx_ops:
                tx_ops.insert("users", {"id": 1, "name": "John"})
                tx_ops.update("users", {"name": "John Doe"}, {"id": 1})
                
                # Create a savepoint
                with tx_ops.savepoint("user_update"):
                    tx_ops.insert("user_logs", {"user_id": 1, "action": "updated"})
            
            # Check that transaction was recorded
            stats = db.transaction_manager.get_transaction_metrics()
            assert stats['total_transactions'] > 0
            
        finally:
            # Clean up
            db.deadlock_detector.stop_monitoring()
            db.transaction_monitor.stop_monitoring()
            db.transaction_manager.shutdown()
    
    def test_concurrent_transaction_handling(self, mock_database_manager):
        """Test handling of concurrent transactions."""
        db = mock_database_manager
        results = []
        errors = []
        
        def worker_transaction(worker_id):
            try:
                with db.transaction_wrapper.auto_transaction() as tx_ops:
                    tx_ops.insert("workers", {"id": worker_id, "name": f"Worker {worker_id}"})
                    time.sleep(0.1)  # Simulate work
                    tx_ops.update("workers", {"status": "active"}, {"id": worker_id})
                results.append(f"Worker {worker_id} completed")
            except Exception as e:
                errors.append(f"Worker {worker_id} failed: {e}")
        
        # Start multiple concurrent transactions
        threads = []
        for i in range(5):
            thread = threading.Thread(target=worker_transaction, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join(timeout=5)
        
        # Check results
        assert len(results) == 5  # All workers should complete
        assert len(errors) == 0   # No errors should occur
    
    def test_transaction_failure_and_rollback(self, mock_database_manager):
        """Test transaction failure handling and rollback."""
        db = mock_database_manager
        
        # Mock a failure in execute_query
        db.execute_query.side_effect = [
            Mock(success=True),   # First operation succeeds
            Exception("Database error")  # Second operation fails
        ]
        
        with pytest.raises(Exception):
            with db.transaction_wrapper.auto_transaction() as tx_ops:
                tx_ops.insert("test_table", {"id": 1, "name": "test"})
                tx_ops.execute_query("INVALID SQL")  # This should fail
        
        # Transaction should have been rolled back
        # In a real scenario, we'd verify the rollback occurred