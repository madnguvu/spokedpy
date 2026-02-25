"""
Unit tests for Visual Parser.
"""

import ast
import pytest
from hypothesis import given, strategies as st
from visual_editor_core.visual_parser import (
    VisualParser, AssignmentBuilder, FunctionCallBuilder, ControlFlowBuilder, ClassDefBuilder
)
from visual_editor_core.models import VisualModel, VisualNode, NodeType


class TestAssignmentBuilder:
    """Test cases for AssignmentBuilder."""
    
    def test_simple_assignment(self):
        """Test building node from simple assignment."""
        builder = AssignmentBuilder()
        ast_node = ast.Assign(
            targets=[ast.Name(id='x', ctx=ast.Store())],
            value=ast.Constant(value=42)
        )
        context = {'position': (100.0, 50.0)}
        
        node = builder.build_node(ast_node, context)
        
        assert node.type == NodeType.VARIABLE
        assert node.parameters['variable_name'] == 'x'
        assert node.parameters['default_value'] == 42
        assert node.position == (100.0, 50.0)
    
    def test_string_assignment(self):
        """Test building node from string assignment."""
        builder = AssignmentBuilder()
        ast_node = ast.Assign(
            targets=[ast.Name(id='message', ctx=ast.Store())],
            value=ast.Constant(value='hello')
        )
        context = {}
        
        node = builder.build_node(ast_node, context)
        
        assert node.parameters['variable_name'] == 'message'
        assert node.parameters['default_value'] == 'hello'
    
    def test_complex_assignment(self):
        """Test handling complex assignments."""
        builder = AssignmentBuilder()
        # Multiple targets: a, b = 1, 2
        ast_node = ast.Assign(
            targets=[
                ast.Tuple(elts=[
                    ast.Name(id='a', ctx=ast.Store()),
                    ast.Name(id='b', ctx=ast.Store())
                ], ctx=ast.Store())
            ],
            value=ast.Tuple(elts=[
                ast.Constant(value=1),
                ast.Constant(value=2)
            ], ctx=ast.Load())
        )
        context = {}
        
        node = builder.build_node(ast_node, context)
        
        # Should create a custom node for complex assignments
        assert node.type == NodeType.CUSTOM
        assert 'code_snippet' in node.parameters


class TestFunctionCallBuilder:
    """Test cases for FunctionCallBuilder."""
    
    def test_simple_function_call(self):
        """Test building node from simple function call."""
        builder = FunctionCallBuilder()
        ast_node = ast.Call(
            func=ast.Name(id='print', ctx=ast.Load()),
            args=[ast.Constant(value='hello')],
            keywords=[]
        )
        context = {}
        
        node = builder.build_node(ast_node, context)
        
        assert node.type == NodeType.FUNCTION
        assert node.parameters['function_name'] == 'print'
        assert len(node.inputs) == 1  # One positional argument
        assert node.inputs[0].name == 'arg_0'
    
    def test_method_call(self):
        """Test building node from method call."""
        builder = FunctionCallBuilder()
        ast_node = ast.Call(
            func=ast.Attribute(
                value=ast.Name(id='obj', ctx=ast.Load()),
                attr='method',
                ctx=ast.Load()
            ),
            args=[],
            keywords=[]
        )
        context = {}
        
        node = builder.build_node(ast_node, context)
        
        assert 'obj.method' in node.parameters['function_name']
    
    def test_function_with_keywords(self):
        """Test function call with keyword arguments."""
        builder = FunctionCallBuilder()
        ast_node = ast.Call(
            func=ast.Name(id='func', ctx=ast.Load()),
            args=[],
            keywords=[ast.keyword(arg='param', value=ast.Constant(value=123))]
        )
        context = {}
        
        node = builder.build_node(ast_node, context)
        
        assert len(node.inputs) == 1
        assert node.inputs[0].name == 'param'


class TestControlFlowBuilder:
    """Test cases for ControlFlowBuilder."""
    
    def test_if_statement(self):
        """Test building node from if statement."""
        builder = ControlFlowBuilder()
        ast_node = ast.If(
            test=ast.Constant(value=True),
            body=[ast.Pass()],
            orelse=[]
        )
        context = {}
        
        node = builder.build_node(ast_node, context)
        
        assert node.type == NodeType.CONTROL_FLOW
        assert node.parameters['control_type'] == 'if'
        assert len(node.inputs) == 1
        assert node.inputs[0].name == 'condition'
    
    def test_for_loop(self):
        """Test building node from for loop."""
        builder = ControlFlowBuilder()
        ast_node = ast.For(
            target=ast.Name(id='i', ctx=ast.Store()),
            iter=ast.Call(func=ast.Name(id='range', ctx=ast.Load()), args=[ast.Constant(value=10)], keywords=[]),
            body=[ast.Pass()],
            orelse=[]
        )
        context = {}
        
        node = builder.build_node(ast_node, context)
        
        assert node.parameters['control_type'] == 'for'
        assert len(node.inputs) == 1
        assert node.inputs[0].name == 'iterable'
    
    def test_while_loop(self):
        """Test building node from while loop."""
        builder = ControlFlowBuilder()
        ast_node = ast.While(
            test=ast.Constant(value=True),
            body=[ast.Pass()],
            orelse=[]
        )
        context = {}
        
        node = builder.build_node(ast_node, context)
        
        assert node.parameters['control_type'] == 'while'
        assert len(node.inputs) == 1
        assert node.inputs[0].name == 'condition'


class TestClassDefBuilder:
    """Test cases for ClassDefBuilder."""
    
    def test_simple_class(self):
        """Test building node from simple class definition."""
        builder = ClassDefBuilder()
        ast_node = ast.ClassDef(
            name='MyClass',
            bases=[],
            keywords=[],
            decorator_list=[],
            body=[ast.Pass()]
        )
        context = {}
        
        node = builder.build_node(ast_node, context)
        
        assert node.type == NodeType.CLASS
        assert node.parameters['class_name'] == 'MyClass'
        assert node.parameters['base_classes'] == []
    
    def test_class_with_inheritance(self):
        """Test building node from class with inheritance."""
        builder = ClassDefBuilder()
        ast_node = ast.ClassDef(
            name='Child',
            bases=[ast.Name(id='Parent', ctx=ast.Load())],
            keywords=[],
            decorator_list=[],
            body=[ast.Pass()]
        )
        context = {}
        
        node = builder.build_node(ast_node, context)
        
        assert node.parameters['class_name'] == 'Child'
        assert node.parameters['base_classes'] == ['Parent']
        assert len(node.inputs) == 1
        assert node.inputs[0].name == 'base_Parent'


class TestVisualParser:
    """Test cases for VisualParser."""
    
    def test_parser_initialization(self):
        """Test parser initialization with default builders."""
        parser = VisualParser()
        
        assert ast.Assign in parser.visual_builders
        assert ast.Call in parser.visual_builders
        assert ast.If in parser.visual_builders
        assert ast.ClassDef in parser.visual_builders
    
    def test_empty_code_parsing(self):
        """Test parsing empty code."""
        parser = VisualParser()
        
        model = parser.parse_code("")
        
        assert len(model.nodes) == 0
    
    def test_simple_variable_assignment(self):
        """Test parsing simple variable assignment."""
        parser = VisualParser()
        code = "x = 42"
        
        model = parser.parse_code(code)
        
        assert len(model.nodes) == 1
        node = list(model.nodes.values())[0]
        assert node.type == NodeType.VARIABLE
        assert node.parameters['variable_name'] == 'x'
        assert node.parameters['default_value'] == 42
    
    def test_function_call_parsing(self):
        """Test parsing function call."""
        parser = VisualParser()
        code = "print('hello')"
        
        model = parser.parse_code(code)
        
        assert len(model.nodes) == 1
        node = list(model.nodes.values())[0]
        assert node.type == NodeType.FUNCTION
        assert node.parameters['function_name'] == 'print'
    
    def test_multiple_statements(self):
        """Test parsing multiple statements."""
        parser = VisualParser()
        code = """
x = 10
y = 20
print(x + y)
"""
        
        model = parser.parse_code(code)
        
        assert len(model.nodes) == 3
        
        # Check node types
        node_types = [node.type for node in model.nodes.values()]
        assert node_types.count(NodeType.VARIABLE) == 2
        assert node_types.count(NodeType.FUNCTION) == 1
    
    def test_function_definition_parsing(self):
        """Test parsing function definition."""
        parser = VisualParser()
        code = """
def greet(name):
    return f"Hello, {name}!"
"""
        
        model = parser.parse_code(code)
        
        assert len(model.nodes) == 1
        node = list(model.nodes.values())[0]
        assert node.type == NodeType.FUNCTION
        assert node.parameters['function_name'] == 'greet'
        assert node.parameters['is_definition'] is True
    
    def test_class_definition_parsing(self):
        """Test parsing class definition."""
        parser = VisualParser()
        code = """
class Person:
    def __init__(self, name):
        self.name = name
"""
        
        model = parser.parse_code(code)
        
        # Should have at least one node for the class
        assert len(model.nodes) >= 1
        
        # Find the class node
        class_nodes = [node for node in model.nodes.values() if node.type == NodeType.CLASS]
        assert len(class_nodes) == 1
        assert class_nodes[0].parameters['class_name'] == 'Person'
    
    def test_control_flow_parsing(self):
        """Test parsing control flow statements."""
        parser = VisualParser()
        code = """
if x > 0:
    print("positive")
for i in range(10):
    print(i)
"""
        
        model = parser.parse_code(code)
        
        # Should have nodes for if and for statements
        control_nodes = [node for node in model.nodes.values() if node.type == NodeType.CONTROL_FLOW]
        assert len(control_nodes) >= 2
    
    def test_syntax_error_handling(self):
        """Test handling of syntax errors."""
        parser = VisualParser()
        code = "x = 42 +"  # Incomplete expression
        
        model = parser.parse_code(code)
        
        # Should return empty model with error information
        assert len(model.nodes) == 0
        assert 'parse_error' in model.metadata
    
    def test_comment_preservation(self):
        """Test preservation of comments."""
        parser = VisualParser()
        code = """
# This is a comment
x = 42  # Another comment
# Final comment
"""
        
        model = parser.parse_code(code)
        parser.preserve_comments(code, model)
        
        assert 'comments' in model.metadata
        comments = model.metadata['comments']
        assert len(comments) == 3
        assert all('text' in comment for comment in comments)
    
    def test_complex_construct_handling(self):
        """Test handling of complex constructs."""
        parser = VisualParser()
        code = """
async def async_func():
    async with context_manager():
        try:
            await some_operation()
        except Exception as e:
            print(f"Error: {e}")
"""
        
        model = parser.parse_code(code)
        
        # Should create nodes for complex constructs
        assert len(model.nodes) > 0
        
        # Should have async function node
        async_nodes = [node for node in model.nodes.values() 
                      if node.type == NodeType.ASYNC]
        assert len(async_nodes) >= 1
    
    def test_supported_constructs(self):
        """Test getting list of supported constructs."""
        parser = VisualParser()
        
        constructs = parser.get_supported_constructs()
        
        assert isinstance(constructs, list)
        assert len(constructs) > 0
        assert 'Variable assignments' in constructs
        assert 'Function calls' in constructs


# Property-based tests
@given(st.text(min_size=1, max_size=20, alphabet=st.characters(min_codepoint=97, max_codepoint=122)))
def test_variable_assignment_property(var_name):
    """Property test: Parser should handle any valid variable assignment."""
    # Ensure it's a valid Python identifier and not a keyword
    import keyword
    if not var_name.isidentifier() or keyword.iskeyword(var_name):
        return
    
    parser = VisualParser()
    code = f"{var_name} = 42"
    
    model = parser.parse_code(code)
    
    # Should successfully parse
    assert len(model.nodes) == 1
    node = list(model.nodes.values())[0]
    assert node.type == NodeType.VARIABLE
    assert node.parameters['variable_name'] == var_name


@given(st.integers(min_value=-1000, max_value=1000))
def test_integer_assignment_property(value):
    """Property test: Parser should handle any integer assignment."""
    parser = VisualParser()
    code = f"x = {value}"
    
    model = parser.parse_code(code)
    
    assert len(model.nodes) == 1
    node = list(model.nodes.values())[0]
    assert node.parameters['default_value'] == value


@given(st.text(min_size=1, max_size=20, alphabet=st.characters(min_codepoint=97, max_codepoint=122)))
def test_function_call_property(func_name):
    """Property test: Parser should handle any valid function call."""
    # Ensure it's a valid Python identifier and not a keyword
    import keyword
    if not func_name.isidentifier() or keyword.iskeyword(func_name):
        return
    
    parser = VisualParser()
    code = f"{func_name}()"
    
    model = parser.parse_code(code)
    
    assert len(model.nodes) == 1
    node = list(model.nodes.values())[0]
    assert node.type == NodeType.FUNCTION
    assert node.parameters['function_name'] == func_name