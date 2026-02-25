"""
Node Palette System for managing visual components and third-party package loading.
"""

import inspect
import importlib
import sys
import ast
import textwrap
from typing import Dict, List, Optional, Any, Callable, Type
from .models import VisualNode, NodeType, InputPort, OutputPort


class CustomComponentValidator:
    """Validates and analyzes custom code snippets for component creation."""
    
    def __init__(self):
        self.supported_constructs = {
            ast.FunctionDef, ast.ClassDef, ast.Assign, ast.AugAssign,
            ast.If, ast.For, ast.While, ast.With, ast.Try, ast.Return,
            ast.Import, ast.ImportFrom, ast.Expr
        }
    
    def validate_code_snippet(self, code: str) -> Dict[str, Any]:
        """Validate a code snippet and extract metadata."""
        result = {
            'valid': False,
            'errors': [],
            'warnings': [],
            'metadata': {},
            'ast_tree': None,
            'functions': [],
            'classes': [],
            'imports': [],
            'variables': []
        }
        
        try:
            # Clean and normalize the code
            code = textwrap.dedent(code).strip()
            
            # Parse the AST
            tree = ast.parse(code)
            result['ast_tree'] = tree
            result['valid'] = True
            
            # Analyze the AST
            self._analyze_ast(tree, result)
            
            # Validate constructs
            self._validate_constructs(tree, result)
            
            # Check for security issues
            self._security_check(tree, result)
            
        except SyntaxError as e:
            result['errors'].append(f"Syntax error: {e}")
        except Exception as e:
            result['errors'].append(f"Validation error: {e}")
        
        return result
    
    def _analyze_ast(self, tree: ast.AST, result: Dict[str, Any]):
        """Analyze AST and extract metadata."""
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                func_info = self._analyze_function(node)
                result['functions'].append(func_info)
            elif isinstance(node, ast.ClassDef):
                class_info = self._analyze_class(node)
                result['classes'].append(class_info)
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                import_info = self._analyze_import(node)
                result['imports'].append(import_info)
            elif isinstance(node, ast.Assign):
                var_info = self._analyze_assignment(node)
                if var_info:
                    result['variables'].extend(var_info)
    
    def _analyze_function(self, node: ast.FunctionDef) -> Dict[str, Any]:
        """Analyze a function definition."""
        return {
            'name': node.name,
            'args': [arg.arg for arg in node.args.args],
            'defaults': len(node.args.defaults),
            'returns': ast.unparse(node.returns) if node.returns else None,
            'docstring': ast.get_docstring(node),
            'decorators': [ast.unparse(dec) for dec in node.decorator_list],
            'lineno': node.lineno
        }
    
    def _analyze_class(self, node: ast.ClassDef) -> Dict[str, Any]:
        """Analyze a class definition."""
        methods = []
        for item in node.body:
            if isinstance(item, ast.FunctionDef):
                methods.append(item.name)
        
        return {
            'name': node.name,
            'bases': [ast.unparse(base) for base in node.bases],
            'methods': methods,
            'docstring': ast.get_docstring(node),
            'decorators': [ast.unparse(dec) for dec in node.decorator_list],
            'lineno': node.lineno
        }
    
    def _analyze_import(self, node: ast.AST) -> Dict[str, Any]:
        """Analyze import statements."""
        if isinstance(node, ast.Import):
            return {
                'type': 'import',
                'modules': [alias.name for alias in node.names],
                'aliases': [alias.asname for alias in node.names if alias.asname]
            }
        elif isinstance(node, ast.ImportFrom):
            return {
                'type': 'from_import',
                'module': node.module,
                'names': [alias.name for alias in node.names],
                'aliases': [alias.asname for alias in node.names if alias.asname],
                'level': node.level
            }
    
    def _analyze_assignment(self, node: ast.Assign) -> List[Dict[str, Any]]:
        """Analyze variable assignments."""
        variables = []
        for target in node.targets:
            if isinstance(target, ast.Name):
                variables.append({
                    'name': target.id,
                    'type': 'variable',
                    'lineno': node.lineno
                })
        return variables
    
    def _validate_constructs(self, tree: ast.AST, result: Dict[str, Any]):
        """Validate that all constructs are supported."""
        for node in ast.walk(tree):
            if type(node) not in self.supported_constructs:
                # Check if it's a commonly used but advanced construct
                if isinstance(node, (ast.Lambda, ast.ListComp, ast.DictComp, ast.SetComp, ast.GeneratorExp)):
                    result['warnings'].append(f"Advanced construct {type(node).__name__} at line {getattr(node, 'lineno', '?')} - may need special handling")
                elif isinstance(node, (ast.Global, ast.Nonlocal)):
                    result['warnings'].append(f"Global/nonlocal statement at line {getattr(node, 'lineno', '?')} - may affect component isolation")
    
    def _security_check(self, tree: ast.AST, result: Dict[str, Any]):
        """Check for potentially dangerous constructs."""
        dangerous_functions = {'eval', 'exec', 'compile', '__import__', 'open', 'file'}
        dangerous_modules = {'os', 'sys', 'subprocess', 'importlib'}
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                if node.func.id in dangerous_functions:
                    result['warnings'].append(f"Potentially dangerous function '{node.func.id}' at line {node.lineno}")
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in dangerous_modules:
                        result['warnings'].append(f"Potentially dangerous module import '{alias.name}'")
    
    def generate_interface_spec(self, validation_result: Dict[str, Any]) -> Dict[str, Any]:
        """Generate interface specification from validation result."""
        spec = {
            'inputs': [],
            'outputs': [],
            'parameters': {},
            'node_type': NodeType.CUSTOM
        }
        
        # If there's a main class, prioritize it over functions
        if validation_result['classes']:
            main_class = validation_result['classes'][0]
            spec['node_type'] = NodeType.CLASS
            spec['outputs'].append({
                'name': 'instance',
                'type': object,
                'description': f"Instance of {main_class['name']}"
            })
            spec['parameters']['class_name'] = main_class['name']
            
            # Look for __init__ method to determine constructor parameters
            init_methods = [f for f in validation_result['functions'] if f['name'] == '__init__']
            if init_methods:
                init_method = init_methods[0]
                # Skip 'self' parameter
                for i, arg in enumerate(init_method['args'][1:]):  # Skip self
                    required = i < (len(init_method['args']) - 1 - init_method['defaults'])
                    spec['inputs'].append({
                        'name': arg,
                        'type': object,
                        'required': required,
                        'description': f"Constructor parameter {arg}"
                    })
        
        # If there's a main function (and no classes), use its signature
        elif validation_result['functions']:
            main_func = validation_result['functions'][0]
            
            # Generate inputs from function parameters
            for i, arg in enumerate(main_func['args']):
                required = i < (len(main_func['args']) - main_func['defaults'])
                spec['inputs'].append({
                    'name': arg,
                    'type': object,  # Default type, could be inferred from annotations
                    'required': required,
                    'description': f"Parameter {arg}"
                })
            
            # Add output for function result
            spec['outputs'].append({
                'name': 'result',
                'type': object,
                'description': f"Result of {main_func['name']}"
            })
            
            spec['parameters']['function_name'] = main_func['name']
        
        # For general code snippets
        else:
            spec['inputs'].append({
                'name': 'input',
                'type': object,
                'required': False,
                'description': "Input data"
            })
            spec['outputs'].append({
                'name': 'output',
                'type': object,
                'description': "Output data"
            })
        
        return spec


class Category:
    """Represents a category of visual components."""
    
    def __init__(self, name: str, description: str = "", icon: str = "folder"):
        self.name = name
        self.description = description
        self.icon = icon  # Lucide icon name
        self.nodes: List['NodeDefinition'] = []
        self.subcategories: Dict[str, 'Category'] = {}
    
    def add_node(self, node_def: 'NodeDefinition'):
        """Add a node definition to this category."""
        self.nodes.append(node_def)
    
    def add_subcategory(self, category: 'Category'):
        """Add a subcategory."""
        self.subcategories[category.name] = category
    
    def get_all_nodes(self) -> List['NodeDefinition']:
        """Get all nodes including from subcategories."""
        all_nodes = self.nodes.copy()
        for subcategory in self.subcategories.values():
            all_nodes.extend(subcategory.get_all_nodes())
        return all_nodes


class NodeDefinition:
    """Defines a visual component that can be instantiated."""
    
    def __init__(self, name: str, node_type: NodeType, description: str = "", 
                 icon: str = "box", category: str = "general"):
        self.name = name
        self.node_type = node_type
        self.description = description
        self.icon = icon  # Lucide icon name
        self.category = category
        self.inputs: List[InputPort] = []
        self.outputs: List[OutputPort] = []
        self.parameters: Dict[str, Any] = {}
        self.metadata: Dict[str, Any] = {}
        self.tags: List[str] = []
    
    def add_input(self, name: str, data_type: Type, required: bool = True, 
                  default_value: Any = None, description: str = ""):
        """Add an input port to this node definition."""
        port = InputPort(
            name=name,
            data_type=data_type,
            required=required,
            default_value=default_value,
            description=description
        )
        self.inputs.append(port)
        return self
    
    def add_output(self, name: str, data_type: Type, description: str = ""):
        """Add an output port to this node definition."""
        port = OutputPort(
            name=name,
            data_type=data_type,
            description=description
        )
        self.outputs.append(port)
        return self
    
    def set_parameter(self, key: str, value: Any):
        """Set a parameter for this node definition."""
        self.parameters[key] = value
        return self
    
    def add_tag(self, tag: str):
        """Add a tag for searching and filtering."""
        if tag not in self.tags:
            self.tags.append(tag)
        return self
    
    def create_instance(self, position: tuple = (0.0, 0.0)) -> VisualNode:
        """Create a new instance of this node type."""
        node = VisualNode(
            type=self.node_type,
            position=position,
            inputs=self.inputs.copy(),
            outputs=self.outputs.copy(),
            parameters=self.parameters.copy(),
            metadata=self.metadata.copy()
        )
        return node
    
    def matches_search(self, query: str) -> bool:
        """Check if this node matches a search query."""
        query_lower = query.lower()
        return (
            query_lower in self.name.lower() or
            query_lower in self.description.lower() or
            any(query_lower in tag.lower() for tag in self.tags) or
            query_lower in self.category.lower()
        )


class SearchIndex:
    """Provides search functionality for visual components."""
    
    def __init__(self):
        self.nodes: List[NodeDefinition] = []
        self.categories: Dict[str, Category] = {}
    
    def add_node(self, node_def: NodeDefinition):
        """Add a node to the search index."""
        self.nodes.append(node_def)
    
    def add_category(self, category: Category):
        """Add a category to the search index."""
        self.categories[category.name] = category
        for node in category.get_all_nodes():
            self.add_node(node)
    
    def search(self, query: str, limit: int = 50) -> List[NodeDefinition]:
        """Search for components matching the query."""
        if not query.strip():
            return self.nodes[:limit]
        
        # Score-based search
        results = []
        query_lower = query.lower()
        
        for node in self.nodes:
            score = 0
            
            # Exact name match gets highest score
            if node.name.lower() == query_lower:
                score += 100
            elif query_lower in node.name.lower():
                score += 50
            
            # Description matches
            if query_lower in node.description.lower():
                score += 20
            
            # Tag matches
            for tag in node.tags:
                if query_lower in tag.lower():
                    score += 30
            
            # Category matches
            if query_lower in node.category.lower():
                score += 10
            
            if score > 0:
                results.append((score, node))
        
        # Sort by score and return
        results.sort(key=lambda x: x[0], reverse=True)
        return [node for score, node in results[:limit]]
    
    def filter_by_category(self, category: str) -> List[NodeDefinition]:
        """Filter nodes by category."""
        return [node for node in self.nodes if node.category == category]
    
    def filter_by_type(self, node_type: NodeType) -> List[NodeDefinition]:
        """Filter nodes by type."""
        return [node for node in self.nodes if node.node_type == node_type]


class PluginLoader:
    """Handles loading of third-party plugins and packages."""
    
    def __init__(self):
        self.loaded_packages: Dict[str, List[NodeDefinition]] = {}
        self.package_cache: Dict[str, Any] = {}
        self.package_dependencies: Dict[str, List[str]] = {}
        self.failed_packages: Dict[str, str] = {}  # Track failed packages and reasons
    
    def load_package(self, package_name: str, include_submodules: bool = False) -> List[NodeDefinition]:
        """Load visual components from a Python package."""
        if package_name in self.loaded_packages:
            return self.loaded_packages[package_name]
        
        if package_name in self.failed_packages:
            print(f"Package {package_name} previously failed: {self.failed_packages[package_name]}")
            return []
        
        try:
            # Import the package
            module = importlib.import_module(package_name)
            self.package_cache[package_name] = module
            
            # Extract functions and classes
            nodes = []
            
            # Get all public functions and classes from main module
            nodes.extend(self._extract_nodes_from_module(module, package_name))
            
            # Load submodules if requested
            if include_submodules:
                nodes.extend(self._load_submodules(module, package_name))
            
            # Track dependencies
            self._extract_dependencies(module, package_name)
            
            self.loaded_packages[package_name] = nodes
            return nodes
            
        except ImportError as e:
            error_msg = f"Import failed: {e}"
            self.failed_packages[package_name] = error_msg
            print(f"Failed to load package {package_name}: {error_msg}")
            return []
        except Exception as e:
            error_msg = f"Processing error: {e}"
            self.failed_packages[package_name] = error_msg
            print(f"Error processing package {package_name}: {error_msg}")
            return []
    
    def _extract_nodes_from_module(self, module: Any, package_name: str) -> List[NodeDefinition]:
        """Extract node definitions from a module."""
        nodes = []
        
        # Get all public functions and classes
        for name, obj in inspect.getmembers(module):
            if name.startswith('_'):
                continue
            
            try:
                if inspect.isfunction(obj) or inspect.isbuiltin(obj):
                    node_def = self._create_function_node(name, obj, package_name)
                    nodes.append(node_def)
                elif inspect.isclass(obj):
                    node_def = self._create_class_node(name, obj, package_name)
                    nodes.append(node_def)
                elif inspect.ismodule(obj) and obj.__name__.startswith(package_name):
                    # Handle submodules
                    submodule_nodes = self._extract_nodes_from_module(obj, f"{package_name}.{name}")
                    nodes.extend(submodule_nodes)
            except Exception as e:
                print(f"Warning: Failed to process {name} from {package_name}: {e}")
                continue
        
        return nodes
    
    def _load_submodules(self, module: Any, package_name: str) -> List[NodeDefinition]:
        """Load nodes from submodules."""
        nodes = []
        
        try:
            if hasattr(module, '__path__'):
                # This is a package, iterate through submodules
                import pkgutil
                
                for importer, modname, ispkg in pkgutil.iter_modules(module.__path__, f"{package_name}."):
                    try:
                        submodule = importlib.import_module(modname)
                        submodule_nodes = self._extract_nodes_from_module(submodule, modname)
                        nodes.extend(submodule_nodes)
                    except Exception as e:
                        print(f"Warning: Failed to load submodule {modname}: {e}")
                        continue
        except Exception as e:
            print(f"Warning: Failed to load submodules for {package_name}: {e}")
        
        return nodes
    
    def _extract_dependencies(self, module: Any, package_name: str):
        """Extract package dependencies."""
        dependencies = []
        
        try:
            # Try to get requirements from setup.py or pyproject.toml
            if hasattr(module, '__file__') and module.__file__:
                import os
                package_dir = os.path.dirname(module.__file__)
                
                # Look for setup.py
                setup_py = os.path.join(package_dir, '..', 'setup.py')
                if os.path.exists(setup_py):
                    dependencies.extend(self._parse_setup_py_deps(setup_py))
                
                # Look for requirements.txt
                req_txt = os.path.join(package_dir, '..', 'requirements.txt')
                if os.path.exists(req_txt):
                    dependencies.extend(self._parse_requirements_txt(req_txt))
            
            self.package_dependencies[package_name] = dependencies
            
        except Exception as e:
            print(f"Warning: Failed to extract dependencies for {package_name}: {e}")
            self.package_dependencies[package_name] = []
    
    def _parse_setup_py_deps(self, setup_py_path: str) -> List[str]:
        """Parse dependencies from setup.py (basic implementation)."""
        dependencies = []
        try:
            with open(setup_py_path, 'r', encoding='utf-8') as f:
                content = f.read()
                # Simple regex to find install_requires
                import re
                matches = re.findall(r'install_requires\s*=\s*\[(.*?)\]', content, re.DOTALL)
                if matches:
                    deps_str = matches[0]
                    # Extract quoted strings
                    deps = re.findall(r'["\']([^"\']+)["\']', deps_str)
                    dependencies.extend(deps)
        except Exception:
            pass
        return dependencies
    
    def _parse_requirements_txt(self, req_txt_path: str) -> List[str]:
        """Parse dependencies from requirements.txt."""
        dependencies = []
        try:
            with open(req_txt_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        # Remove version specifiers
                        dep = line.split('>=')[0].split('==')[0].split('<=')[0].split('>')[0].split('<')[0].split('!=')[0]
                        dependencies.append(dep.strip())
        except Exception:
            pass
        return dependencies
    
    def load_popular_packages(self) -> Dict[str, List[NodeDefinition]]:
        """Load commonly used Python packages."""
        popular_packages = [
            'math', 'random', 'datetime', 'json', 'os', 'sys', 're',
            'collections', 'itertools', 'functools', 'operator',
            'pathlib', 'urllib', 'http', 'email', 'csv', 'sqlite3'
        ]
        
        loaded = {}
        for package in popular_packages:
            try:
                nodes = self.load_package(package)
                if nodes:
                    loaded[package] = nodes
            except Exception as e:
                print(f"Failed to load popular package {package}: {e}")
        
        return loaded
    
    def get_package_dependencies(self, package_name: str) -> List[str]:
        """Get dependencies for a package."""
        return self.package_dependencies.get(package_name, [])
    
    def is_package_available(self, package_name: str) -> bool:
        """Check if a package is available for import."""
        try:
            importlib.import_module(package_name)
            return True
        except ImportError:
            return False
    
    def get_failed_packages(self) -> Dict[str, str]:
        """Get packages that failed to load and their error messages."""
        return self.failed_packages.copy()
    
    def clear_cache(self):
        """Clear the package cache and reload everything."""
        self.loaded_packages.clear()
        self.package_cache.clear()
        self.package_dependencies.clear()
        self.failed_packages.clear()
    
    def _create_function_node(self, name: str, func: Callable, package: str) -> NodeDefinition:
        """Create a node definition from a function."""
        node_def = NodeDefinition(
            name=f"{package}.{name}",
            node_type=NodeType.FUNCTION,
            description=func.__doc__ or f"Function from {package}",
            icon="function-square",
            category=package
        )
        
        # Set function name parameter
        node_def.set_parameter('function_name', f"{package}.{name}")
        node_def.add_tag('function').add_tag(package)
        
        # Try to extract signature information
        try:
            sig = inspect.signature(func)
            for param_name, param in sig.parameters.items():
                param_type = param.annotation if param.annotation != inspect.Parameter.empty else object
                default_val = param.default if param.default != inspect.Parameter.empty else None
                required = param.default == inspect.Parameter.empty
                
                node_def.add_input(param_name, param_type, required, default_val)
            
            # Add output port
            return_type = sig.return_annotation if sig.return_annotation != inspect.Signature.empty else object
            node_def.add_output('result', return_type, f"Result of {name}")
            
        except (ValueError, TypeError):
            # Fallback for functions without clear signatures (like built-in C functions)
            # For math functions, typically take numeric inputs
            if package == 'math':
                node_def.add_input('x', float, True, None, "Numeric input")
                if name in ['pow', 'atan2', 'copysign', 'fmod', 'hypot', 'ldexp', 'remainder']:
                    node_def.add_input('y', float, True, None, "Second numeric input")
                node_def.add_output('result', float, f"Result of {name}")
            else:
                # Generic fallback
                node_def.add_input('args', object, False, None, "Function arguments")
                node_def.add_output('result', object, "Function result")
        
        return node_def
    
    def _create_class_node(self, name: str, cls: Type, package: str) -> NodeDefinition:
        """Create a node definition from a class."""
        node_def = NodeDefinition(
            name=f"{package}.{name}",
            node_type=NodeType.CLASS,
            description=cls.__doc__ or f"Class from {package}",
            icon="box",
            category=package
        )
        
        # Set class name parameter
        node_def.set_parameter('class_name', name)
        node_def.set_parameter('package', package)
        node_def.add_tag('class').add_tag(package)
        
        # Add output for the class instance
        node_def.add_output('instance', cls, f"Instance of {name}")
        
        # Try to extract constructor parameters
        try:
            if hasattr(cls, '__init__'):
                sig = inspect.signature(cls.__init__)
                for param_name, param in sig.parameters.items():
                    if param_name == 'self':
                        continue
                    
                    param_type = param.annotation if param.annotation != inspect.Parameter.empty else object
                    default_val = param.default if param.default != inspect.Parameter.empty else None
                    required = param.default == inspect.Parameter.empty
                    
                    node_def.add_input(param_name, param_type, required, default_val)
        
        except Exception:
            # Fallback
            node_def.add_input('args', object, False, None, "Constructor arguments")
        
        return node_def
    
    def get_package_info(self, package_name: str) -> Dict[str, Any]:
        """Get information about a loaded package."""
        if package_name not in self.package_cache:
            return {}
        
        module = self.package_cache[package_name]
        return {
            'name': package_name,
            'doc': getattr(module, '__doc__', ''),
            'version': getattr(module, '__version__', 'unknown'),
            'file': getattr(module, '__file__', ''),
            'functions': len([n for n in self.loaded_packages.get(package_name, []) 
                           if n.node_type == NodeType.FUNCTION]),
            'classes': len([n for n in self.loaded_packages.get(package_name, []) 
                          if n.node_type == NodeType.CLASS])
        }


class NodePalette:
    """Manages the collection of available visual components."""
    
    def __init__(self):
        self.categories: Dict[str, Category] = {}
        self.search_index: SearchIndex = SearchIndex()
        self.plugin_loader: PluginLoader = PluginLoader()
        self._standard_library_loaded = False
        self._initialize_standard_categories()
        self.load_standard_library()  # Auto-load standard library
    
    def _initialize_standard_categories(self):
        """Initialize standard categories."""
        # Core Python category
        core_category = Category("Core Python", "Built-in Python functions and operators", "python")
        self.add_category(core_category)
        
        # Control Flow category
        control_category = Category("Control Flow", "Conditional and loop constructs", "git-branch")
        self.add_category(control_category)
        
        # Data Structures category
        data_category = Category("Data Structures", "Lists, dictionaries, and other data types", "database")
        self.add_category(data_category)
        
# I/O category
        io_category = Category("Input/Output", "File and console I/O operations", "file-text")
        self.add_category(io_category)
        
        # Math category
        math_category = Category("Mathematics", "Mathematical operations and functions", "calculator")
        self.add_category(math_category)
        
        # String category
        string_category = Category("String Operations", "String manipulation and formatting", "text")
        self.add_category(string_category)
        
        # Type Conversion category
        conversion_category = Category("Type Conversion", "Type conversion functions", "swap")
        self.add_category(conversion_category)
    
    def add_category(self, category: Category):
        """Add a category to the palette."""
        self.categories[category.name] = category
        self.search_index.add_category(category)
    
    def load_standard_library(self):
        """Load components for Python standard library."""
        if self._standard_library_loaded:
            return  # Already loaded, skip
        
        self._standard_library_loaded = True
        
        # Built-in functions
        builtins_category = self.categories["Core Python"]
        
        # Common built-in functions
        builtin_functions = [
            ('print', 'Print values to console', ['value'], ['None']),
            ('len', 'Get length of object', ['obj'], ['int']),
            ('str', 'Convert to string', ['obj'], ['str']),
            ('int', 'Convert to integer', ['obj'], ['int']),
            ('float', 'Convert to float', ['obj'], ['float']),
            ('bool', 'Convert to boolean', ['obj'], ['bool']),
            ('abs', 'Absolute value', ['number'], ['number']),
            ('round', 'Round number', ['number', 'ndigits'], ['number']),
            ('pow', 'Raise to power', ['base', 'exp', 'mod'], ['number']),
            ('sum', 'Sum numeric iterable', ['iterable', 'start'], ['number']),
            ('max', 'Maximum value', ['iterable'], ['object']),
            ('min', 'Minimum value', ['iterable'], ['object']),
            ('all', 'All elements truthy', ['iterable'], ['bool']),
            ('any', 'Any element truthy', ['iterable'], ['bool']),
            ('sorted', 'Sort iterable', ['iterable', 'key', 'reverse'], ['list']),
            ('reversed', 'Reverse iterable', ['iterable'], ['reversed']),
            ('range', 'Create a range', ['start', 'stop', 'step'], ['range']),
            ('enumerate', 'Enumerate iterable', ['iterable', 'start'], ['enumerate']),
            ('zip', 'Zip iterables', ['iterables'], ['zip']),
            ('map', 'Map function over iterable', ['func', 'iterable'], ['map']),
            ('filter', 'Filter iterable', ['func', 'iterable'], ['filter']),
            ('list', 'Create a list', ['iterable'], ['list']),
            ('dict', 'Create a dictionary', ['mapping'], ['dict']),
            ('tuple', 'Create a tuple', ['iterable'], ['tuple']),
            ('set', 'Create a set', ['iterable'], ['set']),
            ('input', 'Read input from user', ['prompt'], ['str']),
            ('open', 'Open file', ['file', 'mode', 'encoding'], ['file']),
            ('isinstance', 'Check instance type', ['obj', 'classinfo'], ['bool']),
            ('issubclass', 'Check subclass', ['cls', 'classinfo'], ['bool']),
            ('getattr', 'Get attribute', ['obj', 'name', 'default'], ['object']),
            ('setattr', 'Set attribute', ['obj', 'name', 'value'], ['None']),
            ('hasattr', 'Has attribute', ['obj', 'name'], ['bool']),
            ('iter', 'Get iterator', ['obj'], ['iterator']),
            ('next', 'Next item', ['iterator', 'default'], ['object']),
            ('type', 'Get type', ['obj'], ['type']),
            ('repr', 'Representation', ['obj'], ['str']),
            ('format', 'Format value', ['value', 'format_spec'], ['str']),
        ]
        
        for func_name, description, inputs, outputs in builtin_functions:
            node_def = NodeDefinition(
                name=func_name,
                node_type=NodeType.FUNCTION,
                description=description,
                icon="function-square",
                category="Core Python"
            )
            
            node_def.set_parameter('function_name', func_name)
            node_def.add_tag('builtin').add_tag('function')
            
            # Add inputs
            for i, input_name in enumerate(inputs):
                required = i == 0  # First parameter usually required
                node_def.add_input(input_name, object, required)
            
            # Add outputs
            for output_name in outputs:
                output_type = {'str': str, 'int': int, 'float': float, 'bool': bool, 
                             'list': list, 'dict': dict, 'tuple': tuple, 'set': set}.get(output_name, object)
                node_def.add_output('result', output_type)
            
            builtins_category.add_node(node_def)
        
        # Control flow constructs
        control_category = self.categories["Control Flow"]
        
        control_constructs = [
            ('if', 'Conditional execution', 'git-branch'),
            ('for', 'For loop iteration', 'repeat'),
            ('while', 'While loop', 'rotate-cw'),
            ('try', 'Exception handling', 'shield'),
            ('with', 'Context manager', 'lock'),
        ]
        
        for construct_name, description, icon in control_constructs:
            node_def = NodeDefinition(
                name=construct_name,
                node_type=NodeType.CONTROL_FLOW,
                description=description,
                icon=icon,
                category="Control Flow"
            )
            
            node_def.set_parameter('control_type', construct_name)
            node_def.add_tag('control').add_tag(construct_name)
            
            # Add appropriate inputs based on construct type
            if construct_name in ['if', 'while']:
                node_def.add_input('condition', bool, True, None, "Condition to evaluate")
            elif construct_name == 'for':
                node_def.add_input('iterable', object, True, None, "Object to iterate over")
            elif construct_name == 'try':
                node_def.add_input('body', object, True, None, "Code to try")
            elif construct_name == 'with':
                node_def.add_input('context', object, True, None, "Context manager")
            
            node_def.add_output('body', object, "Body execution flow")
            control_category.add_node(node_def)

        # Data structure helpers
        data_category = self.categories["Data Structures"]
        data_nodes = [
            ('list.append', 'Append item to list', ['list', 'item'], ['list']),
            ('list.pop', 'Pop item from list', ['list', 'index'], ['object']),
            ('list.extend', 'Extend list', ['list', 'iterable'], ['list']),
            ('dict.get', 'Get value from dict', ['dict', 'key', 'default'], ['object']),
            ('dict.set', 'Set value in dict', ['dict', 'key', 'value'], ['dict']),
            ('dict.keys', 'Get dict keys', ['dict'], ['list']),
            ('dict.values', 'Get dict values', ['dict'], ['list']),
            ('set.add', 'Add item to set', ['set', 'item'], ['set']),
            ('set.remove', 'Remove item from set', ['set', 'item'], ['set']),
        ]
        for func_name, description, inputs, outputs in data_nodes:
            node_def = NodeDefinition(
                name=func_name,
                node_type=NodeType.FUNCTION,
                description=description,
                icon="database",
                category="Data Structures"
            )
            node_def.set_parameter('function_name', func_name)
            node_def.add_tag('data').add_tag('structure')
            for i, input_name in enumerate(inputs):
                required = i == 0
                node_def.add_input(input_name, object, required)
            for output_name in outputs:
                node_def.add_output('result', object)
            data_category.add_node(node_def)

        # Standard library modules (auto-generated nodes)
        stdlib_packages = [
            'math', 'statistics', 'random', 'datetime', 'time', 'pathlib',
            'os', 'json', 'csv', 're', 'itertools', 'functools', 'collections',
            'operator', 'logging'
        ]
        
        # Add I/O operations
        io_category = self.categories["Input/Output"]
        io_nodes = [
            ('input', 'Read input from user', ['prompt'], ['str']),
            ('print', 'Print values to console', ['value'], ['None']),
            ('open', 'Open file', ['file', 'mode', 'encoding'], ['file']),
            ('read', 'Read file contents', ['file'], ['str']),
            ('write', 'Write to file', ['file', 'data'], ['None']),
            ('close', 'Close file', ['file'], ['None']),
            ('readline', 'Read line from file', ['file'], ['str']),
            ('readlines', 'Read all lines from file', ['file'], ['list']),
            ('writelines', 'Write lines to file', ['file', 'lines'], ['None']),
            ('flush', 'Flush file buffer', ['file'], ['None']),
            ('tell', 'Get current file position', ['file'], ['int']),
            ('seek', 'Set file position', ['file', 'position'], ['None']),
            ('truncate', 'Truncate file', ['file', 'size'], ['None']),
        ]
        for func_name, description, inputs, outputs in io_nodes:
            node_def = NodeDefinition(
                name=func_name,
                node_type=NodeType.FUNCTION,
                description=description,
                icon="file-text",
                category="Input/Output"
            )
            node_def.set_parameter('function_name', func_name)
            node_def.add_tag('io').add_tag('file')
            for i, input_name in enumerate(inputs):
                required = i == 0
                node_def.add_input(input_name, object, required)
            for output_name in outputs:
                output_type = {'str': str, 'int': int, 'list': list, 'None': type(None)}.get(output_name, object)
                node_def.add_output('result', output_type)
            io_category.add_node(node_def)
        
        # Add string operations
        string_category = self.categories["String Operations"]
        string_nodes = [
            ('len', 'Get length of string', ['string'], ['int']),
            ('str', 'Convert to string', ['obj'], ['str']),
            ('repr', 'Get string representation', ['obj'], ['str']),
            ('format', 'Format string', ['format_string', 'values'], ['str']),
            ('join', 'Join strings', ['separator', 'iterable'], ['str']),
            ('split', 'Split string', ['string', 'separator'], ['list']),
            ('strip', 'Strip whitespace', ['string'], ['str']),
            ('lstrip', 'Strip left whitespace', ['string'], ['str']),
            ('rstrip', 'Strip right whitespace', ['string'], ['str']),
            ('upper', 'Convert to uppercase', ['string'], ['str']),
            ('lower', 'Convert to lowercase', ['string'], ['str']),
            ('capitalize', 'Capitalize string', ['string'], ['str']),
            ('title', 'Convert to title case', ['string'], ['str']),
            ('swapcase', 'Swap case', ['string'], ['str']),
            ('replace', 'Replace substring', ['string', 'old', 'new'], ['str']),
            ('find', 'Find substring', ['string', 'substring'], ['int']),
            ('index', 'Find substring (raises error)', ['string', 'substring'], ['int']),
            ('count', 'Count occurrences', ['string', 'substring'], ['int']),
            ('startswith', 'Check if starts with', ['string', 'prefix'], ['bool']),
            ('endswith', 'Check if ends with', ['string', 'suffix'], ['bool']),
            ('isalpha', 'Check if all alphabetic', ['string'], ['bool']),
            ('isdigit', 'Check if all digits', ['string'], ['bool']),
            ('isalnum', 'Check if alphanumeric', ['string'], ['bool']),
            ('isspace', 'Check if all whitespace', ['string'], ['bool']),
            ('islower', 'Check if all lowercase', ['string'], ['bool']),
            ('isupper', 'Check if all uppercase', ['string'], ['bool']),
            ('istitle', 'Check if title case', ['string'], ['bool']),
        ]
        for func_name, description, inputs, outputs in string_nodes:
            node_def = NodeDefinition(
                name=func_name,
                node_type=NodeType.FUNCTION,
                description=description,
                icon="text",
                category="String Operations"
            )
            node_def.set_parameter('function_name', func_name)
            node_def.add_tag('string').add_tag('text')
            for i, input_name in enumerate(inputs):
                required = i == 0
                node_def.add_input(input_name, object, required)
            for output_name in outputs:
                output_type = {'str': str, 'int': int, 'list': list, 'bool': bool}.get(output_name, object)
                node_def.add_output('result', output_type)
            string_category.add_node(node_def)
        
        # Add type conversion operations
        conversion_category = self.categories["Type Conversion"]
        conversion_nodes = [
            ('int', 'Convert to integer', ['obj'], ['int']),
            ('float', 'Convert to float', ['obj'], ['float']),
            ('str', 'Convert to string', ['obj'], ['str']),
            ('bool', 'Convert to boolean', ['obj'], ['bool']),
            ('list', 'Convert to list', ['obj'], ['list']),
            ('tuple', 'Convert to tuple', ['obj'], ['tuple']),
            ('dict', 'Convert to dictionary', ['obj'], ['dict']),
            ('set', 'Convert to set', ['obj'], ['set']),
            ('complex', 'Convert to complex number', ['real', 'imag'], ['complex']),
            ('bytes', 'Convert to bytes', ['obj'], ['bytes']),
            ('bytearray', 'Convert to bytearray', ['obj'], ['bytearray']),
            ('frozenset', 'Convert to frozenset', ['obj'], ['frozenset']),
        ]
        for func_name, description, inputs, outputs in conversion_nodes:
            node_def = NodeDefinition(
                name=func_name,
                node_type=NodeType.FUNCTION,
                description=description,
                icon="swap",
                category="Type Conversion"
            )
            node_def.set_parameter('function_name', func_name)
            node_def.add_tag('conversion').add_tag('type')
            for i, input_name in enumerate(inputs):
                required = i == 0
                node_def.add_input(input_name, object, required)
            for output_name in outputs:
                output_type = {'int': int, 'float': float, 'str': str, 'bool': bool, 
                             'list': list, 'tuple': tuple, 'dict': dict, 'set': set,
                             'complex': complex, 'bytes': bytes, 'bytearray': bytearray,
                             'frozenset': frozenset}.get(output_name, object)
                node_def.add_output('result', output_type)
            conversion_category.add_node(node_def)
        for package in stdlib_packages:
            self.load_third_party_package(package, include_submodules=False)
        
        # Update search index with all nodes from categories
        self.search_index = SearchIndex()  # Reset search index
        for category in self.categories.values():
            self.search_index.add_category(category)
    
    def load_third_party_package(self, package_name: str, include_submodules: bool = False):
        """Load components from a third-party package."""
        nodes = self.plugin_loader.load_package(package_name, include_submodules)
        
        if nodes:
            # Create or get category for this package
            if package_name not in self.categories:
                category = Category(
                    package_name, 
                    f"Components from {package_name} package",
                    "package"
                )
                self.add_category(category)
            else:
                category = self.categories[package_name]
            
            # Add nodes to category
            for node in nodes:
                category.add_node(node)
                self.search_index.add_node(node)
    
    def load_popular_packages(self):
        """Load commonly used Python packages."""
        loaded_packages = self.plugin_loader.load_popular_packages()
        
        for package_name, nodes in loaded_packages.items():
            if nodes:
                # Create category for this package
                if package_name not in self.categories:
                    category = Category(
                        package_name,
                        f"Standard library: {package_name}",
                        "library"
                    )
                    self.add_category(category)
                else:
                    category = self.categories[package_name]
                
                # Add nodes to category
                for node in nodes:
                    category.add_node(node)
                    self.search_index.add_node(node)
    
    def get_package_info(self, package_name: str) -> Dict[str, Any]:
        """Get detailed information about a loaded package."""
        info = self.plugin_loader.get_package_info(package_name)
        
        # Add category information
        if package_name in self.categories:
            category = self.categories[package_name]
            info.update({
                'category_name': category.name,
                'category_description': category.description,
                'node_count': len(category.get_all_nodes()),
                'dependencies': self.plugin_loader.get_package_dependencies(package_name)
            })
        
        return info
    
    def is_package_available(self, package_name: str) -> bool:
        """Check if a package is available for loading."""
        return self.plugin_loader.is_package_available(package_name)
    
    def get_failed_packages(self) -> Dict[str, str]:
        """Get packages that failed to load."""
        return self.plugin_loader.get_failed_packages()
    
    def suggest_packages(self, query: str) -> List[str]:
        """Suggest package names based on a query."""
        # Common package suggestions based on functionality
        suggestions = {
            'web': ['requests', 'flask', 'django', 'fastapi', 'urllib3'],
            'data': ['pandas', 'numpy', 'scipy', 'matplotlib', 'seaborn'],
            'ml': ['scikit-learn', 'tensorflow', 'pytorch', 'keras'],
            'database': ['sqlite3', 'sqlalchemy', 'pymongo', 'redis'],
            'gui': ['tkinter', 'pyqt5', 'kivy', 'pygame'],
            'testing': ['pytest', 'unittest', 'mock', 'hypothesis'],
            'async': ['asyncio', 'aiohttp', 'tornado', 'twisted'],
            'crypto': ['cryptography', 'hashlib', 'secrets', 'ssl'],
            'image': ['pillow', 'opencv-python', 'imageio', 'matplotlib'],
            'text': ['re', 'string', 'textwrap', 'difflib'],
            'time': ['datetime', 'time', 'calendar', 'dateutil'],
            'file': ['os', 'pathlib', 'shutil', 'glob', 'tempfile'],
            'network': ['socket', 'urllib', 'http', 'email', 'smtplib'],
            'math': ['math', 'statistics', 'decimal', 'fractions', 'cmath'],
            'json': ['json', 'pickle', 'csv', 'xml', 'yaml'],
        }
        
        query_lower = query.lower()
        suggested = []
        
        # Direct matches
        if query_lower in suggestions:
            suggested.extend(suggestions[query_lower])
        
        # Partial matches
        for category, packages in suggestions.items():
            if query_lower in category:
                suggested.extend(packages)
        
        # Remove duplicates and return
        return list(dict.fromkeys(suggested))[:10]
    
    def search_nodes(self, query: str, category: Optional[str] = None, 
                    node_type: Optional[NodeType] = None) -> List[NodeDefinition]:
        """Search for nodes matching the query with optional filters."""
        results = self.search_index.search(query)
        
        # Apply filters
        if category:
            results = [node for node in results if node.category == category]
        
        if node_type:
            results = [node for node in results if node.node_type == node_type]
        
        return results
    
    def get_categories(self) -> List[Category]:
        """Get all categories."""
        return list(self.categories.values())
    
    def get_category_nodes(self, category_name: str) -> List[NodeDefinition]:
        """Get all nodes in a specific category."""
        if category_name in self.categories:
            return self.categories[category_name].get_all_nodes()
        return []
    
    def create_custom_node(self, code_snippet: str, name: str = "custom", 
                          description: str = "", validate: bool = True) -> Dict[str, Any]:
        """Create a custom node from a code snippet."""
        result = {
            'success': False,
            'node_definition': None,
            'validation_result': None,
            'errors': [],
            'warnings': []
        }
        
        # Validate the code snippet if requested
        if validate:
            validator = CustomComponentValidator()
            validation_result = validator.validate_code_snippet(code_snippet)
            result['validation_result'] = validation_result
            
            if not validation_result['valid']:
                result['errors'] = validation_result['errors']
                result['warnings'] = validation_result['warnings']
                return result
            
            # Generate interface specification
            interface_spec = validator.generate_interface_spec(validation_result)
            
            # Use validation results to enhance the node
            if validation_result['classes']:
                main_class = validation_result['classes'][0]
                if not name or name == "custom":
                    name = main_class['name']
                if not description:
                    description = main_class.get('docstring', f"Custom class: {main_class['name']}")
            elif validation_result['functions']:
                # Only use function name if there are no classes
                main_func = validation_result['functions'][0]
                if not name or name == "custom":
                    name = main_func['name']
                if not description:
                    description = main_func.get('docstring', f"Custom function: {main_func['name']}")
        else:
            # Create default interface spec
            interface_spec = {
                'inputs': [{'name': 'input', 'type': object, 'required': False, 'description': 'Input data'}],
                'outputs': [{'name': 'output', 'type': object, 'description': 'Output data'}],
                'parameters': {},
                'node_type': NodeType.CUSTOM
            }
        
        # Create the node definition
        node_def = NodeDefinition(
            name=name,
            node_type=interface_spec['node_type'],
            description=description or f"Custom node: {name}",
            icon="code",
            category="Custom"
        )
        
        # Set code snippet parameter
        node_def.set_parameter('code_snippet', code_snippet)
        node_def.add_tag('custom').add_tag('user-defined')
        
        # Add inputs from interface spec
        for input_spec in interface_spec['inputs']:
            node_def.add_input(
                input_spec['name'],
                input_spec['type'],
                input_spec.get('required', False),
                input_spec.get('default', None),
                input_spec.get('description', '')
            )
        
        # Add outputs from interface spec
        for output_spec in interface_spec['outputs']:
            node_def.add_output(
                output_spec['name'],
                output_spec['type'],
                output_spec.get('description', '')
            )
        
        # Set additional parameters
        for key, value in interface_spec['parameters'].items():
            node_def.set_parameter(key, value)
        
        # Add validation metadata
        if validate and result['validation_result']:
            node_def.metadata['validation'] = {
                'functions': result['validation_result']['functions'],
                'classes': result['validation_result']['classes'],
                'imports': result['validation_result']['imports'],
                'warnings': result['validation_result']['warnings']
            }
        
        # Add to custom category
        if "Custom" not in self.categories:
            custom_category = Category("Custom", "User-defined custom nodes", "user")
            self.add_category(custom_category)
        
        self.categories["Custom"].add_node(node_def)
        self.search_index.add_node(node_def)
        
        result['success'] = True
        result['node_definition'] = node_def
        result['warnings'] = result.get('validation_result', {}).get('warnings', [])
        
        return result
    
    def validate_custom_code(self, code_snippet: str) -> Dict[str, Any]:
        """Validate custom code without creating a node."""
        validator = CustomComponentValidator()
        return validator.validate_code_snippet(code_snippet)
    
    def get_custom_nodes(self) -> List[NodeDefinition]:
        """Get all custom nodes."""
        if "Custom" in self.categories:
            return self.categories["Custom"].get_all_nodes()
        return []
    
    def remove_custom_node(self, node_name: str) -> bool:
        """Remove a custom node."""
        if "Custom" not in self.categories:
            return False
        
        category = self.categories["Custom"]
        for i, node in enumerate(category.nodes):
            if node.name == node_name:
                # Remove from category
                category.nodes.pop(i)
                
                # Remove from search index
                self.search_index.nodes = [n for n in self.search_index.nodes if n.name != node_name]
                
                return True
        
        return False
    
    def export_custom_node(self, node_name: str) -> Optional[Dict[str, Any]]:
        """Export a custom node definition for sharing."""
        custom_nodes = self.get_custom_nodes()
        
        for node in custom_nodes:
            if node.name == node_name:
                return {
                    'name': node.name,
                    'description': node.description,
                    'code_snippet': node.parameters.get('code_snippet', ''),
                    'inputs': [
                        {
                            'name': inp.name,
                            'type': inp.data_type.__name__ if hasattr(inp.data_type, '__name__') else str(inp.data_type),
                            'required': inp.required,
                            'default': inp.default_value,
                            'description': inp.description
                        }
                        for inp in node.inputs
                    ],
                    'outputs': [
                        {
                            'name': out.name,
                            'type': out.data_type.__name__ if hasattr(out.data_type, '__name__') else str(out.data_type),
                            'description': out.description
                        }
                        for out in node.outputs
                    ],
                    'metadata': node.metadata
                }
        
        return None
    
    def import_custom_node(self, node_data: Dict[str, Any]) -> Dict[str, Any]:
        """Import a custom node from exported data."""
        try:
            code_snippet = node_data.get('code_snippet', '')
            name = node_data.get('name', 'imported_custom')
            description = node_data.get('description', '')
            
            result = self.create_custom_node(code_snippet, name, description, validate=True)
            
            if result['success']:
                # Override with imported interface if provided
                node_def = result['node_definition']
                
                # Clear existing inputs/outputs
                node_def.inputs.clear()
                node_def.outputs.clear()
                
                # Add imported inputs
                for inp_data in node_data.get('inputs', []):
                    # Convert type string back to type
                    type_name = inp_data.get('type', 'object')
                    data_type = {'str': str, 'int': int, 'float': float, 'bool': bool, 'list': list, 'dict': dict}.get(type_name, object)
                    
                    node_def.add_input(
                        inp_data['name'],
                        data_type,
                        inp_data.get('required', False),
                        inp_data.get('default'),
                        inp_data.get('description', '')
                    )
                
                # Add imported outputs
                for out_data in node_data.get('outputs', []):
                    type_name = out_data.get('type', 'object')
                    data_type = {'str': str, 'int': int, 'float': float, 'bool': bool, 'list': list, 'dict': dict}.get(type_name, object)
                    
                    node_def.add_output(
                        out_data['name'],
                        data_type,
                        out_data.get('description', '')
                    )
                
                # Add imported metadata
                if 'metadata' in node_data:
                    node_def.metadata.update(node_data['metadata'])
            
            return result
            
        except Exception as e:
            return {
                'success': False,
                'errors': [f"Import failed: {e}"],
                'warnings': []
            }
    
    def get_node_count(self) -> Dict[str, int]:
        """Get count of nodes by category."""
        counts = {}
        for category_name, category in self.categories.items():
            counts[category_name] = len(category.get_all_nodes())
        return counts
    
    def export_palette(self) -> Dict[str, Any]:
        """Export the entire palette configuration."""
        return {
            'categories': {
                name: {
                    'name': cat.name,
                    'description': cat.description,
                    'icon': cat.icon,
                    'node_count': len(cat.get_all_nodes())
                }
                for name, cat in self.categories.items()
            },
            'total_nodes': len(self.search_index.nodes),
            'loaded_packages': list(self.plugin_loader.loaded_packages.keys())
        }