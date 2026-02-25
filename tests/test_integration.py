"""
Integration tests for the Visual Editor Core.

These tests demonstrate end-to-end functionality of the visual programming system.
"""

import pytest
from visual_editor_core import (
    VisualModel, VisualNode, NodeType, InputPort, OutputPort,
    ASTProcessor, CodeGenerator, VisualParser
)


class TestEndToEndIntegration:
    """Test end-to-end visual programming workflows."""
    
    def test_visual_to_code_generation(self):
        """Test complete workflow: Visual Model -> AST -> Python Code."""
        # Create a visual model with variable and function nodes
        model = VisualModel()
        
        # Add variable node: x = 42
        var_node = VisualNode(
            type=NodeType.VARIABLE,
            parameters={'variable_name': 'x', 'default_value': 42},
            outputs=[OutputPort(name='value', data_type=int)]
        )
        var_id = model.add_node(var_node)
        
        # Add function node: print(x)
        func_node = VisualNode(
            type=NodeType.FUNCTION,
            parameters={'function_name': 'print'},
            inputs=[InputPort(name='value', data_type=int)]
        )
        func_id = model.add_node(func_node)
        
        # Connect them
        connection = model.connect_nodes(var_id, 'value', func_id, 'value')
        assert connection is not None
        
        # Convert to AST
        processor = ASTProcessor()
        ast_tree = processor.visual_to_ast(model)
        
        # Generate Python code
        generator = CodeGenerator()
        code = generator.generate_code(ast_tree)
        
        # Verify the generated code
        assert isinstance(code, str)
        assert 'x = 42' in code
        assert 'print' in code
        
        # Validate the code is syntactically correct
        validation = generator.validate_generated_code(code)
        assert validation['is_valid'] is True
    
    def test_code_to_visual_parsing(self):
        """Test complete workflow: Python Code -> AST -> Visual Model."""
        # Start with Python code
        python_code = """
x = 42
y = 'hello'
print(x)
len(y)
"""
        
        # Parse to visual model
        parser = VisualParser()
        model = parser.parse_code(python_code)
        
        # Verify the model structure
        assert len(model.nodes) == 4  # Two variables, two function calls
        
        # Check node types
        node_types = [node.type for node in model.nodes.values()]
        assert node_types.count(NodeType.VARIABLE) == 2
        assert node_types.count(NodeType.FUNCTION) == 2
        
        # Find specific nodes
        var_nodes = [node for node in model.nodes.values() if node.type == NodeType.VARIABLE]
        func_nodes = [node for node in model.nodes.values() if node.type == NodeType.FUNCTION]
        
        # Check variable nodes
        var_names = [node.parameters.get('variable_name') for node in var_nodes]
        assert 'x' in var_names
        assert 'y' in var_names
        
        # Check function nodes
        func_names = [node.parameters.get('function_name') for node in func_nodes]
        assert 'print' in func_names
        assert 'len' in func_names
    
    def test_round_trip_conversion(self):
        """Test round-trip: Visual -> Code -> Visual."""
        # Create original visual model
        original_model = VisualModel()
        
        # Add a simple variable node
        var_node = VisualNode(
            type=NodeType.VARIABLE,
            parameters={'variable_name': 'test_var', 'default_value': 123}
        )
        original_model.add_node(var_node)
        
        # Convert to code
        processor = ASTProcessor()
        generator = CodeGenerator()
        
        ast_tree = processor.visual_to_ast(original_model)
        code = generator.generate_code(ast_tree)
        
        # Parse back to visual model
        parser = VisualParser()
        new_model = parser.parse_code(code)
        
        # Verify round-trip preservation
        assert len(new_model.nodes) == len(original_model.nodes)
        
        # Check that we have a variable node with the same name
        new_var_nodes = [node for node in new_model.nodes.values() 
                        if node.type == NodeType.VARIABLE]
        assert len(new_var_nodes) == 1
        assert new_var_nodes[0].parameters['variable_name'] == 'test_var'
    
    def test_complex_program_generation(self):
        """Test generating a more complex program with multiple constructs."""
        model = VisualModel()
        
        # Create a class node
        class_node = VisualNode(
            type=NodeType.CLASS,
            parameters={'class_name': 'Calculator'}
        )
        model.add_node(class_node)
        
        # Create a function node
        func_node = VisualNode(
            type=NodeType.FUNCTION,
            parameters={'function_name': 'add', 'is_definition': True}
        )
        model.add_node(func_node)
        
        # Create control flow node
        if_node = VisualNode(
            type=NodeType.CONTROL_FLOW,
            parameters={'control_type': 'if'}
        )
        model.add_node(if_node)
        
        # Convert to code
        processor = ASTProcessor()
        generator = CodeGenerator()
        
        ast_tree = processor.visual_to_ast(model)
        code = generator.generate_code(ast_tree, {
            'add_docstrings': True,
            'format_code': True
        })
        
        # Verify complex constructs are present
        assert 'Calculator' in code
        assert 'add' in code
        assert 'if' in code
        
        # Should be valid Python
        validation = generator.validate_generated_code(code)
        assert validation['is_valid'] is True
    
    def test_error_handling_integration(self):
        """Test error handling across the integration."""
        # Test with invalid Python code
        parser = VisualParser()
        invalid_code = "x = 42 +"  # Syntax error
        
        model = parser.parse_code(invalid_code)
        
        # Should handle gracefully
        assert len(model.nodes) == 0
        assert 'parse_error' in model.metadata
        
        # Test with empty model
        empty_model = VisualModel()
        processor = ASTProcessor()
        generator = CodeGenerator()
        
        ast_tree = processor.visual_to_ast(empty_model)
        code = generator.generate_code(ast_tree)
        
        # Should generate valid empty code
        assert isinstance(code, str)
        validation = generator.validate_generated_code(code)
        assert validation['is_valid'] is True
    
    def test_code_quality_features(self):
        """Test code quality features in the integration."""
        # Create a model with function
        model = VisualModel()
        
        func_node = VisualNode(
            type=NodeType.FUNCTION,
            parameters={'function_name': 'my_function', 'is_definition': True}
        )
        model.add_node(func_node)
        
        # Generate code with all quality features
        processor = ASTProcessor()
        generator = CodeGenerator()
        
        ast_tree = processor.visual_to_ast(model)
        code = generator.generate_code(ast_tree, {
            'add_type_hints': True,
            'add_docstrings': True,
            'format_code': True,
            'optimize_code': True
        })
        
        # Check code metrics
        metrics = generator.get_code_metrics(code)
        assert metrics['total_lines'] > 0
        assert metrics['non_empty_lines'] > 0
        
        # Should be well-formatted
        validation = generator.validate_generated_code(code)
        assert validation['is_valid'] is True
        assert len(validation['errors']) == 0


class TestComponentInteraction:
    """Test interaction between different components."""
    
    def test_ast_processor_with_parser(self):
        """Test AST processor working with visual parser."""
        # Create code with the parser
        parser = VisualParser()
        code = "result = add(10, 20)"
        
        model = parser.parse_code(code)
        
        # Process with AST processor
        processor = ASTProcessor()
        ast_tree = processor.visual_to_ast(model)
        
        # Should be able to generate code back
        generator = CodeGenerator()
        new_code = generator.generate_code(ast_tree)
        
        assert isinstance(new_code, str)
        assert 'result' in new_code
        assert 'add' in new_code
    
    def test_model_validation_with_connections(self):
        """Test model validation with complex connections."""
        model = VisualModel()
        
        # Create nodes with compatible types
        source_node = VisualNode(
            type=NodeType.VARIABLE,
            parameters={'variable_name': 'data'},
            outputs=[OutputPort(name='value', data_type=str)]
        )
        
        target_node = VisualNode(
            type=NodeType.FUNCTION,
            parameters={'function_name': 'process'},
            inputs=[InputPort(name='input', data_type=str)]
        )
        
        source_id = model.add_node(source_node)
        target_id = model.add_node(target_node)
        
        # Create connection
        connection = model.connect_nodes(source_id, 'value', target_id, 'input')
        assert connection is not None
        
        # Validate the complete model
        errors = model.validate_model()
        assert len(errors) == 0
        
        # Should be able to process through AST
        processor = ASTProcessor()
        ast_tree = processor.visual_to_ast(model)
        assert ast_tree is not None
    
    def test_comment_preservation_integration(self):
        """Test comment preservation through the pipeline."""
        code_with_comments = """
# Main calculation
x = 42  # The answer
print(x)  # Display result
"""
        
        parser = VisualParser()
        model = parser.parse_code(code_with_comments)
        parser.preserve_comments(code_with_comments, model)
        
        # Comments should be preserved
        assert 'comments' in model.metadata
        comments = model.metadata['comments']
        assert len(comments) == 3
        
        # Should still be able to process the model
        processor = ASTProcessor()
        ast_tree = processor.visual_to_ast(model)
        
        generator = CodeGenerator()
        new_code = generator.generate_code(ast_tree)
        
        # Generated code should be valid
        validation = generator.validate_generated_code(new_code)
        assert validation['is_valid'] is True