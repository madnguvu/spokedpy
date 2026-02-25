#!/usr/bin/env python3
"""
Simple demonstration of the enhanced connection pooling system.
"""

import time
import tempfile
import os
from visual_editor_core.database import (
    ConnectionPool, 
    PoolConfig, 
    DatabaseConfig, 
    DatabaseType,
    SQLiteAdapter
)


def main():
    """Demonstrate enhanced connection pooling features."""
    print("Enhanced Connection Pool Demonstration")
    print("=" * 50)
    
    # Create a temporary SQLite database
    temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
    temp_db.close()
    
    try:
        # Configure the connection pool with enhanced features
        pool_config = PoolConfig(
            min_connections=2,
            max_connections=5,
            connection_timeout=10,
            performance_monitoring_enabled=True,
            detailed_statistics=True,
            auto_scale_enabled=True,
            connection_max_age=3600,
            failed_connection_retry_interval=30
        )
        
        print(f"Pool Configuration:")
        print(f"  Min connections: {pool_config.min_connections}")
        print(f"  Max connections: {pool_config.max_connections}")
        print(f"  Performance monitoring: {pool_config.performance_monitoring_enabled}")
        print(f"  Auto-scaling: {pool_config.auto_scale_enabled}")
        print(f"  Connection max age: {pool_config.connection_max_age}s")
        
        # Create connection pool
        pool = ConnectionPool(pool_config)
        
        # Register SQLite adapter
        sqlite_config = DatabaseConfig(
            database_type=DatabaseType.SQLITE,
            database=temp_db.name
        )
        pool.register_adapter(DatabaseType.SQLITE, SQLiteAdapter, sqlite_config)
        
        print(f"\n=== Basic Connection Operations ===")
        
        # Get some connections
        connections = []
        for i in range(3):
            conn = pool.get_connection(DatabaseType.SQLITE)
            connections.append(conn)
            print(f"Got connection {i+1}: {conn.connection_id[:8]}...")
        
        # Show enhanced pool statistics
        stats = pool.get_pool_statistics()
        print(f"\nEnhanced Pool Statistics:")
        print(f"  Total connections: {stats.total_connections}")
        print(f"  Active connections: {stats.active_connections}")
        print(f"  Idle connections: {stats.idle_connections}")
        print(f"  Pool efficiency: {stats.pool_efficiency:.2f}")
        print(f"  Peak connections: {stats.peak_connections}")
        print(f"  Connection requests: {stats.connection_requests}")
        print(f"  Average wait time: {stats.average_wait_time:.4f}s")
        print(f"  Average connection age: {stats.average_connection_age:.2f}s")
        
        print(f"\n=== Connection Lifecycle Information ===")
        
        # Get detailed lifecycle info for first connection
        if connections:
            conn = connections[0]
            lifecycle_info = pool.get_connection_lifecycle_info(conn.connection_id)
            if lifecycle_info:
                print(f"Connection {conn.connection_id[:8]}... details:")
                print(f"  Database type: {lifecycle_info['database_type']}")
                print(f"  Status: {lifecycle_info['status']}")
                print(f"  Age: {lifecycle_info['age_seconds']:.2f} seconds")
                print(f"  Total uses: {lifecycle_info['total_uses']}")
                print(f"  Performance score: {lifecycle_info['performance_score']:.2f}")
                print(f"  Is healthy: {lifecycle_info['is_healthy']}")
        
        print(f"\n=== Health Monitoring ===")
        
        # Get comprehensive health summary
        health_summary = pool.get_pool_health_summary()
        print(f"Pool Health Summary:")
        print(f"  Overall status: {health_summary['overall_status']}")
        print(f"  Health score: {health_summary['health_score']:.2f}")
        print(f"  Healthy connections: {health_summary['healthy_connections']}")
        print(f"  Unhealthy connections: {health_summary['unhealthy_connections']}")
        print(f"  Pool utilization: {health_summary['pool_utilization']:.2f}")
        print(f"  Connection success rate: {health_summary['connection_success_rate']:.2f}")
        
        if health_summary['recommendations']:
            print(f"  Recommendations:")
            for rec in health_summary['recommendations']:
                print(f"    - {rec}")
        
        print(f"\n=== Performance Monitoring ===")
        
        # Generate some activity for performance metrics
        for conn in connections:
            pool.return_connection(conn)
            time.sleep(0.05)  # Small delay to simulate work
        
        # Get detailed performance metrics
        metrics = pool.get_detailed_performance_metrics()
        print(f"Performance Metrics:")
        print(f"  Success rate: {metrics['success_rate']:.2f}")
        print(f"  Failed connections: {metrics['failed_connections_count']}")
        print(f"  Auto scaling enabled: {metrics['auto_scaling_enabled']}")
        
        # Show performance trends
        trends = metrics['performance_trends']
        print(f"  Performance trends:")
        if 'utilization_trend' in trends:
            print(f"    Utilization trend: {trends['utilization_trend']}")
            print(f"    Response time trend: {trends['response_time_trend']}")
        else:
            print(f"    Trend: {trends.get('trend', 'insufficient_data')}")
        
        print(f"\n=== Connection Pool Optimization ===")
        
        # Test optimization features
        optimization_result = pool.optimize_pool_performance()
        print(f"Optimization Results:")
        print(f"  Optimizations applied: {len(optimization_result['optimizations_applied'])}")
        for opt in optimization_result['optimizations_applied']:
            print(f"    - {opt}")
        
        print(f"  Recommendations: {len(optimization_result['recommendations'])}")
        for rec in optimization_result['recommendations']:
            print(f"    - {rec}")
        
        print(f"\n=== Failure Recovery Test ===")
        
        # Test failure recovery
        test_conn = pool.get_connection(DatabaseType.SQLITE)
        print(f"Created test connection: {test_conn.connection_id[:8]}...")
        
        # Get stats before failure
        before_stats = pool.get_pool_statistics()
        print(f"Before failure - Connections created: {before_stats.connections_created}")
        print(f"Before failure - Connection failures: {before_stats.connection_failures}")
        
        # Simulate failure and recovery
        recovery_success = pool.handle_connection_failure(test_conn)
        print(f"Recovery attempt successful: {recovery_success}")
        
        # Get stats after failure
        after_stats = pool.get_pool_statistics()
        print(f"After failure - Connection failures: {after_stats.connection_failures}")
        print(f"After failure - Connection recoveries: {after_stats.connection_recoveries}")
        
        # Clean up
        pool.close_all_connections()
        print(f"\nConnection pool closed successfully.")
        
        print(f"\n" + "=" * 50)
        print("Enhanced connection pooling demonstration completed!")
        print("Key features demonstrated:")
        print("  ✓ Configurable pool sizes and timeouts")
        print("  ✓ Connection lifecycle management with automatic cleanup")
        print("  ✓ Connection health monitoring and validation")
        print("  ✓ Automatic replacement of failed connections")
        print("  ✓ Enhanced connection pool statistics")
        print("  ✓ Performance monitoring and optimization")
        print("  ✓ Auto-scaling capabilities")
        print("  ✓ Detailed connection metrics and trends")
        
    except Exception as e:
        print(f"Error during demonstration: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Clean up temp file (ignore errors)
        try:
            if os.path.exists(temp_db.name):
                os.unlink(temp_db.name)
        except:
            pass


if __name__ == "__main__":
    main()