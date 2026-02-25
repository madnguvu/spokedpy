"""
Unit tests for AST Processor.
"""

import ast
import pytest
from hypothesis import given, strategies as st
from visual_editor_core.ast_processor import (
    ASTProcessor, FunctionNodeMapper, VariableNodeMapper, ControlFlowNodeMapper
)
from visual_editor_core.models import (
    VisualNode, VisualModel, NodeType, InputPort, OutputPort
)


class TestFunctionNodeMapper:
    """Test cases for FunctionNodeMapper."""
    
    def test_function_node_to_ast(self):
        """Test converting a function node to AST."""
        mapper = FunctionNodeMapper()
        node = VisualNode(
            type=NodeType.FUNCTION,
            parameters={'function_name': 'print'}
        )
        context = {}
        
        ast_node = mapper.to_ast(node, context)
        
        assert isinstance(ast_node, ast.Call)
        assert isinstance(ast_node.func, ast.Name)
        assert ast_node.func.id == 'print'
    
    def test_function_node_with_arguments(self):
        """Test function node with input arguments."""
        mapper = FunctionNodeMapper()
        node = VisualNode(
            type=NodeType.FUNCTION,
            parameters={'function_name': 'len'},
            inputs=[InputPort(name='obj', data_type=list, required=True)]
        )
        
        # Simulate a connection providing the argument
        context = {f"{node.id}.obj": ast.Name(id='my_list', ctx=ast.Load())}
        
        ast_node = mapper.to_ast(node, context)
        
        assert isinstance(ast_node, ast.Call)
        assert len(ast_node.keywords) == 1
        assert ast_node.keywords[0].arg == 'obj'


class TestVariableNodeMapper:
    """Test cases for VariableNodeMapper."""
    
    def test_variable_node_to_ast(self):
        """Test converting a variable node to AST."""
        mapper = VariableNodeMapper()
        node = VisualNode(
            type=NodeType.VARIABLE,
            parameters={'variable_name': 'x', 'default_value': 42}
        )
        context = {}
        
        ast_node = mapper.to_ast(node, context)
        
        assert isinstance(ast_node, ast.Assign)
        assert len(ast_node.targets) == 1
        assert isinstance(ast_node.targets[0], ast.Name)
        assert ast_node.targets[0].id == 'x'
        assert isinstance(ast_node.value, ast.Constant)
        assert ast_node.value.value == 42


class TestControlFlowNodeMapper:
    """Test cases for ControlFlowNodeMapper."""
    
    def test_if_statement_creation(self):
        """Test creating an if statement."""
        mapper = ControlFlowNodeMapper()
        node = VisualNode(
            type=NodeType.CONTROL_FLOW,
            parameters={'control_type': 'if'}
        )
        context = {}
        
        ast_node = mapper.to_ast(node, context)
        
        assert isinstance(ast_node, ast.If)
        assert isinstance(ast_node.test, ast.Constant)
        assert ast_node.test.value is True
    
    def test_for_loop_creation(self):
        """Test creating a for loop."""
        mapper = ControlFlowNodeMapper()
        node = VisualNode(
            type=NodeType.CONTROL_FLOW,
            parameters={'control_type': 'for'}
        )
        context = {}
        
        ast_node = mapper.to_ast(node, context)
        
        assert isinstance(ast_node, ast.For)
        assert isinstance(ast_node.target, ast.Name)
        assert ast_node.target.id == 'i'
    
    def test_while_loop_creation(self):
        """Test creating a while loop."""
        mapper = ControlFlowNodeMapper()
        node = VisualNode(
            type=NodeType.CONTROL_FLOW,
            parameters={'control_type': 'while'}
        )
        context = {}
        
        ast_node = mapper.to_ast(node, context)
        
        assert isinstance(ast_node, ast.While)
        assert isinstance(ast_node.test, ast.Constant)


class TestASTProcessor:
    """Test cases for ASTProcessor."""
    
    def test_processor_initialization(self):
        """Test processor initialization with default mappers."""
        processor = ASTProcessor()
        
        assert NodeType.FUNCTION in processor.node_mappers
        assert NodeType.VARIABLE in processor.node_mappers
        assert NodeType.CONTROL_FLOW in processor.node_mappers
    
    def test_empty_model_conversion(self):
        """Test converting an empty visual model."""
        processor = ASTProcessor()
        model = VisualModel()
        
        ast_tree = processor.visual_to_ast(model)
        
        assert isinstance(ast_tree, ast.Module)
        assert len(ast_tree.body) == 0
    
    def test_single_variable_node_conversion(self):
        """Test converting a model with a single variable node."""
        processor = ASTProcessor()
        model = VisualModel()
        
        node = VisualNode(
            type=NodeType.VARIABLE,
            parameters={'variable_name': 'test_var', 'default_value': 123}
        )
        model.add_node(node)
        
        ast_tree = processor.visual_to_ast(model)
        
        assert len(ast_tree.body) == 1
        assert isinstance(ast_tree.body[0], ast.Assign)
    
    def test_single_function_node_conversion(self):
        """Test converting a model with a single function node."""
        processor = ASTProcessor()
        model = VisualModel()
        
        node = VisualNode(
            type=NodeType.FUNCTION,
            parameters={'function_name': 'print'}
        )
        model.add_node(node)
        
        ast_tree = processor.visual_to_ast(model)
        
        assert len(ast_tree.body) == 1
        assert isinstance(ast_tree.body[0], ast.Expr)
        assert isinstance(ast_tree.body[0].value, ast.Call)
    
    def test_multiple_nodes_conversion(self):
        """Test converting a model with multiple nodes."""
        processor = ASTProcessor()
        model = VisualModel()
        
        # Add variable node
        var_node = VisualNode(
            type=NodeType.VARIABLE,
            parameters={'variable_name': 'x', 'default_value': 10}
        )
        model.add_node(var_node)
        
        # Add function node
        func_node = VisualNode(
            type=NodeType.FUNCTION,
            parameters={'function_name': 'print'}
        )
        model.add_node(func_node)
        
        ast_tree = processor.visual_to_ast(model)
        
        assert len(ast_tree.body) == 2
    
    def test_ast_to_visual_conversion(self):
        """Test converting AST back to visual model."""
        processor = ASTProcessor()
        
        # Create a simple AST
        ast_tree = ast.Module(body=[
            ast.Assign(
                targets=[ast.Name(id='x', ctx=ast.Store())],
                value=ast.Constant(value=42)
            ),
            ast.Expr(value=ast.Call(
                func=ast.Name(id='print', ctx=ast.Load()),
                args=[ast.Name(id='x', ctx=ast.Load())],
                keywords=[]
            ))
        ], type_ignores=[])
        
        model = processor.ast_to_visual(ast_tree)
        
        assert len(model.nodes) == 2
        
        # Check that we have the expected node types
        node_types = [node.type for node in model.nodes.values()]
        assert NodeType.VARIABLE in node_types
        assert NodeType.FUNCTION in node_types
    
    def test_round_trip_validation_success(self):
        """Test successful round-trip validation."""
        processor = ASTProcessor()
        model = VisualModel()
        
        node = VisualNode(
            type=NodeType.VARIABLE,
            parameters={'variable_name': 'test', 'default_value': 1}
        )
        model.add_node(node)
        
        is_valid = processor.validate_round_trip(model)
        assert is_valid is True
    
    def test_get_generated_code(self):
        """Test code generation from visual model."""
        processor = ASTProcessor()
        model = VisualModel()
        
        node = VisualNode(
            type=NodeType.VARIABLE,
            parameters={'variable_name': 'hello', 'default_value': 'world'}
        )
        model.add_node(node)
        
        code = processor.get_generated_code(model)
        
        assert isinstance(code, str)
        assert len(code) > 0
        # Should contain the variable assignment
        assert 'hello' in code
    
    def test_unsupported_node_type_handling(self):
        """Test handling of unsupported node types."""
        processor = ASTProcessor()
        model = VisualModel()
        
        # Create a node with unsupported type
        node = VisualNode(type=NodeType.CUSTOM)
        model.add_node(node)
        
        ast_tree = processor.visual_to_ast(model)
        
        # Should still generate something (placeholder comment)
        assert len(ast_tree.body) == 1
        assert isinstance(ast_tree.body[0], ast.Expr)
    
    def test_connection_context_building(self):
        """Test building connection context for node relationships."""
        processor = ASTProcessor()
        model = VisualModel()
        
        # Create two nodes with a connection
        var_node = VisualNode(
            type=NodeType.VARIABLE,
            parameters={'variable_name': 'x'},
            outputs=[OutputPort(name='value', data_type=int)]
        )
        func_node = VisualNode(
            type=NodeType.FUNCTION,
            parameters={'function_name': 'print'},
            inputs=[InputPort(name='value', data_type=int)]
        )
        
        var_id = model.add_node(var_node)
        func_id = model.add_node(func_node)
        
        # Connect them
        connection = model.connect_nodes(var_id, 'value', func_id, 'value')
        assert connection is not None
        
        # Build context
        context = processor._build_connection_context(model)
        
        # Should have mapping for the connection
        target_key = f"{func_id}.value"
        assert target_key in context


# Property-based tests
@given(st.text(min_size=1, max_size=20, alphabet=st.characters(min_codepoint=97, max_codepoint=122)))
def test_variable_name_property(var_name):
    """Property test: Variable nodes should handle any valid Python identifier."""
    # Ensure it's a valid Python identifier
    if not var_name.isidentifier():
        return
    
    processor = ASTProcessor()
    model = VisualModel()
    
    node = VisualNode(
        type=NodeType.VARIABLE,
        parameters={'variable_name': var_name, 'default_value': 0}
    )
    model.add_node(node)
    
    ast_tree = processor.visual_to_ast(model)
    
    # Should generate valid AST
    assert len(ast_tree.body) == 1
    assert isinstance(ast_tree.body[0], ast.Assign)
    assert ast_tree.body[0].targets[0].id == var_name


@given(st.text(min_size=1, max_size=20, alphabet=st.characters(min_codepoint=97, max_codepoint=122)))
def test_function_name_property(func_name):
    """Property test: Function nodes should handle any valid function name."""
    # Ensure it's a valid Python identifier
    if not func_name.isidentifier():
        return
    
    processor = ASTProcessor()
    model = VisualModel()
    
    node = VisualNode(
        type=NodeType.FUNCTION,
        parameters={'function_name': func_name}
    )
    model.add_node(node)
    
    ast_tree = processor.visual_to_ast(model)
    
    # Should generate valid AST
    assert len(ast_tree.body) == 1
    assert isinstance(ast_tree.body[0], ast.Expr)
    assert isinstance(ast_tree.body[0].value, ast.Call)
    assert ast_tree.body[0].value.func.id == func_name


@given(st.integers(min_value=1, max_value=10))
def test_multiple_nodes_property(num_nodes):
    """Property test: Processor should handle any number of nodes."""
    processor = ASTProcessor()
    model = VisualModel()
    
    # Add multiple variable nodes
    for i in range(num_nodes):
        node = VisualNode(
            type=NodeType.VARIABLE,
            parameters={'variable_name': f'var_{i}', 'default_value': i}
        )
        model.add_node(node)
    
    ast_tree = processor.visual_to_ast(model)
    
    # Should generate the same number of statements
    assert len(ast_tree.body) == num_nodes