"""
Deadlock detection and resolution system for database transactions.
"""

import logging
import threading
import time
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple
from enum import Enum

from .transaction_models import DeadlockDetectionResult
from .exceptions import TransactionError


class DeadlockResolutionStrategy(Enum):
    """Strategies for resolving deadlocks."""
    ABORT_YOUNGEST = "abort_youngest"  # Abort the most recently started transaction
    ABORT_OLDEST = "abort_oldest"      # Abort the longest running transaction
    ABORT_LEAST_WORK = "abort_least_work"  # Abort transaction with least work done
    ABORT_LOWEST_PRIORITY = "abort_lowest_priority"  # Abort lowest priority transaction
    ABORT_RANDOM = "abort_random"      # Randomly select victim


@dataclass
class LockInfo:
    """Information about a database lock."""
    lock_id: str
    resource_id: str  # Table, row, or other resource identifier
    lock_type: str    # "shared", "exclusive", "update", etc.
    transaction_id: str
    acquired_at: datetime
    requested_at: datetime
    granted: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class WaitForGraph:
    """Wait-for graph for deadlock detection."""
    nodes: Set[str] = field(default_factory=set)  # Transaction IDs
    edges: Dict[str, Set[str]] = field(default_factory=lambda: defaultdict(set))  # waiter -> holder
    lock_info: Dict[str, LockInfo] = field(default_factory=dict)
    
    def add_wait_relationship(self, waiter: str, holder: str, lock_info: LockInfo):
        """Add a wait relationship to the graph."""
        self.nodes.add(waiter)
        self.nodes.add(holder)
        self.edges[waiter].add(holder)
        self.lock_info[lock_info.lock_id] = lock_info
    
    def remove_transaction(self, transaction_id: str):
        """Remove a transaction from the wait-for graph."""
        if transaction_id in self.nodes:
            self.nodes.remove(transaction_id)
        
        # Remove as waiter
        if transaction_id in self.edges:
            del self.edges[transaction_id]
        
        # Remove as holder
        for waiter in list(self.edges.keys()):
            if transaction_id in self.edges[waiter]:
                self.edges[waiter].remove(transaction_id)
    
    def detect_cycles(self) -> List[List[str]]:
        """Detect cycles in the wait-for graph using DFS."""
        cycles = []
        visited = set()
        rec_stack = set()
        
        def dfs(node: str, path: List[str]) -> bool:
            if node in rec_stack:
                # Found a cycle
                cycle_start = path.index(node)
                cycle = path[cycle_start:] + [node]
                cycles.append(cycle)
                return True
            
            if node in visited:
                return False
            
            visited.add(node)
            rec_stack.add(node)
            path.append(node)
            
            for neighbor in self.edges.get(node, set()):
                if dfs(neighbor, path):
                    return True
            
            rec_stack.remove(node)
            path.pop()
            return False
        
        for node in self.nodes:
            if node not in visited:
                dfs(node, [])
        
        return cycles


class DeadlockDetector:
    """
    Advanced deadlock detection and resolution system.
    
    This class monitors database transactions and detects deadlocks using
    wait-for graph analysis. When deadlocks are detected, it applies
    configurable resolution strategies to resolve them.
    """
    
    def __init__(self, 
                 detection_interval: float = 1.0,
                 resolution_strategy: DeadlockResolutionStrategy = DeadlockResolutionStrategy.ABORT_YOUNGEST,
                 max_wait_time: float = 30.0):
        self.detection_interval = detection_interval
        self.resolution_strategy = resolution_strategy
        self.max_wait_time = max_wait_time
        self.logger = logging.getLogger(__name__)
        
        # Wait-for graph
        self.wait_for_graph = WaitForGraph()
        self.graph_lock = threading.RLock()
        
        # Transaction information
        self.transaction_info: Dict[str, Dict[str, Any]] = {}
        self.transaction_priorities: Dict[str, int] = {}  # Higher number = higher priority
        
        # Deadlock history
        self.detected_deadlocks: List[DeadlockDetectionResult] = []
        self.resolution_history: List[Dict[str, Any]] = []
        
        # Statistics
        self.stats = {
            'total_deadlocks_detected': 0,
            'total_deadlocks_resolved': 0,
            'false_positives': 0,
            'resolution_failures': 0,
            'average_detection_time': 0.0,
            'average_resolution_time': 0.0
        }
        
        # Monitoring
        self._monitoring_enabled = False
        self._monitoring_thread: Optional[threading.Thread] = None
    
    def start_monitoring(self):
        """Start the deadlock detection monitoring."""
        if self._monitoring_enabled:
            return
        
        self._monitoring_enabled = True
        self._monitoring_thread = threading.Thread(target=self._monitor_deadlocks, daemon=True)
        self._monitoring_thread.start()
        self.logger.info("Deadlock detection monitoring started")
    
    def stop_monitoring(self):
        """Stop the deadlock detection monitoring."""
        self._monitoring_enabled = False
        if self._monitoring_thread and self._monitoring_thread.is_alive():
            self._monitoring_thread.join(timeout=5)
        self.logger.info("Deadlock detection monitoring stopped")
    
    def register_transaction(self, 
                           transaction_id: str, 
                           priority: int = 0,
                           metadata: Optional[Dict[str, Any]] = None):
        """Register a transaction for deadlock monitoring."""
        with self.graph_lock:
            self.transaction_info[transaction_id] = {
                'start_time': datetime.now(),
                'priority': priority,
                'metadata': metadata or {}
            }
            self.transaction_priorities[transaction_id] = priority
    
    def unregister_transaction(self, transaction_id: str):
        """Unregister a transaction from deadlock monitoring."""
        with self.graph_lock:
            if transaction_id in self.transaction_info:
                del self.transaction_info[transaction_id]
            
            if transaction_id in self.transaction_priorities:
                del self.transaction_priorities[transaction_id]
            
            self.wait_for_graph.remove_transaction(transaction_id)
    
    def add_lock_wait(self, 
                     waiter_transaction_id: str,
                     holder_transaction_id: str,
                     resource_id: str,
                     lock_type: str = "exclusive"):
        """Add a lock wait relationship."""
        lock_info = LockInfo(
            lock_id=str(uuid.uuid4()),
            resource_id=resource_id,
            lock_type=lock_type,
            transaction_id=holder_transaction_id,
            acquired_at=datetime.now(),
            requested_at=datetime.now(),
            granted=False
        )
        
        with self.graph_lock:
            self.wait_for_graph.add_wait_relationship(
                waiter_transaction_id,
                holder_transaction_id,
                lock_info
            )
    
    def remove_lock_wait(self, waiter_transaction_id: str, holder_transaction_id: str):
        """Remove a lock wait relationship."""
        with self.graph_lock:
            if waiter_transaction_id in self.wait_for_graph.edges:
                self.wait_for_graph.edges[waiter_transaction_id].discard(holder_transaction_id)
    
    def detect_deadlocks(self) -> List[DeadlockDetectionResult]:
        """Detect deadlocks in the current wait-for graph."""
        detection_start = time.time()
        deadlocks = []
        
        with self.graph_lock:
            cycles = self.wait_for_graph.detect_cycles()
            
            for cycle in cycles:
                if len(cycle) > 1:  # Actual cycle (not self-loop)
                    # Verify this is a real deadlock
                    if self._verify_deadlock(cycle):
                        deadlock_result = DeadlockDetectionResult(
                            deadlock_detected=True,
                            detection_time=datetime.now(),
                            involved_transactions=cycle[:-1],  # Remove duplicate last element
                            deadlock_chain=self._build_deadlock_chain(cycle),
                            confidence_score=self._calculate_confidence_score(cycle)
                        )
                        
                        deadlocks.append(deadlock_result)
                        self.detected_deadlocks.append(deadlock_result)
                        self.stats['total_deadlocks_detected'] += 1
        
        detection_time = time.time() - detection_start
        self._update_average_detection_time(detection_time)
        
        return deadlocks
    
    def resolve_deadlock(self, deadlock: DeadlockDetectionResult) -> bool:
        """Resolve a detected deadlock using the configured strategy."""
        resolution_start = time.time()
        
        try:
            victim_transaction = self._select_victim(deadlock)
            if not victim_transaction:
                self.logger.error(f"Could not select victim for deadlock resolution")
                self.stats['resolution_failures'] += 1
                return False
            
            deadlock.victim_transaction = victim_transaction
            deadlock.resolution_strategy = self.resolution_strategy.value
            
            # Remove the victim transaction from the wait-for graph
            self.unregister_transaction(victim_transaction)
            
            # Record the resolution
            resolution_record = {
                'deadlock_id': id(deadlock),
                'victim_transaction': victim_transaction,
                'resolution_time': datetime.now(),
                'strategy': self.resolution_strategy.value,
                'involved_transactions': deadlock.involved_transactions
            }
            self.resolution_history.append(resolution_record)
            
            self.stats['total_deadlocks_resolved'] += 1
            
            resolution_time = time.time() - resolution_start
            self._update_average_resolution_time(resolution_time)
            
            self.logger.info(f"Resolved deadlock by aborting transaction {victim_transaction}")
            return True
        
        except Exception as e:
            self.logger.error(f"Failed to resolve deadlock: {e}")
            self.stats['resolution_failures'] += 1
            return False
    
    def get_deadlock_statistics(self) -> Dict[str, Any]:
        """Get deadlock detection and resolution statistics."""
        with self.graph_lock:
            current_wait_relationships = sum(
                len(waiters) for waiters in self.wait_for_graph.edges.values()
            )
            
            return {
                **self.stats,
                'active_transactions': len(self.transaction_info),
                'current_wait_relationships': current_wait_relationships,
                'recent_deadlocks': len([
                    d for d in self.detected_deadlocks 
                    if (datetime.now() - d.detection_time).total_seconds() < 3600
                ]),
                'resolution_success_rate': (
                    self.stats['total_deadlocks_resolved'] / 
                    max(1, self.stats['total_deadlocks_detected'])
                )
            }
    
    def get_wait_for_graph_info(self) -> Dict[str, Any]:
        """Get information about the current wait-for graph."""
        with self.graph_lock:
            return {
                'nodes': list(self.wait_for_graph.nodes),
                'edges': {
                    waiter: list(holders) 
                    for waiter, holders in self.wait_for_graph.edges.items()
                },
                'total_nodes': len(self.wait_for_graph.nodes),
                'total_edges': sum(len(holders) for holders in self.wait_for_graph.edges.values())
            }
    
    def _monitor_deadlocks(self):
        """Background monitoring thread for deadlock detection."""
        while self._monitoring_enabled:
            try:
                # Detect deadlocks
                deadlocks = self.detect_deadlocks()
                
                # Resolve detected deadlocks
                for deadlock in deadlocks:
                    self.resolve_deadlock(deadlock)
                
                # Clean up old transactions
                self._cleanup_old_transactions()
                
                # Sleep until next detection cycle
                time.sleep(self.detection_interval)
                
            except Exception as e:
                self.logger.error(f"Error in deadlock monitoring: {e}")
                time.sleep(5)  # Wait longer on error
    
    def _verify_deadlock(self, cycle: List[str]) -> bool:
        """Verify that a detected cycle represents a real deadlock."""
        # Check if all transactions in the cycle are still active
        for transaction_id in cycle[:-1]:  # Exclude duplicate last element
            if transaction_id not in self.transaction_info:
                return False
        
        # Check if the wait relationships still exist
        for i in range(len(cycle) - 1):
            waiter = cycle[i]
            holder = cycle[i + 1]
            
            if holder not in self.wait_for_graph.edges.get(waiter, set()):
                return False
        
        return True
    
    def _build_deadlock_chain(self, cycle: List[str]) -> List[Dict[str, Any]]:
        """Build a detailed chain of the deadlock."""
        chain = []
        
        for i in range(len(cycle) - 1):
            waiter = cycle[i]
            holder = cycle[i + 1]
            
            # Find the lock information
            lock_info = None
            for lock in self.wait_for_graph.lock_info.values():
                if lock.transaction_id == holder:
                    lock_info = lock
                    break
            
            chain_entry = {
                'waiter_transaction': waiter,
                'holder_transaction': holder,
                'resource_id': lock_info.resource_id if lock_info else 'unknown',
                'lock_type': lock_info.lock_type if lock_info else 'unknown',
                'wait_time': (datetime.now() - lock_info.requested_at).total_seconds() if lock_info else 0
            }
            chain.append(chain_entry)
        
        return chain
    
    def _calculate_confidence_score(self, cycle: List[str]) -> float:
        """Calculate confidence score for deadlock detection."""
        base_score = 0.8  # Base confidence
        
        # Increase confidence for longer cycles
        if len(cycle) > 3:
            base_score += 0.1
        
        # Increase confidence if transactions have been waiting long
        total_wait_time = 0
        wait_count = 0
        
        for lock in self.wait_for_graph.lock_info.values():
            if lock.transaction_id in cycle:
                wait_time = (datetime.now() - lock.requested_at).total_seconds()
                total_wait_time += wait_time
                wait_count += 1
        
        if wait_count > 0:
            avg_wait_time = total_wait_time / wait_count
            if avg_wait_time > 10:  # More than 10 seconds
                base_score += 0.1
        
        return min(1.0, base_score)
    
    def _select_victim(self, deadlock: DeadlockDetectionResult) -> Optional[str]:
        """Select a victim transaction for deadlock resolution."""
        transactions = deadlock.involved_transactions
        
        if not transactions:
            return None
        
        if self.resolution_strategy == DeadlockResolutionStrategy.ABORT_YOUNGEST:
            # Select the most recently started transaction
            youngest = None
            youngest_start_time = None
            
            for tx_id in transactions:
                if tx_id in self.transaction_info:
                    start_time = self.transaction_info[tx_id]['start_time']
                    if youngest_start_time is None or start_time > youngest_start_time:
                        youngest = tx_id
                        youngest_start_time = start_time
            
            return youngest
        
        elif self.resolution_strategy == DeadlockResolutionStrategy.ABORT_OLDEST:
            # Select the longest running transaction
            oldest = None
            oldest_start_time = None
            
            for tx_id in transactions:
                if tx_id in self.transaction_info:
                    start_time = self.transaction_info[tx_id]['start_time']
                    if oldest_start_time is None or start_time < oldest_start_time:
                        oldest = tx_id
                        oldest_start_time = start_time
            
            return oldest
        
        elif self.resolution_strategy == DeadlockResolutionStrategy.ABORT_LOWEST_PRIORITY:
            # Select the transaction with lowest priority
            lowest_priority = None
            lowest_priority_value = float('inf')
            
            for tx_id in transactions:
                priority = self.transaction_priorities.get(tx_id, 0)
                if priority < lowest_priority_value:
                    lowest_priority = tx_id
                    lowest_priority_value = priority
            
            return lowest_priority
        
        else:
            # Default: select first transaction
            return transactions[0]
    
    def _cleanup_old_transactions(self):
        """Clean up old transaction information."""
        cutoff_time = datetime.now() - timedelta(hours=1)
        
        with self.graph_lock:
            old_transactions = [
                tx_id for tx_id, info in self.transaction_info.items()
                if info['start_time'] < cutoff_time
            ]
            
            for tx_id in old_transactions:
                self.unregister_transaction(tx_id)
    
    def _update_average_detection_time(self, detection_time: float):
        """Update the average detection time statistic."""
        current_avg = self.stats['average_detection_time']
        total_detections = self.stats['total_deadlocks_detected']
        
        if total_detections > 0:
            self.stats['average_detection_time'] = (
                (current_avg * (total_detections - 1) + detection_time) / total_detections
            )
        else:
            self.stats['average_detection_time'] = detection_time
    
    def _update_average_resolution_time(self, resolution_time: float):
        """Update the average resolution time statistic."""
        current_avg = self.stats['average_resolution_time']
        total_resolutions = self.stats['total_deadlocks_resolved']
        
        if total_resolutions > 0:
            self.stats['average_resolution_time'] = (
                (current_avg * (total_resolutions - 1) + resolution_time) / total_resolutions
            )
        else:
            self.stats['average_resolution_time'] = resolution_time