"""
Unit tests for Canvas class.
"""

import pytest
from hypothesis import given, strategies as st
from visual_editor_core.canvas import (
    Canvas, ViewportState, DragOperation, ConnectionPreview, 
    SelectionMode, CanvasMode
)
from visual_editor_core.models import VisualNode, NodeType, InputPort, OutputPort


class TestViewportState:
    """Test cases for ViewportState class."""
    
    def test_viewport_creation(self):
        """Test basic viewport creation."""
        viewport = ViewportState()
        assert viewport.zoom == 1.0
        assert viewport.pan_x == 0.0
        assert viewport.pan_y == 0.0
    
    def test_world_to_screen_conversion(self):
        """Test world to screen coordinate conversion."""
        viewport = ViewportState(zoom=2.0, pan_x=10.0, pan_y=20.0)
        
        screen_x, screen_y = viewport.world_to_screen(100.0, 200.0)
        
        # (100 + 10) * 2 = 220, (200 + 20) * 2 = 440
        assert screen_x == 220.0
        assert screen_y == 440.0
    
    def test_screen_to_world_conversion(self):
        """Test screen to world coordinate conversion."""
        viewport = ViewportState(zoom=2.0, pan_x=10.0, pan_y=20.0)
        
        world_x, world_y = viewport.screen_to_world(220.0, 440.0)
        
        # (220 / 2) - 10 = 100, (440 / 2) - 20 = 200
        assert world_x == 100.0
        assert world_y == 200.0
    
    def test_round_trip_conversion(self):
        """Test round-trip coordinate conversion."""
        viewport = ViewportState(zoom=1.5, pan_x=5.0, pan_y=-10.0)
        
        original_x, original_y = 150.0, 300.0
        screen_x, screen_y = viewport.world_to_screen(original_x, original_y)
        world_x, world_y = viewport.screen_to_world(screen_x, screen_y)
        
        assert abs(world_x - original_x) < 0.001
        assert abs(world_y - original_y) < 0.001


class TestCanvas:
    """Test cases for Canvas class."""
    
    def test_canvas_creation(self):
        """Test basic canvas creation."""
        canvas = Canvas(1920, 1080)
        
        assert canvas.viewport.width == 1920
        assert canvas.viewport.height == 1080
        assert len(canvas.model.nodes) == 0
        assert len(canvas.selected_nodes) == 0
    
    def test_add_node(self):
        """Test adding nodes to canvas."""
        canvas = Canvas()
        node = VisualNode(type=NodeType.FUNCTION)
        
        node_id = canvas.add_node(node, (100, 200))
        
        assert node_id in canvas.model.nodes
        assert canvas.model.nodes[node_id].position == (100, 200)
    
    def test_add_node_with_grid_snap(self):
        """Test adding nodes with grid snapping."""
        canvas = Canvas()
        canvas.snap_to_grid = True
        canvas.grid_size = 20.0
        
        node = VisualNode(type=NodeType.FUNCTION)
        node_id = canvas.add_node(node, (105, 195))
        
        # Should snap to nearest grid point (100, 200)
        assert canvas.model.nodes[node_id].position == (100, 200)
    
    def test_remove_node(self):
        """Test removing nodes from canvas."""
        canvas = Canvas()
        node = VisualNode(type=NodeType.FUNCTION)
        
        node_id = canvas.add_node(node)
        assert node_id in canvas.model.nodes
        
        success = canvas.remove_node(node_id)
        assert success is True
        assert node_id not in canvas.model.nodes
    
    def test_move_node(self):
        """Test moving nodes."""
        canvas = Canvas()
        node = VisualNode(type=NodeType.FUNCTION)
        
        node_id = canvas.add_node(node, (100, 100))
        success = canvas.move_node(node_id, (200, 300))
        
        assert success is True
        assert canvas.model.nodes[node_id].position == (200, 300)
    
    def test_select_node(self):
        """Test node selection."""
        canvas = Canvas()
        node = VisualNode(type=NodeType.FUNCTION)
        
        node_id = canvas.add_node(node)
        success = canvas.select_node(node_id)
        
        assert success is True
        assert node_id in canvas.selected_nodes
    
    def test_select_multiple_nodes(self):
        """Test multiple node selection."""
        canvas = Canvas()
        canvas.selection_mode = SelectionMode.MULTIPLE
        
        node1 = VisualNode(type=NodeType.FUNCTION)
        node2 = VisualNode(type=NodeType.VARIABLE)
        
        node1_id = canvas.add_node(node1)
        node2_id = canvas.add_node(node2)
        
        canvas.select_node(node1_id)
        canvas.select_node(node2_id, extend_selection=True)
        
        assert node1_id in canvas.selected_nodes
        assert node2_id in canvas.selected_nodes
        assert len(canvas.selected_nodes) == 2
    
    def test_clear_selection(self):
        """Test clearing selection."""
        canvas = Canvas()
        node = VisualNode(type=NodeType.FUNCTION)
        
        node_id = canvas.add_node(node)
        canvas.select_node(node_id)
        assert len(canvas.selected_nodes) == 1
        
        canvas.clear_selection()
        assert len(canvas.selected_nodes) == 0
    
    def test_select_nodes_in_rectangle(self):
        """Test rectangle selection."""
        canvas = Canvas()
        canvas.snap_to_grid = False  # Disable grid snapping for precise positioning
        canvas.selection_mode = SelectionMode.MULTIPLE  # Enable multiple selection
        
        # Add nodes at different positions
        node1 = VisualNode(type=NodeType.FUNCTION)
        node2 = VisualNode(type=NodeType.VARIABLE)
        node3 = VisualNode(type=NodeType.CLASS)
        
        node1_id = canvas.add_node(node1, (50, 50))
        node2_id = canvas.add_node(node2, (150, 150))
        node3_id = canvas.add_node(node3, (250, 250))
        
        # Select rectangle that includes first two nodes
        canvas.select_nodes_in_rectangle(0, 0, 200, 200)
        
        assert node1_id in canvas.selected_nodes
        assert node2_id in canvas.selected_nodes
        assert node3_id not in canvas.selected_nodes
    
    def test_drag_operation(self):
        """Test drag operations."""
        canvas = Canvas()
        canvas.snap_to_grid = False  # Disable grid snapping for precise positioning
        node = VisualNode(type=NodeType.FUNCTION)
        
        node_id = canvas.add_node(node, (100, 100))
        
        # Start drag
        success = canvas.start_drag_operation([node_id])
        assert success is True
        assert canvas.drag_operation is not None
        assert canvas.drag_operation.is_active is True
        
        # Update drag
        canvas.update_drag_operation((50, 30))
        assert canvas.model.nodes[node_id].position == (150, 130)
        
        # End drag
        canvas.end_drag_operation()
        assert canvas.drag_operation.is_active is False
    
    def test_cancel_drag_operation(self):
        """Test canceling drag operations."""
        canvas = Canvas()
        node = VisualNode(type=NodeType.FUNCTION)
        
        node_id = canvas.add_node(node, (100, 100))
        original_pos = canvas.model.nodes[node_id].position
        
        # Start and update drag
        canvas.start_drag_operation([node_id])
        canvas.update_drag_operation((50, 30))
        
        # Cancel drag - should restore original position
        canvas.cancel_drag_operation()
        assert canvas.model.nodes[node_id].position == original_pos
        assert canvas.drag_operation is None
    
    def test_connection_creation(self):
        """Test creating connections between nodes."""
        canvas = Canvas()
        
        # Create source node with output
        source_node = VisualNode(
            type=NodeType.VARIABLE,
            outputs=[OutputPort(name="value", data_type=str)]
        )
        source_id = canvas.add_node(source_node)
        
        # Create target node with input
        target_node = VisualNode(
            type=NodeType.FUNCTION,
            inputs=[InputPort(name="input", data_type=str)]
        )
        target_id = canvas.add_node(target_node)
        
        # Start connection
        success = canvas.start_connection(source_id, "value", (200, 200))
        assert success is True
        assert canvas.connection_preview is not None
        
        # Update connection preview
        canvas.update_connection_preview((300, 300), target_id, "input")
        assert canvas.connection_preview.is_valid is True
        
        # Complete connection
        connection = canvas.complete_connection()
        assert connection is not None
        assert len(canvas.model.connections) == 1
    
    def test_invalid_connection(self):
        """Test invalid connection handling."""
        canvas = Canvas()
        
        # Create nodes with incompatible types
        source_node = VisualNode(
            type=NodeType.VARIABLE,
            outputs=[OutputPort(name="value", data_type=str)]
        )
        source_id = canvas.add_node(source_node)
        
        target_node = VisualNode(
            type=NodeType.FUNCTION,
            inputs=[InputPort(name="input", data_type=int)]  # Different type
        )
        target_id = canvas.add_node(target_node)
        
        # Try to create connection
        canvas.start_connection(source_id, "value", (200, 200))
        canvas.update_connection_preview((300, 300), target_id, "input")
        
        # Should be invalid due to type mismatch
        assert canvas.connection_preview.is_valid is False
        
        connection = canvas.complete_connection()
        assert connection is None
        assert len(canvas.model.connections) == 0
    
    def test_zoom_operations(self):
        """Test zoom operations."""
        canvas = Canvas()
        
        # Test set zoom
        canvas.set_zoom(2.0)
        assert canvas.viewport.zoom == 2.0
        
        # Test zoom limits
        canvas.set_zoom(10.0)  # Should be clamped to max
        assert canvas.viewport.zoom == 5.0
        
        canvas.set_zoom(0.01)  # Should be clamped to min
        assert canvas.viewport.zoom == 0.1
    
    def test_zoom_to_fit(self):
        """Test zoom to fit functionality."""
        canvas = Canvas()
        
        # Add nodes at various positions
        node1 = VisualNode(type=NodeType.FUNCTION)
        node2 = VisualNode(type=NodeType.VARIABLE)
        
        canvas.add_node(node1, (0, 0))
        canvas.add_node(node2, (1000, 1000))
        
        original_zoom = canvas.viewport.zoom
        canvas.zoom_to_fit()
        
        # Zoom should have changed to fit all nodes
        assert canvas.viewport.zoom != original_zoom
    
    def test_pan_viewport(self):
        """Test viewport panning."""
        canvas = Canvas()
        
        original_pan_x = canvas.viewport.pan_x
        original_pan_y = canvas.viewport.pan_y
        
        canvas.pan_viewport(100, 50)
        
        # Pan should have changed
        assert canvas.viewport.pan_x != original_pan_x
        assert canvas.viewport.pan_y != original_pan_y
    
    def test_get_node_at_position(self):
        """Test finding nodes at positions."""
        canvas = Canvas()
        node = VisualNode(type=NodeType.FUNCTION)
        
        node_id = canvas.add_node(node, (100, 200))
        
        # Should find node at exact position
        found_id = canvas.get_node_at_position(100, 200)
        assert found_id == node_id
        
        # Should find node within tolerance
        found_id = canvas.get_node_at_position(105, 195, tolerance=10)
        assert found_id == node_id
        
        # Should not find node outside tolerance
        found_id = canvas.get_node_at_position(150, 250, tolerance=10)
        assert found_id is None
    
    def test_model_validation(self):
        """Test model validation."""
        canvas = Canvas()
        
        # Add valid nodes
        node1 = VisualNode(type=NodeType.FUNCTION, parameters={'function_name': 'test'})
        node2 = VisualNode(type=NodeType.VARIABLE, parameters={'variable_name': 'var'})
        
        canvas.add_node(node1)
        canvas.add_node(node2)
        
        errors = canvas.validate_model()
        assert len(errors) == 0
    
    def test_canvas_state(self):
        """Test getting canvas state."""
        canvas = Canvas()
        node = VisualNode(type=NodeType.FUNCTION)
        
        canvas.add_node(node)
        canvas.select_node(list(canvas.model.nodes.keys())[0])
        
        state = canvas.get_canvas_state()
        
        assert "viewport" in state
        assert "selection" in state
        assert "settings" in state
        assert "model" in state
        
        assert state["model"]["node_count"] == 1
        assert len(state["selection"]["selected_nodes"]) == 1
    
    def test_move_selected_nodes(self):
        """Test moving selected nodes."""
        canvas = Canvas()
        canvas.selection_mode = SelectionMode.MULTIPLE
        canvas.snap_to_grid = False  # Disable grid snapping for precise positioning
        
        # Add and select multiple nodes
        node1 = VisualNode(type=NodeType.FUNCTION)
        node2 = VisualNode(type=NodeType.VARIABLE)
        
        node1_id = canvas.add_node(node1, (100, 100))
        node2_id = canvas.add_node(node2, (200, 200))
        
        canvas.select_node(node1_id)
        canvas.select_node(node2_id, extend_selection=True)
        
        # Move selected nodes
        canvas.move_selected_nodes((50, 30))
        
        assert canvas.model.nodes[node1_id].position == (150, 130)
        assert canvas.model.nodes[node2_id].position == (250, 230)
    
    def test_zoom_to_selection(self):
        """Test zoom to selection functionality."""
        canvas = Canvas()
        
        # Add and select nodes
        node1 = VisualNode(type=NodeType.FUNCTION)
        node2 = VisualNode(type=NodeType.VARIABLE)
        
        node1_id = canvas.add_node(node1, (0, 0))
        node2_id = canvas.add_node(node2, (500, 500))
        
        canvas.select_node(node1_id)
        canvas.select_node(node2_id, extend_selection=True)
        
        original_zoom = canvas.viewport.zoom
        canvas.zoom_to_selection()
        
        # Zoom should have changed
        assert canvas.viewport.zoom != original_zoom


# Property-based tests
@given(st.floats(min_value=0.1, max_value=5.0))
def test_zoom_property(zoom_level):
    """Property test: Canvas should handle any valid zoom level."""
    canvas = Canvas()
    canvas.set_zoom(zoom_level)
    
    # Zoom should be within valid range
    assert 0.1 <= canvas.viewport.zoom <= 5.0


@given(st.floats(allow_nan=False, allow_infinity=False), 
       st.floats(allow_nan=False, allow_infinity=False))
def test_pan_property(pan_x, pan_y):
    """Property test: Canvas should handle any pan values."""
    canvas = Canvas()
    
    try:
        canvas.pan_viewport(pan_x, pan_y)
        # Should not crash with any valid float values
        assert isinstance(canvas.viewport.pan_x, float)
        assert isinstance(canvas.viewport.pan_y, float)
    except (OverflowError, ValueError):
        # Some extreme values might cause issues, which is acceptable
        pass


@given(st.integers(min_value=1, max_value=20))
def test_multiple_nodes_selection_property(num_nodes):
    """Property test: Canvas should handle selecting any number of nodes."""
    canvas = Canvas()
    canvas.selection_mode = SelectionMode.MULTIPLE
    
    node_ids = []
    for i in range(num_nodes):
        node = VisualNode(type=NodeType.FUNCTION)
        node_id = canvas.add_node(node, (i * 100, i * 100))
        node_ids.append(node_id)
        canvas.select_node(node_id, extend_selection=True)
    
    assert len(canvas.selected_nodes) == num_nodes
    assert all(nid in canvas.selected_nodes for nid in node_ids)