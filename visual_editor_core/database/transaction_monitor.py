"""
Transaction performance monitoring and analysis system.
"""

import logging
import threading
import time
import statistics
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum

from .transaction_models import (
    TransactionStatistics,
    TransactionPerformanceProfile,
    TransactionHealthCheck,
    TransactionResourceUsage,
    TransactionOptimizationSuggestion,
    TransactionType
)
from .models import DatabaseType


class PerformanceAlert(Enum):
    """Types of performance alerts."""
    SLOW_TRANSACTION = "slow_transaction"
    HIGH_ROLLBACK_RATE = "high_rollback_rate"
    FREQUENT_DEADLOCKS = "frequent_deadlocks"
    RESOURCE_EXHAUSTION = "resource_exhaustion"
    CONNECTION_POOL_FULL = "connection_pool_full"
    LONG_RUNNING_TRANSACTION = "long_running_transaction"


@dataclass
class PerformanceThresholds:
    """Configurable performance thresholds."""
    slow_transaction_seconds: float = 10.0
    long_running_transaction_seconds: float = 300.0  # 5 minutes
    high_rollback_rate_percent: float = 20.0
    frequent_deadlocks_per_hour: int = 10
    connection_pool_utilization_percent: float = 90.0
    memory_usage_mb: float = 1024.0
    cpu_usage_percent: float = 80.0
    disk_io_mb_per_second: float = 100.0


class TransactionMonitor:
    """
    Comprehensive transaction performance monitoring system.
    
    This class monitors transaction performance, detects anomalies,
    generates alerts, and provides optimization suggestions.
    """
    
    def __init__(self, 
                 monitoring_interval: float = 5.0,
                 history_retention_hours: int = 24,
                 thresholds: Optional[PerformanceThresholds] = None):
        self.monitoring_interval = monitoring_interval
        self.history_retention_hours = history_retention_hours
        self.thresholds = thresholds or PerformanceThresholds()
        self.logger = logging.getLogger(__name__)
        
        # Performance data storage
        self.transaction_history: deque = deque(maxlen=10000)  # Recent transactions
        self.performance_profiles: Dict[str, TransactionPerformanceProfile] = {}
        self.resource_usage_history: deque = deque(maxlen=1000)
        self.alert_history: deque = deque(maxlen=1000)
        
        # Real-time metrics
        self.current_metrics = {
            'active_transactions': 0,
            'transactions_per_second': 0.0,
            'average_response_time': 0.0,
            'success_rate': 100.0,
            'rollback_rate': 0.0,
            'deadlock_rate': 0.0,
            'connection_pool_utilization': 0.0,
            'cpu_usage': 0.0,
            'memory_usage': 0.0
        }
        
        # Aggregated statistics
        self.hourly_stats: Dict[str, Dict[str, Any]] = defaultdict(dict)
        self.daily_stats: Dict[str, Dict[str, Any]] = defaultdict(dict)
        
        # Thread safety
        self.lock = threading.RLock()
        
        # Monitoring control
        self._monitoring_enabled = False
        self._monitoring_thread: Optional[threading.Thread] = None
        
        # Alert callbacks
        self.alert_callbacks: List[callable] = []
    
    def start_monitoring(self):
        """Start the performance monitoring."""
        if self._monitoring_enabled:
            return
        
        self._monitoring_enabled = True
        self._monitoring_thread = threading.Thread(target=self._monitor_performance, daemon=True)
        self._monitoring_thread.start()
        self.logger.info("Transaction performance monitoring started")
    
    def stop_monitoring(self):
        """Stop the performance monitoring."""
        self._monitoring_enabled = False
        if self._monitoring_thread and self._monitoring_thread.is_alive():
            self._monitoring_thread.join(timeout=5)
        self.logger.info("Transaction performance monitoring stopped")
    
    def record_transaction(self, stats: TransactionStatistics):
        """Record transaction statistics for monitoring."""
        with self.lock:
            # Add to history
            self.transaction_history.append(stats)
            
            # Update performance profiles
            self._update_performance_profile(stats)
            
            # Update real-time metrics
            self._update_real_time_metrics()
            
            # Check for alerts
            self._check_performance_alerts(stats)
            
            # Update aggregated statistics
            self._update_aggregated_stats(stats)
    
    def record_resource_usage(self, usage: TransactionResourceUsage):
        """Record resource usage statistics."""
        with self.lock:
            self.resource_usage_history.append(usage)
            
            # Update current metrics
            self.current_metrics['cpu_usage'] = usage.cpu_usage_percent
            self.current_metrics['memory_usage'] = usage.memory_usage_mb
            
            # Check for resource-based alerts
            self._check_resource_alerts(usage)
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get a comprehensive performance summary."""
        with self.lock:
            recent_transactions = list(self.transaction_history)[-100:]  # Last 100 transactions
            
            if not recent_transactions:
                return {'status': 'no_data'}
            
            # Calculate summary statistics
            durations = [t.duration_seconds for t in recent_transactions if t.duration_seconds]
            success_count = sum(1 for t in recent_transactions if t.success)
            rollback_count = sum(t.rollback_count for t in recent_transactions)
            deadlock_count = sum(t.deadlock_count for t in recent_transactions)
            
            summary = {
                'total_transactions': len(recent_transactions),
                'success_rate': (success_count / len(recent_transactions)) * 100,
                'average_duration': statistics.mean(durations) if durations else 0,
                'median_duration': statistics.median(durations) if durations else 0,
                'p95_duration': self._calculate_percentile(durations, 95) if durations else 0,
                'p99_duration': self._calculate_percentile(durations, 99) if durations else 0,
                'rollback_rate': (rollback_count / len(recent_transactions)) * 100,
                'deadlock_rate': (deadlock_count / len(recent_transactions)) * 100,
                'transactions_per_second': self.current_metrics['transactions_per_second'],
                'active_transactions': self.current_metrics['active_transactions'],
                'connection_pool_utilization': self.current_metrics['connection_pool_utilization'],
                'cpu_usage': self.current_metrics['cpu_usage'],
                'memory_usage': self.current_metrics['memory_usage'],
                'recent_alerts': len([a for a in self.alert_history if 
                                    (datetime.now() - a['timestamp']).total_seconds() < 3600])
            }
            
            return summary
    
    def get_performance_trends(self, hours: int = 24) -> Dict[str, List[Dict[str, Any]]]:
        """Get performance trends over the specified time period."""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        with self.lock:
            recent_transactions = [
                t for t in self.transaction_history 
                if t.start_time >= cutoff_time
            ]
            
            # Group by hour
            hourly_data = defaultdict(list)
            for transaction in recent_transactions:
                hour_key = transaction.start_time.strftime('%Y-%m-%d %H:00')
                hourly_data[hour_key].append(transaction)
            
            # Calculate trends
            trends = {
                'throughput': [],
                'response_time': [],
                'success_rate': [],
                'resource_usage': []
            }
            
            for hour_key in sorted(hourly_data.keys()):
                hour_transactions = hourly_data[hour_key]
                
                # Throughput
                trends['throughput'].append({
                    'timestamp': hour_key,
                    'transactions_per_hour': len(hour_transactions)
                })
                
                # Response time
                durations = [t.duration_seconds for t in hour_transactions if t.duration_seconds]
                trends['response_time'].append({
                    'timestamp': hour_key,
                    'average_duration': statistics.mean(durations) if durations else 0,
                    'p95_duration': self._calculate_percentile(durations, 95) if durations else 0
                })
                
                # Success rate
                success_count = sum(1 for t in hour_transactions if t.success)
                trends['success_rate'].append({
                    'timestamp': hour_key,
                    'success_rate': (success_count / len(hour_transactions)) * 100
                })
            
            # Resource usage trends
            recent_usage = [
                u for u in self.resource_usage_history 
                if u.measurement_time >= cutoff_time
            ]
            
            usage_by_hour = defaultdict(list)
            for usage in recent_usage:
                hour_key = usage.measurement_time.strftime('%Y-%m-%d %H:00')
                usage_by_hour[hour_key].append(usage)
            
            for hour_key in sorted(usage_by_hour.keys()):
                hour_usage = usage_by_hour[hour_key]
                
                trends['resource_usage'].append({
                    'timestamp': hour_key,
                    'avg_cpu_usage': statistics.mean([u.cpu_usage_percent for u in hour_usage]),
                    'avg_memory_usage': statistics.mean([u.memory_usage_mb for u in hour_usage]),
                    'avg_disk_io': statistics.mean([u.disk_io_read_mb + u.disk_io_write_mb for u in hour_usage])
                })
            
            return trends
    
    def get_optimization_suggestions(self) -> List[TransactionOptimizationSuggestion]:
        """Generate optimization suggestions based on performance analysis."""
        suggestions = []
        
        with self.lock:
            recent_transactions = list(self.transaction_history)[-1000:]  # Last 1000 transactions
            
            if not recent_transactions:
                return suggestions
            
            # Analyze slow transactions
            slow_transactions = [
                t for t in recent_transactions 
                if t.duration_seconds and t.duration_seconds > self.thresholds.slow_transaction_seconds
            ]
            
            if len(slow_transactions) > len(recent_transactions) * 0.1:  # More than 10% are slow
                suggestions.append(TransactionOptimizationSuggestion(
                    suggestion_id=f"slow_tx_{int(time.time())}",
                    transaction_pattern="slow_transactions",
                    optimization_type="query",
                    description="High percentage of slow transactions detected",
                    expected_improvement="20-50% faster response times",
                    implementation_effort="medium",
                    risk_level="low",
                    applicable_scenarios=["heavy_queries", "missing_indexes"],
                    implementation_steps=[
                        "Analyze slow query logs",
                        "Add appropriate database indexes",
                        "Optimize query structure",
                        "Consider query result caching"
                    ],
                    validation_criteria=[
                        "Average response time < 5 seconds",
                        "P95 response time < 10 seconds"
                    ],
                    priority_score=0.8
                ))
            
            # Analyze high rollback rate
            rollback_rate = sum(t.rollback_count for t in recent_transactions) / len(recent_transactions) * 100
            if rollback_rate > self.thresholds.high_rollback_rate_percent:
                suggestions.append(TransactionOptimizationSuggestion(
                    suggestion_id=f"rollback_{int(time.time())}",
                    transaction_pattern="high_rollback_rate",
                    optimization_type="isolation_level",
                    description=f"High rollback rate detected: {rollback_rate:.1f}%",
                    expected_improvement="50-80% reduction in rollbacks",
                    implementation_effort="low",
                    risk_level="medium",
                    applicable_scenarios=["concurrent_updates", "deadlock_prone_operations"],
                    implementation_steps=[
                        "Review transaction isolation levels",
                        "Implement optimistic locking where appropriate",
                        "Reduce transaction scope",
                        "Add retry logic for transient failures"
                    ],
                    validation_criteria=[
                        f"Rollback rate < {self.thresholds.high_rollback_rate_percent}%"
                    ],
                    priority_score=0.7
                ))
            
            # Analyze deadlock patterns
            deadlock_count = sum(t.deadlock_count for t in recent_transactions)
            if deadlock_count > self.thresholds.frequent_deadlocks_per_hour:
                suggestions.append(TransactionOptimizationSuggestion(
                    suggestion_id=f"deadlock_{int(time.time())}",
                    transaction_pattern="frequent_deadlocks",
                    optimization_type="batch_size",
                    description="Frequent deadlocks detected",
                    expected_improvement="90% reduction in deadlocks",
                    implementation_effort="high",
                    risk_level="medium",
                    applicable_scenarios=["bulk_operations", "concurrent_access"],
                    implementation_steps=[
                        "Implement consistent lock ordering",
                        "Reduce transaction duration",
                        "Use smaller batch sizes",
                        "Implement deadlock retry logic"
                    ],
                    validation_criteria=[
                        f"Deadlocks per hour < {self.thresholds.frequent_deadlocks_per_hour}"
                    ],
                    priority_score=0.9
                ))
            
            # Analyze resource usage
            if self.resource_usage_history:
                recent_usage = list(self.resource_usage_history)[-100:]
                avg_memory = statistics.mean([u.memory_usage_mb for u in recent_usage])
                
                if avg_memory > self.thresholds.memory_usage_mb:
                    suggestions.append(TransactionOptimizationSuggestion(
                        suggestion_id=f"memory_{int(time.time())}",
                        transaction_pattern="high_memory_usage",
                        optimization_type="batch_size",
                        description=f"High memory usage detected: {avg_memory:.1f} MB",
                        expected_improvement="30-50% reduction in memory usage",
                        implementation_effort="medium",
                        risk_level="low",
                        applicable_scenarios=["large_result_sets", "bulk_operations"],
                        implementation_steps=[
                            "Implement result set pagination",
                            "Use streaming for large data sets",
                            "Reduce batch sizes",
                            "Implement connection pooling"
                        ],
                        validation_criteria=[
                            f"Average memory usage < {self.thresholds.memory_usage_mb} MB"
                        ],
                        priority_score=0.6
                    ))
        
        return sorted(suggestions, key=lambda x: x.priority_score, reverse=True)
    
    def get_health_check(self) -> TransactionHealthCheck:
        """Perform a comprehensive health check of the transaction system."""
        with self.lock:
            current_time = datetime.now()
            one_hour_ago = current_time - timedelta(hours=1)
            
            recent_transactions = [
                t for t in self.transaction_history 
                if t.start_time >= one_hour_ago
            ]
            
            # Calculate health metrics
            active_transactions = self.current_metrics['active_transactions']
            long_running = sum(
                1 for t in recent_transactions 
                if t.duration_seconds and t.duration_seconds > self.thresholds.long_running_transaction_seconds
            )
            failed_transactions = sum(1 for t in recent_transactions if not t.success)
            deadlocks = sum(t.deadlock_count for t in recent_transactions)
            
            # Determine overall health
            warnings = []
            errors = []
            recommendations = []
            
            if long_running > 0:
                warnings.append(f"{long_running} long-running transactions detected")
                recommendations.append("Review and optimize long-running queries")
            
            if failed_transactions > len(recent_transactions) * 0.05:  # More than 5% failures
                errors.append(f"High failure rate: {failed_transactions} failed transactions in last hour")
                recommendations.append("Investigate transaction failure causes")
            
            if deadlocks > self.thresholds.frequent_deadlocks_per_hour:
                errors.append(f"Frequent deadlocks: {deadlocks} in last hour")
                recommendations.append("Implement deadlock prevention strategies")
            
            if self.current_metrics['connection_pool_utilization'] > self.thresholds.connection_pool_utilization_percent:
                warnings.append("High connection pool utilization")
                recommendations.append("Consider increasing connection pool size")
            
            # Determine overall health status
            if errors:
                overall_health = "critical"
            elif warnings:
                overall_health = "warning"
            else:
                overall_health = "healthy"
            
            return TransactionHealthCheck(
                check_time=current_time,
                overall_health=overall_health,
                active_transactions=active_transactions,
                long_running_transactions=long_running,
                failed_transactions_last_hour=failed_transactions,
                deadlocks_last_hour=deadlocks,
                average_response_time=self.current_metrics['average_response_time'],
                connection_pool_utilization=self.current_metrics['connection_pool_utilization'],
                database_health={},  # Would be populated by database-specific checks
                warnings=warnings,
                errors=errors,
                recommendations=recommendations
            )
    
    def add_alert_callback(self, callback: callable):
        """Add a callback function for performance alerts."""
        self.alert_callbacks.append(callback)
    
    def _monitor_performance(self):
        """Background monitoring thread."""
        while self._monitoring_enabled:
            try:
                # Update real-time metrics
                self._update_real_time_metrics()
                
                # Clean up old data
                self._cleanup_old_data()
                
                # Generate periodic reports
                self._generate_periodic_reports()
                
                time.sleep(self.monitoring_interval)
                
            except Exception as e:
                self.logger.error(f"Error in performance monitoring: {e}")
                time.sleep(10)  # Wait longer on error
    
    def _update_performance_profile(self, stats: TransactionStatistics):
        """Update performance profile for transaction type."""
        profile_key = f"{stats.database_type.value if stats.database_type else 'unknown'}_default"
        
        if profile_key not in self.performance_profiles:
            self.performance_profiles[profile_key] = TransactionPerformanceProfile(
                profile_id=profile_key,
                transaction_type=TransactionType.READ_WRITE,
                database_type=stats.database_type or DatabaseType.SQLITE,
                isolation_level="READ_COMMITTED",
                average_duration=0.0,
                median_duration=0.0,
                p95_duration=0.0,
                p99_duration=0.0,
                success_rate=100.0,
                average_operations=0.0,
                average_rows_affected=0.0,
                common_error_patterns=[],
                optimization_suggestions=[],
                sample_size=0
            )
        
        profile = self.performance_profiles[profile_key]
        profile.sample_size += 1
        
        # Update running averages (simplified)
        if stats.duration_seconds:
            profile.average_duration = (
                (profile.average_duration * (profile.sample_size - 1) + stats.duration_seconds) / 
                profile.sample_size
            )
        
        profile.success_rate = (
            (profile.success_rate * (profile.sample_size - 1) + (100 if stats.success else 0)) / 
            profile.sample_size
        )
        
        profile.last_updated = datetime.now()
    
    def _update_real_time_metrics(self):
        """Update real-time performance metrics."""
        with self.lock:
            recent_transactions = list(self.transaction_history)[-100:]  # Last 100 transactions
            
            if recent_transactions:
                # Calculate transactions per second (approximate)
                time_span = (recent_transactions[-1].start_time - recent_transactions[0].start_time).total_seconds()
                if time_span > 0:
                    self.current_metrics['transactions_per_second'] = len(recent_transactions) / time_span
                
                # Calculate average response time
                durations = [t.duration_seconds for t in recent_transactions if t.duration_seconds]
                if durations:
                    self.current_metrics['average_response_time'] = statistics.mean(durations)
                
                # Calculate success rate
                success_count = sum(1 for t in recent_transactions if t.success)
                self.current_metrics['success_rate'] = (success_count / len(recent_transactions)) * 100
                
                # Calculate rollback rate
                rollback_count = sum(t.rollback_count for t in recent_transactions)
                self.current_metrics['rollback_rate'] = (rollback_count / len(recent_transactions)) * 100
    
    def _check_performance_alerts(self, stats: TransactionStatistics):
        """Check for performance alerts based on transaction statistics."""
        alerts = []
        
        # Check for slow transaction
        if stats.duration_seconds and stats.duration_seconds > self.thresholds.slow_transaction_seconds:
            alerts.append({
                'type': PerformanceAlert.SLOW_TRANSACTION,
                'severity': 'warning',
                'message': f"Slow transaction detected: {stats.duration_seconds:.2f}s",
                'transaction_id': stats.transaction_id,
                'timestamp': datetime.now()
            })
        
        # Check for long-running transaction
        if stats.duration_seconds and stats.duration_seconds > self.thresholds.long_running_transaction_seconds:
            alerts.append({
                'type': PerformanceAlert.LONG_RUNNING_TRANSACTION,
                'severity': 'error',
                'message': f"Long-running transaction detected: {stats.duration_seconds:.2f}s",
                'transaction_id': stats.transaction_id,
                'timestamp': datetime.now()
            })
        
        # Store alerts and trigger callbacks
        for alert in alerts:
            self.alert_history.append(alert)
            for callback in self.alert_callbacks:
                try:
                    callback(alert)
                except Exception as e:
                    self.logger.error(f"Alert callback failed: {e}")
    
    def _check_resource_alerts(self, usage: TransactionResourceUsage):
        """Check for resource-based alerts."""
        alerts = []
        
        if usage.cpu_usage_percent > self.thresholds.cpu_usage_percent:
            alerts.append({
                'type': PerformanceAlert.RESOURCE_EXHAUSTION,
                'severity': 'warning',
                'message': f"High CPU usage: {usage.cpu_usage_percent:.1f}%",
                'transaction_id': usage.transaction_id,
                'timestamp': datetime.now()
            })
        
        if usage.memory_usage_mb > self.thresholds.memory_usage_mb:
            alerts.append({
                'type': PerformanceAlert.RESOURCE_EXHAUSTION,
                'severity': 'warning',
                'message': f"High memory usage: {usage.memory_usage_mb:.1f} MB",
                'transaction_id': usage.transaction_id,
                'timestamp': datetime.now()
            })
        
        # Store alerts
        for alert in alerts:
            self.alert_history.append(alert)
            for callback in self.alert_callbacks:
                try:
                    callback(alert)
                except Exception as e:
                    self.logger.error(f"Alert callback failed: {e}")
    
    def _update_aggregated_stats(self, stats: TransactionStatistics):
        """Update hourly and daily aggregated statistics."""
        hour_key = stats.start_time.strftime('%Y-%m-%d %H')
        day_key = stats.start_time.strftime('%Y-%m-%d')
        
        # Update hourly stats
        if hour_key not in self.hourly_stats:
            self.hourly_stats[hour_key] = {
                'transaction_count': 0,
                'total_duration': 0.0,
                'success_count': 0,
                'rollback_count': 0,
                'deadlock_count': 0
            }
        
        hour_stats = self.hourly_stats[hour_key]
        hour_stats['transaction_count'] += 1
        if stats.duration_seconds:
            hour_stats['total_duration'] += stats.duration_seconds
        if stats.success:
            hour_stats['success_count'] += 1
        hour_stats['rollback_count'] += stats.rollback_count
        hour_stats['deadlock_count'] += stats.deadlock_count
        
        # Update daily stats (similar logic)
        if day_key not in self.daily_stats:
            self.daily_stats[day_key] = {
                'transaction_count': 0,
                'total_duration': 0.0,
                'success_count': 0,
                'rollback_count': 0,
                'deadlock_count': 0
            }
        
        day_stats = self.daily_stats[day_key]
        day_stats['transaction_count'] += 1
        if stats.duration_seconds:
            day_stats['total_duration'] += stats.duration_seconds
        if stats.success:
            day_stats['success_count'] += 1
        day_stats['rollback_count'] += stats.rollback_count
        day_stats['deadlock_count'] += stats.deadlock_count
    
    def _cleanup_old_data(self):
        """Clean up old performance data."""
        cutoff_time = datetime.now() - timedelta(hours=self.history_retention_hours)
        
        # Clean up hourly stats
        old_hours = [
            hour for hour in self.hourly_stats.keys()
            if datetime.strptime(hour, '%Y-%m-%d %H') < cutoff_time
        ]
        for hour in old_hours:
            del self.hourly_stats[hour]
        
        # Clean up daily stats (keep longer)
        daily_cutoff = datetime.now() - timedelta(days=30)
        old_days = [
            day for day in self.daily_stats.keys()
            if datetime.strptime(day, '%Y-%m-%d') < daily_cutoff
        ]
        for day in old_days:
            del self.daily_stats[day]
    
    def _generate_periodic_reports(self):
        """Generate periodic performance reports."""
        # This could be extended to generate and store detailed reports
        pass
    
    def _calculate_percentile(self, values: List[float], percentile: int) -> float:
        """Calculate the specified percentile of a list of values."""
        if not values:
            return 0.0
        
        sorted_values = sorted(values)
        index = int((percentile / 100.0) * len(sorted_values))
        index = min(index, len(sorted_values) - 1)
        return sorted_values[index]