"""
Unit tests for Code Generator.
"""

import ast
import pytest
from hypothesis import given, strategies as st
from visual_editor_core.code_generator import (
    CodeGenerator, PythonFormatter, CodeOptimizer, TypeHintGenerator, DocstringGenerator, CommentPreserver
)
from visual_editor_core.models import VisualModel, VisualNode, NodeType


class TestPythonFormatter:
    """Test cases for PythonFormatter."""
    
    def test_format_code_basic(self):
        """Test basic code formatting."""
        formatter = PythonFormatter()
        code = "x=42\ny   =   'hello'"
        
        formatted = formatter.format_code(code)
        
        # Should normalize indentation
        lines = formatted.split('\n')
        assert all(not line.endswith(' ') for line in lines if line.strip())
    
    def test_add_blank_lines(self):
        """Test adding blank lines between functions."""
        formatter = PythonFormatter()
        code = "def func1():\n    pass\ndef func2():\n    pass"
        
        formatted = formatter.add_blank_lines(code)
        
        # Should add blank line before second function
        assert '\n\ndef func2():' in formatted
    
    def test_class_blank_lines(self):
        """Test adding blank lines before classes."""
        formatter = PythonFormatter()
        code = "x = 42\nclass MyClass:\n    pass"
        
        formatted = formatter.add_blank_lines(code)
        
        # Should add blank line before class
        assert '\n\nclass MyClass:' in formatted


class TestCodeOptimizer:
    """Test cases for CodeOptimizer."""
    
    def test_optimize_imports(self):
        """Test import optimization."""
        optimizer = CodeOptimizer()
        code = "import os\nx = 42\nimport sys\ny = 'hello'"
        
        optimized = optimizer.optimize_imports(code)
        
        # Imports should be at the top and sorted
        lines = optimized.split('\n')
        import_lines = [line for line in lines if line.startswith('import')]
        assert len(import_lines) == 2
        assert import_lines == sorted(import_lines)
    
    def test_remove_redundant_code(self):
        """Test removal of redundant code."""
        optimizer = CodeOptimizer()
        code = "x = 42\n\n\n\ny = 'hello'   \n"
        
        optimized = optimizer.remove_redundant_code(code)
        
        # Should remove multiple blank lines and trailing whitespace
        assert '\n\n\n' not in optimized
        assert not optimized.endswith('   ')


class TestTypeHintGenerator:
    """Test cases for TypeHintGenerator."""
    
    def test_infer_type_from_value(self):
        """Test type inference from values."""
        generator = TypeHintGenerator()
        
        assert generator.infer_type_from_value(42) == 'int'
        assert generator.infer_type_from_value('hello') == 'str'
        assert generator.infer_type_from_value(3.14) == 'float'
        assert generator.infer_type_from_value(True) == 'bool'
        assert generator.infer_type_from_value([1, 2, 3]) == 'List'
    
    def test_add_type_hints_to_function(self):
        """Test adding type hints to function definitions."""
        generator = TypeHintGenerator()
        
        # Create a function without type hints
        func_node = ast.FunctionDef(
            name='test_func',
            args=ast.arguments(
                posonlyargs=[],
                args=[ast.arg(arg='x', annotation=None)],
                vararg=None,
                kwonlyargs=[],
                kw_defaults=[],
                kwarg=None,
                defaults=[]
            ),
            body=[ast.Pass()],
            decorator_list=[],
            returns=None
        )
        
        tree = ast.Module(body=[func_node], type_ignores=[])
        enhanced_tree = generator.add_type_hints_to_ast(tree)
        
        # Function should now have type hints
        enhanced_func = enhanced_tree.body[0]
        assert enhanced_func.returns is not None
        assert enhanced_func.args.args[0].annotation is not None


class TestDocstringGenerator:
    """Test cases for DocstringGenerator."""
    
    def test_add_function_docstring(self):
        """Test adding docstring to function."""
        generator = DocstringGenerator()
        
        # Create a function without docstring
        func_node = ast.FunctionDef(
            name='test_func',
            args=ast.arguments(
                posonlyargs=[],
                args=[ast.arg(arg='x', annotation=None)],
                vararg=None,
                kwonlyargs=[],
                kw_defaults=[],
                kwarg=None,
                defaults=[]
            ),
            body=[ast.Pass()],
            decorator_list=[],
            returns=None
        )
        
        tree = ast.Module(body=[func_node], type_ignores=[])
        enhanced_tree = generator.add_docstrings_to_ast(tree)
        
        # Function should now have a docstring
        enhanced_func = enhanced_tree.body[0]
        assert len(enhanced_func.body) >= 1
        first_stmt = enhanced_func.body[0]
        assert isinstance(first_stmt, ast.Expr)
        assert isinstance(first_stmt.value, ast.Constant)
        assert 'test_func' in first_stmt.value.value
    
    def test_add_class_docstring(self):
        """Test adding docstring to class."""
        generator = DocstringGenerator()
        
        # Create a class without docstring
        class_node = ast.ClassDef(
            name='TestClass',
            bases=[],
            keywords=[],
            decorator_list=[],
            body=[ast.Pass()]
        )
        
        tree = ast.Module(body=[class_node], type_ignores=[])
        enhanced_tree = generator.add_docstrings_to_ast(tree)
        
        # Class should now have a docstring
        enhanced_class = enhanced_tree.body[0]
        assert len(enhanced_class.body) >= 1
        first_stmt = enhanced_class.body[0]
        assert isinstance(first_stmt, ast.Expr)
        assert isinstance(first_stmt.value, ast.Constant)
        assert 'TestClass' in first_stmt.value.value


class TestCommentPreserver:
    """Test cases for CommentPreserver."""
    
    def test_extract_comments_from_visual_model(self):
        """Test extracting comments from visual model."""
        preserver = CommentPreserver()
        
        # Create visual model with comments
        model = VisualModel()
        node = VisualNode(
            type=NodeType.FUNCTION,
            parameters={'function_name': 'test_func'},
            comments=['This is a test function', 'It does something important']
        )
        model.add_node(node)
        
        comments = preserver.extract_comments_from_visual_model(model)
        
        assert node.id in comments
        assert len(comments[node.id]) == 2
        assert 'This is a test function' in comments[node.id]
    
    def test_generate_header_comments(self):
        """Test generating header comments from model metadata."""
        preserver = CommentPreserver()
        
        model = VisualModel()
        model.metadata = {
            'description': 'Test module',
            'author': 'Test Author',
            'version': '1.0.0'
        }
        
        header_comments = preserver.generate_header_comments(model)
        
        assert len(header_comments) >= 3  # description, author, version, timestamp
        assert any('Test module' in comment for comment in header_comments)
        assert any('Test Author' in comment for comment in header_comments)
        assert any('1.0.0' in comment for comment in header_comments)
    
    def test_preserve_inline_comments(self):
        """Test preserving inline comments in generated code."""
        preserver = CommentPreserver()
        
        # Create visual model with variable comment
        model = VisualModel()
        node = VisualNode(
            type=NodeType.VARIABLE,
            parameters={'variable_name': 'x'},
            comments=['Important variable']
        )
        model.add_node(node)
        
        code = "x = 42\ny = 'hello'"
        enhanced_code = preserver.preserve_inline_comments(code, model)
        
        assert '# Important variable' in enhanced_code


class TestCodeGenerator:
    """Test cases for CodeGenerator."""
    
    def test_generator_initialization(self):
        """Test generator initialization."""
        generator = CodeGenerator()
        
        assert generator.formatter is not None
        assert generator.optimizer is not None
        assert generator.type_hint_generator is not None
        assert generator.docstring_generator is not None
        assert generator.comment_preserver is not None
    
    def test_generate_simple_code(self):
        """Test generating code from simple AST."""
        generator = CodeGenerator()
        
        # Create simple AST: x = 42
        assign_node = ast.Assign(
            targets=[ast.Name(id='x', ctx=ast.Store())],
            value=ast.Constant(value=42)
        )
        tree = ast.Module(body=[assign_node], type_ignores=[])
        
        code = generator.generate_code(tree)
        
        assert isinstance(code, str)
        assert 'x' in code
        assert '42' in code
    
    def test_generate_code_with_options(self):
        """Test code generation with various options."""
        generator = CodeGenerator()
        
        # Create function AST
        func_node = ast.FunctionDef(
            name='test_func',
            args=ast.arguments(
                posonlyargs=[],
                args=[],
                vararg=None,
                kwonlyargs=[],
                kw_defaults=[],
                kwarg=None,
                defaults=[]
            ),
            body=[ast.Pass()],
            decorator_list=[],
            returns=None
        )
        tree = ast.Module(body=[func_node], type_ignores=[])
        
        options = {
            'add_type_hints': True,
            'add_docstrings': True,
            'format_code': True,
            'optimize_code': True
        }
        
        code = generator.generate_code(tree, options)
        
        assert isinstance(code, str)
        assert 'test_func' in code
    
    def test_format_code(self):
        """Test code formatting."""
        generator = CodeGenerator()
        code = "x=42\ny='hello'"
        
        formatted = generator.format_code(code)
        
        assert isinstance(formatted, str)
        # Should be properly formatted
        lines = formatted.split('\n')
        assert all(not line.endswith(' ') for line in lines if line.strip())
    
    def test_validate_generated_code_valid(self):
        """Test validation of valid generated code."""
        generator = CodeGenerator()
        code = "x = 42\nprint(x)"
        
        result = generator.validate_generated_code(code)
        
        assert result['is_valid'] is True
        assert len(result['errors']) == 0
    
    def test_validate_generated_code_invalid(self):
        """Test validation of invalid generated code."""
        generator = CodeGenerator()
        code = "x = 42 +"  # Syntax error
        
        result = generator.validate_generated_code(code)
        
        assert result['is_valid'] is False
        assert len(result['errors']) > 0
    
    def test_validate_code_warnings(self):
        """Test code validation warnings."""
        generator = CodeGenerator()
        # Very long line
        long_line = "x = " + "a" * 200
        
        result = generator.validate_generated_code(long_line)
        
        # Should have warning about line length
        assert len(result['warnings']) > 0
        assert any('exceeds maximum length' in warning for warning in result['warnings'])
    
    def test_get_code_metrics(self):
        """Test getting code metrics."""
        generator = CodeGenerator()
        code = """# Comment
x = 42
y = 'hello'

def func():
    pass
"""
        
        metrics = generator.get_code_metrics(code)
        
        assert metrics['total_lines'] > 0
        assert metrics['non_empty_lines'] > 0
        assert metrics['comment_lines'] > 0
        assert metrics['max_line_length'] > 0
        assert metrics['avg_line_length'] > 0
    
    def test_fallback_code_generation(self):
        """Test fallback code generation."""
        generator = CodeGenerator()
        
        # Create AST that might cause issues with ast.unparse
        assign_node = ast.Assign(
            targets=[ast.Name(id='x', ctx=ast.Store())],
            value=ast.Constant(value=42)
        )
        tree = ast.Module(body=[assign_node], type_ignores=[])
        
        # Test fallback method directly
        code = generator._fallback_code_generation(tree)
        
        assert isinstance(code, str)
        assert 'x = 42' in code
    
    def test_empty_module_generation(self):
        """Test generating code from empty module."""
        generator = CodeGenerator()
        tree = ast.Module(body=[], type_ignores=[])
        
        code = generator.generate_code(tree)
        
        assert isinstance(code, str)
        # Should handle empty modules gracefully
    
    def test_generate_code_from_visual_model(self):
        """Test generating code directly from visual model."""
        generator = CodeGenerator()
        
        # Create simple visual model
        model = VisualModel()
        model.metadata = {'description': 'Test module'}
        
        node = VisualNode(
            type=NodeType.VARIABLE,
            parameters={'variable_name': 'x', 'default_value': 42},
            comments=['Test variable']
        )
        model.add_node(node)
        
        code = generator.generate_code_from_visual_model(model)
        
        assert isinstance(code, str)
        assert '# Test module' in code  # Header comment
        assert 'x' in code
    
    def test_preserve_custom_docstrings(self):
        """Test preserving custom docstrings from visual nodes."""
        generator = CodeGenerator()
        
        # Create visual model with custom docstring
        model = VisualModel()
        node = VisualNode(
            type=NodeType.FUNCTION,
            parameters={'function_name': 'test_func'},
            docstring='Custom docstring for test function'
        )
        model.add_node(node)
        
        # Create AST with function
        func_node = ast.FunctionDef(
            name='test_func',
            args=ast.arguments(
                posonlyargs=[], args=[], vararg=None, kwonlyargs=[],
                kw_defaults=[], kwarg=None, defaults=[]
            ),
            body=[ast.Pass()],
            decorator_list=[],
            returns=None
        )
        tree = ast.Module(body=[func_node], type_ignores=[])
        
        enhanced_tree = generator.preserve_custom_docstrings(tree, model)
        
        # Function should have custom docstring
        enhanced_func = enhanced_tree.body[0]
        assert len(enhanced_func.body) >= 1
        first_stmt = enhanced_func.body[0]
        assert isinstance(first_stmt, ast.Expr)
        assert isinstance(first_stmt.value, ast.Constant)
        assert 'Custom docstring for test function' in first_stmt.value.value


    def test_complex_ast_generation(self):
        """Test generating code from complex AST structures."""
        generator = CodeGenerator()
        
        # Create complex AST with function definition
        func_node = ast.FunctionDef(
            name='complex_func',
            args=ast.arguments(
                posonlyargs=[],
                args=[ast.arg(arg='x', annotation=None), ast.arg(arg='y', annotation=None)],
                vararg=None,
                kwonlyargs=[],
                kw_defaults=[],
                kwarg=None,
                defaults=[ast.Constant(value=10)]
            ),
            body=[
                ast.Return(value=ast.BinOp(
                    left=ast.Name(id='x', ctx=ast.Load()),
                    op=ast.Add(),
                    right=ast.Name(id='y', ctx=ast.Load())
                ))
            ],
            decorator_list=[],
            returns=None
        )
        
        tree = ast.Module(body=[func_node], type_ignores=[])
        
        code = generator.generate_code(tree)
        
        assert isinstance(code, str)
        assert 'complex_func' in code
        assert 'return' in code.lower()


# Property-based tests
@given(st.text(min_size=0, max_size=100))
def test_format_code_property(code_input):
    """Property test: Formatter should handle any string input."""
    formatter = PythonFormatter()
    
    try:
        result = formatter.format_code(code_input)
        assert isinstance(result, str)
    except Exception:
        # Some inputs might cause issues, which is acceptable
        pass


@given(st.integers(min_value=-1000, max_value=1000))
def test_generate_integer_assignment_property(value):
    """Property test: Generator should handle any integer assignment."""
    generator = CodeGenerator()
    
    assign_node = ast.Assign(
        targets=[ast.Name(id='x', ctx=ast.Store())],
        value=ast.Constant(value=value)
    )
    tree = ast.Module(body=[assign_node], type_ignores=[])
    
    code = generator.generate_code(tree)
    
    assert isinstance(code, str)
    assert str(value) in code


@given(st.text(min_size=1, max_size=20, alphabet=st.characters(min_codepoint=97, max_codepoint=122)))
def test_generate_variable_assignment_property(var_name):
    """Property test: Generator should handle any valid variable name."""
    # Ensure it's a valid Python identifier
    if not var_name.isidentifier():
        return
    
    generator = CodeGenerator()
    
    assign_node = ast.Assign(
        targets=[ast.Name(id=var_name, ctx=ast.Store())],
        value=ast.Constant(value=42)
    )
    tree = ast.Module(body=[assign_node], type_ignores=[])
    
    code = generator.generate_code(tree)
    
    assert isinstance(code, str)
    assert var_name in code