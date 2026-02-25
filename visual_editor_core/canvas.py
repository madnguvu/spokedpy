"""
Canvas class for visual workspace management.

This module provides the Canvas class which manages the visual workspace where users
can arrange and connect visual elements. It handles drag-and-drop, zooming, panning,
and multi-selection operations.
"""

from typing import Dict, List, Tuple, Optional, Set, Any, Callable
from dataclasses import dataclass
from enum import Enum
import uuid
from .models import VisualNode, Connection, VisualModel, ValidationError
from .data_flow_visualizer import DataFlowVisualizer, DataFlowInfo, PerformanceLevel


class SelectionMode(Enum):
    """Selection modes for the canvas."""
    SINGLE = "single"
    MULTIPLE = "multiple"
    RECTANGLE = "rectangle"


class CanvasMode(Enum):
    """Canvas interaction modes."""
    SELECT = "select"
    CONNECT = "connect"
    PAN = "pan"
    ZOOM = "zoom"


@dataclass
class ViewportState:
    """Represents the current viewport state."""
    zoom: float = 1.0
    pan_x: float = 0.0
    pan_y: float = 0.0
    width: float = 1920.0
    height: float = 1080.0
    
    def world_to_screen(self, world_x: float, world_y: float) -> Tuple[float, float]:
        """Convert world coordinates to screen coordinates."""
        screen_x = (world_x + self.pan_x) * self.zoom
        screen_y = (world_y + self.pan_y) * self.zoom
        return screen_x, screen_y
    
    def screen_to_world(self, screen_x: float, screen_y: float) -> Tuple[float, float]:
        """Convert screen coordinates to world coordinates."""
        world_x = (screen_x / self.zoom) - self.pan_x
        world_y = (screen_y / self.zoom) - self.pan_y
        return world_x, world_y


@dataclass
class DragOperation:
    """Represents an ongoing drag operation."""
    node_ids: List[str]
    start_positions: Dict[str, Tuple[float, float]]
    current_offset: Tuple[float, float] = (0.0, 0.0)
    is_active: bool = False


@dataclass
class ConnectionPreview:
    """Represents a connection being created."""
    source_node_id: str
    source_port: str
    target_position: Tuple[float, float]
    is_valid: bool = False
    target_node_id: Optional[str] = None
    target_port: Optional[str] = None


class Canvas:
    """Manages the visual workspace for arranging and connecting visual elements."""
    
    def __init__(self, width: float = 1920.0, height: float = 1080.0):
        self.model = VisualModel()
        self.viewport = ViewportState(width=width, height=height)
        
        # Data flow visualization
        self.data_flow_visualizer = DataFlowVisualizer(self.model)
        
        # Selection state
        self.selected_nodes: Set[str] = set()
        self.selection_mode = SelectionMode.SINGLE
        self.selection_rectangle: Optional[Tuple[float, float, float, float]] = None
        
        # Interaction state
        self.canvas_mode = CanvasMode.SELECT
        self.drag_operation: Optional[DragOperation] = None
        self.connection_preview: Optional[ConnectionPreview] = None
        
        # Grid settings
        self.grid_size = 20.0
        self.snap_to_grid = True
        self.show_grid = True
        
        # Data flow visualization settings
        self.show_data_flow = True
        self.show_performance_indicators = True
        self.animate_data_flow = True
        
        # Event callbacks
        self.on_node_selected: Optional[Callable[[str], None]] = None
        self.on_node_deselected: Optional[Callable[[str], None]] = None
        self.on_connection_created: Optional[Callable[[Connection], None]] = None
        self.on_model_changed: Optional[Callable[[], None]] = None
        self.on_data_flow_update: Optional[Callable[[str, DataFlowInfo], None]] = None
        self.on_performance_alert: Optional[Callable[[str, PerformanceLevel], None]] = None
        
        # Validation
        self.enable_connection_validation = True
        self.show_connection_feedback = True
        
        # Set up data flow visualizer callbacks
        self._setup_data_flow_callbacks()
    
    def add_node(self, node: VisualNode, position: Optional[Tuple[float, float]] = None) -> str:
        """Add a node to the canvas at the specified position."""
        if position:
            if self.snap_to_grid:
                position = self._snap_to_grid(position)
            node.position = position
        
        node_id = self.model.add_node(node)
        self._trigger_model_changed()
        return node_id
    
    def remove_node(self, node_id: str) -> bool:
        """Remove a node from the canvas."""
        if node_id in self.selected_nodes:
            self.selected_nodes.remove(node_id)
        
        success = self.model.remove_node(node_id)
        if success:
            self._trigger_model_changed()
        return success
    
    def move_node(self, node_id: str, new_position: Tuple[float, float]):
        """Move a node to a new position."""
        if node_id not in self.model.nodes:
            return False
        
        if self.snap_to_grid:
            new_position = self._snap_to_grid(new_position)
        
        self.model.nodes[node_id].position = new_position
        self._trigger_model_changed()
        return True
    
    def move_selected_nodes(self, offset: Tuple[float, float]):
        """Move all selected nodes by the given offset."""
        for node_id in self.selected_nodes:
            if node_id in self.model.nodes:
                current_pos = self.model.nodes[node_id].position
                new_pos = (current_pos[0] + offset[0], current_pos[1] + offset[1])
                self.move_node(node_id, new_pos)
    
    def select_node(self, node_id: str, extend_selection: bool = False):
        """Select a node on the canvas."""
        if node_id not in self.model.nodes:
            return False
        
        if not extend_selection or self.selection_mode == SelectionMode.SINGLE:
            self.clear_selection()
        
        if node_id not in self.selected_nodes:
            self.selected_nodes.add(node_id)
            if self.on_node_selected:
                self.on_node_selected(node_id)
        
        return True
    
    def deselect_node(self, node_id: str):
        """Deselect a node on the canvas."""
        if node_id in self.selected_nodes:
            self.selected_nodes.remove(node_id)
            if self.on_node_deselected:
                self.on_node_deselected(node_id)
    
    def clear_selection(self):
        """Clear all selected nodes."""
        for node_id in list(self.selected_nodes):
            self.deselect_node(node_id)
    
    def select_nodes_in_rectangle(self, x1: float, y1: float, x2: float, y2: float):
        """Select all nodes within the given rectangle."""
        min_x, max_x = min(x1, x2), max(x1, x2)
        min_y, max_y = min(y1, y2), max(y1, y2)
        
        for node_id, node in self.model.nodes.items():
            node_x, node_y = node.position
            if min_x <= node_x <= max_x and min_y <= node_y <= max_y:
                self.select_node(node_id, extend_selection=True)
    
    def start_drag_operation(self, node_ids: List[str]):
        """Start a drag operation for the specified nodes."""
        if not node_ids:
            return False
        
        # Ensure all nodes exist
        valid_node_ids = [nid for nid in node_ids if nid in self.model.nodes]
        if not valid_node_ids:
            return False
        
        # Store starting positions
        start_positions = {}
        for node_id in valid_node_ids:
            start_positions[node_id] = self.model.nodes[node_id].position
        
        self.drag_operation = DragOperation(
            node_ids=valid_node_ids,
            start_positions=start_positions,
            is_active=True
        )
        return True
    
    def update_drag_operation(self, offset: Tuple[float, float]):
        """Update the current drag operation with new offset."""
        if not self.drag_operation or not self.drag_operation.is_active:
            return False
        
        self.drag_operation.current_offset = offset
        
        # Update node positions
        for node_id in self.drag_operation.node_ids:
            if node_id in self.model.nodes:
                start_pos = self.drag_operation.start_positions[node_id]
                new_pos = (start_pos[0] + offset[0], start_pos[1] + offset[1])
                
                if self.snap_to_grid:
                    new_pos = self._snap_to_grid(new_pos)
                
                self.model.nodes[node_id].position = new_pos
        
        return True
    
    def end_drag_operation(self):
        """End the current drag operation."""
        if self.drag_operation and self.drag_operation.is_active:
            self.drag_operation.is_active = False
            self._trigger_model_changed()
            return True
        return False
    
    def cancel_drag_operation(self):
        """Cancel the current drag operation and restore original positions."""
        if not self.drag_operation:
            return False
        
        # Restore original positions
        for node_id in self.drag_operation.node_ids:
            if node_id in self.model.nodes:
                original_pos = self.drag_operation.start_positions[node_id]
                self.model.nodes[node_id].position = original_pos
        
        self.drag_operation = None
        self._trigger_model_changed()
        return True
    
    def start_connection(self, source_node_id: str, source_port: str, 
                        target_position: Tuple[float, float]):
        """Start creating a connection from a source port."""
        if source_node_id not in self.model.nodes:
            return False
        
        source_node = self.model.nodes[source_node_id]
        if not source_node.get_output_port(source_port):
            return False
        
        self.connection_preview = ConnectionPreview(
            source_node_id=source_node_id,
            source_port=source_port,
            target_position=target_position
        )
        return True
    
    def update_connection_preview(self, target_position: Tuple[float, float], 
                                 target_node_id: Optional[str] = None, 
                                 target_port: Optional[str] = None):
        """Update the connection preview with new target information."""
        if not self.connection_preview:
            return False
        
        self.connection_preview.target_position = target_position
        self.connection_preview.target_node_id = target_node_id
        self.connection_preview.target_port = target_port
        
        # Validate connection if we have a target
        if target_node_id and target_port and self.enable_connection_validation:
            self.connection_preview.is_valid = self._validate_connection(
                self.connection_preview.source_node_id,
                self.connection_preview.source_port,
                target_node_id,
                target_port
            )
        else:
            self.connection_preview.is_valid = False
        
        return True
    
    def complete_connection(self) -> Optional[Connection]:
        """Complete the current connection if valid."""
        if not self.connection_preview:
            return None
        
        if (self.connection_preview.target_node_id and 
            self.connection_preview.target_port and
            self.connection_preview.is_valid):
            
            connection = self.model.connect_nodes(
                self.connection_preview.source_node_id,
                self.connection_preview.source_port,
                self.connection_preview.target_node_id,
                self.connection_preview.target_port
            )
            
            if connection:
                # Update data flow visualizer with new connection
                self.data_flow_visualizer._create_connection_visualization(connection)
                
                if self.on_connection_created:
                    self.on_connection_created(connection)
            
            self.connection_preview = None
            self._trigger_model_changed()
            return connection
        
        return None
    
    def cancel_connection(self):
        """Cancel the current connection preview."""
        self.connection_preview = None
    
    def remove_connection(self, connection_id: str) -> bool:
        """Remove a connection from the canvas."""
        # Find and remove the connection
        for i, connection in enumerate(self.model.connections):
            if connection.id == connection_id:
                del self.model.connections[i]
                
                # Remove from data flow visualizer
                if connection_id in self.data_flow_visualizer.connection_visualizations:
                    del self.data_flow_visualizer.connection_visualizations[connection_id]
                if connection_id in self.data_flow_visualizer.data_flow_info:
                    del self.data_flow_visualizer.data_flow_info[connection_id]
                if connection_id in self.data_flow_visualizer.flow_particles:
                    del self.data_flow_visualizer.flow_particles[connection_id]
                if connection_id in self.data_flow_visualizer.performance_metrics:
                    del self.data_flow_visualizer.performance_metrics[connection_id]
                
                self._trigger_model_changed()
                return True
        return False
    
    def zoom_to_fit(self, padding: float = 50.0):
        """Zoom the viewport to fit all nodes."""
        if not self.model.nodes:
            return
        
        # Calculate bounding box of all nodes
        positions = [node.position for node in self.model.nodes.values()]
        min_x = min(pos[0] for pos in positions) - padding
        max_x = max(pos[0] for pos in positions) + padding
        min_y = min(pos[1] for pos in positions) - padding
        max_y = max(pos[1] for pos in positions) + padding
        
        # Calculate zoom and pan to fit
        content_width = max_x - min_x
        content_height = max_y - min_y
        
        zoom_x = self.viewport.width / content_width if content_width > 0 else 1.0
        zoom_y = self.viewport.height / content_height if content_height > 0 else 1.0
        
        self.viewport.zoom = min(zoom_x, zoom_y, 2.0)  # Max zoom of 2x
        self.viewport.pan_x = -min_x
        self.viewport.pan_y = -min_y
    
    def zoom_to_selection(self, padding: float = 50.0):
        """Zoom the viewport to fit selected nodes."""
        if not self.selected_nodes:
            return
        
        # Calculate bounding box of selected nodes
        positions = [self.model.nodes[nid].position for nid in self.selected_nodes 
                    if nid in self.model.nodes]
        
        if not positions:
            return
        
        min_x = min(pos[0] for pos in positions) - padding
        max_x = max(pos[0] for pos in positions) + padding
        min_y = min(pos[1] for pos in positions) - padding
        max_y = max(pos[1] for pos in positions) + padding
        
        # Calculate zoom and pan
        content_width = max_x - min_x
        content_height = max_y - min_y
        
        zoom_x = self.viewport.width / content_width if content_width > 0 else 1.0
        zoom_y = self.viewport.height / content_height if content_height > 0 else 1.0
        
        self.viewport.zoom = min(zoom_x, zoom_y, 2.0)
        self.viewport.pan_x = -min_x
        self.viewport.pan_y = -min_y
    
    def set_zoom(self, zoom: float, center_x: float = 0.0, center_y: float = 0.0):
        """Set the zoom level, optionally centered on a point."""
        zoom = max(0.1, min(zoom, 5.0))  # Clamp zoom between 0.1x and 5x
        
        # Adjust pan to keep the center point in the same screen position
        old_zoom = self.viewport.zoom
        if old_zoom != zoom:
            zoom_factor = zoom / old_zoom
            self.viewport.pan_x = center_x - (center_x - self.viewport.pan_x) * zoom_factor
            self.viewport.pan_y = center_y - (center_y - self.viewport.pan_y) * zoom_factor
        
        self.viewport.zoom = zoom
    
    def pan_viewport(self, delta_x: float, delta_y: float):
        """Pan the viewport by the given delta."""
        self.viewport.pan_x += delta_x / self.viewport.zoom
        self.viewport.pan_y += delta_y / self.viewport.zoom
    
    def get_node_at_position(self, x: float, y: float, tolerance: float = 10.0) -> Optional[str]:
        """Get the node at the given position (in world coordinates)."""
        for node_id, node in self.model.nodes.items():
            node_x, node_y = node.position
            distance = ((x - node_x) ** 2 + (y - node_y) ** 2) ** 0.5
            if distance <= tolerance:
                return node_id
        return None
    
    def validate_model(self) -> List[ValidationError]:
        """Validate the current model and return any errors."""
        return self.model.validate_model()
    
    def get_canvas_state(self) -> Dict[str, Any]:
        """Get the current state of the canvas."""
        return {
            'viewport': {
                'zoom': self.viewport.zoom,
                'pan_x': self.viewport.pan_x,
                'pan_y': self.viewport.pan_y,
                'width': self.viewport.width,
                'height': self.viewport.height
            },
            'selection': {
                'selected_nodes': list(self.selected_nodes),
                'selection_mode': self.selection_mode.value
            },
            'settings': {
                'grid_size': self.grid_size,
                'snap_to_grid': self.snap_to_grid,
                'show_grid': self.show_grid,
                'show_data_flow': self.show_data_flow,
                'show_performance_indicators': self.show_performance_indicators,
                'animate_data_flow': self.animate_data_flow
            },
            'model': {
                'node_count': len(self.model.nodes),
                'connection_count': len(self.model.connections)
            },
            'data_flow': self.data_flow_visualizer.get_visualization_state()
        }
    
    def update_data_flow(self, connection_id: str, data_value: Any, transformation_type: str = None):
        """Update data flow information for a connection."""
        if self.show_data_flow:
            self.data_flow_visualizer.update_data_flow(connection_id, data_value, transformation_type)
    
    def update_connection_performance(self, connection_id: str, **metrics):
        """Update performance metrics for a connection."""
        if self.show_performance_indicators:
            self.data_flow_visualizer.update_performance_metrics(connection_id, **metrics)
    
    def highlight_data_transformation(self, connection_id: str, input_data: Any, 
                                    output_data: Any, transformation_type: str):
        """Highlight a data transformation on a connection."""
        if self.show_data_flow:
            self.data_flow_visualizer.highlight_data_transformation(
                connection_id, input_data, output_data, transformation_type
            )
    
    def inspect_connection_point(self, connection_id: str, position: float = 0.5) -> Dict[str, Any]:
        """Inspect data at a specific point along a connection during debugging."""
        return self.data_flow_visualizer.inspect_connection_point(connection_id, position)
    
    def get_connection_visualization(self, connection_id: str):
        """Get the visualization for a connection."""
        return self.data_flow_visualizer.get_connection_visualization(connection_id)
    
    def get_all_connection_visualizations(self):
        """Get all connection visualizations."""
        return self.data_flow_visualizer.get_all_visualizations()
    
    def get_flow_particles(self, connection_id: str):
        """Get flow particles for a connection."""
        return self.data_flow_visualizer.get_flow_particles(connection_id)
    
    def get_performance_bottlenecks(self):
        """Get all connections with performance bottlenecks."""
        return self.data_flow_visualizer.get_performance_bottlenecks()
    
    def set_data_flow_animation(self, enabled: bool):
        """Enable or disable data flow animation."""
        self.animate_data_flow = enabled
        self.data_flow_visualizer.set_animation_enabled(enabled)
    
    def set_data_flow_animation_speed(self, speed: float):
        """Set data flow animation speed."""
        self.data_flow_visualizer.set_animation_speed(speed)
    
    def set_show_data_flow(self, show: bool):
        """Enable or disable data flow visualization."""
        self.show_data_flow = show
        if not show:
            self.data_flow_visualizer.clear_all_highlights()
    
    def set_show_performance_indicators(self, show: bool):
        """Enable or disable performance indicators."""
        self.show_performance_indicators = show
        self.data_flow_visualizer.set_show_performance_indicators(show)
    
    def clear_data_flow_highlights(self):
        """Clear all data flow highlights."""
        self.data_flow_visualizer.clear_all_highlights()
    
    def start_data_flow_trace(self, connection_id: str, initial_data: Any) -> str:
        """Start tracing data flow for a connection."""
        import time
        trace_id = f"trace_{connection_id}_{int(time.time())}"
        self.data_flow_visualizer.tracer.start_trace(trace_id, connection_id, initial_data)
        return trace_id
    
    def end_data_flow_trace(self, trace_id: str):
        """End tracing for a specific trace ID."""
        self.data_flow_visualizer.tracer.end_trace(trace_id)
    
    def get_data_flow_trace_history(self, trace_id: str):
        """Get the trace history for a specific trace ID."""
        return self.data_flow_visualizer.tracer.get_trace_history(trace_id)
    
    def _setup_data_flow_callbacks(self):
        """Set up callbacks for data flow visualizer."""
        def on_data_flow_update(connection_id: str, flow_info: DataFlowInfo):
            if self.on_data_flow_update:
                self.on_data_flow_update(connection_id, flow_info)
        
        def on_performance_alert(connection_id: str, level: PerformanceLevel):
            if self.on_performance_alert:
                self.on_performance_alert(connection_id, level)
        
        self.data_flow_visualizer.on_data_flow_update = on_data_flow_update
        self.data_flow_visualizer.on_performance_alert = on_performance_alert
    
    def _snap_to_grid(self, position: Tuple[float, float]) -> Tuple[float, float]:
        """Snap a position to the grid."""
        x, y = position
        snapped_x = round(x / self.grid_size) * self.grid_size
        snapped_y = round(y / self.grid_size) * self.grid_size
        return snapped_x, snapped_y
    
    def _validate_connection(self, source_node_id: str, source_port: str,
                           target_node_id: str, target_port: str) -> bool:
        """Validate if a connection between two ports is valid."""
        if source_node_id not in self.model.nodes or target_node_id not in self.model.nodes:
            return False
        
        source_node = self.model.nodes[source_node_id]
        target_node = self.model.nodes[target_node_id]
        
        # Check if ports exist
        source_output = source_node.get_output_port(source_port)
        target_input = target_node.get_input_port(target_port)
        
        if not source_output or not target_input:
            return False
        
        # Check type compatibility
        if not source_output.is_compatible_with(target_input):
            return False
        
        # Check for existing connections to the target input
        for connection in self.model.connections:
            if (connection.target_node_id == target_node_id and 
                connection.target_port == target_port):
                return False  # Input already connected
        
        # Check for cycles (simplified check)
        if self._would_create_cycle(source_node_id, target_node_id):
            return False
        
        return True
    
    def _would_create_cycle(self, source_node_id: str, target_node_id: str) -> bool:
        """Check if connecting these nodes would create a cycle."""
        # Simple DFS to check for cycles
        visited = set()
        
        def has_path(start: str, end: str) -> bool:
            if start == end:
                return True
            if start in visited:
                return False
            
            visited.add(start)
            
            # Follow all outgoing connections
            for connection in self.model.connections:
                if connection.source_node_id == start:
                    if has_path(connection.target_node_id, end):
                        return True
            
            return False
        
        return has_path(target_node_id, source_node_id)
    
    def _trigger_model_changed(self):
        """Trigger the model changed callback."""
        if self.on_model_changed:
            self.on_model_changed()