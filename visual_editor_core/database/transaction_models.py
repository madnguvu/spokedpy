"""
Enhanced transaction models for the Visual Editor Core Database Layer.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from enum import Enum

from .models import DatabaseType, DatabaseOperation


class TransactionType(Enum):
    """Types of database transactions."""
    READ_ONLY = "read_only"
    READ_WRITE = "read_write"
    BULK_OPERATION = "bulk_operation"
    MIGRATION = "migration"
    BACKUP = "backup"
    MAINTENANCE = "maintenance"


class TransactionPriority(Enum):
    """Transaction priority levels."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class TransactionConfig:
    """Configuration for database transactions."""
    isolation_level: str = "READ_COMMITTED"
    timeout: int = 300  # 5 minutes default
    readonly: bool = False
    priority: TransactionPriority = TransactionPriority.NORMAL
    transaction_type: TransactionType = TransactionType.READ_WRITE
    max_retry_attempts: int = 3
    retry_delay: float = 0.1
    enable_deadlock_detection: bool = True
    enable_performance_monitoring: bool = True
    auto_rollback_on_error: bool = True
    savepoint_enabled: bool = True
    batch_size: Optional[int] = None  # For bulk operations
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TransactionStatistics:
    """Statistics for transaction performance analysis."""
    transaction_id: str
    start_time: datetime
    end_time: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    operations_executed: int = 0
    rows_affected: int = 0
    bytes_processed: int = 0
    cpu_time_ms: Optional[float] = None
    memory_peak_mb: Optional[float] = None
    disk_io_bytes: Optional[int] = None
    network_io_bytes: Optional[int] = None
    lock_wait_time_ms: Optional[float] = None
    deadlock_count: int = 0
    retry_count: int = 0
    savepoint_count: int = 0
    rollback_count: int = 0
    warning_count: int = 0
    error_count: int = 0
    success: bool = False
    database_type: Optional[DatabaseType] = None  # Added this field
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def calculate_throughput(self) -> Optional[float]:
        """Calculate operations per second."""
        if self.duration_seconds and self.duration_seconds > 0:
            return self.operations_executed / self.duration_seconds
        return None
    
    def calculate_efficiency_score(self) -> float:
        """Calculate transaction efficiency score (0-1)."""
        base_score = 1.0
        
        # Penalize for retries
        if self.retry_count > 0:
            base_score -= min(0.3, self.retry_count * 0.1)
        
        # Penalize for deadlocks
        if self.deadlock_count > 0:
            base_score -= min(0.2, self.deadlock_count * 0.1)
        
        # Penalize for rollbacks
        if self.rollback_count > 0:
            base_score -= min(0.2, self.rollback_count * 0.05)
        
        # Penalize for errors
        if self.error_count > 0:
            base_score -= min(0.4, self.error_count * 0.1)
        
        return max(0.0, base_score)


@dataclass
class TransactionBatch:
    """Represents a batch of operations to be executed in a transaction."""
    batch_id: str
    operations: List[DatabaseOperation]
    config: TransactionConfig
    created_at: datetime = field(default_factory=datetime.now)
    priority: TransactionPriority = TransactionPriority.NORMAL
    dependencies: List[str] = field(default_factory=list)  # Other batch IDs this depends on
    estimated_duration: Optional[float] = None
    estimated_resource_usage: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def validate(self) -> List[str]:
        """Validate the transaction batch."""
        errors = []
        
        if not self.batch_id:
            errors.append("Batch ID is required")
        
        if not self.operations:
            errors.append("At least one operation is required")
        
        # Validate each operation
        for i, operation in enumerate(self.operations):
            if not operation.validate():
                errors.append(f"Operation {i} is invalid")
        
        # Check for conflicting operations
        table_operations = {}
        for operation in self.operations:
            table = operation.table
            if table not in table_operations:
                table_operations[table] = []
            table_operations[table].append(operation.operation_type)
        
        # Check for potential conflicts (e.g., DROP followed by INSERT)
        for table, ops in table_operations.items():
            if 'delete' in ops and 'insert' in ops:
                # This might be intentional, but flag as potential issue
                errors.append(f"Table {table} has both delete and insert operations")
        
        return errors
    
    def estimate_complexity(self) -> int:
        """Estimate the complexity score of this batch."""
        complexity = 0
        
        # Base complexity per operation
        complexity += len(self.operations)
        
        # Additional complexity for different operation types
        for operation in self.operations:
            if operation.operation_type == 'select':
                complexity += 1
            elif operation.operation_type in ['insert', 'update']:
                complexity += 2
            elif operation.operation_type == 'delete':
                complexity += 3
            else:
                complexity += 1
        
        # Additional complexity for dependencies
        complexity += len(self.dependencies) * 2
        
        return complexity


@dataclass
class DeadlockDetectionResult:
    """Result of deadlock detection analysis."""
    deadlock_detected: bool
    detection_time: datetime
    involved_transactions: List[str]
    deadlock_chain: List[Dict[str, Any]]
    victim_transaction: Optional[str] = None
    resolution_strategy: Optional[str] = None
    confidence_score: float = 0.0  # 0-1, how confident we are this is a deadlock
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TransactionPerformanceProfile:
    """Performance profile for transaction analysis."""
    profile_id: str
    transaction_type: TransactionType
    database_type: DatabaseType
    isolation_level: str
    average_duration: float
    median_duration: float
    p95_duration: float
    p99_duration: float
    success_rate: float
    average_operations: float
    average_rows_affected: float
    common_error_patterns: List[str]
    optimization_suggestions: List[str]
    sample_size: int
    last_updated: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TransactionHealthCheck:
    """Health check result for transaction system."""
    check_time: datetime
    overall_health: str  # "healthy", "warning", "critical"
    active_transactions: int
    long_running_transactions: int
    failed_transactions_last_hour: int
    deadlocks_last_hour: int
    average_response_time: float
    connection_pool_utilization: float
    database_health: Dict[DatabaseType, str]
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def is_healthy(self) -> bool:
        """Check if the transaction system is healthy."""
        return self.overall_health == "healthy"
    
    def needs_attention(self) -> bool:
        """Check if the transaction system needs attention."""
        return self.overall_health in ["warning", "critical"]


@dataclass
class TransactionAuditLog:
    """Audit log entry for transaction operations."""
    log_id: str
    transaction_id: str
    event_type: str  # "begin", "commit", "rollback", "savepoint", "error"
    timestamp: datetime
    user_id: Optional[str] = None
    tenant_id: Optional[str] = None
    database_type: Optional[DatabaseType] = None
    connection_id: Optional[str] = None
    operation_details: Dict[str, Any] = field(default_factory=dict)
    performance_metrics: Optional[TransactionStatistics] = None
    error_details: Optional[Dict[str, Any]] = None
    security_context: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TransactionRecoveryInfo:
    """Information for transaction recovery operations."""
    recovery_id: str
    failed_transaction_id: str
    failure_time: datetime
    failure_reason: str
    recovery_strategy: str  # "retry", "partial_rollback", "full_rollback", "manual"
    recovery_attempts: int = 0
    max_recovery_attempts: int = 3
    last_recovery_attempt: Optional[datetime] = None
    recovery_success: bool = False
    recovery_completion_time: Optional[datetime] = None
    data_consistency_verified: bool = False
    manual_intervention_required: bool = False
    recovery_notes: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def can_retry_recovery(self) -> bool:
        """Check if recovery can be retried."""
        return (
            not self.recovery_success and
            self.recovery_attempts < self.max_recovery_attempts and
            not self.manual_intervention_required
        )


@dataclass
class TransactionOptimizationSuggestion:
    """Suggestion for optimizing transaction performance."""
    suggestion_id: str
    transaction_pattern: str
    optimization_type: str  # "index", "query", "batch_size", "isolation_level", etc.
    description: str
    expected_improvement: str  # "10% faster", "50% less memory", etc.
    implementation_effort: str  # "low", "medium", "high"
    risk_level: str  # "low", "medium", "high"
    applicable_scenarios: List[str]
    implementation_steps: List[str]
    validation_criteria: List[str]
    created_at: datetime = field(default_factory=datetime.now)
    priority_score: float = 0.0  # 0-1, higher is more important
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TransactionResourceUsage:
    """Resource usage tracking for transactions."""
    transaction_id: str
    measurement_time: datetime
    cpu_usage_percent: float
    memory_usage_mb: float
    disk_io_read_mb: float
    disk_io_write_mb: float
    network_io_mb: float
    connection_count: int
    lock_count: int
    temp_space_mb: float
    query_cache_hit_ratio: float
    index_usage_efficiency: float
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def calculate_resource_score(self) -> float:
        """Calculate overall resource efficiency score (0-1)."""
        # Normalize and weight different metrics
        cpu_score = max(0, 1 - (self.cpu_usage_percent / 100))
        memory_score = max(0, 1 - (self.memory_usage_mb / 1024))  # Assume 1GB baseline
        cache_score = self.query_cache_hit_ratio
        index_score = self.index_usage_efficiency
        
        # Weighted average
        weights = [0.3, 0.2, 0.3, 0.2]  # CPU, Memory, Cache, Index
        scores = [cpu_score, memory_score, cache_score, index_score]
        
        return sum(w * s for w, s in zip(weights, scores))