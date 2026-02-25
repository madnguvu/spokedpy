#!/usr/bin/env python3
"""
Demonstration of the enhanced connection pooling system.

This script showcases the advanced features of the connection pool including:
- Connection lifecycle management
- Health monitoring and automatic replacement of failed connections
- Performance monitoring and statistics
- Auto-scaling capabilities
- Detailed connection metrics
"""

import time
import tempfile
import os
from datetime import datetime
from visual_editor_core.database import (
    ConnectionPool, 
    PoolConfig, 
    DatabaseConfig, 
    DatabaseType,
    SQLiteAdapter
)


def demonstrate_basic_pooling():
    """Demonstrate basic connection pooling functionality."""
    print("=== Basic Connection Pooling ===")
    
    # Create a temporary SQLite database
    temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
    temp_db.close()
    
    try:
        # Configure the connection pool
        pool_config = PoolConfig(
            min_connections=2,
            max_connections=5,
            connection_timeout=10,
            performance_monitoring_enabled=True,
            detailed_statistics=True
        )
        
        pool = ConnectionPool(pool_config)
        
        # Register SQLite adapter
        sqlite_config = DatabaseConfig(
            database_type=DatabaseType.SQLITE,
            database=temp_db.name
        )
        pool.register_adapter(DatabaseType.SQLITE, SQLiteAdapter, sqlite_config)
        
        # Get some connections
        connections = []
        for i in range(3):
            conn = pool.get_connection(DatabaseType.SQLITE)
            connections.append(conn)
            print(f"Got connection {i+1}: {conn.connection_id}")
        
        # Show pool statistics
        stats = pool.get_pool_statistics()
        print(f"\nPool Statistics:")
        print(f"  Total connections: {stats.total_connections}")
        print(f"  Active connections: {stats.active_connections}")
        print(f"  Idle connections: {stats.idle_connections}")
        print(f"  Pool efficiency: {stats.pool_efficiency:.2f}")
        
        # Return connections
        for conn in connections:
            pool.return_connection(conn)
            print(f"Returned connection: {conn.connection_id}")
        
        pool.close_all_connections()
        
    finally:
        # Try to clean up, but don't fail if file is locked
        try:
            if os.path.exists(temp_db.name):
                os.unlink(temp_db.name)
        except PermissionError:
            pass  # File is locked, OS will clean up eventually


def demonstrate_health_monitoring():
    """Demonstrate connection health monitoring."""
    print("\n=== Connection Health Monitoring ===")
    
    temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
    temp_db.close()
    
    try:
        pool_config = PoolConfig(
            min_connections=1,
            max_connections=3,
            health_check_interval=5,  # Check every 5 seconds
            performance_monitoring_enabled=True
        )
        
        pool = ConnectionPool(pool_config)
        
        sqlite_config = DatabaseConfig(
            database_type=DatabaseType.SQLITE,
            database=temp_db.name
        )
        pool.register_adapter(DatabaseType.SQLITE, SQLiteAdapter, sqlite_config)
        
        # Get a connection
        conn = pool.get_connection(DatabaseType.SQLITE)
        print(f"Created connection: {conn.connection_id}")
        
        # Get connection lifecycle info
        lifecycle_info = pool.get_connection_lifecycle_info(conn.connection_id)
        if lifecycle_info:
            print(f"\nConnection Lifecycle Info:")
            print(f"  Connection ID: {lifecycle_info['connection_id']}")
            print(f"  Database Type: {lifecycle_info['database_type']}")
            print(f"  Status: {lifecycle_info['status']}")
            print(f"  Age: {lifecycle_info['age_seconds']:.2f} seconds")
            print(f"  Total Uses: {lifecycle_info['total_uses']}")
            print(f"  Performance Score: {lifecycle_info['performance_score']:.2f}")
            print(f"  Is Healthy: {lifecycle_info['is_healthy']}")
        
        # Get health summary
        health_summary = pool.get_pool_health_summary()
        print(f"\nPool Health Summary:")
        print(f"  Overall Status: {health_summary['overall_status']}")
        print(f"  Health Score: {health_summary['health_score']:.2f}")
        print(f"  Healthy Connections: {health_summary['healthy_connections']}")
        print(f"  Pool Utilization: {health_summary['pool_utilization']:.2f}")
        
        if health_summary['recommendations']:
            print(f"  Recommendations:")
            for rec in health_summary['recommendations']:
                print(f"    - {rec}")
        
        pool.return_connection(conn)
        pool.close_all_connections()
        
    finally:
        if os.path.exists(temp_db.name):
            os.unlink(temp_db.name)


def demonstrate_performance_monitoring():
    """Demonstrate performance monitoring capabilities."""
    print("\n=== Performance Monitoring ===")
    
    temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
    temp_db.close()
    
    try:
        pool_config = PoolConfig(
            min_connections=2,
            max_connections=4,
            performance_monitoring_enabled=True,
            detailed_statistics=True
        )
        
        pool = ConnectionPool(pool_config)
        
        sqlite_config = DatabaseConfig(
            database_type=DatabaseType.SQLITE,
            database=temp_db.name
        )
        pool.register_adapter(DatabaseType.SQLITE, SQLiteAdapter, sqlite_config)
        
        # Generate some activity
        print("Generating connection activity...")
        for i in range(10):
            conn = pool.get_connection(DatabaseType.SQLITE)
            time.sleep(0.1)  # Simulate work
            pool.return_connection(conn)
        
        # Get detailed performance metrics
        metrics = pool.get_detailed_performance_metrics()
        
        print(f"\nDetailed Performance Metrics:")
        print(f"  Success Rate: {metrics['success_rate']:.2f}")
        print(f"  Failed Connections: {metrics['failed_connections_count']}")
        print(f"  Auto Scaling Enabled: {metrics['auto_scaling_enabled']}")
        
        # Show performance trends
        trends = metrics['performance_trends']
        print(f"\nPerformance Trends:")
        print(f"  Utilization Trend: {trends['utilization_trend']}")
        print(f"  Response Time Trend: {trends['response_time_trend']}")
        
        # Show connection performance
        if metrics['connection_performance']:
            print(f"\nConnection Performance:")
            for conn_id, perf in metrics['connection_performance'].items():
                print(f"  Connection {conn_id[:8]}...")
                print(f"    Age: {perf['age_seconds']:.2f} seconds")
                print(f"    Total Uses: {perf['total_uses']}")
                print(f"    Performance Score: {perf['performance_score']:.2f}")
        
        pool.close_all_connections()
        
    finally:
        if os.path.exists(temp_db.name):
            os.unlink(temp_db.name)


def demonstrate_failure_recovery():
    """Demonstrate automatic failure recovery."""
    print("\n=== Failure Recovery ===")
    
    temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
    temp_db.close()
    
    try:
        pool_config = PoolConfig(
            min_connections=1,
            max_connections=3,
            failed_connection_retry_interval=2,  # Retry every 2 seconds
            performance_monitoring_enabled=True
        )
        
        pool = ConnectionPool(pool_config)
        
        sqlite_config = DatabaseConfig(
            database_type=DatabaseType.SQLITE,
            database=temp_db.name
        )
        pool.register_adapter(DatabaseType.SQLITE, SQLiteAdapter, sqlite_config)
        
        # Get a connection
        conn = pool.get_connection(DatabaseType.SQLITE)
        print(f"Created connection: {conn.connection_id}")
        
        # Get initial statistics
        initial_stats = pool.get_pool_statistics()
        print(f"Initial connections created: {initial_stats.connections_created}")
        print(f"Initial connection failures: {initial_stats.connection_failures}")
        
        # Simulate connection failure
        print(f"\nSimulating connection failure...")
        recovery_success = pool.handle_connection_failure(conn)
        print(f"Recovery attempt successful: {recovery_success}")
        
        # Check updated statistics
        updated_stats = pool.get_pool_statistics()
        print(f"Connection failures: {updated_stats.connection_failures}")
        print(f"Connection recoveries: {updated_stats.connection_recoveries}")
        print(f"Total connections: {updated_stats.total_connections}")
        
        pool.close_all_connections()
        
    finally:
        if os.path.exists(temp_db.name):
            os.unlink(temp_db.name)


def demonstrate_auto_scaling():
    """Demonstrate auto-scaling capabilities."""
    print("\n=== Auto-Scaling ===")
    
    temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
    temp_db.close()
    
    try:
        pool_config = PoolConfig(
            min_connections=2,
            max_connections=6,
            auto_scale_enabled=True,
            scale_up_threshold=0.8,
            scale_down_threshold=0.3,
            performance_monitoring_enabled=True
        )
        
        pool = ConnectionPool(pool_config)
        
        sqlite_config = DatabaseConfig(
            database_type=DatabaseType.SQLITE,
            database=temp_db.name
        )
        pool.register_adapter(DatabaseType.SQLITE, SQLiteAdapter, sqlite_config)
        
        print(f"Auto-scaling enabled with thresholds:")
        print(f"  Scale up threshold: {pool_config.scale_up_threshold}")
        print(f"  Scale down threshold: {pool_config.scale_down_threshold}")
        print(f"  Min connections: {pool_config.min_connections}")
        print(f"  Max connections: {pool_config.max_connections}")
        
        # Get initial metrics
        initial_metrics = pool.get_detailed_performance_metrics()
        print(f"\nInitial auto-scaling status: {initial_metrics['auto_scaling_enabled']}")
        
        # Simulate high load
        connections = []
        print(f"\nSimulating high load...")
        for i in range(4):
            conn = pool.get_connection(DatabaseType.SQLITE)
            connections.append(conn)
            stats = pool.get_pool_statistics()
            print(f"  Connection {i+1}: Utilization = {stats.pool_efficiency:.2f}")
        
        # Return connections
        for conn in connections:
            pool.return_connection(conn)
        
        pool.close_all_connections()
        
    finally:
        if os.path.exists(temp_db.name):
            os.unlink(temp_db.name)


def main():
    """Run all demonstrations."""
    print("Enhanced Connection Pool Demonstration")
    print("=" * 50)
    
    try:
        demonstrate_basic_pooling()
        demonstrate_health_monitoring()
        demonstrate_performance_monitoring()
        demonstrate_failure_recovery()
        demonstrate_auto_scaling()
        
        print("\n" + "=" * 50)
        print("All demonstrations completed successfully!")
        
    except Exception as e:
        print(f"Error during demonstration: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()