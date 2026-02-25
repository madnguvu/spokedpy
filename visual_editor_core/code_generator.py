"""
Code Generator for producing high-quality Python source code from AST representations.
"""

import ast
from typing import Optional, Dict, Any, List
import re


class PythonFormatter:
    """Handles Python code formatting according to PEP 8 standards."""
    
    def __init__(self):
        self.indent_size = 4
        self.max_line_length = 88  # Black's default
    
    def format_code(self, code: str) -> str:
        """Format Python code according to PEP 8 standards."""
        lines = code.split('\n')
        formatted_lines = []
        
        for line in lines:
            # Remove trailing whitespace
            line = line.rstrip()
            
            # Ensure proper indentation (simplified)
            if line.strip():
                # Count leading spaces and normalize to multiples of 4
                leading_spaces = len(line) - len(line.lstrip())
                indent_level = leading_spaces // self.indent_size
                normalized_line = ' ' * (indent_level * self.indent_size) + line.lstrip()
                formatted_lines.append(normalized_line)
            else:
                formatted_lines.append('')
        
        return '\n'.join(formatted_lines)
    
    def add_blank_lines(self, code: str) -> str:
        """Add appropriate blank lines between functions and classes."""
        lines = code.split('\n')
        result = []
        
        for i, line in enumerate(lines):
            stripped = line.strip()
            
            # Add blank lines before class and function definitions
            if (stripped.startswith('class ') or stripped.startswith('def ') or 
                stripped.startswith('async def ')):
                if i > 0 and lines[i-1].strip():  # Previous line is not empty
                    result.append('')  # Add blank line
            
            result.append(line)
        
        return '\n'.join(result)


class CodeOptimizer:
    """Optimizes generated Python code for readability and performance."""
    
    def optimize_imports(self, code: str) -> str:
        """Optimize import statements."""
        lines = code.split('\n')
        imports = []
        other_lines = []
        
        for line in lines:
            stripped = line.strip()
            if stripped.startswith('import ') or stripped.startswith('from '):
                imports.append(line)
            else:
                other_lines.append(line)
        
        # Sort imports (simplified)
        imports.sort()
        
        # Combine imports and other code
        if imports and other_lines:
            return '\n'.join(imports) + '\n\n' + '\n'.join(other_lines)
        else:
            return '\n'.join(imports + other_lines)
    
    def remove_redundant_code(self, code: str) -> str:
        """Remove redundant or unnecessary code constructs."""
        # Remove multiple consecutive blank lines
        code = re.sub(r'\n\s*\n\s*\n', '\n\n', code)
        
        # Remove trailing whitespace
        lines = code.split('\n')
        lines = [line.rstrip() for line in lines]
        
        return '\n'.join(lines)
    
    def optimize_variable_names(self, code: str) -> str:
        """Optimize variable names for readability."""
        # This is a simplified implementation
        # In practice, this would involve AST analysis and renaming
        return code


class TypeHintGenerator:
    """Generates type hints for functions and variables."""
    
    def __init__(self):
        self.type_mappings = {
            int: 'int',
            float: 'float',
            str: 'str',
            bool: 'bool',
            list: 'List',
            dict: 'Dict',
            tuple: 'Tuple',
            set: 'Set'
        }
    
    def add_type_hints_to_ast(self, tree: ast.Module) -> ast.Module:
        """Add type hints to function definitions in the AST."""
        class TypeHintVisitor(ast.NodeTransformer):
            def visit_FunctionDef(self, node):
                # Add return type annotation if missing
                if node.returns is None:
                    node.returns = ast.Name(id='Any', ctx=ast.Load())
                
                # Add parameter type annotations if missing
                for arg in node.args.args:
                    if arg.annotation is None:
                        arg.annotation = ast.Name(id='Any', ctx=ast.Load())
                
                return node
        
        visitor = TypeHintVisitor()
        return visitor.visit(tree)
    
    def infer_type_from_value(self, value: Any) -> str:
        """Infer type annotation from a value."""
        value_type = type(value)
        return self.type_mappings.get(value_type, 'Any')


class DocstringGenerator:
    """Generates docstrings for functions and classes."""
    
    def __init__(self):
        self.docstring_templates = {
            'function': self._generate_function_docstring_template,
            'class': self._generate_class_docstring_template,
            'method': self._generate_method_docstring_template
        }
    
    def add_docstrings_to_ast(self, tree: ast.Module) -> ast.Module:
        """Add docstrings to functions and classes in the AST."""
        class DocstringVisitor(ast.NodeTransformer):
            def __init__(self, generator):
                self.generator = generator
            
            def visit_FunctionDef(self, node):
                # Check if function already has a docstring
                if (not node.body or 
                    not isinstance(node.body[0], ast.Expr) or
                    not isinstance(node.body[0].value, ast.Constant)):
                    
                    # Generate a docstring based on function signature
                    docstring = self.generator._generate_function_docstring(node)
                    docstring_node = ast.Expr(value=ast.Constant(value=docstring))
                    node.body.insert(0, docstring_node)
                
                return self.generic_visit(node)
            
            def visit_AsyncFunctionDef(self, node):
                # Handle async functions the same way
                return self.visit_FunctionDef(node)
            
            def visit_ClassDef(self, node):
                # Check if class already has a docstring
                if (not node.body or 
                    not isinstance(node.body[0], ast.Expr) or
                    not isinstance(node.body[0].value, ast.Constant)):
                    
                    # Generate a class docstring
                    docstring = self.generator._generate_class_docstring(node)
                    docstring_node = ast.Expr(value=ast.Constant(value=docstring))
                    node.body.insert(0, docstring_node)
                
                return self.generic_visit(node)
        
        visitor = DocstringVisitor(self)
        return visitor.visit(tree)
    
    def _generate_function_docstring(self, func_node):
        """Generate a comprehensive docstring for a function."""
        parts = []
        
        # Function description
        func_name = func_node.name
        if func_name.startswith('_'):
            parts.append(f"Private function {func_name}.")
        elif func_name.startswith('__') and func_name.endswith('__'):
            parts.append(f"Special method {func_name}.")
        else:
            parts.append(f"Function {func_name}.")
        
        # Parameters section
        if func_node.args.args:
            parts.append("\nArgs:")
            for arg in func_node.args.args:
                arg_name = arg.arg
                # Try to infer type from annotation
                if arg.annotation:
                    if isinstance(arg.annotation, ast.Name):
                        arg_type = arg.annotation.id
                    else:
                        arg_type = "Any"
                else:
                    arg_type = "Any"
                
                parts.append(f"    {arg_name} ({arg_type}): Description of {arg_name}.")
        
        # Default arguments
        if func_node.args.defaults:
            if not any("Args:" in part for part in parts):
                parts.append("\nArgs:")
            parts.append("    *args: Variable length argument list.")
        
        # Keyword arguments
        if func_node.args.kwonlyargs:
            if not any("Args:" in part for part in parts):
                parts.append("\nArgs:")
            for kwarg in func_node.args.kwonlyargs:
                parts.append(f"    {kwarg.arg}: Keyword argument {kwarg.arg}.")
        
        # Returns section
        if func_node.returns:
            parts.append("\nReturns:")
            if isinstance(func_node.returns, ast.Name):
                return_type = func_node.returns.id
            else:
                return_type = "Any"
            parts.append(f"    {return_type}: Description of return value.")
        else:
            parts.append("\nReturns:")
            parts.append("    None: This function doesn't return a value.")
        
        # Raises section for common patterns
        if any(isinstance(stmt, ast.Raise) for stmt in ast.walk(func_node)):
            parts.append("\nRaises:")
            parts.append("    Exception: Description of when this exception is raised.")
        
        return ''.join(parts)
    
    def _generate_class_docstring(self, class_node):
        """Generate a comprehensive docstring for a class."""
        parts = []
        
        # Class description
        class_name = class_node.name
        parts.append(f"Class {class_name}.")
        
        # Inheritance information
        if class_node.bases:
            base_names = []
            for base in class_node.bases:
                if isinstance(base, ast.Name):
                    base_names.append(base.id)
                else:
                    base_names.append("Unknown")
            
            if base_names:
                parts.append(f"\nInherits from: {', '.join(base_names)}")
        
        # Attributes section (if we can detect them)
        parts.append("\nAttributes:")
        parts.append("    Attributes will be documented here.")
        
        # Methods section
        methods = [node for node in class_node.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]
        if methods:
            parts.append("\nMethods:")
            for method in methods[:3]:  # Limit to first 3 methods
                parts.append(f"    {method.name}(): {method.name.replace('_', ' ').title()} method.")
        
        return ''.join(parts)
    
    def _generate_function_docstring_template(self, name, args, returns=None):
        """Generate a template docstring for a function."""
        return f"Function {name}.\n\nArgs:\n    args: Function arguments.\n\nReturns:\n    result: Function result."
    
    def _generate_class_docstring_template(self, name, bases=None):
        """Generate a template docstring for a class."""
        return f"Class {name}.\n\nA class for {name.lower()} operations."
    
    def _generate_method_docstring_template(self, name, args, returns=None):
        """Generate a template docstring for a method."""
        return f"Method {name}.\n\nArgs:\n    self: Instance reference.\n\nReturns:\n    result: Method result."
    
    def preserve_existing_docstrings(self, tree: ast.Module) -> Dict[str, str]:
        """Extract and preserve existing docstrings from an AST."""
        docstrings = {}
        
        class DocstringExtractor(ast.NodeVisitor):
            def visit_FunctionDef(self, node):
                if (node.body and 
                    isinstance(node.body[0], ast.Expr) and
                    isinstance(node.body[0].value, ast.Constant) and
                    isinstance(node.body[0].value.value, str)):
                    docstrings[f"function_{node.name}"] = node.body[0].value.value
                self.generic_visit(node)
            
            def visit_AsyncFunctionDef(self, node):
                self.visit_FunctionDef(node)
            
            def visit_ClassDef(self, node):
                if (node.body and 
                    isinstance(node.body[0], ast.Expr) and
                    isinstance(node.body[0].value, ast.Constant) and
                    isinstance(node.body[0].value.value, str)):
                    docstrings[f"class_{node.name}"] = node.body[0].value.value
                self.generic_visit(node)
        
        extractor = DocstringExtractor()
        extractor.visit(tree)
        return docstrings


class CommentPreserver:
    """Handles preservation and generation of comments from visual annotations."""
    
    def __init__(self):
        self.comment_mappings = {}
    
    def extract_comments_from_visual_model(self, model) -> Dict[str, List[str]]:
        """Extract comments from visual nodes for preservation in generated code."""
        comments = {}
        
        for node_id, node in model.nodes.items():
            if node.comments:
                comments[node_id] = node.comments.copy()
        
        return comments
    
    def add_comments_to_ast(self, tree: ast.Module, visual_model, node_comments: Dict[str, List[str]]) -> ast.Module:
        """Add comments from visual annotations to the AST."""
        class CommentVisitor(ast.NodeTransformer):
            def __init__(self, comments_dict, visual_model):
                self.comments = comments_dict
                self.visual_model = visual_model
                self.node_to_ast_mapping = {}
            
            def visit_FunctionDef(self, node):
                # Find corresponding visual node
                visual_node_id = self._find_visual_node_for_function(node.name)
                if visual_node_id and visual_node_id in self.comments:
                    # Add comments as docstring if no docstring exists
                    if (not node.body or 
                        not isinstance(node.body[0], ast.Expr) or
                        not isinstance(node.body[0].value, ast.Constant)):
                        
                        comment_text = '\n'.join(self.comments[visual_node_id])
                        docstring_node = ast.Expr(value=ast.Constant(value=comment_text))
                        node.body.insert(0, docstring_node)
                
                return self.generic_visit(node)
            
            def visit_ClassDef(self, node):
                # Find corresponding visual node
                visual_node_id = self._find_visual_node_for_class(node.name)
                if visual_node_id and visual_node_id in self.comments:
                    # Add comments as docstring if no docstring exists
                    if (not node.body or 
                        not isinstance(node.body[0], ast.Expr) or
                        not isinstance(node.body[0].value, ast.Constant)):
                        
                        comment_text = '\n'.join(self.comments[visual_node_id])
                        docstring_node = ast.Expr(value=ast.Constant(value=comment_text))
                        node.body.insert(0, docstring_node)
                
                return self.generic_visit(node)
            
            def _find_visual_node_for_function(self, func_name):
                """Find visual node ID for a function name."""
                for node_id, node in self.visual_model.nodes.items():
                    if (node.type.value == 'function' and 
                        node.parameters.get('function_name') == func_name):
                        return node_id
                return None
            
            def _find_visual_node_for_class(self, class_name):
                """Find visual node ID for a class name."""
                for node_id, node in self.visual_model.nodes.items():
                    if (node.type.value == 'class' and 
                        node.parameters.get('class_name') == class_name):
                        return node_id
                return None
        
        visitor = CommentVisitor(node_comments, visual_model)
        return visitor.visit(tree)
    
    def preserve_inline_comments(self, code: str, visual_model) -> str:
        """Add inline comments to generated code based on visual annotations."""
        lines = code.split('\n')
        enhanced_lines = []
        
        for line in lines:
            enhanced_line = line
            
            # Look for opportunities to add inline comments
            # This is a simplified implementation - in practice would need more sophisticated mapping
            if '=' in line and not line.strip().startswith('#'):
                # Variable assignment - check if we have comments for this
                var_name = line.split('=')[0].strip()
                comment = self._find_comment_for_variable(var_name, visual_model)
                if comment:
                    enhanced_line = f"{line}  # {comment}"
            
            enhanced_lines.append(enhanced_line)
        
        return '\n'.join(enhanced_lines)
    
    def _find_comment_for_variable(self, var_name: str, visual_model) -> Optional[str]:
        """Find comment for a variable from visual model."""
        for node in visual_model.nodes.values():
            if (node.type.value == 'variable' and 
                node.parameters.get('variable_name') == var_name and
                node.comments):
                return node.comments[0]  # Return first comment
        return None
    
    def generate_header_comments(self, visual_model) -> List[str]:
        """Generate header comments for the module based on visual model metadata."""
        comments = []
        
        # Add module-level comments from metadata
        if 'description' in visual_model.metadata:
            comments.append(f"# {visual_model.metadata['description']}")
        
        if 'author' in visual_model.metadata:
            comments.append(f"# Author: {visual_model.metadata['author']}")
        
        if 'version' in visual_model.metadata:
            comments.append(f"# Version: {visual_model.metadata['version']}")
        
        # Add generation timestamp
        from datetime import datetime
        comments.append(f"# Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        return comments


class CodeGenerator:
    """Produces high-quality Python source code from AST representations."""
    
    def __init__(self):
        self.formatter = PythonFormatter()
        self.optimizer = CodeOptimizer()
        self.type_hint_generator = TypeHintGenerator()
        self.docstring_generator = DocstringGenerator()
        self.comment_preserver = CommentPreserver()
    
    def generate_code(self, tree: ast.Module, options: Optional[Dict[str, Any]] = None, visual_model=None) -> str:
        """Generate Python source code from an AST."""
        if options is None:
            options = {}
        
        # Apply enhancements based on options
        enhanced_tree = tree
        
        if options.get('add_type_hints', False):
            enhanced_tree = self.add_type_hints(enhanced_tree)
        
        if options.get('add_docstrings', False):
            enhanced_tree = self.generate_docstrings(enhanced_tree)
        
        # Preserve comments from visual annotations
        if options.get('preserve_comments', True) and visual_model:
            node_comments = self.comment_preserver.extract_comments_from_visual_model(visual_model)
            enhanced_tree = self.comment_preserver.add_comments_to_ast(enhanced_tree, visual_model, node_comments)
        
        # Preserve custom docstrings from visual nodes
        if visual_model:
            enhanced_tree = self.preserve_custom_docstrings(enhanced_tree, visual_model)
        
        # Fix missing locations for proper code generation
        ast.fix_missing_locations(enhanced_tree)
        
        # Generate code
        try:
            code = ast.unparse(enhanced_tree)
        except Exception:
            # Fallback to basic string representation
            code = self._fallback_code_generation(enhanced_tree)
        
        # Add header comments if visual model is provided
        if visual_model:
            header_comments = self.comment_preserver.generate_header_comments(visual_model)
            if header_comments:
                code = '\n'.join(header_comments) + '\n\n' + code
        
        # Apply formatting and optimization
        if options.get('format_code', True):
            code = self.format_code(code)
        
        if options.get('optimize_code', True):
            code = self._optimize_generated_code(code)
        
        # Add inline comments from visual annotations
        if options.get('preserve_comments', True) and visual_model:
            code = self.comment_preserver.preserve_inline_comments(code, visual_model)
        
        return code
    
    def format_code(self, code: str) -> str:
        """Format Python code according to standards."""
        formatted = self.formatter.format_code(code)
        formatted = self.formatter.add_blank_lines(formatted)
        return formatted
    
    def add_type_hints(self, tree: ast.Module) -> ast.Module:
        """Add type hints to the AST when type information is available."""
        return self.type_hint_generator.add_type_hints_to_ast(tree)
    
    def generate_docstrings(self, tree: ast.Module) -> ast.Module:
        """Generate docstrings for functions and classes."""
        return self.docstring_generator.add_docstrings_to_ast(tree)
    
    def _optimize_generated_code(self, code: str) -> str:
        """Apply optimizations to generated code."""
        code = self.optimizer.optimize_imports(code)
        code = self.optimizer.remove_redundant_code(code)
        return code
    
    def _fallback_code_generation(self, tree: ast.Module) -> str:
        """Fallback code generation when ast.unparse fails."""
        statements = []
        
        for node in tree.body:
            if isinstance(node, ast.Assign):
                # Variable assignment
                if len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                    var_name = node.targets[0].id
                    if isinstance(node.value, ast.Constant):
                        statements.append(f"{var_name} = {repr(node.value.value)}")
                    else:
                        statements.append(f"{var_name} = # Complex expression")
            
            elif isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
                # Function call
                if isinstance(node.value.func, ast.Name):
                    func_name = node.value.func.id
                    statements.append(f"{func_name}()")
            
            elif isinstance(node, ast.FunctionDef):
                # Function definition
                statements.append(f"def {node.name}():")
                statements.append("    pass")
            
            elif isinstance(node, ast.ClassDef):
                # Class definition
                statements.append(f"class {node.name}:")
                statements.append("    pass")
            
            else:
                statements.append(f"# {type(node).__name__}")
        
        return '\n'.join(statements) if statements else "# Empty module"
    
    def validate_generated_code(self, code: str) -> Dict[str, Any]:
        """Validate that generated code is syntactically correct."""
        result = {
            'is_valid': False,
            'errors': [],
            'warnings': []
        }
        
        try:
            # Try to parse the generated code
            ast.parse(code)
            result['is_valid'] = True
        except SyntaxError as e:
            result['errors'].append(f"Syntax error: {e}")
        except Exception as e:
            result['errors'].append(f"Parse error: {e}")
        
        # Check for common issues
        lines = code.split('\n')
        for i, line in enumerate(lines, 1):
            # Check line length
            if len(line) > self.formatter.max_line_length:
                result['warnings'].append(f"Line {i} exceeds maximum length")
            
            # Check for trailing whitespace
            if line.endswith(' ') or line.endswith('\t'):
                result['warnings'].append(f"Line {i} has trailing whitespace")
        
        return result
    
    def get_code_metrics(self, code: str) -> Dict[str, Any]:
        """Get metrics about the generated code."""
        lines = code.split('\n')
        
        return {
            'total_lines': len(lines),
            'non_empty_lines': len([line for line in lines if line.strip()]),
            'comment_lines': len([line for line in lines if line.strip().startswith('#')]),
            'max_line_length': max(len(line) for line in lines) if lines else 0,
            'avg_line_length': sum(len(line) for line in lines) / len(lines) if lines else 0
        }
    
    def generate_code_from_visual_model(self, visual_model, options: Optional[Dict[str, Any]] = None) -> str:
        """Generate Python code directly from a visual model."""
        # Import here to avoid circular imports
        from .ast_processor import ASTProcessor
        
        if options is None:
            options = {
                'add_type_hints': True,
                'add_docstrings': True,
                'preserve_comments': True,
                'format_code': True,
                'optimize_code': True
            }
        
        # Convert visual model to AST
        processor = ASTProcessor()
        ast_tree = processor.visual_to_ast(visual_model)
        
        # Generate code with visual model context
        return self.generate_code(ast_tree, options, visual_model)
    
    def preserve_custom_docstrings(self, tree: ast.Module, visual_model) -> ast.Module:
        """Preserve custom docstrings from visual nodes."""
        class CustomDocstringVisitor(ast.NodeTransformer):
            def __init__(self, visual_model):
                self.visual_model = visual_model
            
            def visit_FunctionDef(self, node):
                # Find corresponding visual node
                visual_node = self._find_visual_node_for_function(node.name)
                if visual_node and visual_node.docstring:
                    # Replace or add custom docstring
                    if (node.body and 
                        isinstance(node.body[0], ast.Expr) and
                        isinstance(node.body[0].value, ast.Constant)):
                        # Replace existing docstring
                        node.body[0].value.value = visual_node.docstring
                    else:
                        # Add new docstring
                        docstring_node = ast.Expr(value=ast.Constant(value=visual_node.docstring))
                        node.body.insert(0, docstring_node)
                
                return self.generic_visit(node)
            
            def visit_ClassDef(self, node):
                # Find corresponding visual node
                visual_node = self._find_visual_node_for_class(node.name)
                if visual_node and visual_node.docstring:
                    # Replace or add custom docstring
                    if (node.body and 
                        isinstance(node.body[0], ast.Expr) and
                        isinstance(node.body[0].value, ast.Constant)):
                        # Replace existing docstring
                        node.body[0].value.value = visual_node.docstring
                    else:
                        # Add new docstring
                        docstring_node = ast.Expr(value=ast.Constant(value=visual_node.docstring))
                        node.body.insert(0, docstring_node)
                
                return self.generic_visit(node)
            
            def _find_visual_node_for_function(self, func_name):
                """Find visual node for a function name."""
                for node in self.visual_model.nodes.values():
                    if (node.type.value == 'function' and 
                        node.parameters.get('function_name') == func_name):
                        return node
                return None
            
            def _find_visual_node_for_class(self, class_name):
                """Find visual node for a class name."""
                for node in self.visual_model.nodes.values():
                    if (node.type.value == 'class' and 
                        node.parameters.get('class_name') == class_name):
                        return node
                return None
        
        visitor = CustomDocstringVisitor(visual_model)
        return visitor.visit(tree)