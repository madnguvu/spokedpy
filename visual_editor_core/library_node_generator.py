"""
Library Node Generator - Generate visual nodes from Python libraries.

This module provides functionality to:
1. Introspect installed Python packages
2. Parse library source code to extract functions, classes, and methods
3. Generate node definitions for use in the visual editor
"""

import ast
import inspect
import importlib
import importlib.util
import pkgutil
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field


@dataclass
class GeneratedNode:
    """Represents a node generated from a library."""
    id: str
    name: str
    type: str
    category: str
    description: str
    icon: str
    inputs: List[Dict[str, Any]] = field(default_factory=list)
    outputs: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    source_code: str = ""
    library_name: str = ""
    module_path: str = ""


class LibraryNodeGenerator:
    """Generate visual nodes from Python libraries."""
    
    # Icon mapping for different types of constructs
    ICON_MAP = {
        'function': 'function',
        'async_function': 'clock',
        'class': 'box',
        'method': 'code',
        'property': 'tag',
        'staticmethod': 'anchor',
        'classmethod': 'layers',
        'module': 'package',
        'constant': 'lock',
        'exception': 'alert-triangle',
        'decorator': 'at-sign',
        'context_manager': 'folder-open',
        'generator': 'repeat',
        'coroutine': 'zap',
    }
    
    # Category mapping for standard library modules
    STDLIB_CATEGORIES = {
        'os': 'System & OS',
        'sys': 'System & OS',
        'io': 'I/O Operations',
        'json': 'Data Formats',
        'csv': 'Data Formats',
        'xml': 'Data Formats',
        'html': 'Data Formats',
        'pickle': 'Data Formats',
        'sqlite3': 'Database',
        'collections': 'Data Structures',
        'itertools': 'Iteration Tools',
        'functools': 'Functional Programming',
        'operator': 'Operators',
        'math': 'Mathematics',
        'decimal': 'Mathematics',
        'fractions': 'Mathematics',
        'random': 'Mathematics',
        'statistics': 'Mathematics',
        'datetime': 'Date & Time',
        'time': 'Date & Time',
        'calendar': 'Date & Time',
        'threading': 'Concurrency',
        'multiprocessing': 'Concurrency',
        'asyncio': 'Async Programming',
        'concurrent': 'Concurrency',
        'queue': 'Concurrency',
        'socket': 'Networking',
        'http': 'Networking',
        'urllib': 'Networking',
        'email': 'Networking',
        'ftplib': 'Networking',
        'smtplib': 'Networking',
        're': 'Text Processing',
        'string': 'Text Processing',
        'textwrap': 'Text Processing',
        'difflib': 'Text Processing',
        'unicodedata': 'Text Processing',
        'pathlib': 'File System',
        'glob': 'File System',
        'shutil': 'File System',
        'tempfile': 'File System',
        'filecmp': 'File System',
        'zipfile': 'Compression',
        'tarfile': 'Compression',
        'gzip': 'Compression',
        'bz2': 'Compression',
        'lzma': 'Compression',
        'hashlib': 'Cryptography',
        'hmac': 'Cryptography',
        'secrets': 'Cryptography',
        'logging': 'Debugging & Logging',
        'traceback': 'Debugging & Logging',
        'warnings': 'Debugging & Logging',
        'pdb': 'Debugging & Logging',
        'unittest': 'Testing',
        'doctest': 'Testing',
        'typing': 'Type Hints',
        'abc': 'Abstract Base Classes',
        'dataclasses': 'Data Classes',
        'enum': 'Enumerations',
        'copy': 'Object Copying',
        'weakref': 'Weak References',
        'types': 'Type Objects',
        'contextlib': 'Context Managers',
        'argparse': 'CLI & Arguments',
        'configparser': 'Configuration',
        'struct': 'Binary Data',
        'array': 'Binary Data',
        'ctypes': 'C Interop',
        'subprocess': 'Process Management',
        'signal': 'Process Management',
    }
    
    def __init__(self):
        self.generated_nodes: Dict[str, GeneratedNode] = {}
        self.installed_packages: Dict[str, str] = {}
        self._refresh_installed_packages()
    
    def _refresh_installed_packages(self):
        """Refresh the list of installed packages."""
        try:
            result = subprocess.run(
                [sys.executable, '-m', 'pip', 'list', '--format=json'],
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode == 0:
                import json
                packages = json.loads(result.stdout)
                self.installed_packages = {
                    pkg['name'].lower(): pkg['version']
                    for pkg in packages
                }
        except Exception as e:
            print(f"Warning: Could not refresh installed packages: {e}")
    
    def get_installed_packages(self) -> List[Dict[str, str]]:
        """Get list of installed packages with their versions."""
        self._refresh_installed_packages()
        return [
            {'name': name, 'version': version}
            for name, version in sorted(self.installed_packages.items())
        ]
    
    def install_package(self, package_name: str) -> Tuple[bool, str]:
        """Install a Python package using pip."""
        try:
            result = subprocess.run(
                [sys.executable, '-m', 'pip', 'install', package_name],
                capture_output=True,
                text=True,
                timeout=120
            )
            if result.returncode == 0:
                self._refresh_installed_packages()
                return True, f"Successfully installed {package_name}"
            else:
                return False, result.stderr
        except subprocess.TimeoutExpired:
            return False, "Installation timed out"
        except Exception as e:
            return False, str(e)
    
    def generate_nodes_from_module(self, module_name: str, 
                                    include_private: bool = False,
                                    max_depth: int = 2) -> List[GeneratedNode]:
        """Generate nodes from a Python module."""
        nodes = []
        
        try:
            module = importlib.import_module(module_name)
        except ImportError as e:
            print(f"Could not import module {module_name}: {e}")
            return nodes
        
        category = self.STDLIB_CATEGORIES.get(
            module_name.split('.')[0], 
            f"Library: {module_name}"
        )
        
        # Get all public members
        for name, obj in inspect.getmembers(module):
            if not include_private and name.startswith('_'):
                continue
            
            node = self._create_node_from_object(
                name, obj, module_name, category
            )
            if node:
                nodes.append(node)
        
        return nodes
    
    def generate_nodes_from_source_file(self, file_path: str) -> List[GeneratedNode]:
        """Generate nodes from a Python source file."""
        nodes = []
        path = Path(file_path)
        
        if not path.exists() or not path.suffix == '.py':
            return nodes
        
        try:
            source_code = path.read_text(encoding='utf-8')
            tree = ast.parse(source_code)
        except Exception as e:
            print(f"Could not parse {file_path}: {e}")
            return nodes
        
        module_name = path.stem
        category = f"Custom: {module_name}"
        
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                generated = self._create_node_from_ast_function(
                    node, source_code, module_name, category, is_async=False
                )
                if generated:
                    nodes.append(generated)
            elif isinstance(node, ast.AsyncFunctionDef):
                generated = self._create_node_from_ast_function(
                    node, source_code, module_name, category, is_async=True
                )
                if generated:
                    nodes.append(generated)
            elif isinstance(node, ast.ClassDef):
                generated = self._create_node_from_ast_class(
                    node, source_code, module_name, category
                )
                if generated:
                    nodes.append(generated)
        
        return nodes
    
    def _create_node_from_object(self, name: str, obj: Any, 
                                  module_name: str, category: str) -> Optional[GeneratedNode]:
        """Create a node from a Python object."""
        node_type = 'function'
        icon = 'function'
        inputs = []
        outputs = [{'name': 'result', 'type': 'object'}]
        description = ""
        source_code = ""
        
        try:
            # Get docstring
            description = inspect.getdoc(obj) or f"{name} from {module_name}"
            if len(description) > 200:
                description = description[:200] + "..."
            
            # Try to get source code
            try:
                source_code = inspect.getsource(obj)
            except (OSError, TypeError):
                pass
            
            if inspect.isfunction(obj):
                node_type = 'function'
                icon = self.ICON_MAP['function']
                inputs = self._extract_parameters_from_callable(obj)
            elif inspect.iscoroutinefunction(obj):
                node_type = 'async_function'
                icon = self.ICON_MAP['async_function']
                inputs = self._extract_parameters_from_callable(obj)
            elif inspect.isclass(obj):
                node_type = 'class'
                icon = self.ICON_MAP['class']
                # For classes, inputs are constructor parameters
                if hasattr(obj, '__init__'):
                    inputs = self._extract_parameters_from_callable(obj.__init__)
                outputs = [{'name': 'instance', 'type': name}]
            elif inspect.ismethod(obj):
                node_type = 'method'
                icon = self.ICON_MAP['method']
                inputs = self._extract_parameters_from_callable(obj)
            elif inspect.isgeneratorfunction(obj):
                node_type = 'generator'
                icon = self.ICON_MAP['generator']
                inputs = self._extract_parameters_from_callable(obj)
                outputs = [{'name': 'generator', 'type': 'iterator'}]
            elif callable(obj):
                node_type = 'callable'
                icon = self.ICON_MAP['function']
                try:
                    inputs = self._extract_parameters_from_callable(obj)
                except Exception:
                    inputs = [{'name': 'args', 'type': 'object', 'required': False}]
            else:
                # Skip non-callable objects for now
                return None
            
        except Exception as e:
            print(f"Error creating node from {name}: {e}")
            return None
        
        node_id = f"lib_{module_name}_{name}".replace('.', '_')
        
        return GeneratedNode(
            id=node_id,
            name=f"{name}",
            type=node_type,
            category=category,
            description=description,
            icon=icon,
            inputs=inputs,
            outputs=outputs,
            metadata={
                'source_module': module_name,
                'is_library_node': True
            },
            source_code=source_code[:2000] if source_code else "",
            library_name=module_name.split('.')[0],
            module_path=module_name
        )
    
    def _extract_parameters_from_callable(self, func) -> List[Dict[str, Any]]:
        """Extract parameters from a callable."""
        inputs = []
        try:
            sig = inspect.signature(func)
            for param_name, param in sig.parameters.items():
                if param_name in ('self', 'cls'):
                    continue
                
                param_info = {
                    'name': param_name,
                    'type': 'object',
                    'required': param.default == inspect.Parameter.empty
                }
                
                # Try to get type hint
                if param.annotation != inspect.Parameter.empty:
                    param_info['type'] = self._annotation_to_string(param.annotation)
                
                # Add default value info
                if param.default != inspect.Parameter.empty:
                    param_info['default'] = repr(param.default)
                
                inputs.append(param_info)
        except (ValueError, TypeError):
            inputs = [{'name': 'args', 'type': 'object', 'required': False}]
        
        return inputs
    
    def _annotation_to_string(self, annotation) -> str:
        """Convert a type annotation to a string."""
        if hasattr(annotation, '__name__'):
            return annotation.__name__
        return str(annotation).replace('typing.', '')
    
    def _create_node_from_ast_function(self, node, 
                                        source_code: str,
                                        module_name: str,
                                        category: str,
                                        is_async: bool = False) -> GeneratedNode:
        """Create a node from an AST function definition."""
        name = node.name
        node_type = 'async_function' if is_async else 'function'
        icon = self.ICON_MAP[node_type]
        
        # Extract docstring
        description = ast.get_docstring(node) or f"{name} function"
        if len(description) > 200:
            description = description[:200] + "..."
        
        # Extract source segment
        try:
            segment = ast.get_source_segment(source_code, node)
            func_source = segment if segment else ""
        except Exception:
            func_source = ""
        
        # Extract parameters
        inputs = []
        for arg in node.args.args:
            if arg.arg in ('self', 'cls'):
                continue
            inputs.append({
                'name': arg.arg,
                'type': 'object',
                'required': True
            })
        
        node_id = f"custom_{module_name}_{name}".replace('.', '_')
        
        return GeneratedNode(
            id=node_id,
            name=name,
            type=node_type,
            category=category,
            description=description,
            icon=icon,
            inputs=inputs,
            outputs=[{'name': 'result', 'type': 'object'}],
            metadata={
                'source_module': module_name,
                'is_async': is_async,
                'lineno': node.lineno
            },
            source_code=func_source[:2000],
            library_name=module_name,
            module_path=module_name
        )
    
    def _create_node_from_ast_class(self, node: ast.ClassDef,
                                     source_code: str,
                                     module_name: str,
                                     category: str) -> GeneratedNode:
        """Create a node from an AST class definition."""
        name = node.name
        
        # Extract docstring
        description = ast.get_docstring(node) or f"{name} class"
        if len(description) > 200:
            description = description[:200] + "..."
        
        # Extract source segment
        try:
            segment = ast.get_source_segment(source_code, node)
            class_source = segment if segment else ""
        except Exception:
            class_source = ""
        
        # Find __init__ method for constructor parameters
        inputs = []
        for item in node.body:
            if isinstance(item, ast.FunctionDef) and item.name == '__init__':
                for arg in item.args.args:
                    if arg.arg == 'self':
                        continue
                    inputs.append({
                        'name': arg.arg,
                        'type': 'object',
                        'required': True
                    })
                break
        
        node_id = f"custom_{module_name}_{name}".replace('.', '_')
        
        return GeneratedNode(
            id=node_id,
            name=name,
            type='class',
            category=category,
            description=description,
            icon=self.ICON_MAP['class'],
            inputs=inputs,
            outputs=[{'name': 'instance', 'type': name}],
            metadata={
                'source_module': module_name,
                'base_classes': [
                    base.id for base in node.bases 
                    if isinstance(base, ast.Name)
                ],
                'lineno': node.lineno
            },
            source_code=class_source[:2000],
            library_name=module_name,
            module_path=module_name
        )
    
    def to_palette_format(self, nodes: List[GeneratedNode]) -> List[Dict[str, Any]]:
        """Convert generated nodes to palette format."""
        return [
            {
                'id': node.id,
                'name': node.name,
                'type': node.type,
                'category': node.category,
                'description': node.description,
                'icon': node.icon,
                'inputs': node.inputs,
                'outputs': node.outputs,
                'paradigm': 'node_based',
                'metadata': node.metadata,
                'source_code': node.source_code,
                'library_name': node.library_name,
                'module_path': node.module_path
            }
            for node in nodes
        ]


# Singleton instance
_generator = None

def get_library_node_generator() -> LibraryNodeGenerator:
    """Get the global library node generator instance."""
    global _generator
    if _generator is None:
        _generator = LibraryNodeGenerator()
    return _generator
