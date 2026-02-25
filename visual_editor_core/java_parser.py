"""
Java to Universal IR Parser.

This module parses Java code and converts it to Universal Intermediate Representation.
"""

import re
from typing import Dict, List, Optional, Any
from .universal_ir import (
    UniversalProject, UniversalModule, UniversalFunction, UniversalClass,
    UniversalVariable, Parameter, TypeSignature, DataType, SemanticDescription,
    Contract, PurityLevel
)


class JavaParser:
    """Parses Java code into Universal IR."""
    
    def __init__(self):
        self.current_module: Optional[UniversalModule] = None
        self.type_inference = JavaTypeInference()
        # Collect language-specific metadata here
        self.implementation_hints: Dict[str, Any] = {}
    
    def parse_code(self, java_code: str, filename: str = "Unknown.java") -> UniversalModule:
        """Parse Java code into a Universal Module."""
        # reset hints for each parse
        self.implementation_hints = {}

        module = UniversalModule(
            name=filename.replace('.java', ''),
            source_language="java",
            source_file=filename,
        )

        self.current_module = module
        
        # Parse Java constructs
        self._parse_package(java_code)
        self._parse_imports(java_code)
        self._parse_interfaces(java_code)
        self._parse_classes(java_code)

        return module

    def _parse_package(self, code: str) -> None:
        """Extract package name and store in implementation_hints if present."""
        package_pattern = r'^\s*package\s+([\w\.]+)\s*;'
        match = re.search(package_pattern, code, re.MULTILINE)
        if match:
            self.implementation_hints["java_package"] = match.group(1)

    def _parse_imports(self, code: str) -> None:
        """Extract import statements and store in module.imports and implementation_hints."""
        import_pattern = r'^\s*import\s+([\w\.\*]+)\s*;'
        imports = re.findall(import_pattern, code, re.MULTILINE)
        if imports:
            self.implementation_hints["external_libraries"] = imports
            # Also store in module.imports for the dependency strategy pipeline
            if self.current_module is not None:
                for imp in imports:
                    self.current_module.imports.append(f"import {imp};")

    def _parse_interfaces(self, code: str):
        """Parse Java interface declarations."""
        interface_pattern = r'(?:public\s+)?interface\s+(\w+)(?:<[^>]+>)?(?:\s+extends\s+([\w,\s<>]+))?\s*\{([^}]*(?:\{[^}]*\}[^}]*)*)\}'
        interfaces = re.finditer(interface_pattern, code, re.MULTILINE | re.DOTALL)
        
        for match in interfaces:
            interface_name = match.group(1)
            extends = match.group(2)
            body = match.group(3)
            
            cls = UniversalClass(
                name=interface_name,
                source_language="java"
            )
            
            if extends:
                for ext in extends.split(','):
                    cls.base_classes.append(ext.strip().split('<')[0])
            
            cls.implementation_hints = {'is_interface': True}
            
            # Parse interface methods
            self._parse_interface_methods(cls, body)
            
            if self.current_module is not None and hasattr(self.current_module, "classes"):
                self.current_module.classes.append(cls)
    
    def _parse_interface_methods(self, cls: UniversalClass, body: str):
        """Parse method signatures in an interface."""
        method_pattern = r'(?:default\s+)?(\w+(?:<[^>]+>)?)\s+(\w+)\s*\(([^)]*)\)(?:\s+throws\s+[\w,\s]+)?;'
        methods = re.finditer(method_pattern, body)
        
        for match in methods:
            return_type_str = match.group(1)
            method_name = match.group(2)
            params_str = match.group(3)
            
            parameters = self._parse_java_parameters(params_str)
            return_type = self._parse_java_type(return_type_str)
            
            method = UniversalFunction(
                name=method_name,
                parameters=parameters,
                return_type=return_type,
                source_language="java",
                implementation_hints={'is_abstract': True}
            )
            
            cls.methods.append(method)
    
    def _parse_classes(self, code: str):
        """Parse Java class declarations."""
        class_pattern = r'(?:(public|private|protected)\s+)?(?:(abstract|final)\s+)?class\s+(\w+)(?:<[^>]+>)?(?:\s+extends\s+(\w+)(?:<[^>]+>)?)?(?:\s+implements\s+([\w,\s<>]+))?\s*\{([^}]*(?:\{[^}]*\}[^}]*)*)\}'
        classes = re.finditer(class_pattern, code, re.MULTILINE | re.DOTALL)
        
        for match in classes:
            visibility = match.group(1) or 'package'
            modifier = match.group(2)
            class_name = match.group(3)
            extends = match.group(4)
            implements = match.group(5)
            body = match.group(6)
            
            cls = UniversalClass(
                name=class_name,
                source_language="java"
            )
            
            if extends:
                cls.base_classes.append(extends)
            
            cls.implementation_hints = {
                'visibility': visibility,
                'is_abstract': modifier == 'abstract',
                'is_final': modifier == 'final',
                'implements': [i.strip().split('<')[0] for i in implements.split(',')] if implements else []
            }
            
            # Parse class members
            self._parse_class_fields(cls, body)
            self._parse_class_methods(cls, body)
            
            if self.current_module is not None and hasattr(self.current_module, "classes"):
                self.current_module.classes.append(cls)
    
    def _parse_class_fields(self, cls: UniversalClass, body: str):
        """Parse class field declarations."""
        field_pattern = r'(?:(public|private|protected)\s+)?(?:(static)\s+)?(?:(final)\s+)?(\w+(?:<[^>]+>)?)\s+(\w+)(?:\s*=\s*([^;]+))?;'
        fields = re.finditer(field_pattern, body)
        
        for match in fields:
            visibility = match.group(1) or 'package'
            is_static = match.group(2) is not None
            is_final = match.group(3) is not None
            type_str = match.group(4)
            field_name = match.group(5)
            default_value = match.group(6)
            
            # Skip if this looks like a method
            if '(' in type_str:
                continue
    
    def _parse_class_methods(self, cls: UniversalClass, body: str):
        """Parse methods within a Java class."""
        method_pattern = r'(?:(public|private|protected)\s+)?(?:(static)\s+)?(?:(abstract|final|synchronized)\s+)?(?:(\w+(?:<[^>]+>)?)\s+)?(\w+)\s*\(([^)]*)\)(?:\s+throws\s+([\w,\s]+))?\s*(?:\{([^}]*(?:\{[^}]*\}[^}]*)*)\}|;)'
        methods = re.finditer(method_pattern, body, re.MULTILINE | re.DOTALL)
        
        for match in methods:
            visibility = match.group(1) or 'package'
            is_static = match.group(2) is not None
            modifier = match.group(3)
            return_type_str = match.group(4)
            method_name = match.group(5)
            params_str = match.group(6)
            throws = match.group(7)
            method_body = match.group(8) or ""
            
            # Skip field declarations that matched
            if return_type_str is None and method_name != cls.name:
                continue
            
            parameters = self._parse_java_parameters(params_str)
            
            # Constructor has no return type
            if method_name == cls.name:
                return_type = TypeSignature(DataType.VOID)
                is_constructor = True
            else:
                return_type = self._parse_java_type(return_type_str) if return_type_str else TypeSignature(DataType.VOID)
                is_constructor = False
            
            method = UniversalFunction(
                name=method_name,
                parameters=parameters,
                return_type=return_type,
                source_language="java",
                source_code=match.group(0),
                implementation_hints={
                    'visibility': visibility,
                    'is_static': is_static,
                    'is_abstract': modifier == 'abstract',
                    'is_final': modifier == 'final',
                    'is_synchronized': modifier == 'synchronized',
                    'is_constructor': is_constructor,
                    'throws': [t.strip() for t in throws.split(',')] if throws else [],
                    'control_flow': self._extract_control_flow(method_body)
                }
            )
            
            cls.methods.append(method)
    
    def _parse_enums(self, code: str):
        """Parse Java enum declarations."""
        enum_pattern = r'(?:public\s+)?enum\s+(\w+)(?:\s+implements\s+([\w,\s]+))?\s*\{([^}]*(?:\{[^}]*\}[^}]*)*)\}'
        enums = re.finditer(enum_pattern, code, re.MULTILINE | re.DOTALL)
        
        for match in enums:
            enum_name = match.group(1)
            implements = match.group(2)
            body = match.group(3)
            
            cls = UniversalClass(
                name=enum_name,
                source_language="java"
            )
            cls.implementation_hints = {
                'is_enum': True,
                'implements': [i.strip() for i in implements.split(',')] if implements else []
            }
            
            if self.current_module is not None and hasattr(self.current_module, "classes"):
                self.current_module.classes.append(cls)
    
    def _parse_java_parameters(self, params_str: str) -> List[Parameter]:
        """Parse Java method parameters."""
        parameters = []
        if not params_str.strip():
            return parameters
        
        # Handle varargs and generics
        params = self._smart_split(params_str, ',')
        
        for param in params:
            param = param.strip()
            if not param:
                continue
            
            # Handle annotations
            param = re.sub(r'@\w+(?:\([^)]*\))?\s*', '', param)
            
            # Handle final modifier
            param = param.replace('final ', '')
            
            # Handle varargs
            is_varargs = '...' in param
            param = param.replace('...', '')
            
            # Match: Type name
            parts = param.strip().split()
            if len(parts) >= 2:
                type_str = ' '.join(parts[:-1])
                name = parts[-1]
                
                param_type = self._parse_java_type(type_str)
                
                p = Parameter(
                    name=name,
                    type_sig=param_type,
                    required=True
                )
                parameters.append(p)
        
        return parameters
    
    def _parse_java_type(self, type_str: str) -> TypeSignature:
        """Parse Java type into UIR TypeSignature."""
        if not type_str:
            return TypeSignature(DataType.ANY)
        
        type_str = type_str.strip()
        
        # Handle arrays
        if type_str.endswith('[]'):
            return TypeSignature(DataType.ARRAY)
        
        # Handle generics - extract base type
        base_type = type_str.split('<')[0].strip()
        
        type_mapping = {
            'void': DataType.VOID,
            'boolean': DataType.BOOLEAN,
            'Boolean': DataType.BOOLEAN,
            'byte': DataType.INTEGER,
            'Byte': DataType.INTEGER,
            'short': DataType.INTEGER,
            'Short': DataType.INTEGER,
            'int': DataType.INTEGER,
            'Integer': DataType.INTEGER,
            'long': DataType.INTEGER,
            'Long': DataType.INTEGER,
            'float': DataType.FLOAT,
            'Float': DataType.FLOAT,
            'double': DataType.FLOAT,
            'Double': DataType.FLOAT,
            'char': DataType.STRING,
            'Character': DataType.STRING,
            'String': DataType.STRING,
            'Object': DataType.OBJECT,
            'List': DataType.ARRAY,
            'ArrayList': DataType.ARRAY,
            'Set': DataType.ARRAY,
            'HashSet': DataType.ARRAY,
            'Map': DataType.OBJECT,
            'HashMap': DataType.OBJECT,
        }
        
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
        """Extract control flow structures from method body."""
        control_flow = []
        
        if not body:
            return control_flow
        
        patterns = [
            (r'if\s*\([^)]+\)\s*\{', 'if_condition'),
            (r'for\s*\([^)]+\)\s*\{', 'for_loop'),
            (r'while\s*\([^)]+\)\s*\{', 'while_loop'),
            (r'do\s*\{', 'while_loop'),
            (r'try\s*\{', 'try_except'),
            (r'switch\s*\([^)]+\)\s*\{', 'switch'),
        ]
        
        for pattern, kind in patterns:
            for match in re.finditer(pattern, body):
                control_flow.append({
                    'kind': kind,
                    'source_code': match.group(0),
                    'lineno': body[:match.start()].count('\n') + 1
                })
        
        return control_flow


class JavaTypeInference:
    """Infers types from Java code patterns."""
    
    def infer_return_type(self, body: str) -> TypeSignature:
        """Infer return type from method body."""
        if not body:
            return TypeSignature(DataType.VOID)
        
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
        
        if value.startswith('"'):
            return TypeSignature(DataType.STRING)
        if value in ['true', 'false']:
            return TypeSignature(DataType.BOOLEAN)
        if value == 'null':
            return TypeSignature(DataType.ANY)
        if re.match(r'^-?\d+[lL]?$', value):
            return TypeSignature(DataType.INTEGER)
        if re.match(r'^-?\d+\.\d*[fFdD]?$', value):
            return TypeSignature(DataType.FLOAT)
        if value.startswith('new '):
            return TypeSignature(DataType.OBJECT)
        
        return TypeSignature(DataType.ANY)
