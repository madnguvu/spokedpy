"""
TypeScript to Universal IR Parser.

This module parses TypeScript code and converts it to Universal Intermediate Representation.
TypeScript is a superset of JavaScript with static typing.
"""

import re
from typing import Dict, List, Optional, Any
from .universal_ir import (
    UniversalProject, UniversalModule, UniversalFunction, UniversalClass,
    UniversalVariable, Parameter, TypeSignature, DataType, SemanticDescription,
    Contract, PurityLevel
)


class TypeScriptParser:
    """Parses TypeScript code into Universal IR."""
    
    def __init__(self):
        self.current_module: Optional[UniversalModule] = None
        self.type_inference = TypeScriptTypeInference()
    
    def parse_code(self, ts_code: str, filename: str = "unknown.ts") -> UniversalModule:
        """Parse TypeScript code into a Universal Module."""
        # Create universal module
        module = UniversalModule(
            name=filename.replace('.ts', '').replace('.tsx', ''),
            source_language="typescript",
            source_file=filename
        )
        
        self.current_module = module
        
        # Parse using regex patterns (TypeScript extends JavaScript patterns)
        self._parse_imports(ts_code)
        self._parse_interfaces(ts_code)
        self._parse_type_aliases(ts_code)
        self._parse_functions(ts_code)
        self._parse_classes(ts_code)
        self._parse_arrow_functions(ts_code)
        self._parse_variables(ts_code)
        
        return module

    def _parse_imports(self, code: str):
        """Parse TypeScript import statements."""
        if self.current_module is None:
            return
        # Match: import X from 'Y'; import { A, B } from 'Y'; import 'Y';
        import_pattern = r'^[ \t]*(import\s+.+?[\'"][^\'"]+[\'"])\s*;?'
        for m in re.finditer(import_pattern, code, re.MULTILINE):
            stmt = m.group(1).rstrip(';').strip()
            self.current_module.imports.append(stmt + ';')
    
    def _parse_interfaces(self, code: str):
        """Parse TypeScript interface declarations."""
        interface_pattern = r'(?:export\s+)?interface\s+(\w+)(?:\s+extends\s+([\w,\s]+))?\s*\{([^}]*(?:\{[^}]*\}[^}]*)*)\}'
        interfaces = re.finditer(interface_pattern, code, re.MULTILINE | re.DOTALL)
        
        for match in interfaces:
            interface_name = match.group(1)
            extends = match.group(2)
            body = match.group(3)
            
            if self.current_module is None:
                continue
            
            # Store interface info in imports list as metadata marker
            self.current_module.imports.append(f"interface:{interface_name}")
    
    def _parse_type_aliases(self, code: str):
        """Parse TypeScript type alias declarations."""
        type_pattern = r'(?:export\s+)?type\s+(\w+)(?:<[^>]+>)?\s*=\s*([^;]+);'
        types = re.finditer(type_pattern, code, re.MULTILINE)
        
        for match in types:
            type_name = match.group(1)
            type_def = match.group(2).strip()
            
            if self.current_module is None:
                continue
            
            # Store type alias info in imports list as metadata marker
            self.current_module.imports.append(f"type:{type_name}")
    
    def _parse_functions(self, code: str):
        """Parse TypeScript function declarations."""
        # Match: function name<T>(params): ReturnType { body }
        func_pattern = r'(?:export\s+)?(?:async\s+)?function\s+(\w+)(?:<[^>]+>)?\s*\(([^)]*)\)(?:\s*:\s*([^{]+))?\s*\{([^}]*(?:\{[^}]*\}[^}]*)*)\}'
        functions = re.finditer(func_pattern, code, re.MULTILINE | re.DOTALL)
        
        for match in functions:
            is_async = 'async' in match.group(0)
            is_export = 'export' in match.group(0)
            func_name = match.group(1)
            params_str = match.group(2)
            return_type_str = match.group(3)
            body = match.group(4)
            
            # Parse typed parameters
            parameters = self._parse_typed_parameters(params_str)
            
            # Parse return type
            return_type = self._parse_typescript_type(return_type_str) if return_type_str else self.type_inference.infer_return_type(body)
            
            # Create universal function
            func = UniversalFunction(
                name=func_name,
                parameters=parameters,
                return_type=return_type,
                source_language="typescript",
                source_code=match.group(0),
                implementation_hints={
                    'is_async': is_async,
                    'is_export': is_export,
                    'body_complexity': len(body.split('\n')),
                    'control_flow': self._extract_control_flow(body)
                }
            )
            
            if self.current_module is not None:
                self.current_module.functions.append(func)
    
    def _parse_classes(self, code: str):
        """Parse TypeScript class declarations."""
        class_pattern = r'(?:export\s+)?(?:abstract\s+)?class\s+(\w+)(?:<[^>]+>)?(?:\s+extends\s+(\w+)(?:<[^>]+>)?)?(?:\s+implements\s+([\w,\s<>]+))?\s*\{([^}]*(?:\{[^}]*\}[^}]*)*)\}'
        classes = re.finditer(class_pattern, code, re.MULTILINE | re.DOTALL)
        
        for match in classes:
            is_abstract = 'abstract' in match.group(0)
            class_name = match.group(1)
            base_class = match.group(2)
            implements = match.group(3)
            body = match.group(4)
            
            # Create class
            cls = UniversalClass(
                name=class_name,
                source_language="typescript"
            )
            
            if base_class:
                cls.base_classes.append(base_class)
            
            # Parse class methods
            self._parse_class_methods(cls, body)
            
            # Parse class properties
            self._parse_class_properties(cls, body)
            
            cls.implementation_hints = {
                'is_abstract': is_abstract,
                'implements': implements.split(',') if implements else []
            }
            
            if self.current_module is not None:
                self.current_module.classes.append(cls)
    
    def _parse_class_methods(self, cls: UniversalClass, body: str):
        """Parse methods within a class body."""
        # Match: [public|private|protected] [async] methodName(params): ReturnType { body }
        method_pattern = r'(?:(public|private|protected)\s+)?(?:(static)\s+)?(?:(async)\s+)?(\w+)(?:<[^>]+>)?\s*\(([^)]*)\)(?:\s*:\s*([^{]+))?\s*\{([^}]*(?:\{[^}]*\}[^}]*)*)\}'
        methods = re.finditer(method_pattern, body, re.MULTILINE | re.DOTALL)
        
        for match in methods:
            visibility = match.group(1) or 'public'
            is_static = match.group(2) is not None
            is_async = match.group(3) is not None
            method_name = match.group(4)
            params_str = match.group(5)
            return_type_str = match.group(6)
            method_body = match.group(7)
            
            parameters = self._parse_typed_parameters(params_str)
            return_type = self._parse_typescript_type(return_type_str) if return_type_str else TypeSignature(DataType.ANY)
            
            method = UniversalFunction(
                name=method_name,
                parameters=parameters,
                return_type=return_type,
                source_language="typescript",
                source_code=match.group(0),
                implementation_hints={
                    'visibility': visibility,
                    'is_static': is_static,
                    'is_async': is_async,
                    'is_constructor': method_name == 'constructor',
                    'control_flow': self._extract_control_flow(method_body)
                }
            )
            
            cls.methods.append(method)
    
    def _parse_class_properties(self, cls: UniversalClass, body: str):
        """Parse class properties."""
        # Match: [public|private|protected] [readonly] propertyName: Type = value;
        prop_pattern = r'(?:(public|private|protected)\s+)?(?:(readonly)\s+)?(\w+)(?:\?)?(?:\s*:\s*([^=;\n]+))?(?:\s*=\s*([^;\n]+))?;'
        props = re.finditer(prop_pattern, body, re.MULTILINE)
        
        for match in props:
            visibility = match.group(1) or 'public'
            is_readonly = match.group(2) is not None
            prop_name = match.group(3)
            type_str = match.group(4)
            default_value = match.group(5)
            
            # Skip if this looks like a method
            if '(' in (type_str or '') or prop_name in ['constructor', 'async', 'function']:
                continue
            
            prop_type = self._parse_typescript_type(type_str) if type_str else TypeSignature(DataType.ANY)
            
            # Create Parameter for property (since cls.properties expects Parameter)
            prop = Parameter(
                name=prop_name,
                type_sig=prop_type,
                default_value=default_value.strip() if default_value else None,
                required=not is_readonly and default_value is None
            )
            
            cls.properties.append(prop)
    
    def _parse_arrow_functions(self, code: str):
        """Parse TypeScript arrow functions."""
        # Match: const name = (params): ReturnType => { body } OR expression
        arrow_pattern = r'(?:export\s+)?(?:const|let|var)\s+(\w+)(?:\s*:\s*[^=]+)?\s*=\s*(?:async\s+)?\(([^)]*)\)(?:\s*:\s*([^=]+))?\s*=>\s*(?:\{([^}]*(?:\{[^}]*\}[^}]*)*)\}|([^;\n]+))'
        arrow_functions = re.finditer(arrow_pattern, code, re.MULTILINE | re.DOTALL)
        
        for match in arrow_functions:
            is_async = 'async' in match.group(0)
            func_name = match.group(1)
            params_str = match.group(2)
            return_type_str = match.group(3)
            body = match.group(4) or match.group(5)
            
            parameters = self._parse_typed_parameters(params_str)
            return_type = self._parse_typescript_type(return_type_str) if return_type_str else self.type_inference.infer_return_type(body)
            
            func = UniversalFunction(
                name=func_name,
                parameters=parameters,
                return_type=return_type,
                source_language="typescript",
                source_code=match.group(0),
                implementation_hints={
                    'is_async': is_async,
                    'is_arrow_function': True,
                    'body_complexity': len(body.split('\n')) if body else 1,
                    'control_flow': self._extract_control_flow(body) if body else []
                }
            )
            
            if self.current_module is not None:
                self.current_module.functions.append(func)
    
    def _parse_variables(self, code: str):
        """Parse TypeScript variable declarations."""
        var_pattern = r'(?:export\s+)?(?:const|let|var)\s+(\w+)(?:\s*:\s*([^=;\n]+))?\s*=\s*([^;\n]+);'
        variables = re.finditer(var_pattern, code, re.MULTILINE)
        
        for match in variables:
            var_name = match.group(1)
            type_str = match.group(2)
            value = match.group(3)
            
            # Skip if this is a function (arrow function already parsed)
            if '=>' in value or 'function' in value:
                continue
            
            var_type = self._parse_typescript_type(type_str) if type_str else TypeSignature(DataType.ANY)
            is_const = 'const' in match.group(0)
            
            var = UniversalVariable(
                name=var_name,
                type_sig=var_type,
                value=value.strip(),
                is_constant=is_const,
                source_language="typescript"
            )
            
            if self.current_module is not None:
                self.current_module.variables.append(var)
    
    def _parse_typed_parameters(self, params_str: str) -> List[Parameter]:
        """Parse TypeScript typed parameters."""
        parameters = []
        if not params_str.strip():
            return parameters
        
        # Split by comma, but respect generics
        params = self._smart_split(params_str, ',')
        
        for param in params:
            param = param.strip()
            if not param:
                continue
            
            # Handle destructuring - simplified
            if param.startswith('{') or param.startswith('['):
                parameters.append(Parameter(
                    name='destructured',
                    type_sig=TypeSignature(DataType.OBJECT),
                    required=True
                ))
                continue
            
            # Match: name?: Type = default
            param_match = re.match(r'(\w+)(\?)?(?:\s*:\s*([^=]+))?(?:\s*=\s*(.+))?', param)
            if param_match:
                name = param_match.group(1)
                is_optional = param_match.group(2) is not None
                type_str = param_match.group(3)
                default = param_match.group(4)
                
                param_type = self._parse_typescript_type(type_str) if type_str else TypeSignature(DataType.ANY)
                
                parameters.append(Parameter(
                    name=name,
                    type_sig=param_type,
                    required=not is_optional and default is None,
                    default_value=default.strip() if default else None
                ))
        
        return parameters
    
    def _parse_typescript_type(self, type_str: str) -> TypeSignature:
        """Parse TypeScript type annotation into UIR TypeSignature."""
        if not type_str:
            return TypeSignature(DataType.ANY)
        
        type_str = type_str.strip()
        
        # Handle common TypeScript types
        type_mapping = {
            'string': DataType.STRING,
            'number': DataType.FLOAT,
            'boolean': DataType.BOOLEAN,
            'void': DataType.VOID,
            'any': DataType.ANY,
            'unknown': DataType.ANY,
            'never': DataType.VOID,
            'null': DataType.ANY,
            'undefined': DataType.ANY,
            'object': DataType.OBJECT,
        }
        
        # Check for array types
        if type_str.endswith('[]'):
            return TypeSignature(DataType.ARRAY)
        if type_str.startswith('Array<'):
            return TypeSignature(DataType.ARRAY)
        
        # Check for function types
        if '=>' in type_str or type_str.startswith('Function'):
            return TypeSignature(DataType.FUNCTION)
        
        # Check for Promise types
        if type_str.startswith('Promise<'):
            inner = type_str[8:-1] if type_str.endswith('>') else type_str[8:]
            inner_type = self._parse_typescript_type(inner)
            # Return the inner type (Promise unwrapped)
            return inner_type
        
        # Direct mapping
        base_type = type_str.split('<')[0].split('|')[0].strip().lower()
        return TypeSignature(type_mapping.get(base_type, DataType.OBJECT))
    
    def _smart_split(self, s: str, delimiter: str) -> List[str]:
        """Split string respecting brackets."""
        result = []
        current = []
        depth = 0
        
        for char in s:
            if char in '<([{':
                depth += 1
            elif char in '>)]}':
                depth -= 1
            
            if char == delimiter and depth == 0:
                result.append(''.join(current).strip())
                current = []
            else:
                current.append(char)
        
        if current:
            result.append(''.join(current).strip())
        
        return result
    
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
        
        # Find for loops
        for_pattern = r'for\s*\([^)]+\)\s*\{'
        for match in re.finditer(for_pattern, body):
            control_flow.append({
                'kind': 'for_loop',
                'source_code': match.group(0),
                'lineno': body[:match.start()].count('\n') + 1
            })
        
        # Find while loops
        while_pattern = r'while\s*\([^)]+\)\s*\{'
        for match in re.finditer(while_pattern, body):
            control_flow.append({
                'kind': 'while_loop',
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
        
        return control_flow


class TypeScriptTypeInference:
    """Infers types from TypeScript code patterns."""
    
    def infer_return_type(self, body: str) -> TypeSignature:
        """Infer return type from function body."""
        if not body:
            return TypeSignature(DataType.VOID)
        
        body_lower = body.lower()
        
        # Check for explicit returns
        if 'return ' not in body_lower:
            return TypeSignature(DataType.VOID)
        
        # Find return statements
        return_pattern = r'return\s+([^;]+)'
        returns = re.findall(return_pattern, body)
        
        if not returns:
            return TypeSignature(DataType.VOID)
        
        last_return = returns[-1].strip()
        
        # Infer type from return value
        if last_return.startswith('"') or last_return.startswith("'") or last_return.startswith('`'):
            return TypeSignature(DataType.STRING)
        if last_return in ['true', 'false']:
            return TypeSignature(DataType.BOOLEAN)
        if last_return.startswith('['):
            return TypeSignature(DataType.ARRAY)
        if last_return.startswith('{'):
            return TypeSignature(DataType.OBJECT)
        if re.match(r'^-?\d+(\.\d+)?$', last_return):
            return TypeSignature(DataType.FLOAT)
        if 'await' in last_return:
            return TypeSignature(DataType.ANY)
        
        return TypeSignature(DataType.ANY)
