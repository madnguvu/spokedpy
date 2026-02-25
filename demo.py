#!/usr/bin/env python3
"""
Demo script for Visual Editor Core functionality.

This script demonstrates the key features of the visual programming system:
1. Creating visual models programmatically
2. Converting visual models to Python code
3. Parsing Python code back to visual models
4. Round-trip conversion validation
"""

from visual_editor_core import (
    VisualModel, VisualNode, NodeType, InputPort, OutputPort,
    ASTProcessor, CodeGenerator, VisualParser
)


def demo_visual_to_code():
    """Demonstrate creating a visual model and generating Python code."""
    print("=== Demo 1: Visual Model to Python Code ===")
    
    # Create a visual model
    model = VisualModel()
    
    # Add a variable node: message = "Hello, World!"
    message_node = VisualNode(
        type=NodeType.VARIABLE,
        parameters={'variable_name': 'message', 'default_value': 'Hello, World!'},
        position=(100, 100),
        outputs=[OutputPort(name='value', data_type=str)]
    )
    message_id = model.add_node(message_node)
    
    # Add a function node: print(message)
    print_node = VisualNode(
        type=NodeType.FUNCTION,
        parameters={'function_name': 'print'},
        position=(300, 100),
        inputs=[InputPort(name='value', data_type=str)]
    )
    print_id = model.add_node(print_node)
    
    # Connect the nodes
    connection = model.connect_nodes(message_id, 'value', print_id, 'value')
    print(f"Created connection: {connection.id}")
    
    # Convert to Python code
    processor = ASTProcessor()
    generator = CodeGenerator()
    
    ast_tree = processor.visual_to_ast(model)
    code = generator.generate_code(ast_tree, {
        'format_code': True,
        'add_docstrings': False
    })
    
    print("Generated Python code:")
    print("-" * 40)
    print(code)
    print("-" * 40)
    
    # Validate the code
    validation = generator.validate_generated_code(code)
    print(f"Code is valid: {validation['is_valid']}")
    if validation['errors']:
        print(f"Errors: {validation['errors']}")
    
    return model, code


def demo_code_to_visual():
    """Demonstrate parsing Python code into a visual model."""
    print("\n=== Demo 2: Python Code to Visual Model ===")
    
    # Sample Python code
    python_code = """
# Calculate area of a rectangle
width = 10
height = 20
area = width * height
print(f"Area: {area}")
"""
    
    print("Original Python code:")
    print("-" * 40)
    print(python_code)
    print("-" * 40)
    
    # Parse to visual model
    parser = VisualParser()
    model = parser.parse_code(python_code)
    parser.preserve_comments(python_code, model)
    
    print(f"Parsed into {len(model.nodes)} visual nodes:")
    for node_id, node in model.nodes.items():
        print(f"  - {node.type.value}: {node.parameters}")
    
    print(f"Found {len(model.metadata.get('comments', []))} comments")
    
    return model


def demo_round_trip():
    """Demonstrate round-trip conversion: Visual -> Code -> Visual."""
    print("\n=== Demo 3: Round-trip Conversion ===")
    
    # Create original visual model
    original_model = VisualModel()
    
    # Add a class node
    class_node = VisualNode(
        type=NodeType.CLASS,
        parameters={'class_name': 'Calculator'},
        position=(100, 50)
    )
    original_model.add_node(class_node)
    
    # Add a variable node
    var_node = VisualNode(
        type=NodeType.VARIABLE,
        parameters={'variable_name': 'result', 'default_value': 42},
        position=(100, 150)
    )
    original_model.add_node(var_node)
    
    print(f"Original model has {len(original_model.nodes)} nodes")
    
    # Convert to code
    processor = ASTProcessor()
    generator = CodeGenerator()
    
    ast_tree = processor.visual_to_ast(original_model)
    code = generator.generate_code(ast_tree)
    
    print("Generated code:")
    print("-" * 30)
    print(code)
    print("-" * 30)
    
    # Parse back to visual model
    parser = VisualParser()
    new_model = parser.parse_code(code)
    
    print(f"Parsed model has {len(new_model.nodes)} nodes")
    
    # Compare models
    original_types = [node.type for node in original_model.nodes.values()]
    new_types = [node.type for node in new_model.nodes.values()]
    
    print(f"Original node types: {[t.value for t in original_types]}")
    print(f"New node types: {[t.value for t in new_types]}")
    
    # Validate round-trip
    is_valid = processor.validate_round_trip(original_model)
    print(f"Round-trip validation: {'PASSED' if is_valid else 'FAILED'}")


def demo_code_quality():
    """Demonstrate code quality features."""
    print("\n=== Demo 4: Code Quality Features ===")
    
    # Create a model with a function
    model = VisualModel()
    
    func_node = VisualNode(
        type=NodeType.FUNCTION,
        parameters={'function_name': 'calculate_sum', 'is_definition': True},
        position=(100, 100)
    )
    model.add_node(func_node)
    
    # Generate code with all quality features
    processor = ASTProcessor()
    generator = CodeGenerator()
    
    ast_tree = processor.visual_to_ast(model)
    
    # Generate with different options
    basic_code = generator.generate_code(ast_tree)
    enhanced_code = generator.generate_code(ast_tree, {
        'add_type_hints': True,
        'add_docstrings': True,
        'format_code': True,
        'optimize_code': True
    })
    
    print("Basic generated code:")
    print("-" * 30)
    print(basic_code)
    print("-" * 30)
    
    print("Enhanced code with quality features:")
    print("-" * 30)
    print(enhanced_code)
    print("-" * 30)
    
    # Get code metrics
    metrics = generator.get_code_metrics(enhanced_code)
    print("Code metrics:")
    for key, value in metrics.items():
        print(f"  {key}: {value}")


def main():
    """Run all demos."""
    print("Visual Editor Core - Feature Demonstration")
    print("=" * 50)
    
    try:
        # Run demos
        model1, code1 = demo_visual_to_code()
        model2 = demo_code_to_visual()
        demo_round_trip()
        demo_code_quality()
        
        print("\n=== Demo Summary ===")
        print("✓ Visual model creation and code generation")
        print("✓ Python code parsing to visual models")
        print("✓ Round-trip conversion validation")
        print("✓ Code quality and formatting features")
        print("\nAll demos completed successfully!")
        
    except Exception as e:
        print(f"\nDemo failed with error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()