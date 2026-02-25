"""
Data Flow Visualization System for the Visual Editor Core.

This module provides comprehensive data flow visualization capabilities including:
- Connection line display with direction indicators
- Real-time data flow animation
- Data type and value display at connection points
- Data transformation highlighting
- Connection point inspection during debugging
- Performance bottleneck visual indicators
- Data flow tracing for complex structures
"""

from typing import Dict, List, Tuple, Optional, Any, Callable, Set
from dataclasses import dataclass, field
from enum import Enum
import time
import threading
from collections import deque
from .models import VisualModel, VisualNode, Connection


class FlowDirection(Enum):
    """Direction of data flow."""
    FORWARD = "forward"
    BACKWARD = "backward"
    BIDIRECTIONAL = "bidirectional"


class FlowAnimationType(Enum):
    """Types of flow animation."""
    PULSE = "pulse"
    PARTICLE = "particle"
    WAVE = "wave"
    GLOW = "glow"


class PerformanceLevel(Enum):
    """Performance levels for bottleneck indication."""
    OPTIMAL = "optimal"
    GOOD = "good"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class DataFlowInfo:
    """Information about data flowing through a connection."""
    connection_id: str
    data_type: str
    current_value: Any
    previous_value: Any = None
    flow_direction: FlowDirection = FlowDirection.FORWARD
    timestamp: float = field(default_factory=time.time)
    transformation_applied: bool = False
    transformation_type: Optional[str] = None
    performance_metrics: Dict[str, float] = field(default_factory=dict)
    
    def has_value_changed(self) -> bool:
        """Check if the value has changed from previous."""
        return self.current_value != self.previous_value
    
    def get_type_change(self) -> Optional[Tuple[str, str]]:
        """Get type change information if applicable."""
        if self.previous_value is not None:
            prev_type = type(self.previous_value).__name__
            curr_type = type(self.current_value).__name__
            if prev_type != curr_type:
                return (prev_type, curr_type)
        return None


@dataclass
class ConnectionVisualization:
    """Visual representation of a connection."""
    connection_id: str
    source_position: Tuple[float, float]
    target_position: Tuple[float, float]
    control_points: List[Tuple[float, float]] = field(default_factory=list)
    line_width: float = 2.0
    line_color: str = "#666666"
    animation_type: FlowAnimationType = FlowAnimationType.PARTICLE
    animation_speed: float = 1.0
    show_direction_arrow: bool = True
    show_data_labels: bool = True
    highlight_active: bool = False
    performance_indicator: PerformanceLevel = PerformanceLevel.OPTIMAL
    
    def calculate_bezier_curve(self) -> List[Tuple[float, float]]:
        """Calculate bezier curve points for smooth connection lines."""
        if not self.control_points:
            # Generate default control points for smooth curves
            start_x, start_y = self.source_position
            end_x, end_y = self.target_position
            
            # Create control points for a smooth S-curve
            mid_x = (start_x + end_x) / 2
            control1 = (start_x + (mid_x - start_x) * 0.5, start_y)
            control2 = (end_x - (end_x - mid_x) * 0.5, end_y)
            self.control_points = [control1, control2]
        
        # Generate curve points using bezier calculation
        curve_points = []
        num_points = 50
        
        for i in range(num_points + 1):
            t = i / num_points
            
            # Cubic bezier curve calculation
            x = (1-t)**3 * self.source_position[0] + \
                3*(1-t)**2*t * self.control_points[0][0] + \
                3*(1-t)*t**2 * self.control_points[1][0] + \
                t**3 * self.target_position[0]
            
            y = (1-t)**3 * self.source_position[1] + \
                3*(1-t)**2*t * self.control_points[0][1] + \
                3*(1-t)*t**2 * self.control_points[1][1] + \
                t**3 * self.target_position[1]
            
            curve_points.append((x, y))
        
        return curve_points
    
    def get_midpoint(self) -> Tuple[float, float]:
        """Get the midpoint of the connection for label placement."""
        curve_points = self.calculate_bezier_curve()
        mid_index = len(curve_points) // 2
        return curve_points[mid_index]
    
    def get_direction_vector(self) -> Tuple[float, float]:
        """Get the direction vector for arrow placement."""
        curve_points = self.calculate_bezier_curve()
        if len(curve_points) >= 2:
            # Use points near the end for direction
            p1 = curve_points[-2]
            p2 = curve_points[-1]
            dx = p2[0] - p1[0]
            dy = p2[1] - p1[1]
            # Normalize
            length = (dx**2 + dy**2)**0.5
            if length > 0:
                return (dx/length, dy/length)
        return (1.0, 0.0)


@dataclass
class FlowParticle:
    """Represents a particle flowing through a connection."""
    particle_id: str
    connection_id: str
    position: float = 0.0  # Position along the curve (0.0 to 1.0)
    speed: float = 1.0
    size: float = 4.0
    color: str = "#00ff00"
    data_value: Any = None
    creation_time: float = field(default_factory=time.time)
    
    def update_position(self, delta_time: float):
        """Update particle position based on speed and time."""
        self.position += self.speed * delta_time
        if self.position > 1.0:
            self.position = self.position - 1.0  # Wrap around properly
    
    def is_expired(self, max_age: float = 5.0) -> bool:
        """Check if particle should be removed."""
        return time.time() - self.creation_time > max_age


@dataclass
class PerformanceMetrics:
    """Performance metrics for a connection."""
    connection_id: str
    throughput: float = 0.0  # Data items per second
    latency: float = 0.0  # Average processing time in ms
    error_rate: float = 0.0  # Percentage of failed operations
    memory_usage: float = 0.0  # Memory usage in MB
    cpu_usage: float = 0.0  # CPU usage percentage
    last_updated: float = field(default_factory=time.time)
    
    def get_performance_level(self) -> PerformanceLevel:
        """Determine performance level based on metrics."""
        if self.error_rate > 10 or self.latency > 1000 or self.cpu_usage > 90:
            return PerformanceLevel.CRITICAL
        elif self.error_rate > 5 or self.latency > 500 or self.cpu_usage > 70:
            return PerformanceLevel.WARNING
        elif self.error_rate > 1 or self.latency > 100 or self.cpu_usage > 50:
            return PerformanceLevel.GOOD
        else:
            return PerformanceLevel.OPTIMAL
    
    def update_metrics(self, throughput: float = None, latency: float = None,
                      error_rate: float = None, memory_usage: float = None,
                      cpu_usage: float = None):
        """Update performance metrics."""
        if throughput is not None:
            self.throughput = throughput
        if latency is not None:
            self.latency = latency
        if error_rate is not None:
            self.error_rate = error_rate
        if memory_usage is not None:
            self.memory_usage = memory_usage
        if cpu_usage is not None:
            self.cpu_usage = cpu_usage
        self.last_updated = time.time()


class DataFlowTracer:
    """Traces data flow through complex structures."""
    
    def __init__(self):
        self.trace_history: Dict[str, List[Dict[str, Any]]] = {}
        self.active_traces: Set[str] = set()
        self.max_trace_length = 1000
        self.trace_callbacks: List[Callable[[str, Dict[str, Any]], None]] = []
    
    def start_trace(self, trace_id: str, connection_id: str, initial_data: Any):
        """Start tracing data flow for a connection."""
        self.active_traces.add(trace_id)
        if trace_id not in self.trace_history:
            self.trace_history[trace_id] = []
        
        trace_entry = {
            'timestamp': time.time(),
            'connection_id': connection_id,
            'event': 'trace_start',
            'data': initial_data,
            'data_type': type(initial_data).__name__,
            'data_size': self._calculate_data_size(initial_data)
        }
        
        self._add_trace_entry(trace_id, trace_entry)
    
    def trace_data_transformation(self, trace_id: str, connection_id: str,
                                 input_data: Any, output_data: Any,
                                 transformation_type: str):
        """Trace a data transformation."""
        if trace_id not in self.active_traces:
            return
        
        trace_entry = {
            'timestamp': time.time(),
            'connection_id': connection_id,
            'event': 'transformation',
            'transformation_type': transformation_type,
            'input_data': input_data,
            'output_data': output_data,
            'input_type': type(input_data).__name__,
            'output_type': type(output_data).__name__,
            'input_size': self._calculate_data_size(input_data),
            'output_size': self._calculate_data_size(output_data)
        }
        
        self._add_trace_entry(trace_id, trace_entry)
    
    def trace_data_flow(self, trace_id: str, connection_id: str, data: Any,
                       source_node: str, target_node: str):
        """Trace data flowing through a connection."""
        if trace_id not in self.active_traces:
            return
        
        trace_entry = {
            'timestamp': time.time(),
            'connection_id': connection_id,
            'event': 'data_flow',
            'data': data,
            'data_type': type(data).__name__,
            'data_size': self._calculate_data_size(data),
            'source_node': source_node,
            'target_node': target_node
        }
        
        self._add_trace_entry(trace_id, trace_entry)
    
    def end_trace(self, trace_id: str):
        """End tracing for a specific trace ID."""
        if trace_id in self.active_traces:
            self.active_traces.remove(trace_id)
            
            if trace_id in self.trace_history:
                trace_entry = {
                    'timestamp': time.time(),
                    'event': 'trace_end',
                    'total_entries': len(self.trace_history[trace_id])
                }
                self._add_trace_entry(trace_id, trace_entry)
    
    def get_trace_history(self, trace_id: str) -> List[Dict[str, Any]]:
        """Get the trace history for a specific trace ID."""
        return self.trace_history.get(trace_id, [])
    
    def get_active_traces(self) -> Set[str]:
        """Get all active trace IDs."""
        return self.active_traces.copy()
    
    def clear_trace_history(self, trace_id: str = None):
        """Clear trace history for a specific trace or all traces."""
        if trace_id:
            self.trace_history.pop(trace_id, None)
            self.active_traces.discard(trace_id)
        else:
            self.trace_history.clear()
            self.active_traces.clear()
    
    def add_trace_callback(self, callback: Callable[[str, Dict[str, Any]], None]):
        """Add a callback to be called when trace entries are added."""
        self.trace_callbacks.append(callback)
    
    def _add_trace_entry(self, trace_id: str, entry: Dict[str, Any]):
        """Add an entry to the trace history."""
        if trace_id not in self.trace_history:
            self.trace_history[trace_id] = []
        
        self.trace_history[trace_id].append(entry)
        
        # Limit trace length
        if len(self.trace_history[trace_id]) > self.max_trace_length:
            self.trace_history[trace_id].pop(0)
        
        # Notify callbacks
        for callback in self.trace_callbacks:
            callback(trace_id, entry)
    
    def _calculate_data_size(self, data: Any) -> int:
        """Calculate approximate size of data in bytes."""
        try:
            import sys
            return sys.getsizeof(data)
        except:
            return 0


class DataFlowVisualizer:
    """Main class for data flow visualization system."""
    
    def __init__(self, model: VisualModel):
        self.model = model
        self.connection_visualizations: Dict[str, ConnectionVisualization] = {}
        self.data_flow_info: Dict[str, DataFlowInfo] = {}
        self.flow_particles: Dict[str, List[FlowParticle]] = {}
        self.performance_metrics: Dict[str, PerformanceMetrics] = {}
        self.tracer = DataFlowTracer()
        
        # Animation settings
        self.animation_enabled = True
        self.animation_speed = 1.0
        self.particle_count_per_connection = 3
        self.show_performance_indicators = True
        self.show_data_labels = True
        self.show_direction_arrows = True
        
        # Update thread for animations
        self._animation_thread = None
        self._stop_animation = False
        self._last_update_time = time.time()
        
        # Callbacks
        self.on_data_flow_update: Optional[Callable[[str, DataFlowInfo], None]] = None
        self.on_performance_alert: Optional[Callable[[str, PerformanceLevel], None]] = None
        self.on_bottleneck_detected: Optional[Callable[[str, Dict[str, Any]], None]] = None
        
        # Initialize visualizations for existing connections
        self._initialize_connection_visualizations()
    
    def _initialize_connection_visualizations(self):
        """Initialize visualizations for all existing connections."""
        for connection in self.model.connections:
            self._create_connection_visualization(connection)
    
    def _create_connection_visualization(self, connection: Connection):
        """Create visualization for a connection."""
        # Get node positions
        source_node = self.model.nodes.get(connection.source_node_id)
        target_node = self.model.nodes.get(connection.target_node_id)
        
        if not source_node or not target_node:
            return
        
        # Create visualization
        visualization = ConnectionVisualization(
            connection_id=connection.id,
            source_position=source_node.position,
            target_position=target_node.position,
            show_direction_arrow=self.show_direction_arrows,
            show_data_labels=self.show_data_labels
        )
        
        self.connection_visualizations[connection.id] = visualization
        
        # Initialize data flow info
        self.data_flow_info[connection.id] = DataFlowInfo(
            connection_id=connection.id,
            data_type=connection.data_type.__name__ if connection.data_type else "Any",
            current_value=None  # Initialize with None
        )
        
        # Initialize performance metrics
        self.performance_metrics[connection.id] = PerformanceMetrics(
            connection_id=connection.id
        )
        
        # Initialize particles for animation
        if self.animation_enabled:
            self._create_flow_particles(connection.id)
    
    def _create_flow_particles(self, connection_id: str):
        """Create flow particles for a connection."""
        particles = []
        for i in range(self.particle_count_per_connection):
            particle = FlowParticle(
                particle_id=f"{connection_id}_particle_{i}",
                connection_id=connection_id,
                position=i / self.particle_count_per_connection,
                speed=self.animation_speed * (0.8 + 0.4 * (i / self.particle_count_per_connection))
            )
            particles.append(particle)
        
        self.flow_particles[connection_id] = particles
    
    def update_data_flow(self, connection_id: str, data_value: Any,
                        transformation_type: str = None):
        """Update data flow information for a connection."""
        if connection_id not in self.data_flow_info:
            return
        
        flow_info = self.data_flow_info[connection_id]
        
        # Update flow info
        flow_info.previous_value = flow_info.current_value
        flow_info.current_value = data_value
        flow_info.timestamp = time.time()
        
        if transformation_type:
            flow_info.transformation_applied = True
            flow_info.transformation_type = transformation_type
        
        # Update particle colors based on data type
        if connection_id in self.flow_particles:
            data_type = type(data_value).__name__
            color = self._get_type_color(data_type)
            for particle in self.flow_particles[connection_id]:
                particle.color = color
                particle.data_value = data_value
        
        # Update visualization highlighting
        if connection_id in self.connection_visualizations:
            viz = self.connection_visualizations[connection_id]
            viz.highlight_active = True
            
            # Update line color based on data type
            viz.line_color = self._get_type_color(type(data_value).__name__)
            
            # Update performance indicator
            if connection_id in self.performance_metrics:
                perf_level = self.performance_metrics[connection_id].get_performance_level()
                viz.performance_indicator = perf_level
        
        # Trigger callback
        if self.on_data_flow_update:
            self.on_data_flow_update(connection_id, flow_info)
        
        # Start tracing if not already active
        trace_id = f"flow_{connection_id}_{int(time.time())}"
        connection = next((c for c in self.model.connections if c.id == connection_id), None)
        if connection:
            self.tracer.trace_data_flow(
                trace_id, connection_id, data_value,
                connection.source_node_id, connection.target_node_id
            )
    
    def update_performance_metrics(self, connection_id: str, **metrics):
        """Update performance metrics for a connection."""
        if connection_id not in self.performance_metrics:
            return
        
        perf_metrics = self.performance_metrics[connection_id]
        perf_metrics.update_metrics(**metrics)
        
        # Check for performance alerts
        perf_level = perf_metrics.get_performance_level()
        if perf_level in [PerformanceLevel.WARNING, PerformanceLevel.CRITICAL]:
            if self.on_performance_alert:
                self.on_performance_alert(connection_id, perf_level)
            
            # Check for bottlenecks
            if perf_level == PerformanceLevel.CRITICAL:
                bottleneck_info = {
                    'connection_id': connection_id,
                    'throughput': perf_metrics.throughput,
                    'latency': perf_metrics.latency,
                    'error_rate': perf_metrics.error_rate,
                    'cpu_usage': perf_metrics.cpu_usage
                }
                if self.on_bottleneck_detected:
                    self.on_bottleneck_detected(connection_id, bottleneck_info)
        
        # Update visualization
        if connection_id in self.connection_visualizations:
            viz = self.connection_visualizations[connection_id]
            viz.performance_indicator = perf_level
            
            # Adjust line width based on throughput
            base_width = 2.0
            throughput_factor = min(perf_metrics.throughput / 100.0, 3.0)
            viz.line_width = base_width + throughput_factor
    
    def highlight_data_transformation(self, connection_id: str, input_data: Any,
                                    output_data: Any, transformation_type: str):
        """Highlight a data transformation on a connection."""
        if connection_id not in self.data_flow_info:
            return
        
        flow_info = self.data_flow_info[connection_id]
        flow_info.transformation_applied = True
        flow_info.transformation_type = transformation_type
        
        # Update visualization with transformation highlighting
        if connection_id in self.connection_visualizations:
            viz = self.connection_visualizations[connection_id]
            viz.highlight_active = True
            viz.animation_type = FlowAnimationType.GLOW
            viz.animation_speed = 2.0  # Faster animation for transformations
        
        # Trace the transformation
        trace_id = f"transform_{connection_id}_{int(time.time())}"
        self.tracer.trace_data_transformation(
            trace_id, connection_id, input_data, output_data, transformation_type
        )
    
    def inspect_connection_point(self, connection_id: str, position: float = 0.5) -> Dict[str, Any]:
        """Inspect data at a specific point along a connection during debugging."""
        if connection_id not in self.data_flow_info:
            return {}
        
        flow_info = self.data_flow_info[connection_id]
        connection = next((c for c in self.model.connections if c.id == connection_id), None)
        
        inspection_data = {
            'connection_id': connection_id,
            'position': position,
            'current_value': flow_info.current_value,
            'data_type': flow_info.data_type,
            'timestamp': flow_info.timestamp,
            'has_transformation': flow_info.transformation_applied,
            'transformation_type': flow_info.transformation_type,
            'value_changed': flow_info.has_value_changed(),
            'type_change': flow_info.get_type_change()
        }
        
        if connection:
            inspection_data.update({
                'source_node': connection.source_node_id,
                'source_port': connection.source_port,
                'target_node': connection.target_node_id,
                'target_port': connection.target_port
            })
        
        # Add performance metrics
        if connection_id in self.performance_metrics:
            perf = self.performance_metrics[connection_id]
            inspection_data['performance'] = {
                'throughput': perf.throughput,
                'latency': perf.latency,
                'error_rate': perf.error_rate,
                'performance_level': perf.get_performance_level().value
            }
        
        return inspection_data
    
    def get_connection_visualization(self, connection_id: str) -> Optional[ConnectionVisualization]:
        """Get the visualization for a connection."""
        return self.connection_visualizations.get(connection_id)
    
    def get_all_visualizations(self) -> Dict[str, ConnectionVisualization]:
        """Get all connection visualizations."""
        return self.connection_visualizations.copy()
    
    def get_flow_particles(self, connection_id: str) -> List[FlowParticle]:
        """Get flow particles for a connection."""
        return self.flow_particles.get(connection_id, [])
    
    def get_performance_bottlenecks(self) -> List[Dict[str, Any]]:
        """Get all connections with performance bottlenecks."""
        bottlenecks = []
        for connection_id, metrics in self.performance_metrics.items():
            if metrics.get_performance_level() == PerformanceLevel.CRITICAL:
                bottlenecks.append({
                    'connection_id': connection_id,
                    'metrics': {
                        'throughput': metrics.throughput,
                        'latency': metrics.latency,
                        'error_rate': metrics.error_rate,
                        'cpu_usage': metrics.cpu_usage
                    }
                })
        return bottlenecks
    
    def start_animation(self):
        """Start the animation thread."""
        if self._animation_thread is None or not self._animation_thread.is_alive():
            self._stop_animation = False
            self._animation_thread = threading.Thread(target=self._animation_loop)
            self._animation_thread.daemon = True
            self._animation_thread.start()
    
    def stop_animation(self):
        """Stop the animation thread."""
        self._stop_animation = True
        if self._animation_thread and self._animation_thread.is_alive():
            self._animation_thread.join(timeout=1.0)
    
    def _animation_loop(self):
        """Main animation loop."""
        while not self._stop_animation:
            current_time = time.time()
            delta_time = current_time - self._last_update_time
            self._last_update_time = current_time
            
            # Update all particles
            for connection_id, particles in self.flow_particles.items():
                for particle in particles:
                    particle.update_position(delta_time)
                
                # Remove expired particles and create new ones
                active_particles = [p for p in particles if not p.is_expired()]
                while len(active_particles) < self.particle_count_per_connection:
                    new_particle = FlowParticle(
                        particle_id=f"{connection_id}_particle_{len(active_particles)}",
                        connection_id=connection_id,
                        speed=self.animation_speed
                    )
                    active_particles.append(new_particle)
                
                self.flow_particles[connection_id] = active_particles
            
            # Sleep for smooth animation (60 FPS)
            time.sleep(1.0 / 60.0)
    
    def _get_type_color(self, data_type: str) -> str:
        """Get color for a data type."""
        type_colors = {
            'int': '#ff6b6b',
            'float': '#4ecdc4',
            'str': '#45b7d1',
            'bool': '#96ceb4',
            'list': '#ffeaa7',
            'dict': '#dda0dd',
            'tuple': '#98d8c8',
            'set': '#f7dc6f',
            'NoneType': '#95a5a6',
            'function': '#e17055',
            'object': '#74b9ff'
        }
        return type_colors.get(data_type, '#666666')
    
    def set_animation_enabled(self, enabled: bool):
        """Enable or disable animations."""
        self.animation_enabled = enabled
        if enabled:
            self.start_animation()
        else:
            self.stop_animation()
    
    def set_animation_speed(self, speed: float):
        """Set animation speed multiplier."""
        self.animation_speed = max(0.1, min(speed, 5.0))
        
        # Update existing particles
        for particles in self.flow_particles.values():
            for particle in particles:
                particle.speed = self.animation_speed
    
    def set_show_performance_indicators(self, show: bool):
        """Enable or disable performance indicators."""
        self.show_performance_indicators = show
        
        # Update visualizations
        for viz in self.connection_visualizations.values():
            if not show:
                viz.performance_indicator = PerformanceLevel.OPTIMAL
    
    def set_show_data_labels(self, show: bool):
        """Enable or disable data labels."""
        self.show_data_labels = show
        for viz in self.connection_visualizations.values():
            viz.show_data_labels = show
    
    def set_show_direction_arrows(self, show: bool):
        """Enable or disable direction arrows."""
        self.show_direction_arrows = show
        for viz in self.connection_visualizations.values():
            viz.show_direction_arrow = show
    
    def clear_all_highlights(self):
        """Clear all connection highlights."""
        for viz in self.connection_visualizations.values():
            viz.highlight_active = False
            viz.animation_type = FlowAnimationType.PARTICLE
            viz.animation_speed = self.animation_speed
    
    def get_visualization_state(self) -> Dict[str, Any]:
        """Get the current state of the visualization system."""
        return {
            'animation_enabled': self.animation_enabled,
            'animation_speed': self.animation_speed,
            'show_performance_indicators': self.show_performance_indicators,
            'show_data_labels': self.show_data_labels,
            'show_direction_arrows': self.show_direction_arrows,
            'connection_count': len(self.connection_visualizations),
            'active_particles': sum(len(particles) for particles in self.flow_particles.values()),
            'active_traces': len(self.tracer.get_active_traces()),
            'performance_bottlenecks': len(self.get_performance_bottlenecks())
        }
    
    def cleanup(self):
        """Clean up resources."""
        self.stop_animation()
        self.tracer.clear_trace_history()
        self.connection_visualizations.clear()
        self.data_flow_info.clear()
        self.flow_particles.clear()
        self.performance_metrics.clear()