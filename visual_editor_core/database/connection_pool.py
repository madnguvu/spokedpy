"""
Database connection pool for managing database connections efficiently.
"""

import threading
import time
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from queue import Queue, Empty, Full
from dataclasses import dataclass, field

from .models import DatabaseConnection, DatabaseType, ConnectionStatus, HealthMetrics
from .exceptions import ConnectionError, DatabaseError


@dataclass
class PoolStatistics:
    """Connection pool statistics."""
    total_connections: int = 0
    active_connections: int = 0
    idle_connections: int = 0
    failed_connections: int = 0
    pool_size: int = 0
    max_connections: int = 0
    connections_created: int = 0
    connections_destroyed: int = 0
    connection_requests: int = 0
    connection_timeouts: int = 0
    average_wait_time: float = 0.0
    peak_connections: int = 0
    connection_failures: int = 0
    connection_recoveries: int = 0
    health_check_failures: int = 0
    stale_connections_cleaned: int = 0
    pool_efficiency: float = 0.0  # active_connections / total_connections
    average_connection_age: float = 0.0
    last_updated: datetime = field(default_factory=datetime.now)


@dataclass
class PoolConfig:
    """Connection pool configuration."""
    min_connections: int = 2
    max_connections: int = 10
    connection_timeout: int = 30
    idle_timeout: int = 300
    max_retries: int = 3
    retry_delay: float = 1.0
    health_check_interval: int = 60
    cleanup_interval: int = 120
    connection_max_age: int = 3600  # Maximum age of a connection in seconds
    failed_connection_retry_interval: int = 30  # Retry failed connections every 30 seconds
    performance_monitoring_enabled: bool = True
    detailed_statistics: bool = True
    auto_scale_enabled: bool = False  # Automatically scale pool based on demand
    scale_up_threshold: float = 0.8  # Scale up when 80% of connections are active
    scale_down_threshold: float = 0.3  # Scale down when less than 30% are active


class ConnectionPool:
    """Database connection pool manager."""
    
    def __init__(self, config: PoolConfig = None):
        self.config = config or PoolConfig()
        self._connections: Dict[str, DatabaseConnection] = {}
        self._available_connections: Queue = Queue(maxsize=self.config.max_connections)
        self._failed_connections: Dict[str, datetime] = {}  # Track failed connections for retry
        self._connection_metrics: Dict[str, Dict[str, Any]] = {}  # Per-connection metrics
        self._lock = threading.RLock()
        self._statistics = PoolStatistics()
        self._running = False
        self._cleanup_thread = None
        self._health_check_thread = None
        self._performance_monitor_thread = None
        self._adapters: Dict[DatabaseType, Any] = {}
        self._performance_history: List[Dict[str, Any]] = []  # Store performance snapshots
        
        # Start background threads
        self._start_background_threads()
    
    def register_adapter(self, database_type: DatabaseType, adapter_class: Any, adapter_config: Any):
        """Register a database adapter with the pool."""
        with self._lock:
            self._adapters[database_type] = {
                'class': adapter_class,
                'config': adapter_config
            }
    
    def get_connection(self, database_type: DatabaseType = None, timeout: int = None) -> DatabaseConnection:
        """Get a connection from the pool with enhanced tracking."""
        timeout = timeout or self.config.connection_timeout
        start_time = time.time()
        
        with self._lock:
            self._statistics.connection_requests += 1
        
        try:
            # Try to get an available connection
            connection = self._get_available_connection(database_type, timeout)
            
            if connection and self._validate_connection(connection):
                connection.mark_used()
                self._track_connection_usage(connection, start_time)
                return connection
            
            # Create new connection if pool not full
            if self._can_create_connection():
                connection = self._create_connection(database_type)
                if connection:
                    connection.mark_used()
                    self._track_connection_usage(connection, start_time)
                    return connection
            
            # Wait for available connection
            connection = self._wait_for_connection(timeout - (time.time() - start_time))
            if connection:
                connection.mark_used()
                self._track_connection_usage(connection, start_time)
                return connection
            
            # Timeout occurred
            with self._lock:
                self._statistics.connection_timeouts += 1
            
            raise ConnectionError("Connection pool timeout", str(database_type))
            
        except Exception as e:
            wait_time = time.time() - start_time
            self._update_wait_time_statistics(wait_time)
            raise e
    
    def _track_connection_usage(self, connection: DatabaseConnection, start_time: float):
        """Track connection usage for performance monitoring."""
        wait_time = time.time() - start_time
        self._update_wait_time_statistics(wait_time)
        
        with self._lock:
            if connection.connection_id in self._connection_metrics:
                metrics = self._connection_metrics[connection.connection_id]
                metrics['total_uses'] += 1
                
                # Update performance score based on response time
                if wait_time < 0.1:  # Very fast
                    metrics['performance_score'] = min(1.0, metrics['performance_score'] + 0.01)
                elif wait_time > 1.0:  # Slow
                    metrics['performance_score'] = max(0.1, metrics['performance_score'] - 0.05)
    
    def return_connection(self, connection: DatabaseConnection) -> bool:
        """Return a connection to the pool with enhanced tracking."""
        try:
            with self._lock:
                if connection.connection_id in self._connections:
                    # Update connection usage time
                    if connection.connection_id in self._connection_metrics:
                        metrics = self._connection_metrics[connection.connection_id]
                        usage_time = (datetime.now() - connection.last_used).total_seconds()
                        metrics['total_time_active'] += usage_time
                    
                    if self._validate_connection(connection):
                        # Return to available pool
                        try:
                            self._available_connections.put_nowait(connection)
                            return True
                        except Full:
                            # Pool is full, close connection
                            self._close_connection(connection)
                            return True
                    else:
                        # Connection is invalid, remove it
                        self._remove_connection(connection)
                        return True
                
                return False
        except Exception:
            return False
    
    def close_connection(self, connection: DatabaseConnection) -> bool:
        """Close a specific connection."""
        try:
            with self._lock:
                return self._close_connection(connection)
        except Exception:
            return False
    
    def resize_pool(self, new_size: int) -> bool:
        """Resize the connection pool."""
        try:
            with self._lock:
                old_size = self.config.max_connections
                self.config.max_connections = new_size
                
                if new_size < old_size:
                    # Reduce pool size by closing excess connections
                    excess = old_size - new_size
                    closed = 0
                    
                    # Close idle connections first
                    while closed < excess and not self._available_connections.empty():
                        try:
                            connection = self._available_connections.get_nowait()
                            self._close_connection(connection)
                            closed += 1
                        except Empty:
                            break
                
                self._update_statistics()
                return True
        except Exception:
            return False
    
    def get_pool_statistics(self) -> PoolStatistics:
        """Get current pool statistics."""
        with self._lock:
            self._update_statistics()
            return self._statistics
    
    def test_connections(self) -> List[Dict[str, Any]]:
        """Test all connections in the pool."""
        results = []
        
        with self._lock:
            for connection in self._connections.values():
                test_result = {
                    'connection_id': connection.connection_id,
                    'database_type': connection.database_type.value,
                    'is_healthy': self._validate_connection(connection),
                    'last_used': connection.last_used,
                    'status': connection.status.value
                }
                results.append(test_result)
        
        return results
    
    def close_all_connections(self) -> bool:
        """Close all connections in the pool."""
        try:
            self._running = False
            
            # Stop background threads
            threads_to_stop = [
                self._cleanup_thread,
                self._health_check_thread,
                self._performance_monitor_thread
            ]
            
            for thread in threads_to_stop:
                if thread and thread.is_alive():
                    thread.join(timeout=5)
            
            with self._lock:
                # Close all connections
                for connection in list(self._connections.values()):
                    self._close_connection(connection)
                
                # Clear queues
                while not self._available_connections.empty():
                    try:
                        self._available_connections.get_nowait()
                    except Empty:
                        break
                
                self._connections.clear()
                self._connection_metrics.clear()
                self._failed_connections.clear()
                self._performance_history.clear()
                self._update_statistics()
            
            return True
        except Exception:
            return False
    
    def configure_pool(self, config: PoolConfig) -> bool:
        """Configure the connection pool."""
        try:
            with self._lock:
                self.config = config
                
                # Resize pool if necessary
                if len(self._connections) > config.max_connections:
                    self.resize_pool(config.max_connections)
            
            return True
        except Exception:
            return False
    
    def monitor_connection_health(self) -> Dict[str, Any]:
        """Monitor connection health."""
        health_report = {
            'timestamp': datetime.now(),
            'total_connections': 0,
            'healthy_connections': 0,
            'unhealthy_connections': 0,
            'connection_details': []
        }
        
        with self._lock:
            for connection in self._connections.values():
                health_report['total_connections'] += 1
                
                is_healthy = self._validate_connection(connection)
                if is_healthy:
                    health_report['healthy_connections'] += 1
                else:
                    health_report['unhealthy_connections'] += 1
                
                health_report['connection_details'].append({
                    'connection_id': connection.connection_id,
                    'database_type': connection.database_type.value,
                    'is_healthy': is_healthy,
                    'last_used': connection.last_used,
                    'age': datetime.now() - connection.created_at
                })
        
        return health_report
    
    def handle_connection_failure(self, connection: DatabaseConnection) -> bool:
        """Handle connection failure with automatic replacement."""
        try:
            with self._lock:
                # Mark connection as failed
                connection.status = ConnectionStatus.FAILED
                self._failed_connections[connection.connection_id] = datetime.now()
                self._statistics.connection_failures += 1
                
                # Remove from pool
                self._remove_connection(connection)
                
                # Try to create replacement connection immediately
                replacement_created = False
                if self._can_create_connection():
                    new_connection = self._create_connection(connection.database_type)
                    if new_connection:
                        replacement_created = True
                        self._statistics.connection_recoveries += 1
                
                # If we couldn't create a replacement immediately, schedule retry
                if not replacement_created:
                    self._schedule_connection_retry(connection.database_type)
                
                return replacement_created
        except Exception:
            return False
    
    def _schedule_connection_retry(self, database_type: DatabaseType):
        """Schedule a retry for creating a new connection."""
        # This will be handled by the health check worker
        pass
    
    def _retry_failed_connections(self):
        """Retry creating connections for failed ones."""
        current_time = datetime.now()
        retry_interval = timedelta(seconds=self.config.failed_connection_retry_interval)
        
        with self._lock:
            # Find failed connections that are ready for retry
            failed_to_retry = []
            for conn_id, fail_time in self._failed_connections.items():
                if current_time - fail_time >= retry_interval:
                    failed_to_retry.append(conn_id)
            
            # Remove old failed connection records and try to create new ones
            for conn_id in failed_to_retry:
                del self._failed_connections[conn_id]
                
                # Try to create a new connection if we're below max
                if self._can_create_connection():
                    # Try each database type
                    for db_type in self._adapters.keys():
                        new_connection = self._create_connection(db_type)
                        if new_connection:
                            self._statistics.connection_recoveries += 1
                            break
    
    def optimize_pool_performance(self) -> Dict[str, Any]:
        """Optimize pool performance."""
        optimization_results = {
            'optimizations_applied': [],
            'performance_improvement': 0.0,
            'recommendations': []
        }
        
        try:
            with self._lock:
                # Clean up stale connections
                cleaned = self._cleanup_stale_connections()
                if cleaned > 0:
                    optimization_results['optimizations_applied'].append(f"Cleaned {cleaned} stale connections")
                
                # Adjust pool size based on usage patterns
                stats = self._statistics
                if stats.connection_timeouts > 0 and len(self._connections) < self.config.max_connections:
                    optimization_results['recommendations'].append("Consider increasing pool size")
                
                if stats.idle_connections > self.config.max_connections * 0.5:
                    optimization_results['recommendations'].append("Consider decreasing pool size")
                
                # Update statistics
                self._update_statistics()
        
        except Exception as e:
            optimization_results['error'] = str(e)
        
        return optimization_results
    
    def _get_available_connection(self, database_type: DatabaseType, timeout: int) -> Optional[DatabaseConnection]:
        """Get an available connection from the pool."""
        try:
            connection = self._available_connections.get(timeout=min(timeout, 1))
            
            # Check if connection matches requested type
            if database_type and connection.database_type != database_type:
                # Return connection and try again
                self._available_connections.put_nowait(connection)
                return None
            
            return connection
        except Empty:
            return None
    
    def _can_create_connection(self) -> bool:
        """Check if we can create a new connection."""
        with self._lock:
            return len(self._connections) < self.config.max_connections
    
    def _create_connection(self, database_type: DatabaseType) -> Optional[DatabaseConnection]:
        """Create a new database connection."""
        if not database_type or database_type not in self._adapters:
            # Use first available adapter
            if self._adapters:
                database_type = next(iter(self._adapters.keys()))
            else:
                return None
        
        try:
            adapter_info = self._adapters[database_type]
            adapter = adapter_info['class'](adapter_info['config'])
            connection = adapter.connect()
            
            with self._lock:
                self._connections[connection.connection_id] = connection
                self._statistics.connections_created += 1
                self._update_statistics()
            
            return connection
        except Exception:
            return None
    
    def _wait_for_connection(self, timeout: float) -> Optional[DatabaseConnection]:
        """Wait for an available connection."""
        if timeout <= 0:
            return None
        
        try:
            return self._available_connections.get(timeout=timeout)
        except Empty:
            return None
    
    def _create_connection(self, database_type: DatabaseType) -> Optional[DatabaseConnection]:
        """Create a new database connection with enhanced lifecycle tracking."""
        if not database_type or database_type not in self._adapters:
            # Use first available adapter
            if self._adapters:
                database_type = next(iter(self._adapters.keys()))
            else:
                return None
        
        try:
            adapter_info = self._adapters[database_type]
            adapter = adapter_info['class'](adapter_info['config'])
            connection = adapter.connect()
            
            with self._lock:
                self._connections[connection.connection_id] = connection
                self._statistics.connections_created += 1
                
                # Initialize connection metrics
                self._connection_metrics[connection.connection_id] = {
                    'created_at': datetime.now(),
                    'total_uses': 0,
                    'total_time_active': 0.0,
                    'last_health_check': datetime.now(),
                    'health_check_failures': 0,
                    'performance_score': 1.0
                }
                
                # Update peak connections
                if len(self._connections) > self._statistics.peak_connections:
                    self._statistics.peak_connections = len(self._connections)
                
                self._update_statistics()
            
            return connection
        except Exception:
            return None
    
    def _validate_connection(self, connection: DatabaseConnection) -> bool:
        """Enhanced connection validation with detailed health checking."""
        try:
            if not connection or connection.status != ConnectionStatus.CONNECTED:
                return False
            
            current_time = datetime.now()
            
            # Check if connection is too old (max age)
            max_age = timedelta(seconds=self.config.connection_max_age)
            if current_time - connection.created_at > max_age:
                return False
            
            # Check if connection has been idle too long
            idle_timeout = timedelta(seconds=self.config.idle_timeout)
            if current_time - connection.last_used > idle_timeout:
                return False
            
            # Enhanced health check with adapter-specific validation
            # Only perform detailed health check periodically to avoid overhead
            if connection.connection_id in self._connection_metrics:
                metrics = self._connection_metrics[connection.connection_id]
                last_health_check = metrics.get('last_health_check', current_time)
                
                # Only do detailed health check every 30 seconds
                if (current_time - last_health_check).total_seconds() > 30:
                    if connection.database_type in self._adapters:
                        try:
                            adapter_info = self._adapters[connection.database_type]
                            adapter = adapter_info['class'](adapter_info['config'])
                            
                            # Perform a simple query to test connection
                            test_result = adapter.execute_query("SELECT 1")
                            if not test_result.success:
                                return False
                            
                            # Update connection metrics
                            metrics['last_health_check'] = current_time
                            metrics['health_check_failures'] = 0
                            
                        except Exception:
                            # Health check failed
                            metrics['health_check_failures'] += 1
                            self._statistics.health_check_failures += 1
                            
                            # If too many health check failures, consider connection unhealthy
                            if metrics['health_check_failures'] > 3:
                                return False
            
            return True
        except Exception:
            return False
    
    def _close_connection(self, connection: DatabaseConnection) -> bool:
        """Close a database connection."""
        try:
            # Get adapter and close connection
            if connection.database_type in self._adapters:
                adapter_info = self._adapters[connection.database_type]
                adapter = adapter_info['class'](adapter_info['config'])
                adapter.disconnect()
            
            # Remove from pool
            self._remove_connection(connection)
            return True
        except Exception:
            return False
    
    def _remove_connection(self, connection: DatabaseConnection) -> bool:
        """Remove connection from pool with enhanced cleanup."""
        try:
            with self._lock:
                if connection.connection_id in self._connections:
                    del self._connections[connection.connection_id]
                    
                    # Clean up connection metrics
                    if connection.connection_id in self._connection_metrics:
                        del self._connection_metrics[connection.connection_id]
                    
                    # Remove from failed connections if present
                    if connection.connection_id in self._failed_connections:
                        del self._failed_connections[connection.connection_id]
                    
                    self._statistics.connections_destroyed += 1
                    self._update_statistics()
                    return True
                return False
        except Exception:
            return False
    
    def _update_statistics(self):
        """Update pool statistics with enhanced metrics."""
        self._statistics.total_connections = len(self._connections)
        self._statistics.idle_connections = self._available_connections.qsize()
        self._statistics.active_connections = self._statistics.total_connections - self._statistics.idle_connections
        self._statistics.pool_size = self.config.max_connections
        self._statistics.max_connections = self.config.max_connections
        self._statistics.last_updated = datetime.now()
        
        # Calculate pool efficiency
        if self._statistics.total_connections > 0:
            self._statistics.pool_efficiency = self._statistics.active_connections / self._statistics.total_connections
        else:
            self._statistics.pool_efficiency = 0.0
        
        # Calculate average connection age
        if self._connection_metrics:
            current_time = datetime.now()
            total_age = sum(
                (current_time - metrics['created_at']).total_seconds()
                for metrics in self._connection_metrics.values()
            )
            self._statistics.average_connection_age = total_age / len(self._connection_metrics)
        else:
            self._statistics.average_connection_age = 0.0
        
        # Count failed connections
        self._statistics.failed_connections = len(self._failed_connections)
    
    def get_detailed_performance_metrics(self) -> Dict[str, Any]:
        """Get detailed performance metrics for the connection pool."""
        with self._lock:
            self._update_statistics()
            
            # Calculate performance metrics
            total_requests = self._statistics.connection_requests
            success_rate = 1.0 - (self._statistics.connection_timeouts / max(total_requests, 1))
            
            # Connection utilization over time
            utilization_history = []
            for snapshot in self._performance_history[-10:]:  # Last 10 snapshots
                utilization_history.append({
                    'timestamp': snapshot['timestamp'],
                    'utilization': snapshot['active_connections'] / max(snapshot['total_connections'], 1)
                })
            
            # Per-connection performance
            connection_performance = {}
            for conn_id, metrics in self._connection_metrics.items():
                if conn_id in self._connections:
                    connection = self._connections[conn_id]
                    connection_performance[conn_id] = {
                        'database_type': connection.database_type.value,
                        'age_seconds': (datetime.now() - metrics['created_at']).total_seconds(),
                        'total_uses': metrics['total_uses'],
                        'average_response_time': metrics.get('average_response_time', 0.0),
                        'health_check_failures': metrics['health_check_failures'],
                        'performance_score': metrics['performance_score'],
                        'last_used': connection.last_used.isoformat()
                    }
            
            return {
                'pool_statistics': self._statistics,
                'success_rate': success_rate,
                'utilization_history': utilization_history,
                'connection_performance': connection_performance,
                'failed_connections_count': len(self._failed_connections),
                'auto_scaling_enabled': self.config.auto_scale_enabled,
                'performance_trends': self._calculate_performance_trends()
            }
    
    def _calculate_performance_trends(self) -> Dict[str, Any]:
        """Calculate performance trends from historical data."""
        if len(self._performance_history) < 2:
            return {'trend': 'insufficient_data'}
        
        recent_snapshots = self._performance_history[-5:]  # Last 5 snapshots
        
        # Calculate trends
        utilization_trend = []
        response_time_trend = []
        
        for snapshot in recent_snapshots:
            total_conns = max(snapshot['total_connections'], 1)
            utilization_trend.append(snapshot['active_connections'] / total_conns)
            response_time_trend.append(snapshot.get('average_response_time', 0.0))
        
        # Simple trend calculation (positive = increasing, negative = decreasing)
        utilization_change = utilization_trend[-1] - utilization_trend[0] if len(utilization_trend) > 1 else 0
        response_time_change = response_time_trend[-1] - response_time_trend[0] if len(response_time_trend) > 1 else 0
        
        return {
            'utilization_trend': 'increasing' if utilization_change > 0.1 else 'decreasing' if utilization_change < -0.1 else 'stable',
            'response_time_trend': 'increasing' if response_time_change > 0.1 else 'decreasing' if response_time_change < -0.1 else 'stable',
            'utilization_change': utilization_change,
            'response_time_change': response_time_change
        }
    
    def _update_wait_time_statistics(self, wait_time: float):
        """Update wait time statistics."""
        with self._lock:
            current_avg = self._statistics.average_wait_time
            requests = self._statistics.connection_requests
            
            if requests > 1:
                # Calculate running average
                self._statistics.average_wait_time = ((current_avg * (requests - 1)) + wait_time) / requests
            else:
                self._statistics.average_wait_time = wait_time
    
    def _start_background_threads(self):
        """Start background maintenance threads."""
        self._running = True
        
        # Cleanup thread
        self._cleanup_thread = threading.Thread(target=self._cleanup_worker, daemon=True)
        self._cleanup_thread.start()
        
        # Health check thread
        self._health_check_thread = threading.Thread(target=self._health_check_worker, daemon=True)
        self._health_check_thread.start()
        
        # Performance monitoring thread (if enabled)
        if self.config.performance_monitoring_enabled:
            self._performance_monitor_thread = threading.Thread(target=self._performance_monitor_worker, daemon=True)
            self._performance_monitor_thread.start()
    
    def _cleanup_worker(self):
        """Enhanced background worker for cleaning up stale connections."""
        while self._running:
            try:
                time.sleep(self.config.cleanup_interval)
                if self._running:
                    cleaned = self._cleanup_stale_connections()
                    if cleaned > 0:
                        with self._lock:
                            self._statistics.stale_connections_cleaned += cleaned
                    
                    # Also clean up old performance history
                    self._cleanup_performance_history()
                    
                    # Auto-scaling logic
                    if self.config.auto_scale_enabled:
                        self._auto_scale_pool()
                        
            except Exception:
                pass
    
    def _health_check_worker(self):
        """Enhanced background worker for health checking connections."""
        while self._running:
            try:
                time.sleep(self.config.health_check_interval)
                if self._running:
                    self._perform_health_checks()
                    self._retry_failed_connections()
            except Exception:
                pass
    
    def _performance_monitor_worker(self):
        """Background worker for performance monitoring."""
        while self._running:
            try:
                time.sleep(30)  # Monitor every 30 seconds
                if self._running:
                    self._capture_performance_snapshot()
            except Exception:
                pass
    
    def _capture_performance_snapshot(self):
        """Capture a performance snapshot for trend analysis."""
        with self._lock:
            snapshot = {
                'timestamp': datetime.now(),
                'total_connections': len(self._connections),
                'active_connections': len(self._connections) - self._available_connections.qsize(),
                'idle_connections': self._available_connections.qsize(),
                'failed_connections': len(self._failed_connections),
                'connection_requests': self._statistics.connection_requests,
                'connection_timeouts': self._statistics.connection_timeouts,
                'average_wait_time': self._statistics.average_wait_time,
                'pool_efficiency': self._statistics.pool_efficiency
            }
            
            self._performance_history.append(snapshot)
            
            # Keep only last 100 snapshots to prevent memory growth
            if len(self._performance_history) > 100:
                self._performance_history = self._performance_history[-100:]
    
    def _cleanup_performance_history(self):
        """Clean up old performance history data."""
        cutoff_time = datetime.now() - timedelta(hours=24)  # Keep 24 hours of history
        
        self._performance_history = [
            snapshot for snapshot in self._performance_history
            if snapshot['timestamp'] > cutoff_time
        ]
    
    def _auto_scale_pool(self):
        """Automatically scale the pool based on demand."""
        if not self.config.auto_scale_enabled:
            return
        
        with self._lock:
            current_utilization = self._statistics.pool_efficiency
            current_max = self.config.max_connections
            
            # Scale up if utilization is high
            if current_utilization > self.config.scale_up_threshold and current_max < 50:  # Cap at 50
                new_max = min(current_max + 2, 50)
                self.config.max_connections = new_max
                
            # Scale down if utilization is low
            elif current_utilization < self.config.scale_down_threshold and current_max > self.config.min_connections:
                new_max = max(current_max - 1, self.config.min_connections)
                self.resize_pool(new_max)
    
    def _cleanup_stale_connections(self) -> int:
        """Clean up stale connections."""
        cleaned = 0
        
        with self._lock:
            stale_connections = []
            max_age = timedelta(seconds=self.config.idle_timeout)
            
            for connection in self._connections.values():
                if datetime.now() - connection.last_used > max_age:
                    stale_connections.append(connection)
            
            for connection in stale_connections:
                if self._close_connection(connection):
                    cleaned += 1
        
        return cleaned
    
    def _perform_health_checks(self):
        """Perform health checks on all connections."""
        with self._lock:
            unhealthy_connections = []
            
            for connection in self._connections.values():
                if not self._validate_connection(connection):
                    unhealthy_connections.append(connection)
            
            for connection in unhealthy_connections:
                self.handle_connection_failure(connection)
    
    def get_connection_lifecycle_info(self, connection_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed lifecycle information for a specific connection."""
        with self._lock:
            if connection_id not in self._connections:
                return None
            
            connection = self._connections[connection_id]
            metrics = self._connection_metrics.get(connection_id, {})
            
            return {
                'connection_id': connection_id,
                'database_type': connection.database_type.value,
                'status': connection.status.value,
                'created_at': connection.created_at.isoformat(),
                'last_used': connection.last_used.isoformat(),
                'age_seconds': (datetime.now() - connection.created_at).total_seconds(),
                'idle_time_seconds': (datetime.now() - connection.last_used).total_seconds(),
                'total_uses': metrics.get('total_uses', 0),
                'total_time_active': metrics.get('total_time_active', 0.0),
                'health_check_failures': metrics.get('health_check_failures', 0),
                'performance_score': metrics.get('performance_score', 1.0),
                'is_healthy': self._validate_connection(connection)
            }
    
    def get_pool_health_summary(self) -> Dict[str, Any]:
        """Get a comprehensive health summary of the connection pool."""
        with self._lock:
            self._update_statistics()
            
            healthy_connections = 0
            unhealthy_connections = 0
            
            for connection in self._connections.values():
                if self._validate_connection(connection):
                    healthy_connections += 1
                else:
                    unhealthy_connections += 1
            
            # Calculate health score (0.0 to 1.0)
            total_connections = len(self._connections)
            if total_connections > 0:
                health_score = healthy_connections / total_connections
            else:
                health_score = 1.0 if total_connections == 0 else 0.0
            
            # Determine overall status
            if health_score >= 0.9:
                overall_status = "excellent"
            elif health_score >= 0.7:
                overall_status = "good"
            elif health_score >= 0.5:
                overall_status = "fair"
            else:
                overall_status = "poor"
            
            return {
                'overall_status': overall_status,
                'health_score': health_score,
                'total_connections': total_connections,
                'healthy_connections': healthy_connections,
                'unhealthy_connections': unhealthy_connections,
                'failed_connections': len(self._failed_connections),
                'pool_utilization': self._statistics.pool_efficiency,
                'average_wait_time': self._statistics.average_wait_time,
                'connection_success_rate': 1.0 - (self._statistics.connection_timeouts / max(self._statistics.connection_requests, 1)),
                'auto_scaling_active': self.config.auto_scale_enabled,
                'performance_monitoring_active': self.config.performance_monitoring_enabled,
                'recommendations': self._generate_health_recommendations()
            }
    
    def _generate_health_recommendations(self) -> List[str]:
        """Generate health and performance recommendations."""
        recommendations = []
        
        # Check pool utilization
        if self._statistics.pool_efficiency > 0.9:
            recommendations.append("Consider increasing max_connections - pool utilization is very high")
        elif self._statistics.pool_efficiency < 0.3:
            recommendations.append("Consider decreasing max_connections - pool utilization is low")
        
        # Check timeout rate
        timeout_rate = self._statistics.connection_timeouts / max(self._statistics.connection_requests, 1)
        if timeout_rate > 0.05:  # More than 5% timeouts
            recommendations.append("High timeout rate detected - consider increasing connection_timeout or max_connections")
        
        # Check failed connections
        if len(self._failed_connections) > 0:
            recommendations.append(f"{len(self._failed_connections)} failed connections need attention")
        
        # Check health check failures
        if self._statistics.health_check_failures > 10:
            recommendations.append("High number of health check failures - investigate connection stability")
        
        # Check average wait time
        if self._statistics.average_wait_time > 1.0:
            recommendations.append("High average wait time - consider optimizing connection creation or increasing pool size")
        
        # Auto-scaling recommendation
        if not self.config.auto_scale_enabled and (self._statistics.pool_efficiency > 0.8 or self._statistics.pool_efficiency < 0.4):
            recommendations.append("Consider enabling auto-scaling for better resource utilization")
        
        return recommendations