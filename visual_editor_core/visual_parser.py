"""
Visual Parser for converting Python source code back into visual models.
"""

import ast
from typing import Dict, Type, List, Optional, Any
from .models import VisualModel, VisualNode, NodeType, InputPort, OutputPort


class VisualBuilder:
    """Base class for building visual nodes from AST nodes."""
    
    def __init__(self, node_type: NodeType):
        self.node_type = node_type
    
    def build_node(self, ast_node: ast.AST, context: Dict[str, Any]) -> VisualNode:
        """Build a visual node from an AST node."""
        raise NotImplementedError("Subclasses must implement build_node")


class AssignmentBuilder(VisualBuilder):
    """Builds variable nodes from assignment statements."""
    
    def __init__(self):
        super().__init__(NodeType.VARIABLE)
    
    def build_node(self, ast_node: ast.Assign, context: Dict[str, Any]) -> VisualNode:
        """Build a variable node from an assignment."""
        if len(ast_node.targets) != 1 or not isinstance(ast_node.targets[0], ast.Name):
            # Complex assignment - create a custom node
            try:
                # Fix missing locations before unparsing
                ast.fix_missing_locations(ast_node)
                code_snippet = ast.unparse(ast_node)
            except:
                code_snippet = "# Complex assignment"
            
            return VisualNode(
                type=NodeType.CUSTOM,
                parameters={'code_snippet': code_snippet},
                position=context.get('position', (0.0, 0.0))
            )
        
        var_name = ast_node.targets[0].id
        
        # Extract default value if it's a constant
        default_value = None
        if isinstance(ast_node.value, ast.Constant):
            default_value = ast_node.value.value
        elif isinstance(ast_node.value, ast.Name):
            default_value = f"${ast_node.value.id}"  # Reference to another variable
        elif isinstance(ast_node.value, ast.UnaryOp) and isinstance(ast_node.value.op, ast.USub):
            # Handle negative numbers
            if isinstance(ast_node.value.operand, ast.Constant):
                default_value = -ast_node.value.operand.value
        elif isinstance(ast_node.value, ast.Call):
            # Handle function call assignments like: result = add(10, 20)
            if isinstance(ast_node.value.func, ast.Name):
                default_value = f"${ast_node.value.func.id}(...)"  # Indicate function call
        
        node = VisualNode(
            type=NodeType.VARIABLE,
            parameters={
                'variable_name': var_name,
                'default_value': default_value
            },
            position=context.get('position', (0.0, 0.0)),
            outputs=[OutputPort(name='value', data_type=type(default_value) if default_value else object)]
        )
        
        return node


class FunctionCallBuilder(VisualBuilder):
    """Builds function nodes from function calls."""
    
    def __init__(self):
        super().__init__(NodeType.FUNCTION)
    
    def build_node(self, ast_node: ast.Call, context: Dict[str, Any]) -> VisualNode:
        """Build a function node from a function call."""
        # Extract function name
        func_name = "unknown_function"
        if isinstance(ast_node.func, ast.Name):
            func_name = ast_node.func.id
        elif isinstance(ast_node.func, ast.Attribute):
            # Method call like obj.method()
            func_name = f"{ast.unparse(ast_node.func.value)}.{ast_node.func.attr}"
        
        # Create input ports for arguments
        inputs = []
        
        # Positional arguments
        for i, arg in enumerate(ast_node.args):
            inputs.append(InputPort(
                name=f'arg_{i}',
                data_type=object,
                required=True
            ))
        
        # Keyword arguments
        for keyword in ast_node.keywords:
            inputs.append(InputPort(
                name=keyword.arg or 'kwargs',
                data_type=object,
                required=False
            ))
        
        node = VisualNode(
            type=NodeType.FUNCTION,
            parameters={'function_name': func_name},
            position=context.get('position', (0.0, 0.0)),
            inputs=inputs,
            outputs=[OutputPort(name='result', data_type=object)]
        )
        
        return node


class ControlFlowBuilder(VisualBuilder):
    """Builds control flow nodes from control statements."""
    
    def __init__(self):
        super().__init__(NodeType.CONTROL_FLOW)
    
    def build_node(self, ast_node: ast.stmt, context: Dict[str, Any]) -> VisualNode:
        """Build a control flow node from a control statement."""
        control_type = type(ast_node).__name__.lower()
        
        # Create appropriate input ports based on control type
        inputs = []
        if isinstance(ast_node, ast.If):
            inputs.append(InputPort(name='condition', data_type=bool, required=True))
        elif isinstance(ast_node, ast.For):
            inputs.append(InputPort(name='iterable', data_type=object, required=True))
        elif isinstance(ast_node, ast.While):
            inputs.append(InputPort(name='condition', data_type=bool, required=True))
        
        node = VisualNode(
            type=NodeType.CONTROL_FLOW,
            parameters={'control_type': control_type},
            position=context.get('position', (0.0, 0.0)),
            inputs=inputs,
            outputs=[OutputPort(name='body', data_type=object)]
        )
        
        return node


class ClassDefBuilder(VisualBuilder):
    """Builds class nodes from class definitions."""
    
    def __init__(self):
        super().__init__(NodeType.CLASS)
    
    def build_node(self, ast_node: ast.ClassDef, context: Dict[str, Any]) -> VisualNode:
        """Build a class node from a class definition."""
        class_name = ast_node.name
        
        # Extract base classes
        base_classes = []
        for base in ast_node.bases:
            if isinstance(base, ast.Name):
                base_classes.append(base.id)
        
        # Create inputs for base classes
        inputs = []
        for base in base_classes:
            inputs.append(InputPort(name=f'base_{base}', data_type=type, required=False))
        
        node = VisualNode(
            type=NodeType.CLASS,
            parameters={
                'class_name': class_name,
                'base_classes': base_classes
            },
            position=context.get('position', (0.0, 0.0)),
            inputs=inputs,
            outputs=[OutputPort(name='class', data_type=type)]
        )
        
        return node


class VisualParser:
    """Converts Python source code back into visual models."""
    
    def __init__(self):
        self.ast_parser = ast.parse
        self.visual_builders: Dict[Type, VisualBuilder] = {}
        
        # Register default builders
        self._register_default_builders()
    
    def _register_default_builders(self):
        """Register the default visual builders."""
        self.register_builder(ast.Assign, AssignmentBuilder())
        self.register_builder(ast.Call, FunctionCallBuilder())
        self.register_builder(ast.If, ControlFlowBuilder())
        self.register_builder(ast.For, ControlFlowBuilder())
        self.register_builder(ast.While, ControlFlowBuilder())
        self.register_builder(ast.ClassDef, ClassDefBuilder())
    
    def parse_code(self, source: str) -> VisualModel:
        """Parse Python source code into a visual model."""
        try:
            # Parse the source code into an AST
            tree = self.ast_parser(source)
            
            # Convert AST to visual model
            model = VisualModel()
            context = {'position_y': 0.0}
            
            for stmt in tree.body:
                nodes = self.handle_statement(stmt, context)
                for node in nodes:
                    model.add_node(node)
                    # Update position for next node
                    context['position_y'] += 80.0
            
            # Try to infer connections based on variable usage
            self._infer_connections(model, tree)
            
            return model
            
        except SyntaxError as e:
            # Return empty model with error information
            model = VisualModel()
            model.metadata['parse_error'] = str(e)
            return model
    
    def handle_statement(self, stmt: ast.stmt, context: Dict[str, Any]) -> List[VisualNode]:
        """Handle a single AST statement and return corresponding visual nodes."""
        nodes = []
        
        # Update position context
        position = (100.0, context.get('position_y', 0.0))
        context['position'] = position
        
        if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
            # Function call expression
            builder = self.visual_builders.get(ast.Call)
            if builder:
                node = builder.build_node(stmt.value, context)
                nodes.append(node)
        
        elif type(stmt) in self.visual_builders:
            # Direct statement mapping
            builder = self.visual_builders[type(stmt)]
            node = builder.build_node(stmt, context)
            nodes.append(node)
        
        else:
            # Handle complex constructs
            complex_nodes = self.handle_complex_constructs(stmt)
            nodes.extend(complex_nodes)
        
        return nodes
    
    def handle_complex_constructs(self, node: ast.AST) -> List[VisualNode]:
        """Handle complex Python constructs during parsing."""
        nodes = []
        
        if isinstance(node, ast.FunctionDef):
            # Function definition
            func_node = VisualNode(
                type=NodeType.FUNCTION,
                parameters={
                    'function_name': node.name,
                    'is_definition': True
                },
                position=(100.0, 0.0)
            )
            
            # Add input ports for parameters
            inputs = []
            for arg in node.args.args:
                inputs.append(InputPort(name=arg.arg, data_type=object, required=True))
            func_node.inputs = inputs
            func_node.outputs = [OutputPort(name='function', data_type=object)]
            
            nodes.append(func_node)
        
        elif isinstance(node, ast.AsyncFunctionDef):
            # Async function definition
            async_node = VisualNode(
                type=NodeType.ASYNC,
                parameters={
                    'function_name': node.name,
                    'is_async': True
                },
                position=(100.0, 0.0)
            )
            nodes.append(async_node)
        
        elif isinstance(node, (ast.With, ast.AsyncWith)):
            # Context manager
            context_node = VisualNode(
                type=NodeType.CONTEXT_MANAGER,
                parameters={
                    'is_async': isinstance(node, ast.AsyncWith)
                },
                position=(100.0, 0.0)
            )
            nodes.append(context_node)
        
        elif isinstance(node, ast.Try):
            # Exception handling
            try_node = VisualNode(
                type=NodeType.CONTROL_FLOW,
                parameters={'control_type': 'try'},
                position=(100.0, 0.0)
            )
            nodes.append(try_node)
        
        else:
            # Fallback - create custom node with code snippet
            try:
                code_snippet = ast.unparse(node)
            except:
                code_snippet = f"# Unsupported construct: {type(node).__name__}"
            
            custom_node = VisualNode(
                type=NodeType.CUSTOM,
                parameters={'code_snippet': code_snippet},
                position=(100.0, 0.0)
            )
            nodes.append(custom_node)
        
        return nodes
    
    def _infer_connections(self, model: VisualModel, tree: ast.Module):
        """Infer connections between nodes based on variable usage."""
        # Simple heuristic: connect variable assignments to their usage
        variable_definitions = {}
        
        # Find variable definitions
        for node_id, node in model.nodes.items():
            if node.type == NodeType.VARIABLE:
                var_name = node.parameters.get('variable_name')
                if var_name:
                    variable_definitions[var_name] = node_id
        
        # Find variable usage and create connections
        for node_id, node in model.nodes.items():
            if node.type == NodeType.FUNCTION:
                # Check if function uses any defined variables
                # This is a simplified approach - in practice, we'd need more sophisticated analysis
                func_name = node.parameters.get('function_name', '')
                
                # Look for common patterns like print(variable)
                for var_name, var_node_id in variable_definitions.items():
                    if var_name in func_name or len(node.inputs) > 0:
                        # Try to create a connection
                        var_node = model.nodes[var_node_id]
                        if var_node.outputs and node.inputs:
                            connection = model.connect_nodes(
                                var_node_id, var_node.outputs[0].name,
                                node_id, node.inputs[0].name
                            )
    
    def preserve_comments(self, source: str, model: VisualModel):
        """Preserve comments from source code in the visual model."""
        lines = source.split('\n')
        comments = []
        
        for i, line in enumerate(lines):
            stripped = line.strip()
            # Check for comments (both standalone and inline)
            if '#' in line:
                comment_start = line.find('#')
                comment_text = line[comment_start:].strip()
                if comment_text:  # Only add non-empty comments
                    comments.append({
                        'line': i + 1,
                        'text': comment_text,
                        'position': (400.0, i * 20.0)
                    })
        
        model.metadata['comments'] = comments
    
    def register_builder(self, ast_type: Type, builder: VisualBuilder):
        """Register a builder for a specific AST node type."""
        self.visual_builders[ast_type] = builder
    
    def get_supported_constructs(self) -> List[str]:
        """Get list of supported Python constructs."""
        return [
            'Variable assignments',
            'Function calls',
            'Function definitions',
            'Class definitions',
            'Control flow (if, for, while)',
            'Context managers (with)',
            'Exception handling (try/except)',
            'Async/await patterns'
        ]