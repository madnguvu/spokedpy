"""
Go to Universal IR Parser.

This module parses Go code and converts it to Universal Intermediate Representation.
"""

import re
from typing import Dict, List, Optional, Any
from .universal_ir import (
    UniversalProject, UniversalModule, UniversalFunction, UniversalClass,
    UniversalVariable, Parameter, TypeSignature, DataType, SemanticDescription,
    Contract, PurityLevel
)


class GoParser:
    """Parses Go code into Universal IR."""
    
    def __init__(self):
        self.current_module = None
        self.type_inference = GoTypeInference()
    
    def parse_code(self, go_code: str, filename: str = "main.go") -> UniversalModule:
        """Parse Go code into a Universal Module."""
        module = UniversalModule(
            name=filename.replace('.go', ''),
            source_language="go",
            source_file=filename
        )
        
        self.current_module = module
        
        # Parse Go constructs
        self._parse_package(go_code)
        self._parse_imports(go_code)
        self._parse_interfaces(go_code)
        self._parse_structs(go_code)
        self._parse_functions(go_code)
        self._parse_methods(go_code)
        self._parse_constants(go_code)
        self._parse_variables(go_code)
        
        return module
        
    def _parse_package(self, code: str):
        """Parse package declaration."""
        package_pattern = r'package\s+(\w+)'
        match = re.search(package_pattern, code)
        if match and self.current_module is not None:
            # store go package name in metadata to avoid dynamic attributes
            module_metadata = getattr(self.current_module, "metadata", None)
            if module_metadata is None:
                module_metadata = {}
                setattr(self.current_module, "metadata", module_metadata)
            module_metadata["go_package"] = match.group(1)
    
    def _parse_imports(self, code: str):
        """Parse import statements."""
        # Single import
        single_pattern = r'import\s+"([^"]+)"'
        # Multi import
        multi_pattern = r'import\s*\(([^)]+)\)'
        
        imports = re.findall(single_pattern, code)
        
        multi_match = re.search(multi_pattern, code, re.DOTALL)
        if multi_match:
            import_block = multi_match.group(1)
            imports.extend(re.findall(r'"([^"]+)"', import_block))

        # Store all imports in module.imports
        if imports and self.current_module is not None:
            for imp in imports:
                self.current_module.imports.append(f'import "{imp}"')
    
    def _parse_interfaces(self, code: str):
        """Parse Go interface declarations."""
        interface_pattern = r'type\s+(\w+)\s+interface\s*\{([^}]*)\}'
        interfaces = re.finditer(interface_pattern, code, re.MULTILINE | re.DOTALL)
        
        for match in interfaces:
            interface_name = match.group(1)
            body = match.group(2)
            
            cls = UniversalClass(
                name=interface_name,
                source_language="go"
            )
            
            cls.implementation_hints = {'is_interface': True}
            
            # Parse interface methods
            method_pattern = r'(\w+)\s*\(([^)]*)\)\s*(?:\(([^)]+)\)|(\w+))?'
            methods = re.finditer(method_pattern, body)
            
            for method_match in methods:
                method_name = method_match.group(1)
                params_str = method_match.group(2)
                returns_multi = method_match.group(3)
                returns_single = method_match.group(4)
                
                parameters = self._parse_go_parameters(params_str)
                return_type = self._parse_go_return_type(returns_multi or returns_single)
                
                method = UniversalFunction(
                    name=method_name,
                    parameters=parameters,
                    return_type=return_type,
                    source_language="go",
                    implementation_hints={'is_interface_method': True}
                )
                
                cls.methods.append(method)
            
            if self.current_module is not None:
                self.current_module.classes.append(cls)
    
    def _parse_structs(self, code: str):
        """Parse Go struct declarations."""
        struct_pattern = r'type\s+(\w+)\s+struct\s*\{([^}]*)\}'
        structs = re.finditer(struct_pattern, code, re.MULTILINE | re.DOTALL)
        for match in structs:
            struct_name = match.group(1)
            body = match.group(2)
            
            cls = UniversalClass(
                name=struct_name,
                source_language="go"
            )
            
            cls.implementation_hints = {'is_struct': True}
            
            # Parse struct fields
            field_pattern = r'(\w+)\s+(\S+)(?:\s+`[^`]+`)?'
            fields = re.finditer(field_pattern, body)
            
            for field_match in fields:
                field_name = field_match.group(1)
                field_type = field_match.group(2)
                
                # Determine if exported (starts with uppercase)
                is_exported = field_name[0].isupper() if field_name else False
            
            if self.current_module is not None:
                self.current_module.classes.append(cls)
                self.current_module.classes.append(cls)
    
    def _parse_functions(self, code: str):
        """Parse Go function declarations (not methods)."""
        # Match: func name(params) returnType { body }
        func_pattern = r'func\s+(\w+)\s*\(([^)]*)\)\s*(?:\(([^)]+)\)|(\w+))?\s*\{([^}]*(?:\{[^}]*\}[^}]*)*)\}'
        functions = re.finditer(func_pattern, code, re.MULTILINE | re.DOTALL)
        
        for match in functions:
            func_name = match.group(1)
            params_str = match.group(2)
            returns_multi = match.group(3)
            returns_single = match.group(4)
            body = match.group(5)
            
            parameters = self._parse_go_parameters(params_str)
            return_type = self._parse_go_return_type(returns_multi or returns_single)
            
            is_exported = func_name[0].isupper() if func_name else False
            
            func = UniversalFunction(
                name=func_name,
                parameters=parameters,
                return_type=return_type,
                source_language="go",
                source_code=match.group(0),
                implementation_hints={
                    'is_exported': is_exported,
                    'control_flow': self._extract_control_flow(body)
                }
            )
            
            if self.current_module is not None:
                self.current_module.functions.append(func)
    
    def _parse_methods(self, code: str):
        """Parse Go method declarations (with receiver)."""
        # Match: func (receiver Type) name(params) returnType { body }
        method_pattern = r'func\s+\((\w+)\s+\*?(\w+)\)\s+(\w+)\s*\(([^)]*)\)\s*(?:\(([^)]+)\)|(\w+))?\s*\{([^}]*(?:\{[^}]*\}[^}]*)*)\}'
        methods = re.finditer(method_pattern, code, re.MULTILINE | re.DOTALL)
        
        for match in methods:
            receiver_name = match.group(1)
            receiver_type = match.group(2)
            method_name = match.group(3)
            params_str = match.group(4)
            returns_multi = match.group(5)
            returns_single = match.group(6)
            body = match.group(7)
            
            parameters = self._parse_go_parameters(params_str)
            return_type = self._parse_go_return_type(returns_multi or returns_single)
            
            is_exported = method_name[0].isupper() if method_name else False
            method = UniversalFunction(
                name=method_name,
                parameters=parameters,
                return_type=return_type,
                source_language="go",
                source_code=match.group(0),
                implementation_hints={
                    'receiver': receiver_name,
                    'receiver_type': receiver_type,
                    'is_exported': is_exported,
                    'control_flow': self._extract_control_flow(body)
                }
            )
            # Find the struct and add method
            if self.current_module is not None:
                for cls in self.current_module.classes:
                    if cls.name == receiver_type:
                        cls.methods.append(method)
                        break
    
    def _parse_constants(self, code: str):
        """Parse Go constant declarations."""
        # Single const: const name [type] = value
        const_pattern = r'const\s+(\w+)\s*(?:(\w+)\s*)?=\s*([^\n]+)'
        constants = re.finditer(const_pattern, code)

        for match in constants:
            const_name = match.group(1)
            const_type = match.group(2)
            value = match.group(3).strip()

            var = UniversalVariable(
                name=const_name,
                type_sig=self._parse_go_type(const_type) if const_type else self.type_inference.infer_type(value),
                value=value,
                is_constant=True,
                source_language="go"
            )

            if self.current_module is not None:
                self.current_module.variables.append(var)
    
    def _parse_variables(self, code: str):
        """Parse Go variable declarations."""
        # var name type = value
        var_pattern = r'var\s+(\w+)\s+(\S+)(?:\s*=\s*([^\n]+))?'
        variables = re.finditer(var_pattern, code)

        for match in variables:
            var_name = match.group(1)
            var_type = match.group(2)
            value = match.group(3)

            var = UniversalVariable(
                name=var_name,
                type_sig=self._parse_go_type(var_type),
                value=value.strip() if value else None,
                is_constant=False,
                source_language="go"
            )

            if self.current_module is not None:
                self.current_module.variables.append(var)
    
    def _parse_go_parameters(self, params_str: str) -> List[Parameter]:
        """Parse Go function parameters."""
        parameters = []
        if not params_str.strip():
            return parameters
        
        # Go allows grouping: (a, b int, c string)
        # Split by comma but be careful with types
        parts = [p.strip() for p in params_str.split(',')]
        
        # Go often has type after name, may be shared
        last_type = None
        processed = []
        
        for part in reversed(parts):
            tokens = part.split()
            if len(tokens) >= 2:
                name = tokens[0]
                type_str = ' '.join(tokens[1:])
                last_type = type_str
                processed.append((name, type_str))
            elif len(tokens) == 1:
                # Use last known type
                processed.append((tokens[0], last_type or 'interface{}'))
        
        for name, type_str in reversed(processed):
            param_type = self._parse_go_type(type_str)
            
            # Handle variadic (...type)
            if type_str and type_str.startswith('...'):
                parameters.append(Parameter(
                    name=name,
                    type_sig=TypeSignature(DataType.ARRAY),
                    required=False
                ))
            else:
                parameters.append(Parameter(
                    name=name,
                    type_sig=param_type,
                    required=True
                ))
        
        return parameters
    
    def _parse_go_return_type(self, type_str: str) -> TypeSignature:
        """Parse Go return type."""
        if not type_str:
            return TypeSignature(DataType.VOID)
        
        # Multiple return values
        if ',' in type_str:
            return TypeSignature(DataType.ARRAY)
        
        return self._parse_go_type(type_str.strip())
    
    def _parse_go_type(self, type_str: str) -> TypeSignature:
        """Parse Go type into UIR TypeSignature."""
        if not type_str:
            return TypeSignature(DataType.ANY)
        
        type_str = type_str.strip()
        
        # Handle pointers
        if type_str.startswith('*'):
            type_str = type_str[1:]
        
        # Handle slices/arrays
        if type_str.startswith('[]'):
            return TypeSignature(DataType.ARRAY)
        
        # Handle maps
        if type_str.startswith('map['):
            return TypeSignature(DataType.OBJECT)
        
        type_mapping = {
            'bool': DataType.BOOLEAN,
            'int': DataType.INTEGER,
            'int8': DataType.INTEGER,
            'int16': DataType.INTEGER,
            'int32': DataType.INTEGER,
            'int64': DataType.INTEGER,
            'uint': DataType.INTEGER,
            'uint8': DataType.INTEGER,
            'uint16': DataType.INTEGER,
            'uint32': DataType.INTEGER,
            'uint64': DataType.INTEGER,
            'byte': DataType.INTEGER,
            'rune': DataType.INTEGER,
            'float32': DataType.FLOAT,
            'float64': DataType.FLOAT,
            'string': DataType.STRING,
            'error': DataType.OBJECT,
            'interface{}': DataType.ANY,
            'any': DataType.ANY,
        }
        
        return TypeSignature(type_mapping.get(type_str, DataType.OBJECT))
    
    def _extract_control_flow(self, body: str) -> List[Dict[str, Any]]:
        """Extract control flow structures from function body."""
        control_flow = []
        
        if not body:
            return control_flow
        
        patterns = [
            (r'if\s+[^{]+\{', 'if_condition'),
            (r'for\s+[^{]*\{', 'for_loop'),
            (r'switch\s+[^{]*\{', 'switch'),
            (r'select\s*\{', 'switch'),
        ]
        
        for pattern, kind in patterns:
            for match in re.finditer(pattern, body):
                control_flow.append({
                    'kind': kind,
                    'source_code': match.group(0),
                    'lineno': body[:match.start()].count('\n') + 1
                })
        
        return control_flow


class GoTypeInference:
    """Infers types from Go code patterns."""
    
    def infer_type(self, value: str) -> TypeSignature:
        """Infer type from a value expression."""
        if not value:
            return TypeSignature(DataType.ANY)
        
        value = value.strip()
        
        if value.startswith('"') or value.startswith('`'):
            return TypeSignature(DataType.STRING)
        if value in ['true', 'false']:
            return TypeSignature(DataType.BOOLEAN)
        if value == 'nil':
            return TypeSignature(DataType.ANY)
        if re.match(r'^-?\d+$', value):
            return TypeSignature(DataType.INTEGER)
        if re.match(r'^-?\d+\.\d+$', value):
            return TypeSignature(DataType.FLOAT)
        
        return TypeSignature(DataType.ANY)
