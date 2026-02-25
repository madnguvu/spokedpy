"""
Unit tests for core data models.
"""

import pytest
from hypothesis import given, strategies as st
from visual_editor_core.models import (
    VisualNode, Connection, VisualModel, InputPort, OutputPort,
    NodeType, ValidationError
)


class TestInputPort:
    """Test cases for InputPort class."""
    
    def test_input_port_creation(self):
        """Test basic input port creation."""
        port = InputPort(name="input1", data_type=int, required=True)
        assert port.name == "input1"
        assert port.data_type == int
        assert port.required is True
        
    def test_validate_value_success(self):
        """Test successful value validation."""
        port = InputPort(name="input1", data_type=int)
        assert port.validate_value(42) is True
        
    def test_validate_value_failure(self):
        """Test failed value validation."""
        port = InputPort(name="input1", data_type=int)
        assert port.validate_value("not an int") is False
        
    def test_validate_optional_none(self):
        """Test validation of None for optional ports."""
        port = InputPort(name="input1", data_type=int, required=False)
        assert port.validate_value(None) is True


class TestOutputPort:
    """Test cases for OutputPort class."""
    
    def test_output_port_creation(self):
        """Test basic output port creation."""
        port = OutputPort(name="output1", data_type=str)
        assert port.name == "output1"
        assert port.data_type == str
        
    def test_compatibility_check_success(self):
        """Test successful compatibility check."""
        output_port = OutputPort(name="out", data_type=int)
        input_port = InputPort(name="in", data_type=int)
        assert output_port.is_compatible_with(input_port) is True
        
    def test_compatibility_check_inheritance(self):
        """Test compatibility with inheritance."""
        output_port = OutputPort(name="out", data_type=bool)  # bool is subclass of int
        input_port = InputPort(name="in", data_type=int)
        assert output_port.is_compatible_with(input_port) is True


class TestVisualNode:
    """Test cases for VisualNode class."""
    
    def test_node_creation_with_defaults(self):
        """Test node creation with default values."""
        node = VisualNode()
        assert node.id is not None
        assert node.type == NodeType.FUNCTION
        assert node.position == (0.0, 0.0)
        assert len(node.inputs) == 0
        assert len(node.outputs) == 0
        
    def test_node_validation_success(self):
        """Test successful node validation."""
        node = VisualNode(
            type=NodeType.FUNCTION,
            parameters={'function_name': 'test_func'}
        )
        errors = node.validate()
        assert len(errors) == 0
        
    def test_node_validation_missing_function_name(self):
        """Test validation failure for missing function name."""
        node = VisualNode(type=NodeType.FUNCTION)
        errors = node.validate()
        assert len(errors) == 1
        assert "function_name" in str(errors[0])
        
    def test_node_validation_duplicate_ports(self):
        """Test validation failure for duplicate port names."""
        node = VisualNode(
            type=NodeType.VARIABLE,  # Use a type that doesn't require function_name
            inputs=[
                InputPort(name="duplicate", data_type=int),
                InputPort(name="duplicate", data_type=str)
            ]
        )
        errors = node.validate()
        assert len(errors) == 1
        assert "Duplicate input port names" in str(errors[0])
        
    def test_get_port_methods(self):
        """Test port retrieval methods."""
        input_port = InputPort(name="test_input", data_type=int)
        output_port = OutputPort(name="test_output", data_type=str)
        
        node = VisualNode(inputs=[input_port], outputs=[output_port])
        
        assert node.get_input_port("test_input") == input_port
        assert node.get_input_port("nonexistent") is None
        assert node.get_output_port("test_output") == output_port
        assert node.get_output_port("nonexistent") is None


class TestConnection:
    """Test cases for Connection class."""
    
    def test_connection_creation(self):
        """Test basic connection creation."""
        conn = Connection(
            source_node_id="node1",
            source_port="out",
            target_node_id="node2", 
            target_port="in"
        )
        assert conn.source_node_id == "node1"
        assert conn.target_node_id == "node2"
        
    def test_validate_compatibility_success(self):
        """Test successful connection validation."""
        source_node = VisualNode(
            outputs=[OutputPort(name="out", data_type=int)]
        )
        target_node = VisualNode(
            inputs=[InputPort(name="in", data_type=int)]
        )
        
        conn = Connection(source_port="out", target_port="in")
        assert conn.validate_compatibility(source_node, target_node) is True
        
    def test_validate_compatibility_failure(self):
        """Test failed connection validation."""
        source_node = VisualNode(
            outputs=[OutputPort(name="out", data_type=str)]
        )
        target_node = VisualNode(
            inputs=[InputPort(name="in", data_type=int)]
        )
        
        conn = Connection(source_port="out", target_port="in")
        assert conn.validate_compatibility(source_node, target_node) is False
        
    def test_get_data_flow_info(self):
        """Test data flow information retrieval."""
        conn = Connection(
            source_node_id="node1",
            source_port="out",
            target_node_id="node2",
            target_port="in",
            data_type=int
        )
        
        info = conn.get_data_flow_info()
        assert info['data_type'] == 'int'
        assert info['source'] == 'node1.out'
        assert info['target'] == 'node2.in'


class TestVisualModel:
    """Test cases for VisualModel class."""
    
    def test_model_creation(self):
        """Test basic model creation."""
        model = VisualModel()
        assert len(model.nodes) == 0
        assert len(model.connections) == 0
        
    def test_add_remove_node(self):
        """Test adding and removing nodes."""
        model = VisualModel()
        node = VisualNode()
        
        node_id = model.add_node(node)
        assert node_id == node.id
        assert node_id in model.nodes
        
        success = model.remove_node(node_id)
        assert success is True
        assert node_id not in model.nodes
        
    def test_connect_nodes_success(self):
        """Test successful node connection."""
        model = VisualModel()
        
        source_node = VisualNode(
            outputs=[OutputPort(name="out", data_type=int)]
        )
        target_node = VisualNode(
            inputs=[InputPort(name="in", data_type=int)]
        )
        
        source_id = model.add_node(source_node)
        target_id = model.add_node(target_node)
        
        connection = model.connect_nodes(source_id, "out", target_id, "in")
        assert connection is not None
        assert len(model.connections) == 1
        
    def test_connect_nodes_failure(self):
        """Test failed node connection."""
        model = VisualModel()
        
        source_node = VisualNode(
            outputs=[OutputPort(name="out", data_type=str)]
        )
        target_node = VisualNode(
            inputs=[InputPort(name="in", data_type=int)]
        )
        
        source_id = model.add_node(source_node)
        target_id = model.add_node(target_node)
        
        connection = model.connect_nodes(source_id, "out", target_id, "in")
        assert connection is None
        assert len(model.connections) == 0
        
    def test_model_validation(self):
        """Test model validation."""
        model = VisualModel()
        
        # Add valid nodes
        node1 = VisualNode(type=NodeType.FUNCTION, parameters={'function_name': 'func1'})
        node2 = VisualNode(type=NodeType.FUNCTION, parameters={'function_name': 'func2'})
        
        model.add_node(node1)
        model.add_node(node2)
        
        errors = model.validate_model()
        assert len(errors) == 0
        
    def test_cycle_detection(self):
        """Test cycle detection in model."""
        model = VisualModel()
        
        # Create nodes that will form a cycle
        node1 = VisualNode(
            inputs=[InputPort(name="in", data_type=int)],
            outputs=[OutputPort(name="out", data_type=int)]
        )
        node2 = VisualNode(
            inputs=[InputPort(name="in", data_type=int)],
            outputs=[OutputPort(name="out", data_type=int)]
        )
        
        id1 = model.add_node(node1)
        id2 = model.add_node(node2)
        
        # Create cycle: node1 -> node2 -> node1
        model.connect_nodes(id1, "out", id2, "in")
        model.connect_nodes(id2, "out", id1, "in")
        
        errors = model.validate_model()
        cycle_errors = [e for e in errors if "circular" in str(e)]
        assert len(cycle_errors) == 1
        
    def test_execution_order(self):
        """Test topological sort for execution order."""
        model = VisualModel()
        
        # Create a simple chain: node1 -> node2 -> node3
        nodes = []
        for i in range(3):
            node = VisualNode(
                inputs=[InputPort(name="in", data_type=int)] if i > 0 else [],
                outputs=[OutputPort(name="out", data_type=int)] if i < 2 else []
            )
            nodes.append(model.add_node(node))
            
        # Connect them in sequence
        model.connect_nodes(nodes[0], "out", nodes[1], "in")
        model.connect_nodes(nodes[1], "out", nodes[2], "in")
        
        order = model.get_execution_order()
        assert order == nodes  # Should be in the same order we created them


# Property-based tests
@given(st.text(min_size=1), st.sampled_from([int, str, float, bool]))
def test_input_port_property_validation(name, data_type):
    """Property test: InputPort should validate values of correct type."""
    port = InputPort(name=name, data_type=data_type)
    
    # Generate a value of the correct type
    if data_type == int:
        test_value = 42
    elif data_type == str:
        test_value = "test"
    elif data_type == float:
        test_value = 3.14
    elif data_type == bool:
        test_value = True
    else:
        test_value = None
        
    assert port.validate_value(test_value) is True


@given(st.floats(allow_nan=False, allow_infinity=False), 
       st.floats(allow_nan=False, allow_infinity=False))
def test_visual_node_position_property(x, y):
    """Property test: VisualNode should accept any valid position coordinates."""
    node = VisualNode(position=(x, y))
    assert node.position == (x, y)