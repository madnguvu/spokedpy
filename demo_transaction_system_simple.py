#!/usr/bin/env python3
"""
Simple demo script showcasing the Visual Editor Core Transaction Management System.

This script demonstrates the transaction management components without requiring
actual database connections.
"""

import logging
import time
from datetime import datetime
from unittest.mock import Mock

from visual_editor_core.database.transaction_manager import (
    TransactionManager,
    IsolationLevel
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
from visual_editor_core.database.transaction_models import (
    TransactionStatistics,
    TransactionConfig
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def create_mock_database_manager():
    """Create a mock database manager for demonstration."""
    mock_db = Mock()
    
    # Mock connection
    mock_connection = DatabaseConnection(
        connection_id="demo_conn_1",
        database_type=DatabaseType.SQLITE,
        status=ConnectionStatus.CONNECTED,
        created_at=datetime.now(),
        last_used=datetime.now(),
        connection_string="demo.db"
    )
    
    mock_db.get_connection.return_value = mock_connection
    mock_db.execute_query.return_value = Mock(success=True, data=[])
    
    return mock_db


def demo_transaction_manager():
    """Demonstrate TransactionManager functionality."""
    logger.info("\n=== Demo 1: Transaction Manager ===")
    
    mock_db = create_mock_database_manager()
    transaction_manager = TransactionManager(mock_db)
    
    try:
        # Basic transaction
        with transaction_manager.transaction() as context:
            logger.info(f"Created transaction: {context.transaction_id}")
            
            # Add operations
            operation = DatabaseOperation(
                operation_type="insert",
                table="demo_table",
                data={"id": 1, "name": "Demo Record"}
            )
            context.add_operation(operation)
            logger.info("Added operation to transaction")
            
            # Create savepoint
            savepoint_id = context.create_savepoint("demo_savepoint")
            logger.info(f"Created savepoint: {savepoint_id}")
            
            # Add another operation
            operation2 = DatabaseOperation(
                operation_type="update",
                table="demo_table",
                data={"name": "Updated Demo Record"},
                conditions={"id": 1}
            )
            context.add_operation(operation2)
            logger.info("Added second operation")
            
            logger.info(f"Transaction has {len(context.operations)} operations")
            logger.info(f"Transaction has {len(context.savepoints)} savepoints")
        
        logger.info("Transaction completed successfully")
        
        # Get statistics
        stats = transaction_manager.get_transaction_metrics()
        logger.info(f"Total transactions: {stats['total_transactions']}")
        logger.info(f"Successful transactions: {stats['successful_transactions']}")
        
    finally:
        transaction_manager.shutdown()


def demo_transaction_wrapper():
    """Demonstrate TransactionWrapper functionality."""
    logger.info("\n=== Demo 2: Transaction Wrapper ===")
    
    mock_db = create_mock_database_manager()
    transaction_wrapper = TransactionWrapper(mock_db)
    
    # Bulk insert demo
    records = [
        {"id": i, "name": f"Record {i}", "value": i * 10}
        for i in range(1, 11)
    ]
    
    logger.info(f"Performing bulk insert of {len(records)} records...")
    result = transaction_wrapper.bulk_insert(
        table="demo_table",
        records=records,
        batch_size=3
    )
    
    if result.success:
        logger.info(f"Bulk insert completed: {result.operations_count} operations")
        logger.info(f"Execution time: {result.execution_time:.3f} seconds")
    else:
        logger.error(f"Bulk insert failed: {result.error_message}")
    
    # Bulk update demo
    updates = [
        {"id": i, "name": f"Updated Record {i}", "status": "active"}
        for i in range(1, 6)
    ]
    
    logger.info(f"Performing bulk update of {len(updates)} records...")
    result = transaction_wrapper.bulk_update(
        table="demo_table",
        updates=updates,
        condition_columns=["id"],
        batch_size=2
    )
    
    if result.success:
        logger.info(f"Bulk update completed: {result.operations_count} operations")
        logger.info(f"Execution time: {result.execution_time:.3f} seconds")
    else:
        logger.error(f"Bulk update failed: {result.error_message}")


def demo_deadlock_detector():
    """Demonstrate DeadlockDetector functionality."""
    logger.info("\n=== Demo 3: Deadlock Detector ===")
    
    detector = DeadlockDetector(detection_interval=0.1)
    
    try:
        # Register transactions
        tx1 = "transaction_1"
        tx2 = "transaction_2"
        
        detector.register_transaction(tx1, priority=1)
        detector.register_transaction(tx2, priority=2)
        logger.info(f"Registered transactions: {tx1}, {tx2}")
        
        # Create deadlock scenario
        detector.add_lock_wait(tx1, tx2, "resource_A")
        detector.add_lock_wait(tx2, tx1, "resource_B")
        logger.info("Created circular wait condition (deadlock scenario)")
        
        # Detect deadlocks
        deadlocks = detector.detect_deadlocks()
        logger.info(f"Detected {len(deadlocks)} deadlock(s)")
        
        for deadlock in deadlocks:
            logger.info(f"Deadlock involves: {deadlock.involved_transactions}")
            logger.info(f"Confidence score: {deadlock.confidence_score:.2f}")
            
            # Resolve deadlock
            resolved = detector.resolve_deadlock(deadlock)
            if resolved:
                logger.info(f"Resolved deadlock by aborting: {deadlock.victim_transaction}")
            else:
                logger.error("Failed to resolve deadlock")
        
        # Get statistics
        stats = detector.get_deadlock_statistics()
        logger.info(f"Deadlock statistics:")
        logger.info(f"  Total detected: {stats['total_deadlocks_detected']}")
        logger.info(f"  Total resolved: {stats['total_deadlocks_resolved']}")
        logger.info(f"  Success rate: {stats['resolution_success_rate']:.2f}")
        
    finally:
        detector.stop_monitoring()


def demo_transaction_monitor():
    """Demonstrate TransactionMonitor functionality."""
    logger.info("\n=== Demo 4: Transaction Monitor ===")
    
    monitor = TransactionMonitor(monitoring_interval=0.1)
    
    try:
        # Record some sample transactions
        for i in range(10):
            stats = TransactionStatistics(
                transaction_id=f"demo_tx_{i}",
                start_time=datetime.now(),
                end_time=datetime.now(),
                duration_seconds=0.5 + i * 0.1,
                operations_executed=2 + i,
                success=i < 8,  # 2 failures
                database_type=DatabaseType.SQLITE
            )
            monitor.record_transaction(stats)
        
        logger.info("Recorded 10 sample transactions")
        
        # Get performance summary
        summary = monitor.get_performance_summary()
        logger.info("Performance Summary:")
        logger.info(f"  Total transactions: {summary['total_transactions']}")
        logger.info(f"  Success rate: {summary['success_rate']:.1f}%")
        logger.info(f"  Average duration: {summary['average_duration']:.3f}s")
        logger.info(f"  P95 duration: {summary['p95_duration']:.3f}s")
        
        # Get optimization suggestions
        suggestions = monitor.get_optimization_suggestions()
        logger.info(f"Optimization suggestions: {len(suggestions)}")
        for suggestion in suggestions[:2]:  # Show first 2
            logger.info(f"  - {suggestion.description}")
            logger.info(f"    Priority: {suggestion.priority_score:.2f}")
        
        # Get health check
        health = monitor.get_health_check()
        logger.info(f"System health: {health.overall_health}")
        logger.info(f"Active transactions: {health.active_transactions}")
        
        if health.warnings:
            logger.warning("Warnings:")
            for warning in health.warnings:
                logger.warning(f"  - {warning}")
        
        if health.recommendations:
            logger.info("Recommendations:")
            for rec in health.recommendations:
                logger.info(f"  - {rec}")
        
    finally:
        monitor.stop_monitoring()


def demo_integration():
    """Demonstrate integration of all components."""
    logger.info("\n=== Demo 5: Component Integration ===")
    
    mock_db = create_mock_database_manager()
    
    # Create all components
    transaction_manager = TransactionManager(mock_db)
    transaction_wrapper = TransactionWrapper(mock_db, transaction_manager)
    deadlock_detector = DeadlockDetector()
    transaction_monitor = TransactionMonitor()
    
    try:
        # Start monitoring
        deadlock_detector.start_monitoring()
        transaction_monitor.start_monitoring()
        logger.info("Started all monitoring components")
        
        # Simulate a complex transaction workflow
        with transaction_wrapper.auto_transaction() as tx_ops:
            logger.info("Starting complex transaction workflow...")
            
            # Insert operation
            tx_ops.insert("users", {"id": 1, "name": "John Doe"})
            logger.info("Inserted user record")
            
            # Update operation
            tx_ops.update("users", {"status": "active"}, {"id": 1})
            logger.info("Updated user status")
            
            # Create savepoint for risky operation
            with tx_ops.savepoint("risky_operation"):
                tx_ops.insert("user_logs", {"user_id": 1, "action": "login"})
                logger.info("Inserted log record (within savepoint)")
        
        logger.info("Complex transaction completed successfully")
        
        # Record transaction statistics
        stats = TransactionStatistics(
            transaction_id="integration_demo",
            start_time=datetime.now(),
            end_time=datetime.now(),
            duration_seconds=1.2,
            operations_executed=3,
            success=True,
            database_type=DatabaseType.SQLITE
        )
        transaction_monitor.record_transaction(stats)
        
        # Get comprehensive statistics
        tm_stats = transaction_manager.get_transaction_metrics()
        dd_stats = deadlock_detector.get_deadlock_statistics()
        pm_summary = transaction_monitor.get_performance_summary()
        
        logger.info("Integration Statistics:")
        logger.info(f"  Transaction Manager - Total: {tm_stats['total_transactions']}")
        logger.info(f"  Deadlock Detector - Active: {dd_stats['active_transactions']}")
        logger.info(f"  Performance Monitor - Success Rate: {pm_summary['success_rate']:.1f}%")
        
    finally:
        # Clean up all components
        deadlock_detector.stop_monitoring()
        transaction_monitor.stop_monitoring()
        transaction_manager.shutdown()
        logger.info("Cleaned up all components")


def main():
    """Run all demonstrations."""
    logger.info("Visual Editor Core Transaction Management System Demo")
    logger.info("=" * 60)
    
    try:
        demo_transaction_manager()
        demo_transaction_wrapper()
        demo_deadlock_detector()
        demo_transaction_monitor()
        demo_integration()
        
        logger.info("\n" + "=" * 60)
        logger.info("All demonstrations completed successfully!")
        
    except Exception as e:
        logger.error(f"Demo failed: {e}")
        raise


if __name__ == "__main__":
    main()