"""
PHP to Universal IR Parser.

This module parses PHP code and converts it to Universal Intermediate Representation.
"""

import re
from typing import Dict, List, Optional, Any
from .universal_ir import (
    UniversalProject, UniversalModule, UniversalFunction, UniversalClass,
    UniversalVariable, Parameter, TypeSignature, DataType, SemanticDescription,
    Contract, PurityLevel
)


class PHPParser:
    """Parses PHP code into Universal IR."""
    
    def __init__(self):
        self.current_module: Optional[UniversalModule] = None
        self.type_inference = PHPTypeInference()
    
    def parse_code(self, php_code: str, filename: str = "unknown.php") -> UniversalModule:
        """Parse PHP code into a Universal Module."""
        module = UniversalModule(
            name=filename.replace('.php', ''),
            source_language="php",
            source_file=filename
        )
        
        self.current_module = module
        
        # Remove PHP tags for parsing
        code = self._strip_php_tags(php_code)
        
        # Parse PHP constructs
        self._parse_namespaces(code)
        self._parse_use_statements(code)
        self._parse_interfaces(code)
        self._parse_traits(code)
        self._parse_classes(code)
        self._parse_functions(code)
        self._parse_constants(code)
        
        return module
    
    def _strip_php_tags(self, code: str) -> str:
        """Remove PHP opening and closing tags."""
        code = re.sub(r'<\?php\s*', '', code)
        code = re.sub(r'<\?\s*', '', code)
        code = re.sub(r'\?>', '', code)
        return code
    
    def _parse_namespaces(self, code: str):
        """Parse PHP namespace declarations."""
        namespace_pattern = r'namespace\s+([\w\\]+)\s*;'
        matches = re.finditer(namespace_pattern, code)
        
        for match in matches:
            namespace = match.group(1)
            if self.current_module is not None:
                # Store namespace in imports list as a marker
                self.current_module.imports.insert(0, f"namespace:{namespace}")

    def _parse_use_statements(self, code: str):
        """Parse PHP use/require/include statements."""
        if self.current_module is None:
            return
        # use Namespace\Class;  use Namespace\Class as Alias;
        use_pattern = r'^\s*(use\s+[\w\\]+(?:\s+as\s+\w+)?)\s*;'
        for m in re.finditer(use_pattern, code, re.MULTILINE):
            self.current_module.imports.append(m.group(1).strip() + ';')
        # require / require_once / include / include_once
        req_pattern = r"^\s*((?:require|include)(?:_once)?\s*(?:\(?\s*['\"][^'\"]+['\"]\s*\)?))\s*;"
        for m in re.finditer(req_pattern, code, re.MULTILINE):
            self.current_module.imports.append(m.group(1).strip() + ';')
    
    def _parse_interfaces(self, code: str):
        """Parse PHP interface declarations."""
        interface_pattern = r'interface\s+(\w+)(?:\s+extends\s+([\w,\s\\]+))?\s*\{([^}]*(?:\{[^}]*\}[^}]*)*)\}'
        interfaces = re.finditer(interface_pattern, code, re.MULTILINE | re.DOTALL)
        
        for match in interfaces:
            interface_name = match.group(1)
            extends = match.group(2)
            body = match.group(3)
            
            # Create class to represent interface
            cls = UniversalClass(
                name=interface_name,
                source_language="php"
            )
            
            if extends:
                for ext in extends.split(','):
                    cls.base_classes.append(ext.strip())
            
            cls.implementation_hints = {'is_interface': True}
            
            # Parse interface methods (signatures only)
            self._parse_interface_methods(cls, body)
            
            if self.current_module is not None:
                self.current_module.classes.append(cls)
    
    def _parse_interface_methods(self, cls: UniversalClass, body: str):
        """Parse method signatures in an interface."""
        method_pattern = r'(?:public\s+)?(?:static\s+)?function\s+(\w+)\s*\(([^)]*)\)(?:\s*:\s*([^;]+))?;'
        methods = re.finditer(method_pattern, body)
        
        for match in methods:
            method_name = match.group(1)
            params_str = match.group(2)
            return_type_str = match.group(3)
            
            parameters = self._parse_php_parameters(params_str)
            return_type = self._parse_php_type(return_type_str) if return_type_str else TypeSignature(DataType.ANY)
            
            method = UniversalFunction(
                name=method_name,
                parameters=parameters,
                return_type=return_type,
                source_language="php",
                implementation_hints={'is_abstract': True}
            )
            
            cls.methods.append(method)
    
    def _parse_traits(self, code: str):
        """Parse PHP trait declarations."""
        trait_pattern = r'trait\s+(\w+)\s*\{([^}]*(?:\{[^}]*\}[^}]*)*)\}'
        traits = re.finditer(trait_pattern, code, re.MULTILINE | re.DOTALL)
        
        for match in traits:
            trait_name = match.group(1)
            body = match.group(2)
            
            cls = UniversalClass(
                name=trait_name,
                source_language="php"
            )
            
            cls.implementation_hints = {'is_trait': True}
            
            self._parse_class_methods(cls, body)
            self._parse_class_properties(cls, body)
            
            if self.current_module is not None:
                self.current_module.classes.append(cls)
    
    def _parse_classes(self, code: str):
        """Parse PHP class declarations."""
        class_pattern = r'(?:(abstract|final)\s+)?class\s+(\w+)(?:\s+extends\s+(\w+))?(?:\s+implements\s+([\w,\s\\]+))?\s*\{([^}]*(?:\{[^}]*\}[^}]*)*)\}'
        classes = re.finditer(class_pattern, code, re.MULTILINE | re.DOTALL)
        
        for match in classes:
            modifier = match.group(1)
            class_name = match.group(2)
            base_class = match.group(3)
            implements = match.group(4)
            body = match.group(5)
            
            cls = UniversalClass(
                name=class_name,
                source_language="php"
            )
            
            if base_class:
                cls.base_classes.append(base_class)
            
            cls.implementation_hints = {
                'is_abstract': modifier == 'abstract',
                'is_final': modifier == 'final',
                'implements': [i.strip() for i in implements.split(',')] if implements else []
            }
            
            # Parse class members
            self._parse_class_properties(cls, body)
            self._parse_class_methods(cls, body)
            self._parse_class_constants(cls, body)
            
            if self.current_module is not None:
                self.current_module.classes.append(cls)
    
    def _parse_class_properties(self, cls: UniversalClass, body: str):
        """Parse class properties."""
        prop_pattern = r'(?:(public|private|protected)\s+)?(?:(static)\s+)?(?:(readonly)\s+)?(?:(\??\w+)\s+)?\$(\w+)(?:\s*=\s*([^;]+))?;'
        props = re.finditer(prop_pattern, body)
        
        for match in props:
            visibility = match.group(1) or 'public'
            is_static = match.group(2) is not None
            is_readonly = match.group(3) is not None
            type_str = match.group(4)
            prop_name = match.group(5)
            default_value = match.group(6)
            
            prop_type = self._parse_php_type(type_str) if type_str else TypeSignature(DataType.ANY)
            
            # Store as class variable info
            # Note: PHP properties stored as implementation metadata
    
    def _parse_class_methods(self, cls: UniversalClass, body: str):
        """Parse methods within a PHP class."""
        method_pattern = r'(?:(public|private|protected)\s+)?(?:(static)\s+)?(?:(abstract)\s+)?function\s+(\w+)\s*\(([^)]*)\)(?:\s*:\s*([^{;]+))?\s*(?:\{([^}]*(?:\{[^}]*\}[^}]*)*)\}|;)'
        methods = re.finditer(method_pattern, body, re.MULTILINE | re.DOTALL)
        
        for match in methods:
            visibility = match.group(1) or 'public'
            is_static = match.group(2) is not None
            is_abstract = match.group(3) is not None
            method_name = match.group(4)
            params_str = match.group(5)
            return_type_str = match.group(6)
            method_body = match.group(7) or ""
            
            parameters = self._parse_php_parameters(params_str)
            return_type = self._parse_php_type(return_type_str) if return_type_str else self.type_inference.infer_return_type(method_body)
            
            method = UniversalFunction(
                name=method_name,
                parameters=parameters,
                return_type=return_type,
                source_language="php",
                source_code=match.group(0),
                implementation_hints={
                    'visibility': visibility,
                    'is_static': is_static,
                    'is_abstract': is_abstract,
                    'is_constructor': method_name == '__construct',
                    'is_destructor': method_name == '__destruct',
                    'is_magic': method_name.startswith('__'),
                    'control_flow': self._extract_control_flow(method_body)
                }
            )
            
            cls.methods.append(method)
    
    def _parse_class_constants(self, cls: UniversalClass, body: str):
        """Parse class constants."""
        const_pattern = r'(?:(public|private|protected)\s+)?const\s+(\w+)\s*=\s*([^;]+);'
        constants = re.finditer(const_pattern, body)
        
        for match in constants:
            visibility = match.group(1) or 'public'
            const_name = match.group(2)
            value = match.group(3).strip()
            
            # Store constant info in class hints
            if 'constants' not in cls.implementation_hints:
                cls.implementation_hints['constants'] = []
            cls.implementation_hints['constants'].append({
                'name': const_name,
                'value': value,
                'visibility': visibility
            })
    
    def _parse_functions(self, code: str):
        """Parse top-level PHP functions."""
        # Remove class/interface/trait bodies first
        code_clean = re.sub(r'(?:class|interface|trait)\s+\w+[^{]*\{[^}]*(?:\{[^}]*\}[^}]*)*\}', '', code, flags=re.MULTILINE | re.DOTALL)
        
        func_pattern = r'function\s+(\w+)\s*\(([^)]*)\)(?:\s*:\s*([^{]+))?\s*\{([^}]*(?:\{[^}]*\}[^}]*)*)\}'
        functions = re.finditer(func_pattern, code_clean, re.MULTILINE | re.DOTALL)
        
        for match in functions:
            func_name = match.group(1)
            params_str = match.group(2)
            return_type_str = match.group(3)
            func_body = match.group(4)
            
            parameters = self._parse_php_parameters(params_str)
            return_type = self._parse_php_type(return_type_str) if return_type_str else self.type_inference.infer_return_type(func_body)
            
            func = UniversalFunction(
                name=func_name,
                parameters=parameters,
                return_type=return_type,
                source_language="php",
                source_code=match.group(0),
                implementation_hints={
                    'control_flow': self._extract_control_flow(func_body)
                }
            )
            
            if self.current_module is not None:
                self.current_module.functions.append(func)
    
    def _parse_constants(self, code: str):
        """Parse PHP constant definitions."""
        const_pattern = r'(?:define\s*\(\s*[\'"](\w+)[\'"]\s*,\s*([^)]+)\)|const\s+(\w+)\s*=\s*([^;]+);)'
        constants = re.finditer(const_pattern, code)
        
        for match in constants:
            if match.group(1):
                # define() style
                const_name = match.group(1)
                value = match.group(2).strip()
            else:
                # const style
                const_name = match.group(3)
                value = match.group(4).strip()
            
            var = UniversalVariable(
                name=const_name,
                type_sig=self.type_inference.infer_type(value),
                value=value,
                is_constant=True,
                source_language="php"
            )
            
            if self.current_module is not None:
                self.current_module.variables.append(var)
    
    def _parse_php_parameters(self, params_str: str) -> List[Parameter]:
        """Parse PHP function parameters."""
        parameters = []
        if not params_str.strip():
            return parameters
        
        for param in params_str.split(','):
            param = param.strip()
            if not param:
                continue
            
            # Match: ?Type $name = default or Type $name or $name
            param_match = re.match(r'(?:(\??)(\w+)\s+)?(?:(&)?)?\$(\w+)(?:\s*=\s*(.+))?', param)
            if param_match:
                is_nullable = param_match.group(1) == '?'
                type_str = param_match.group(2)
                is_reference = param_match.group(3) is not None
                name = param_match.group(4)
                default = param_match.group(5)
                
                param_type = self._parse_php_type(type_str) if type_str else TypeSignature(DataType.ANY)
                
                parameters.append(Parameter(
                    name=name,
                    type_sig=param_type,
                    required=default is None and not is_nullable,
                    default_value=default.strip() if default else None
                ))
        
        return parameters
    
    def _parse_php_type(self, type_str: str) -> TypeSignature:
        """Parse PHP type hint into UIR TypeSignature."""
        if not type_str:
            return TypeSignature(DataType.ANY)
        
        type_str = type_str.strip().lstrip('?')
        
        type_mapping = {
            'string': DataType.STRING,
            'int': DataType.INTEGER,
            'integer': DataType.INTEGER,
            'float': DataType.FLOAT,
            'double': DataType.FLOAT,
            'bool': DataType.BOOLEAN,
            'boolean': DataType.BOOLEAN,
            'array': DataType.ARRAY,
            'object': DataType.OBJECT,
            'callable': DataType.FUNCTION,
            'void': DataType.VOID,
            'null': DataType.ANY,
            'mixed': DataType.ANY,
            'self': DataType.OBJECT,
            'static': DataType.OBJECT,
            'parent': DataType.OBJECT,
        }
        
        return TypeSignature(type_mapping.get(type_str.lower(), DataType.OBJECT))
    
    def _extract_control_flow(self, body: str) -> List[Dict[str, Any]]:
        """Extract control flow structures from function body."""
        control_flow = []
        
        if not body:
            return control_flow
        
        # Find if statements
        if_pattern = r'if\s*\([^)]+\)\s*\{'
        for match in re.finditer(if_pattern, body):
            control_flow.append({
                'kind': 'if_condition',
                'source_code': match.group(0),
                'lineno': body[:match.start()].count('\n') + 1
            })
        
        # Find loops
        loop_patterns = [
            (r'for\s*\([^)]+\)\s*\{', 'for_loop'),
            (r'foreach\s*\([^)]+\)\s*\{', 'for_loop'),
            (r'while\s*\([^)]+\)\s*\{', 'while_loop'),
            (r'do\s*\{', 'while_loop'),
        ]
        
        for pattern, kind in loop_patterns:
            for match in re.finditer(pattern, body):
                control_flow.append({
                    'kind': kind,
                    'source_code': match.group(0),
                    'lineno': body[:match.start()].count('\n') + 1
                })
        
        # Find try-catch
        try_pattern = r'try\s*\{'
        for match in re.finditer(try_pattern, body):
            control_flow.append({
                'kind': 'try_except',
                'source_code': match.group(0),
                'lineno': body[:match.start()].count('\n') + 1
            })
        
        # Find switch statements
        switch_pattern = r'switch\s*\([^)]+\)\s*\{'
        for match in re.finditer(switch_pattern, body):
            control_flow.append({
                'kind': 'switch',
                'source_code': match.group(0),
                'lineno': body[:match.start()].count('\n') + 1
            })
        
        return control_flow


class PHPTypeInference:
    """Infers types from PHP code patterns."""
    
    def infer_return_type(self, body: str) -> TypeSignature:
        """Infer return type from function body."""
        if not body:
            return TypeSignature(DataType.VOID)
        
        # Check for return statements
        return_pattern = r'return\s+([^;]+);'
        returns = re.findall(return_pattern, body)
        
        if not returns:
            return TypeSignature(DataType.VOID)
        
        last_return = returns[-1].strip()
        return self.infer_type(last_return)
    
    def infer_type(self, value: str) -> TypeSignature:
        """Infer type from a value expression."""
        if not value:
            return TypeSignature(DataType.ANY)
        
        value = value.strip()
        
        # String literals
        if value.startswith('"') or value.startswith("'"):
            return TypeSignature(DataType.STRING)
        
        # Boolean
        if value.lower() in ['true', 'false']:
            return TypeSignature(DataType.BOOLEAN)
        
        # Null
        if value.lower() == 'null':
            return TypeSignature(DataType.ANY)
        
        # Array
        if value.startswith('[') or value.startswith('array('):
            return TypeSignature(DataType.ARRAY)
        
        # Number
        if re.match(r'^-?\d+$', value):
            return TypeSignature(DataType.INTEGER)
        if re.match(r'^-?\d+\.\d+$', value):
            return TypeSignature(DataType.FLOAT)
        
        # Object instantiation
        if value.startswith('new '):
            return TypeSignature(DataType.OBJECT)
        
        return TypeSignature(DataType.ANY)
