"""
JavaScript to Universal IR Parser.

This module parses JavaScript code and converts it to Universal Intermediate Representation.
Uses esprima-python for JavaScript AST parsing.
"""

import json
import re
from typing import Dict, List, Optional, Any
from .universal_ir import (
    UniversalProject, UniversalModule, UniversalFunction, UniversalClass,
    UniversalVariable, Parameter, TypeSignature, DataType, SemanticDescription,
    Contract, PurityLevel
)

try:
    import esprima
    ESPRIMA_AVAILABLE = True
except ImportError:
    ESPRIMA_AVAILABLE = False


class JavaScriptParser:
    """Parses JavaScript code into Universal IR."""
    
    def __init__(self):
        self.current_module = None
        self.type_inference = JavaScriptTypeInference()
    
    def parse_code(self, js_code: str, filename: str = "unknown.js") -> UniversalModule:
        """Parse JavaScript code into a Universal Module."""
        if not ESPRIMA_AVAILABLE:
            # Fallback to regex-based parsing for basic functions
            return self._parse_with_regex(js_code, filename)
        
        try:
            # Parse JavaScript AST
            ast = esprima.parseScript(js_code, {'loc': True, 'range': True})
            
            # Create universal module
            module = UniversalModule(
                name=filename.replace('.js', ''),
                source_language="javascript",
                source_file=filename
            )
            
            self.current_module = module
            
            # Process AST nodes
            for node in ast.body:
                self._process_node(node, js_code)
            
            return module
            
        except Exception as e:
            print(f"JavaScript parsing failed: {e}")
            return self._parse_with_regex(js_code, filename)
    
    def _parse_with_regex(self, js_code: str, filename: str) -> UniversalModule:
        """Fallback regex-based parser for basic JavaScript functions."""
        module = UniversalModule(
            name=filename.replace('.js', ''),
            source_language="javascript",
            source_file=filename
        )
        
        # ── Parse import / require statements ──
        # ES6 imports: import X from 'Y', import { X } from 'Y', import 'Y'
        es6_import_pattern = r'^[ \t]*(import\s+.+?[\'"][^"\']+[\'"])\s*;?'
        for m in re.finditer(es6_import_pattern, js_code, re.MULTILINE):
            stmt = m.group(1).rstrip(';').strip()
            module.imports.append(stmt + ';')

        # CommonJS require: const X = require('Y')
        cjs_pattern = r'^[ \t]*((?:const|let|var)\s+\w+\s*=\s*require\s*\([\'"][^\'"]+[\'"]\))\s*;?'
        for m in re.finditer(cjs_pattern, js_code, re.MULTILINE):
            stmt = m.group(1).rstrip(';').strip()
            module.imports.append(stmt + ';')

        # Parse function declarations
        func_pattern = r'(?:async\s+)?function\s+(\w+)\s*\(([^)]*)\)\s*\{([^}]*(?:\{[^}]*\}[^}]*)*)\}'
        functions = re.finditer(func_pattern, js_code, re.MULTILINE | re.DOTALL)
        
        for match in functions:
            is_async = 'async' in match.group(0)
            func_name = match.group(1)
            params_str = match.group(2)
            body = match.group(3)
            
            # Parse parameters
            parameters = []
            if params_str.strip():
                for param in params_str.split(','):
                    param = param.strip()
                    if '=' in param:
                        # Default parameter
                        name, default = param.split('=', 1)
                        parameters.append(Parameter(
                            name=name.strip(),
                            type_sig=TypeSignature(DataType.ANY),
                            default_value=default.strip(),
                            required=False
                        ))
                    else:
                        parameters.append(Parameter(
                            name=param,
                            type_sig=TypeSignature(DataType.ANY),
                            required=True
                        ))
            
            # Infer return type
            return_type = self.type_inference.infer_return_type(body)
            
            # Create universal function
            func = UniversalFunction(
                name=func_name,
                parameters=parameters,
                return_type=return_type,
                source_language="javascript",
                source_code=match.group(0),
                implementation_hints={
                    'is_async': is_async,
                    'body_complexity': len(body.split('\n'))
                }
            )
            
            module.functions.append(func)
        
        # Parse arrow functions
        arrow_pattern = r'(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?\(([^)]*)\)\s*=>\s*\{([^}]*(?:\{[^}]*\}[^}]*)*)\}'
        arrow_functions = re.finditer(arrow_pattern, js_code, re.MULTILINE | re.DOTALL)
        
        for match in arrow_functions:
            is_async = 'async' in match.group(0)
            func_name = match.group(1)
            params_str = match.group(2)
            body = match.group(3)
            
            # Parse parameters (same as above)
            parameters = []
            if params_str.strip():
                for param in params_str.split(','):
                    param = param.strip()
                    parameters.append(Parameter(
                        name=param,
                        type_sig=TypeSignature(DataType.ANY),
                        required=True
                    ))
            
            return_type = self.type_inference.infer_return_type(body)
            
            func = UniversalFunction(
                name=func_name,
                parameters=parameters,
                return_type=return_type,
                source_language="javascript",
                source_code=match.group(0),
                implementation_hints={
                    'is_async': is_async,
                    'is_arrow_function': True,
                    'body_complexity': len(body.split('\n'))
                }
            )
            
            module.functions.append(func)
        
        # Parse simple variable declarations
        var_pattern = r'(?:const|let|var)\s+(\w+)\s*=\s*([^;]+);'
        variables = re.finditer(var_pattern, js_code)
        
        for match in variables:
            var_name = match.group(1)
            value_str = match.group(2).strip()
            
            # Skip if it's a function (already parsed above)
            if 'function' in value_str or '=>' in value_str:
                continue
            
            # Infer type from value
            var_type = self.type_inference.infer_type_from_value(value_str)
            is_const = match.group(0).startswith('const')
            
            var = UniversalVariable(
                name=var_name,
                type_sig=var_type,
                value=value_str,
                is_constant=is_const,
                source_language="javascript"
            )
            
            module.variables.append(var)
        
        return module
    
    def _process_node(self, node: Dict, source_code: str):
        """Process an AST node and add to current module."""
        node_type = node.get('type')
        
        if node_type == 'ImportDeclaration':
            self._process_import_declaration(node, source_code)
        elif node_type == 'FunctionDeclaration':
            self._process_function_declaration(node, source_code)
        elif node_type == 'VariableDeclaration':
            self._process_variable_declaration(node, source_code)
        elif node_type == 'ClassDeclaration':
            self._process_class_declaration(node, source_code)

    def _process_import_declaration(self, node: Dict, source_code: str):
        """Process an import declaration node and store in module.imports."""
        if self.current_module is None:
            return
        # Reconstruct the import statement from the source range
        range_info = node.get('range')
        if range_info and len(range_info) == 2:
            import_text = source_code[range_info[0]:range_info[1]].strip()
            if not import_text.endswith(';'):
                import_text += ';'
            self.current_module.imports.append(import_text)
        else:
            # Fallback: build from AST structure
            source = node.get('source', {})
            source_value = source.get('value', '') if source else ''
            specifiers = node.get('specifiers', [])
            if source_value:
                if not specifiers:
                    self.current_module.imports.append(f"import '{source_value}';")
                else:
                    names = []
                    default_name = None
                    for spec in specifiers:
                        spec_type = spec.get('type', '')
                        if spec_type == 'ImportDefaultSpecifier':
                            default_name = spec.get('local', {}).get('name', '')
                        elif spec_type == 'ImportNamespaceSpecifier':
                            default_name = f"* as {spec.get('local', {}).get('name', '')}"
                        else:
                            imported = spec.get('imported', {}).get('name', '')
                            local = spec.get('local', {}).get('name', '')
                            if imported and local and imported != local:
                                names.append(f"{imported} as {local}")
                            elif imported:
                                names.append(imported)
                    parts = []
                    if default_name:
                        parts.append(default_name)
                    if names:
                        parts.append('{ ' + ', '.join(names) + ' }')
                    self.current_module.imports.append(
                        f"import {', '.join(parts)} from '{source_value}';"
                    )
    
    def _process_function_declaration(self, node: Dict, source_code: str):
        """Process a function declaration node."""
        func_name = node['id']['name']
        
        # Extract parameters
        parameters = []
        for param in node['params']:
            param_name = param['name']
            parameters.append(Parameter(
                name=param_name,
                type_sig=TypeSignature(DataType.ANY),
                required=True
            ))
        
        # Extract source code
        start = node['range'][0]
        end = node['range'][1]
        func_source = source_code[start:end]
        
        func = UniversalFunction(
            name=func_name,
            parameters=parameters,
            return_type=TypeSignature(DataType.ANY),
            source_language="javascript",
            source_code=func_source,
            implementation_hints={
                'is_async': node.get('async', False)
            }
        )
        
        self.current_module.functions.append(func)
    
    def _process_variable_declaration(self, node: Dict, source_code: str):
        """Process a variable declaration node."""
        for declaration in node['declarations']:
            var_name = declaration['id']['name']
            is_const = node['kind'] == 'const'
            
            var = UniversalVariable(
                name=var_name,
                type_sig=TypeSignature(DataType.ANY),
                is_constant=is_const,
                source_language="javascript"
            )
            
            self.current_module.variables.append(var)
    
    def _process_class_declaration(self, node: Dict, source_code: str):
        """Process a class declaration node."""
        class_name = node['id']['name']
        
        cls = UniversalClass(
            name=class_name,
            source_language="javascript"
        )
        
        # Process class methods
        for method in node['body']['body']:
            if method['type'] == 'MethodDefinition':
                method_name = method['key']['name']
                
                # Extract parameters
                parameters = []
                for param in method['value']['params']:
                    param_name = param['name']
                    parameters.append(Parameter(
                        name=param_name,
                        type_sig=TypeSignature(DataType.ANY),
                        required=True
                    ))
                
                func = UniversalFunction(
                    name=method_name,
                    parameters=parameters,
                    return_type=TypeSignature(DataType.ANY),
                    source_language="javascript",
                    implementation_hints={
                        'is_method': True,
                        'is_constructor': method_name == 'constructor'
                    }
                )
                
                cls.methods.append(func)
        
        self.current_module.classes.append(cls)


class JavaScriptTypeInference:
    """Infers types from JavaScript code patterns."""
    
    def infer_type_from_value(self, value_str: str) -> TypeSignature:
        """Infer type from a JavaScript value string."""
        value_str = value_str.strip()
        
        # Boolean
        if value_str in ['true', 'false']:
            return TypeSignature(DataType.BOOLEAN)
        
        # Number
        if re.match(r'^-?\d+$', value_str):
            return TypeSignature(DataType.INTEGER)
        if re.match(r'^-?\d*\.\d+$', value_str):
            return TypeSignature(DataType.FLOAT)
        
        # String
        if (value_str.startswith('"') and value_str.endswith('"')) or \
           (value_str.startswith("'") and value_str.endswith("'")):
            return TypeSignature(DataType.STRING)
        
        # Array
        if value_str.startswith('[') and value_str.endswith(']'):
            return TypeSignature(DataType.ARRAY)
        
        # Object
        if value_str.startswith('{') and value_str.endswith('}'):
            return TypeSignature(DataType.OBJECT)
        
        # Function
        if 'function' in value_str or '=>' in value_str:
            return TypeSignature(DataType.FUNCTION)
        
        return TypeSignature(DataType.ANY)
    
    def infer_return_type(self, function_body: str) -> TypeSignature:
        """Infer return type from function body."""
        # Look for return statements
        return_matches = re.findall(r'return\s+([^;]+);?', function_body)
        
        if not return_matches:
            return TypeSignature(DataType.VOID)
        
        # Analyze return values
        for return_val in return_matches:
            return_val = return_val.strip()
            
            # Try to infer type from return value
            inferred_type = self.infer_type_from_value(return_val)
            if inferred_type.base_type != DataType.ANY:
                return inferred_type
        
        return TypeSignature(DataType.ANY)


def parse_javascript_file(file_path: str) -> UniversalModule:
    """Parse a JavaScript file into Universal IR."""
    parser = JavaScriptParser()
    
    with open(file_path, 'r', encoding='utf-8') as f:
        js_code = f.read()
    
    return parser.parse_code(js_code, file_path)


def parse_javascript_code(js_code: str, filename: str = "code.js") -> UniversalModule:
    """Parse JavaScript code string into Universal IR."""
    parser = JavaScriptParser()
    return parser.parse_code(js_code, filename)