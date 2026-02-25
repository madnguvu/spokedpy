#!/usr/bin/env python3
"""
Demo script showcasing the Visual Editor Core Transaction Management System.

This script demonstrates:
- Automatic rollback on failures
- Nested transaction support with savepoints
- Transaction performance monitoring
- Deadlock detection and resolution
- Transaction-aware database operations
"""

import asyncio
import logging
import random
import time
import threading
from datetime import datetime
from typing import List

from visual_editor_core.database.database_manager import DatabaseManager
from visual_editor_core.database.models import DatabaseConfig, DatabaseType, DatabaseOperation
from visual_editor_core.database.transaction_models import (
    TransactionConfig,
    TransactionType,
    TransactionPriority,
    TransactionBatch
)
from visual_editor_core.database.transaction_manager import IsolationLevel
from visual_editor_core.database.exceptions import TransactionError


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class TransactionSystemDemo:
    """Demonstration of the transaction management system."""
    
    def __init__(self):
        """Initialize the demo with database manager."""
        # Configure SQLite for demo (easier setup)
        sqlite_config = DatabaseConfig(
            database_type=DatabaseType.SQLITE,
            database="demo_transactions.db"
        )
        
        self.db_manager = DatabaseManager(sqlite_config=sqlite_config)
        self.setup_demo_tables()
    
    def setup_demo_tables(self):
        """Set up demo tables for testing."""
        logger.info("Setting up demo tables...")
        
        # Create demo tables
        tables = {
            "users": """
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                email TEXT UNIQUE,
                balance DECIMAL(10,2) DEFAULT 0.00,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            """,
            "accounts": """
                id INTEGER PRIMARY KEY,
                user_id INTEGER,
                account_type TEXT,
                balance DECIMAL(10,2) DEFAULT 0.00,
                FOREIGN KEY (user_id) REFERENCES users(id)
            """,
            "transactions": """
                id INTEGER PRIMARY KEY,
                from_account_id INTEGER,
                to_account_id INTEGER,
                amount DECIMAL(10,2),
                transaction_type TEXT,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (from_account_id) REFERENCES accounts(id),
                FOREIGN KEY (to_account_id) REFERENCES accounts(id)
            """,
            "audit_log": """
                id INTEGER PRIMARY KEY,
                table_name TEXT,
                operation TEXT,
                record_id INTEGER,
                old_values TEXT,
                new_values TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            """
        }
        
        # Create tables using database manager
        for table_name, table_def in tables.items():
            try:
                result = self.db_manager.execute_query(
                    f"CREATE TABLE IF NOT EXISTS {table_name} ({table_def})"
                )
                if result.success:
                    logger.info(f"Created table: {table_name}")
                else:
                    logger.error(f"Failed to create table {table_name}: {result.error_message}")
            except Exception as e:
                logger.error(f"Error creating table {table_name}: {e}")
    
    def demo_basic_transaction(self):
        """Demonstrate basic transaction with automatic rollback."""
        logger.info("\n=== Demo 1: Basic Transaction with Automatic Rollback ===")
        
        transaction_wrapper = self.db_manager.get_transaction_wrapper()
        
        try:
            with transaction_wrapper.auto_transaction() as tx_ops:
                logger.info("Starting transaction...")
                
                # Insert a user
                tx_ops.insert("users", {
                    "name": "John Doe",
                    "email": "john@example.com",
                    "balance": 1000.00
                })
                logger.info("Inserted user: John Doe")
                
                # Insert an account
                tx_ops.insert("accounts", {
                    "user_id": 1,
                    "account_type": "checking",
                    "balance": 1000.00
                })
                logger.info("Inserted account for John Doe")
                
                # Simulate an error (this will cause rollback)
                if random.choice([True, False]):
                    raise Exception("Simulated database error!")
                
                logger.info("Transaction completed successfully")
                
        except Exception as e:
            logger.error(f"Transaction failed and was rolled back: {e}")
        
        # Check if data was actually inserted (should be empty if rolled back)
        result = self.db_manager.execute_query("SELECT COUNT(*) as count FROM users")
        if result.success:
            count = result.data[0]['count']
            logger.info(f"Users in database after transaction: {count}")
    
    def demo_nested_transactions(self):
        """Demonstrate nested transactions with savepoints."""
        logger.info("\n=== Demo 2: Nested Transactions with Savepoints ===")
        
        transaction_manager = self.db_manager.get_transaction_manager()
        
        try:
            with transaction_manager.transaction() as parent_context:
                logger.info("Starting parent transaction...")
                
                # Add user in parent transaction
                parent_context.add_operation(DatabaseOperation(
                    operation_type="insert",
                    table="users",
                    data={"name": "Alice Smith", "email": "alice@example.com", "balance": 2000.00}
                ))
                logger.info("Added user operation to parent transaction")
                
                # Create nested transaction with savepoint
                try:
                    with transaction_manager.nested_transaction(parent_context, "account_creation") as nested_context:
                        logger.info("Starting nested transaction...")
                        
                        # Add account in nested transaction
                        nested_context.add_operation(DatabaseOperation(
                            operation_type="insert",
                            table="accounts",
                            data={"user_id": 2, "account_type": "savings", "balance": 2000.00}
                        ))
                        logger.info("Added account operation to nested transaction")
                        
                        # Simulate error in nested transaction
                        if random.choice([True, False]):
                            raise Exception("Nested transaction error!")
                        
                        logger.info("Nested transaction completed")
                        
                except Exception as e:
                    logger.error(f"Nested transaction failed, rolled back to savepoint: {e}")
                
                logger.info("Parent transaction continuing...")
                
        except Exception as e:
            logger.error(f"Parent transaction failed: {e}")
    
    def demo_bulk_operations(self):
        """Demonstrate bulk operations with batching."""
        logger.info("\n=== Demo 3: Bulk Operations with Batching ===")
        
        transaction_wrapper = self.db_manager.get_transaction_wrapper()
        
        # Generate test data
        users_data = []
        for i in range(100):
            users_data.append({
                "name": f"User {i}",
                "email": f"user{i}@example.com",
                "balance": random.uniform(100, 5000)
            })
        
        logger.info(f"Performing bulk insert of {len(users_data)} users...")
        
        start_time = time.time()
        result = transaction_wrapper.bulk_insert(
            table="users",
            records=users_data,
            batch_size=20  # Process in batches of 20
        )
        end_time = time.time()
        
        if result.success:
            logger.info(f"Bulk insert completed in {end_time - start_time:.2f} seconds")
            logger.info(f"Inserted {result.operations_count} records")
        else:
            logger.error(f"Bulk insert failed: {result.error_message}")
    
    def demo_concurrent_transactions(self):
        """Demonstrate concurrent transaction handling."""
        logger.info("\n=== Demo 4: Concurrent Transaction Handling ===")
        
        def worker_transaction(worker_id: int, num_operations: int):
            """Worker function for concurrent transactions."""
            transaction_wrapper = self.db_manager.get_transaction_wrapper()
            
            try:
                with transaction_wrapper.auto_transaction() as tx_ops:
                    logger.info(f"Worker {worker_id} starting transaction...")
                    
                    for i in range(num_operations):
                        tx_ops.insert("audit_log", {
                            "table_name": "concurrent_test",
                            "operation": "insert",
                            "record_id": worker_id * 1000 + i,
                            "new_values": f"Worker {worker_id} operation {i}"
                        })
                        
                        # Simulate some work
                        time.sleep(0.01)
                    
                    logger.info(f"Worker {worker_id} completed {num_operations} operations")
                    
            except Exception as e:
                logger.error(f"Worker {worker_id} failed: {e}")
        
        # Start multiple concurrent workers
        threads = []
        num_workers = 5
        operations_per_worker = 10
        
        logger.info(f"Starting {num_workers} concurrent workers...")
        
        start_time = time.time()
        for worker_id in range(num_workers):
            thread = threading.Thread(
                target=worker_transaction,
                args=(worker_id, operations_per_worker)
            )
            threads.append(thread)
            thread.start()
        
        # Wait for all workers to complete
        for thread in threads:
            thread.join()
        
        end_time = time.time()
        logger.info(f"All workers completed in {end_time - start_time:.2f} seconds")
        
        # Check results
        result = self.db_manager.execute_query("SELECT COUNT(*) as count FROM audit_log")
        if result.success:
            count = result.data[0]['count']
            expected = num_workers * operations_per_worker
            logger.info(f"Expected {expected} records, found {count} records")
    
    def demo_deadlock_simulation(self):
        """Demonstrate deadlock detection and resolution."""
        logger.info("\n=== Demo 5: Deadlock Detection and Resolution ===")
        
        deadlock_detector = self.db_manager.get_deadlock_detector()
        
        # Register some transactions
        tx1_id = "deadlock_tx_1"
        tx2_id = "deadlock_tx_2"
        
        deadlock_detector.register_transaction(tx1_id, priority=1)
        deadlock_detector.register_transaction(tx2_id, priority=2)
        
        logger.info("Registered transactions for deadlock simulation")
        
        # Simulate deadlock scenario
        deadlock_detector.add_lock_wait(tx1_id, tx2_id, "resource_A")
        deadlock_detector.add_lock_wait(tx2_id, tx1_id, "resource_B")
        
        logger.info("Created circular wait condition")
        
        # Detect deadlocks
        deadlocks = deadlock_detector.detect_deadlocks()
        
        if deadlocks:
            logger.info(f"Detected {len(deadlocks)} deadlock(s)")
            
            for deadlock in deadlocks:
                logger.info(f"Deadlock involves transactions: {deadlock.involved_transactions}")
                
                # Resolve the deadlock
                resolved = deadlock_detector.resolve_deadlock(deadlock)
                if resolved:
                    logger.info(f"Resolved deadlock by aborting transaction: {deadlock.victim_transaction}")
                else:
                    logger.error("Failed to resolve deadlock")
        else:
            logger.info("No deadlocks detected")
        
        # Clean up
        deadlock_detector.unregister_transaction(tx1_id)
        deadlock_detector.unregister_transaction(tx2_id)
    
    def demo_performance_monitoring(self):
        """Demonstrate transaction performance monitoring."""
        logger.info("\n=== Demo 6: Transaction Performance Monitoring ===")
        
        transaction_monitor = self.db_manager.get_transaction_monitor()
        
        # Get current performance summary
        summary = transaction_monitor.get_performance_summary()
        logger.info("Current Performance Summary:")
        for key, value in summary.items():
            if isinstance(value, float):
                logger.info(f"  {key}: {value:.2f}")
            else:
                logger.info(f"  {key}: {value}")
        
        # Get optimization suggestions
        suggestions = transaction_monitor.get_optimization_suggestions()
        if suggestions:
            logger.info(f"\nOptimization Suggestions ({len(suggestions)}):")
            for suggestion in suggestions[:3]:  # Show top 3
                logger.info(f"  - {suggestion.description}")
                logger.info(f"    Expected improvement: {suggestion.expected_improvement}")
                logger.info(f"    Priority score: {suggestion.priority_score:.2f}")
        else:
            logger.info("No optimization suggestions at this time")
        
        # Get health check
        health_check = transaction_monitor.get_health_check()
        logger.info(f"\nSystem Health: {health_check.overall_health}")
        logger.info(f"Active Transactions: {health_check.active_transactions}")
        
        if health_check.warnings:
            logger.warning("Warnings:")
            for warning in health_check.warnings:
                logger.warning(f"  - {warning}")
        
        if health_check.recommendations:
            logger.info("Recommendations:")
            for rec in health_check.recommendations:
                logger.info(f"  - {rec}")
    
    def demo_transaction_statistics(self):
        """Demonstrate transaction statistics collection."""
        logger.info("\n=== Demo 7: Transaction Statistics ===")
        
        # Get comprehensive statistics
        stats = self.db_manager.get_transaction_statistics()
        
        logger.info("Transaction Manager Statistics:")
        if 'transaction_manager' in stats:
            tm_stats = stats['transaction_manager']
            for key, value in tm_stats.items():
                if isinstance(value, float):
                    logger.info(f"  {key}: {value:.2f}")
                else:
                    logger.info(f"  {key}: {value}")
        
        logger.info("\nDeadlock Detector Statistics:")
        if 'deadlock_detector' in stats:
            dd_stats = stats['deadlock_detector']
            for key, value in dd_stats.items():
                if isinstance(value, float):
                    logger.info(f"  {key}: {value:.2f}")
                else:
                    logger.info(f"  {key}: {value}")
        
        logger.info("\nPerformance Monitor Statistics:")
        if 'performance_monitor' in stats:
            pm_stats = stats['performance_monitor']
            for key, value in pm_stats.items():
                if isinstance(value, float):
                    logger.info(f"  {key}: {value:.2f}")
                else:
                    logger.info(f"  {key}: {value}")
    
    def run_all_demos(self):
        """Run all demonstration scenarios."""
        logger.info("Starting Visual Editor Core Transaction Management System Demo")
        logger.info("=" * 70)
        
        try:
            # Run all demos
            self.demo_basic_transaction()
            self.demo_nested_transactions()
            self.demo_bulk_operations()
            self.demo_concurrent_transactions()
            self.demo_deadlock_simulation()
            self.demo_performance_monitoring()
            self.demo_transaction_statistics()
            
            logger.info("\n" + "=" * 70)
            logger.info("Demo completed successfully!")
            
        except Exception as e:
            logger.error(f"Demo failed with error: {e}")
            raise
        
        finally:
            # Clean up
            logger.info("Cleaning up resources...")
            self.db_manager.close()


def main():
    """Main function to run the demo."""
    try:
        demo = TransactionSystemDemo()
        demo.run_all_demos()
    except KeyboardInterrupt:
        logger.info("Demo interrupted by user")
    except Exception as e:
        logger.error(f"Demo failed: {e}")
        raise


if __name__ == "__main__":
    main()