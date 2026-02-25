"""
Tests for the data flow visualization system.
"""

import pytest
import time
from unittest.mock import Mock, patch
from visual_editor_core.data_flow_visualizer import (
    DataFlowVisualizer, DataFlowInfo, ConnectionVisualization, FlowParticle,
    PerformanceMetrics, DataFlowTracer, FlowDirection, FlowAnimationType,
    PerformanceLevel
)
from visual_editor_core.models import VisualModel, VisualNode, Connection, InputPort, OutputPort, NodeType


class TestDataFlowInfo:
    """Test DataFlowInfo class."""
    
    def test_data_flow_info_creation(self):
        """Test creating DataFlowInfo."""
        info = DataFlowInfo(
            connection_id="conn1",
            data_type="int",
            current_value=42,
            previous_value=41
        )
        
        assert info.connection_id == "conn1"
        assert info.data_type == "int"
        assert info.current_value == 42
        assert info.previous_value == 41
        assert info.flow_direction == FlowDirection.FORWARD
        assert isinstance(info.timestamp, float)
    
    def test_has_value_changed(self):
        """Test value change detection."""
        info = DataFlowInfo("conn1", "int", 42, 41)
        assert info.has_value_changed() is True
        
        info.previous_value = 42
        assert info.has_value_changed() is False
    
    def test_get_type_change(self):
        """Test type change detection."""
        info = DataFlowInfo("conn1", "int", 42, "41")
        type_change = info.get_type_change()
        assert type_change == ("str", "int")
        
        info.previous_value = 41
        assert info.get_type_change() is None


class TestConnectionVisualization:
    """Test ConnectionVisualization class."""
    
    def test_connection_visualization_creation(self):
        """Test creating ConnectionVisualization."""
        viz = ConnectionVisualization(
            connection_id="conn1",
            source_position=(0, 0),
            target_position=(100, 100)
        )
        
        assert viz.connection_id == "conn1"
        assert viz.source_position == (0, 0)
        assert viz.target_position == (100, 100)
        assert viz.line_width == 2.0
        assert viz.animation_type == FlowAnimationType.PARTICLE
    
    def test_calculate_bezier_curve(self):
        """Test bezier curve calculation."""
        viz = ConnectionVisualization(
            connection_id="conn1",
            source_position=(0, 0),
            target_position=(100, 100)
        )
        
        curve_points = viz.calculate_bezier_curve()
        assert len(curve_points) == 51  # 0 to 50 inclusive
        assert curve_points[0] == (0, 0)
        assert curve_points[-1] == (100, 100)
    
    def test_get_midpoint(self):
        """Test midpoint calculation."""
        viz = ConnectionVisualization(
            connection_id="conn1",
            source_position=(0, 0),
            target_position=(100, 100)
        )
        
        midpoint = viz.get_midpoint()
        assert isinstance(midpoint, tuple)
        assert len(midpoint) == 2
        # Midpoint should be roughly in the middle
        assert 40 <= midpoint[0] <= 60
        assert 40 <= midpoint[1] <= 60
    
    def test_get_direction_vector(self):
        """Test direction vector calculation."""
        viz = ConnectionVisualization(
            connection_id="conn1",
            source_position=(0, 0),
            target_position=(100, 0)
        )
        
        direction = viz.get_direction_vector()
        assert isinstance(direction, tuple)
        assert len(direction) == 2
        # Should point roughly to the right
        assert direction[0] > 0.5


class TestFlowParticle:
    """Test FlowParticle class."""
    
    def test_flow_particle_creation(self):
        """Test creating FlowParticle."""
        particle = FlowParticle(
            particle_id="p1",
            connection_id="conn1",
            position=0.5,
            speed=1.0
        )
        
        assert particle.particle_id == "p1"
        assert particle.connection_id == "conn1"
        assert particle.position == 0.5
        assert particle.speed == 1.0
        assert particle.size == 4.0
        assert particle.color == "#00ff00"
    
    def test_update_position(self):
        """Test particle position update."""
        particle = FlowParticle("p1", "conn1", position=0.0, speed=1.0)
        
        particle.update_position(0.5)  # 0.5 seconds
        assert particle.position == 0.5
        
        particle.update_position(0.6)  # Another 0.6 seconds
        assert abs(particle.position - 0.1) < 1e-10  # Should wrap around (1.1 -> 0.1)
    
    def test_is_expired(self):
        """Test particle expiration."""
        particle = FlowParticle("p1", "conn1")
        assert particle.is_expired(max_age=10.0) is False
        
        # Mock time to simulate aging
        with patch('time.time', return_value=particle.creation_time + 11.0):
            assert particle.is_expired(max_age=10.0) is True


class TestPerformanceMetrics:
    """Test PerformanceMetrics class."""
    
    def test_performance_metrics_creation(self):
        """Test creating PerformanceMetrics."""
        metrics = PerformanceMetrics(connection_id="conn1")
        
        assert metrics.connection_id == "conn1"
        assert metrics.throughput == 0.0
        assert metrics.latency == 0.0
        assert metrics.error_rate == 0.0
        assert isinstance(metrics.last_updated, float)
    
    def test_get_performance_level(self):
        """Test performance level determination."""
        metrics = PerformanceMetrics("conn1")
        
        # Optimal performance
        assert metrics.get_performance_level() == PerformanceLevel.OPTIMAL
        
        # Good performance
        metrics.update_metrics(latency=200, cpu_usage=60)
        assert metrics.get_performance_level() == PerformanceLevel.GOOD
        
        # Warning performance
        metrics.update_metrics(error_rate=7, latency=600)
        assert metrics.get_performance_level() == PerformanceLevel.WARNING
        
        # Critical performance
        metrics.update_metrics(error_rate=15, latency=1500, cpu_usage=95)
        assert metrics.get_performance_level() == PerformanceLevel.CRITICAL
    
    def test_update_metrics(self):
        """Test metrics update."""
        metrics = PerformanceMetrics("conn1")
        old_timestamp = metrics.last_updated
        
        time.sleep(0.01)  # Small delay
        metrics.update_metrics(throughput=50.0, latency=100.0)
        
        assert metrics.throughput == 50.0
        assert metrics.latency == 100.0
        assert metrics.last_updated > old_timestamp


class TestDataFlowTracer:
    """Test DataFlowTracer class."""
    
    def test_tracer_creation(self):
        """Test creating DataFlowTracer."""
        tracer = DataFlowTracer()
        
        assert len(tracer.trace_history) == 0
        assert len(tracer.active_traces) == 0
        assert tracer.max_trace_length == 1000
    
    def test_start_trace(self):
        """Test starting a trace."""
        tracer = DataFlowTracer()
        tracer.start_trace("trace1", "conn1", "initial_data")
        
        assert "trace1" in tracer.active_traces
        assert "trace1" in tracer.trace_history
        assert len(tracer.trace_history["trace1"]) == 1
        
        entry = tracer.trace_history["trace1"][0]
        assert entry["event"] == "trace_start"
        assert entry["connection_id"] == "conn1"
        assert entry["data"] == "initial_data"
    
    def test_trace_data_transformation(self):
        """Test tracing data transformation."""
        tracer = DataFlowTracer()
        tracer.start_trace("trace1", "conn1", "input")
        
        tracer.trace_data_transformation("trace1", "conn1", "input", "output", "uppercase")
        
        assert len(tracer.trace_history["trace1"]) == 2
        entry = tracer.trace_history["trace1"][1]
        assert entry["event"] == "transformation"
        assert entry["transformation_type"] == "uppercase"
        assert entry["input_data"] == "input"
        assert entry["output_data"] == "output"
    
    def test_trace_data_flow(self):
        """Test tracing data flow."""
        tracer = DataFlowTracer()
        tracer.start_trace("trace1", "conn1", "data")
        
        tracer.trace_data_flow("trace1", "conn1", "flowing_data", "node1", "node2")
        
        assert len(tracer.trace_history["trace1"]) == 2
        entry = tracer.trace_history["trace1"][1]
        assert entry["event"] == "data_flow"
        assert entry["data"] == "flowing_data"
        assert entry["source_node"] == "node1"
        assert entry["target_node"] == "node2"
    
    def test_end_trace(self):
        """Test ending a trace."""
        tracer = DataFlowTracer()
        tracer.start_trace("trace1", "conn1", "data")
        tracer.end_trace("trace1")
        
        assert "trace1" not in tracer.active_traces
        assert len(tracer.trace_history["trace1"]) == 2
        
        end_entry = tracer.trace_history["trace1"][1]
        assert end_entry["event"] == "trace_end"
    
    def test_clear_trace_history(self):
        """Test clearing trace history."""
        tracer = DataFlowTracer()
        tracer.start_trace("trace1", "conn1", "data")
        tracer.start_trace("trace2", "conn2", "data")
        
        # Clear specific trace
        tracer.clear_trace_history("trace1")
        assert "trace1" not in tracer.trace_history
        assert "trace1" not in tracer.active_traces
        assert "trace2" in tracer.trace_history
        
        # Clear all traces
        tracer.clear_trace_history()
        assert len(tracer.trace_history) == 0
        assert len(tracer.active_traces) == 0


class TestDataFlowVisualizer:
    """Test DataFlowVisualizer class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.model = VisualModel()
        
        # Create test nodes
        self.node1 = VisualNode(
            id="node1",
            type=NodeType.FUNCTION,
            position=(0, 0),
            outputs=[OutputPort("output", int, "Output value")]
        )
        self.node2 = VisualNode(
            id="node2",
            type=NodeType.FUNCTION,
            position=(100, 100),
            inputs=[InputPort("input", int, True, description="Input value")]
        )
        
        self.model.add_node(self.node1)
        self.model.add_node(self.node2)
        
        # Create test connection
        self.connection = self.model.connect_nodes("node1", "output", "node2", "input")
        
        self.visualizer = DataFlowVisualizer(self.model)
    
    def test_visualizer_creation(self):
        """Test creating DataFlowVisualizer."""
        assert self.visualizer.model == self.model
        assert len(self.visualizer.connection_visualizations) == 1
        assert len(self.visualizer.data_flow_info) == 1
        assert len(self.visualizer.performance_metrics) == 1
        assert self.visualizer.animation_enabled is True
    
    def test_update_data_flow(self):
        """Test updating data flow."""
        connection_id = self.connection.id
        
        self.visualizer.update_data_flow(connection_id, 42, "calculation")
        
        flow_info = self.visualizer.data_flow_info[connection_id]
        assert flow_info.current_value == 42
        assert flow_info.transformation_type == "calculation"
        assert flow_info.transformation_applied is True
        
        # Check particle color update
        particles = self.visualizer.flow_particles[connection_id]
        for particle in particles:
            assert particle.data_value == 42
    
    def test_update_performance_metrics(self):
        """Test updating performance metrics."""
        connection_id = self.connection.id
        
        self.visualizer.update_performance_metrics(
            connection_id,
            throughput=75.0,
            latency=150.0,
            error_rate=2.0
        )
        
        metrics = self.visualizer.performance_metrics[connection_id]
        assert metrics.throughput == 75.0
        assert metrics.latency == 150.0
        assert metrics.error_rate == 2.0
        assert metrics.get_performance_level() == PerformanceLevel.GOOD
    
    def test_highlight_data_transformation(self):
        """Test highlighting data transformation."""
        connection_id = self.connection.id
        
        self.visualizer.highlight_data_transformation(
            connection_id, "input", "OUTPUT", "uppercase"
        )
        
        flow_info = self.visualizer.data_flow_info[connection_id]
        assert flow_info.transformation_applied is True
        assert flow_info.transformation_type == "uppercase"
        
        viz = self.visualizer.connection_visualizations[connection_id]
        assert viz.highlight_active is True
        assert viz.animation_type == FlowAnimationType.GLOW
    
    def test_inspect_connection_point(self):
        """Test inspecting connection point."""
        connection_id = self.connection.id
        
        # Update with some data first
        self.visualizer.update_data_flow(connection_id, 42)
        
        inspection = self.visualizer.inspect_connection_point(connection_id, 0.5)
        
        assert inspection["connection_id"] == connection_id
        assert inspection["position"] == 0.5
        assert inspection["current_value"] == 42
        assert inspection["source_node"] == "node1"
        assert inspection["target_node"] == "node2"
        assert "performance" in inspection
    
    def test_get_performance_bottlenecks(self):
        """Test getting performance bottlenecks."""
        connection_id = self.connection.id
        
        # Create a bottleneck
        self.visualizer.update_performance_metrics(
            connection_id,
            error_rate=15.0,
            latency=2000.0,
            cpu_usage=95.0
        )
        
        bottlenecks = self.visualizer.get_performance_bottlenecks()
        assert len(bottlenecks) == 1
        assert bottlenecks[0]["connection_id"] == connection_id
        assert bottlenecks[0]["metrics"]["error_rate"] == 15.0
    
    def test_animation_control(self):
        """Test animation control."""
        # Test enabling/disabling animation
        self.visualizer.set_animation_enabled(False)
        assert self.visualizer.animation_enabled is False
        
        self.visualizer.set_animation_enabled(True)
        assert self.visualizer.animation_enabled is True
        
        # Test animation speed
        self.visualizer.set_animation_speed(2.0)
        assert self.visualizer.animation_speed == 2.0
        
        # Check particles updated
        connection_id = self.connection.id
        particles = self.visualizer.flow_particles[connection_id]
        for particle in particles:
            assert particle.speed == 2.0
    
    def test_visualization_settings(self):
        """Test visualization settings."""
        # Test performance indicators
        self.visualizer.set_show_performance_indicators(False)
        assert self.visualizer.show_performance_indicators is False
        
        # Test data labels
        self.visualizer.set_show_data_labels(False)
        assert self.visualizer.show_data_labels is False
        
        viz = self.visualizer.connection_visualizations[self.connection.id]
        assert viz.show_data_labels is False
        
        # Test direction arrows
        self.visualizer.set_show_direction_arrows(False)
        assert self.visualizer.show_direction_arrows is False
        
        viz = self.visualizer.connection_visualizations[self.connection.id]
        assert viz.show_direction_arrow is False
    
    def test_clear_highlights(self):
        """Test clearing highlights."""
        connection_id = self.connection.id
        
        # Add some highlights
        self.visualizer.highlight_data_transformation(
            connection_id, "input", "output", "transform"
        )
        
        viz = self.visualizer.connection_visualizations[connection_id]
        assert viz.highlight_active is True
        
        # Clear highlights
        self.visualizer.clear_all_highlights()
        assert viz.highlight_active is False
        assert viz.animation_type == FlowAnimationType.PARTICLE
    
    def test_get_visualization_state(self):
        """Test getting visualization state."""
        state = self.visualizer.get_visualization_state()
        
        assert "animation_enabled" in state
        assert "animation_speed" in state
        assert "connection_count" in state
        assert "active_particles" in state
        assert "active_traces" in state
        assert "performance_bottlenecks" in state
        
        assert state["connection_count"] == 1
        assert state["animation_enabled"] is True
    
    def test_cleanup(self):
        """Test cleanup."""
        # Start animation first
        self.visualizer.start_animation()
        
        # Add some data
        connection_id = self.connection.id
        self.visualizer.update_data_flow(connection_id, 42)
        self.visualizer.tracer.start_trace("trace1", connection_id, "data")
        
        # Cleanup
        self.visualizer.cleanup()
        
        assert len(self.visualizer.connection_visualizations) == 0
        assert len(self.visualizer.data_flow_info) == 0
        assert len(self.visualizer.flow_particles) == 0
        assert len(self.visualizer.performance_metrics) == 0
        assert len(self.visualizer.tracer.trace_history) == 0


class TestDataFlowVisualizerIntegration:
    """Integration tests for data flow visualizer."""
    
    def test_callback_integration(self):
        """Test callback integration."""
        model = VisualModel()
        
        # Create nodes and connection
        node1 = VisualNode(id="node1", outputs=[OutputPort("out", int)])
        node2 = VisualNode(id="node2", inputs=[InputPort("in", int)])
        model.add_node(node1)
        model.add_node(node2)
        connection = model.connect_nodes("node1", "out", "node2", "in")
        
        visualizer = DataFlowVisualizer(model)
        
        # Set up callbacks
        data_flow_updates = []
        performance_alerts = []
        
        def on_data_flow_update(conn_id, flow_info):
            data_flow_updates.append((conn_id, flow_info))
        
        def on_performance_alert(conn_id, level):
            performance_alerts.append((conn_id, level))
        
        visualizer.on_data_flow_update = on_data_flow_update
        visualizer.on_performance_alert = on_performance_alert
        
        # Trigger updates
        visualizer.update_data_flow(connection.id, 42)
        assert len(data_flow_updates) == 1
        
        # Trigger performance alert
        visualizer.update_performance_metrics(
            connection.id,
            error_rate=15.0,
            latency=2000.0
        )
        assert len(performance_alerts) == 1
        assert performance_alerts[0][1] == PerformanceLevel.CRITICAL
    
    def test_complex_data_flow_scenario(self):
        """Test complex data flow scenario."""
        model = VisualModel()
        
        # Create a chain of nodes
        nodes = []
        for i in range(3):
            node = VisualNode(
                id=f"node{i}",
                inputs=[InputPort("in", int)] if i > 0 else [],
                outputs=[OutputPort("out", int)] if i < 2 else []
            )
            nodes.append(node)
            model.add_node(node)
        
        # Connect them
        connections = []
        for i in range(2):
            conn = model.connect_nodes(f"node{i}", "out", f"node{i+1}", "in")
            connections.append(conn)
        
        visualizer = DataFlowVisualizer(model)
        
        # Simulate data flowing through the chain
        data_values = [10, 20, 30]
        for i, (conn, value) in enumerate(zip(connections, data_values)):
            visualizer.update_data_flow(conn.id, value, f"transform_{i}")
            
            # Add performance metrics
            visualizer.update_performance_metrics(
                conn.id,
                throughput=100.0 - i * 20,
                latency=50.0 + i * 25
            )
        
        # Check all connections have data
        assert len(visualizer.data_flow_info) == 2
        for conn in connections:
            assert conn.id in visualizer.data_flow_info
            assert visualizer.data_flow_info[conn.id].transformation_applied
        
        # Check performance metrics
        bottlenecks = visualizer.get_performance_bottlenecks()
        # Should have no critical bottlenecks with these metrics
        assert len(bottlenecks) == 0
        
        # Check visualization state
        state = visualizer.get_visualization_state()
        assert state["connection_count"] == 2
        assert state["active_particles"] > 0


if __name__ == "__main__":
    pytest.main([__file__])