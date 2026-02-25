"""
Enhanced execution visualization for live visual feedback during program execution.
"""

import time
import json
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, asdict
from enum import Enum


class ExecutionEventType(Enum):
    """Types of execution events for visualization."""
    NODE_START = "node_start"
    NODE_COMPLETE = "node_complete"
    NODE_ERROR = "node_error"
    DATA_FLOW = "data_flow"
    VARIABLE_UPDATE = "variable_update"
    BREAKPOINT_HIT = "breakpoint_hit"
    EXECUTION_PAUSE = "execution_pause"
    EXECUTION_RESUME = "execution_resume"
    EXECUTION_COMPLETE = "execution_complete"
    EXECUTION_ERROR = "execution_error"


@dataclass
class ExecutionEvent:
    """Represents an execution event for visualization."""
    event_type: ExecutionEventType
    timestamp: float
    node_id: Optional[str] = None
    connection_id: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    message: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'event_type': self.event_type.value,
            'timestamp': self.timestamp,
            'node_id': self.node_id,
            'connection_id': self.connection_id,
            'data': self.data,
            'message': self.message
        }


class ExecutionVisualizer:
    """Provides real-time visual feedback during program execution."""
    
    def __init__(self):
        self.events: List[ExecutionEvent] = []
        self.event_callbacks: List[Callable[[ExecutionEvent], None]] = []
        self.active_nodes: Dict[str, float] = {}  # node_id -> start_time
        self.data_flows: Dict[str, Any] = {}  # connection_id -> current_data
        self.execution_speed = 1.0  # Speed multiplier for visualization
        self.highlight_duration = 2.0  # How long to highlight nodes
        self.animation_enabled = True
        self.real_time_mode = True
        
    def add_event_callback(self, callback: Callable[[ExecutionEvent], None]):
        """Add a callback to be called when events occur."""
        self.event_callbacks.append(callback)
    
    def emit_event(self, event: ExecutionEvent):
        """Emit an execution event."""
        self.events.append(event)
        
        # Call all registered callbacks
        for callback in self.event_callbacks:
            try:
                callback(event)
            except Exception as e:
                print(f"Error in event callback: {e}")
    
    def start_node_execution(self, node_id: str, node_type: str, parameters: Dict[str, Any] = None):
        """Signal that a node has started executing."""
        current_time = time.time()
        self.active_nodes[node_id] = current_time
        
        event = ExecutionEvent(
            event_type=ExecutionEventType.NODE_START,
            timestamp=current_time,
            node_id=node_id,
            data={
                'node_type': node_type,
                'parameters': parameters or {},
                'execution_speed': self.execution_speed
            },
            message=f"Started executing {node_type} node"
        )
        self.emit_event(event)
    
    def complete_node_execution(self, node_id: str, result: Any = None, 
                               output_variables: Dict[str, Any] = None):
        """Signal that a node has completed execution."""
        current_time = time.time()
        start_time = self.active_nodes.pop(node_id, current_time)
        execution_time = current_time - start_time
        
        event = ExecutionEvent(
            event_type=ExecutionEventType.NODE_COMPLETE,
            timestamp=current_time,
            node_id=node_id,
            data={
                'result': str(result) if result is not None else None,
                'execution_time': execution_time,
                'output_variables': output_variables or {},
                'highlight_duration': self.highlight_duration
            },
            message=f"Completed node execution in {execution_time:.3f}s"
        )
        self.emit_event(event)
    
    def error_node_execution(self, node_id: str, error: Exception):
        """Signal that a node encountered an error."""
        current_time = time.time()
        self.active_nodes.pop(node_id, None)
        
        event = ExecutionEvent(
            event_type=ExecutionEventType.NODE_ERROR,
            timestamp=current_time,
            node_id=node_id,
            data={
                'error_type': type(error).__name__,
                'error_message': str(error),
                'highlight_duration': self.highlight_duration * 2  # Longer highlight for errors
            },
            message=f"Node execution failed: {error}"
        )
        self.emit_event(event)
    
    def update_data_flow(self, connection_id: str, data_value: Any, 
                        source_node: str, target_node: str, port_name: str = None):
        """Update data flow visualization."""
        current_time = time.time()
        self.data_flows[connection_id] = data_value
        
        # Determine data type and size for visualization
        data_type = type(data_value).__name__
        data_size = len(str(data_value)) if data_value is not None else 0
        
        event = ExecutionEvent(
            event_type=ExecutionEventType.DATA_FLOW,
            timestamp=current_time,
            connection_id=connection_id,
            data={
                'value': str(data_value)[:100] if data_value is not None else None,  # Truncate long values
                'data_type': data_type,
                'data_size': data_size,
                'source_node': source_node,
                'target_node': target_node,
                'port_name': port_name,
                'animation_speed': self.execution_speed
            },
            message=f"Data flow: {data_type} from {source_node} to {target_node}"
        )
        self.emit_event(event)
    
    def update_variable(self, variable_name: str, old_value: Any, new_value: Any, node_id: str = None):
        """Signal that a variable has been updated."""
        current_time = time.time()
        
        event = ExecutionEvent(
            event_type=ExecutionEventType.VARIABLE_UPDATE,
            timestamp=current_time,
            node_id=node_id,
            data={
                'variable_name': variable_name,
                'old_value': str(old_value) if old_value is not None else None,
                'new_value': str(new_value) if new_value is not None else None,
                'old_type': type(old_value).__name__ if old_value is not None else 'None',
                'new_type': type(new_value).__name__ if new_value is not None else 'None'
            },
            message=f"Variable '{variable_name}' updated: {old_value} → {new_value}"
        )
        self.emit_event(event)
    
    def hit_breakpoint(self, node_id: str, variables: Dict[str, Any]):
        """Signal that a breakpoint has been hit."""
        current_time = time.time()
        
        event = ExecutionEvent(
            event_type=ExecutionEventType.BREAKPOINT_HIT,
            timestamp=current_time,
            node_id=node_id,
            data={
                'variables': {k: str(v) for k, v in variables.items()},
                'breakpoint_type': 'user_set'
            },
            message=f"Breakpoint hit at node {node_id}"
        )
        self.emit_event(event)
    
    def pause_execution(self, reason: str = "User requested"):
        """Signal that execution has been paused."""
        current_time = time.time()
        
        event = ExecutionEvent(
            event_type=ExecutionEventType.EXECUTION_PAUSE,
            timestamp=current_time,
            data={'reason': reason},
            message=f"Execution paused: {reason}"
        )
        self.emit_event(event)
    
    def resume_execution(self):
        """Signal that execution has been resumed."""
        current_time = time.time()
        
        event = ExecutionEvent(
            event_type=ExecutionEventType.EXECUTION_RESUME,
            timestamp=current_time,
            message="Execution resumed"
        )
        self.emit_event(event)
    
    def complete_execution(self, success: bool, final_variables: Dict[str, Any] = None, 
                          execution_time: float = 0.0):
        """Signal that execution has completed."""
        current_time = time.time()
        
        event = ExecutionEvent(
            event_type=ExecutionEventType.EXECUTION_COMPLETE,
            timestamp=current_time,
            data={
                'success': success,
                'total_execution_time': execution_time,
                'final_variables': {k: str(v) for k, v in (final_variables or {}).items()},
                'nodes_executed': len([e for e in self.events if e.event_type == ExecutionEventType.NODE_COMPLETE])
            },
            message=f"Execution {'completed successfully' if success else 'failed'} in {execution_time:.3f}s"
        )
        self.emit_event(event)
    
    def error_execution(self, error: Exception):
        """Signal that execution encountered a fatal error."""
        current_time = time.time()
        
        event = ExecutionEvent(
            event_type=ExecutionEventType.EXECUTION_ERROR,
            timestamp=current_time,
            data={
                'error_type': type(error).__name__,
                'error_message': str(error)
            },
            message=f"Execution error: {error}"
        )
        self.emit_event(event)
    
    def set_execution_speed(self, speed: float):
        """Set the execution speed multiplier for visualization."""
        self.execution_speed = max(0.1, min(10.0, speed))
    
    def set_highlight_duration(self, duration: float):
        """Set how long nodes should be highlighted."""
        self.highlight_duration = max(0.5, min(10.0, duration))
    
    def enable_animation(self):
        """Enable animation effects."""
        self.animation_enabled = True
    
    def disable_animation(self):
        """Disable animation effects."""
        self.animation_enabled = False
    
    def enable_real_time_mode(self):
        """Enable real-time execution visualization."""
        self.real_time_mode = True
    
    def disable_real_time_mode(self):
        """Disable real-time mode for faster execution."""
        self.real_time_mode = False
    
    def get_execution_summary(self) -> Dict[str, Any]:
        """Get a summary of the execution."""
        if not self.events:
            return {'total_events': 0}
        
        start_time = self.events[0].timestamp
        end_time = self.events[-1].timestamp
        total_time = end_time - start_time
        
        event_counts = {}
        for event in self.events:
            event_type = event.event_type.value
            event_counts[event_type] = event_counts.get(event_type, 0) + 1
        
        nodes_executed = len(set(e.node_id for e in self.events if e.node_id and e.event_type == ExecutionEventType.NODE_COMPLETE))
        
        return {
            'total_events': len(self.events),
            'total_execution_time': total_time,
            'nodes_executed': nodes_executed,
            'event_counts': event_counts,
            'start_time': start_time,
            'end_time': end_time,
            'execution_speed': self.execution_speed,
            'animation_enabled': self.animation_enabled
        }
    
    def get_events_json(self) -> str:
        """Get all events as JSON for frontend consumption."""
        return json.dumps([event.to_dict() for event in self.events], indent=2)
    
    def get_recent_events(self, count: int = 10) -> List[ExecutionEvent]:
        """Get the most recent execution events."""
        return self.events[-count:] if self.events else []
    
    def clear_events(self):
        """Clear all execution events."""
        self.events.clear()
        self.active_nodes.clear()
        self.data_flows.clear()
    
    def get_active_nodes(self) -> List[str]:
        """Get list of currently executing nodes."""
        return list(self.active_nodes.keys())
    
    def get_data_flow_state(self) -> Dict[str, Any]:
        """Get current data flow state."""
        return self.data_flows.copy()
    
    def create_execution_timeline(self) -> List[Dict[str, Any]]:
        """Create a timeline of execution events."""
        if not self.events:
            return []
        
        start_time = self.events[0].timestamp
        timeline = []
        
        for event in self.events:
            timeline_entry = {
                'relative_time': event.timestamp - start_time,
                'event_type': event.event_type.value,
                'node_id': event.node_id,
                'connection_id': event.connection_id,
                'message': event.message,
                'data': event.data
            }
            timeline.append(timeline_entry)
        
        return timeline