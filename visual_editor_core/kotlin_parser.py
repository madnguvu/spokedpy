"""
Kotlin to Universal IR Parser.

This module parses Kotlin code and converts it to Universal Intermediate Representation.
"""

import re
from typing import Dict, List, Optional, Any
from .universal_ir import (
    UniversalProject, UniversalModule, UniversalFunction, UniversalClass,
    UniversalVariable, Parameter, TypeSignature, DataType, SemanticDescription,
    Contract, PurityLevel
)


class KotlinParser:
    """Parses Kotlin code into Universal IR."""
    
    def __init__(self):
        self.current_module: Optional[UniversalModule] = None
        self.type_inference = KotlinTypeInference()
    
    def parse_code(self, kotlin_code: str, filename: str = "Main.kt") -> UniversalModule:
        """Parse Kotlin code into a Universal Module."""
        module = UniversalModule(
            name=filename.replace('.kt', ''),
            source_language="kotlin",
            source_file=filename
        )
        
        self.current_module = module
        
        # Parse Kotlin constructs
        self._parse_package(kotlin_code)
        self._parse_imports(kotlin_code)
        self._parse_interfaces(kotlin_code)
        self._parse_classes(kotlin_code)
        self._parse_data_classes(kotlin_code)
        self._parse_objects(kotlin_code)
        self._parse_functions(kotlin_code)
        
        return module
    
    def _parse_package(self, code: str):
        """Parse package declaration."""
        package_pattern = r'package\s+([\w.]+)'
        match = re.search(package_pattern, code)
        if match and self.current_module is not None:
            # Store package name in imports list as a marker
            self.current_module.imports.insert(0, f"package:{match.group(1)}")
    
    def _parse_imports(self, code: str):
        """Parse import statements."""
        import_pattern = r'import\s+([\w.*]+)'
        imports = re.findall(import_pattern, code)
        if imports and self.current_module is not None:
            for imp in imports:
                self.current_module.imports.append(f"import {imp}")
    
    def _parse_interfaces(self, code: str):
        """Parse Kotlin interface declarations."""
        interface_pattern = r'interface\s+(\w+)(?:<[^>]+>)?(?:\s*:\s*([^{]+))?\s*\{([^}]*(?:\{[^}]*\}[^}]*)*)\}'
        interfaces = re.finditer(interface_pattern, code, re.MULTILINE | re.DOTALL)
        
        for match in interfaces:
            interface_name = match.group(1)
            extends = match.group(2)
            body = match.group(3)
            
            cls = UniversalClass(
                name=interface_name,
                source_language="kotlin"
            )
            
            cls.implementation_hints = {'is_interface': True}
            
            if extends:
                cls.base_classes = [e.strip() for e in extends.split(',')]
            
            # Parse interface methods
            method_pattern = r'fun\s+(\w+)\s*\(([^)]*)\)(?:\s*:\s*([^{=\n]+))?'
            methods = re.finditer(method_pattern, body)
            
            for method_match in methods:
                method_name = method_match.group(1)
                params_str = method_match.group(2)
                return_type_str = method_match.group(3)
                
                parameters = self._parse_kotlin_parameters(params_str)
                return_type = self._parse_kotlin_type(return_type_str.strip() if return_type_str else None)
                
                method = UniversalFunction(
                    name=method_name,
                    parameters=parameters,
                    return_type=return_type,
                    source_language="kotlin",
                    implementation_hints={'is_interface_method': True}
                )
                
                cls.methods.append(method)
            
            if self.current_module is not None:
                self.current_module.classes.append(cls)
    
    def _parse_classes(self, code: str):
        """Parse Kotlin class declarations."""
        class_pattern = r'(?:open\s+|abstract\s+|sealed\s+)?class\s+(\w+)(?:<[^>]+>)?(?:\s*\(([^)]*)\))?(?:\s*:\s*([^{]+))?\s*\{([^}]*(?:\{[^}]*\}[^}]*)*)\}'
        classes = re.finditer(class_pattern, code, re.MULTILINE | re.DOTALL)
        
        for match in classes:
            class_name = match.group(1)
            primary_constructor = match.group(2)
            extends = match.group(3)
            body = match.group(4)
            
            cls = UniversalClass(
                name=class_name,
                source_language="kotlin"
            )
            
            cls.implementation_hints = {'is_class': True}
            
            if extends:
                cls.base_classes = [e.strip().split('(')[0] for e in extends.split(',')]
            
            # Parse primary constructor parameters
            if primary_constructor:
                params = self._parse_kotlin_parameters(primary_constructor)
                constructor = UniversalFunction(
                    name=class_name,
                    parameters=params,
                    return_type=TypeSignature(DataType.VOID),
                    source_language="kotlin",
                    implementation_hints={'is_constructor': True}
                )
                cls.methods.append(constructor)
            
            # Parse methods
            self._parse_class_methods(body, cls)
            
            if self.current_module is not None:
                self.current_module.classes.append(cls)
    
    def _parse_data_classes(self, code: str):
        """Parse Kotlin data class declarations."""
        data_class_pattern = r'data\s+class\s+(\w+)(?:<[^>]+>)?\s*\(([^)]*)\)(?:\s*:\s*([^{]+))?\s*(?:\{([^}]*)\})?'
        data_classes = re.finditer(data_class_pattern, code, re.MULTILINE | re.DOTALL)
        
        for match in data_classes:
            class_name = match.group(1)
            constructor_params = match.group(2)
            extends = match.group(3)
            body = match.group(4) or ""
            
            cls = UniversalClass(
                name=class_name,
                source_language="kotlin"
            )
            
            cls.implementation_hints = {'is_data_class': True}
            
            if extends:
                cls.base_classes = [e.strip().split('(')[0] for e in extends.split(',')]
            
            # Parse constructor parameters
            params = self._parse_kotlin_parameters(constructor_params)
            constructor = UniversalFunction(
                name=class_name,
                parameters=params,
                return_type=TypeSignature(DataType.VOID),
                source_language="kotlin",
                implementation_hints={'is_constructor': True}
            )
            cls.methods.append(constructor)
            # Parse any additional methods
            if body:
                self._parse_class_methods(body, cls)
            
            if self.current_module is not None:
                self.current_module.classes.append(cls)
    
    def _parse_objects(self, code: str):
        """Parse Kotlin object declarations (singletons)."""
        object_pattern = r'object\s+(\w+)(?:\s*:\s*([^{]+))?\s*\{([^}]*(?:\{[^}]*\}[^}]*)*)\}'
        objects = re.finditer(object_pattern, code, re.MULTILINE | re.DOTALL)
        
        for match in objects:
            object_name = match.group(1)
            implements = match.group(2)
            body = match.group(3)
            
            cls = UniversalClass(
                name=object_name,
                source_language="kotlin"
            )
            
            cls.implementation_hints = {'is_object': True}
            
            if implements:
                cls.base_classes = [i.strip().split('(')[0] for i in implements.split(',')]
            
            # Parse object methods
            self._parse_class_methods(body, cls)
            
            if self.current_module is not None:
                self.current_module.classes.append(cls)
    
    def _parse_class_methods(self, body: str, cls: UniversalClass):
        """Parse methods from class body."""
        method_pattern = r'(?:override\s+)?(?:open\s+)?(?:suspend\s+)?fun\s+(\w+)\s*\(([^)]*)\)(?:\s*:\s*([^{=]+))?\s*\{([^}]*(?:\{[^}]*\}[^}]*)*)\}'
        methods = re.finditer(method_pattern, body, re.MULTILINE | re.DOTALL)
        
        for match in methods:
            method_name = match.group(1)
            params_str = match.group(2)
            return_type_str = match.group(3)
            method_body = match.group(4)
            
            parameters = self._parse_kotlin_parameters(params_str)
            return_type = self._parse_kotlin_type(return_type_str.strip() if return_type_str else None)
            
            is_suspend = 'suspend' in match.group(0)[:match.group(0).find('fun')]
            
            method = UniversalFunction(
                name=method_name,
                parameters=parameters,
                return_type=return_type,
                source_language="kotlin",
                source_code=match.group(0),
                implementation_hints={
                    'is_suspend': is_suspend,
                    'control_flow': self._extract_control_flow(method_body)
                }
            )
            
            cls.methods.append(method)
    
    def _parse_functions(self, code: str):
        """Parse Kotlin top-level function declarations."""
        func_pattern = r'(?:suspend\s+)?fun\s+(\w+)\s*\(([^)]*)\)(?:\s*:\s*([^{=]+))?\s*\{([^}]*(?:\{[^}]*\}[^}]*)*)\}'
        functions = re.finditer(func_pattern, code, re.MULTILINE | re.DOTALL)
        
        for match in functions:
            func_name = match.group(1)
            params_str = match.group(2)
            return_type_str = match.group(3)
            body = match.group(4)
            
            # Skip if inside a class (heuristic)
            start = match.start()
            preceding = code[:start]
            last_class = preceding.rfind('class ')
            last_object = preceding.rfind('object ')
            last_interface = preceding.rfind('interface ')
            last_close = preceding.rfind('}')
            
            container_start = max(last_class, last_object, last_interface)
            if container_start > last_close and container_start != -1:
                continue
            
            parameters = self._parse_kotlin_parameters(params_str)
            return_type = self._parse_kotlin_type(return_type_str.strip() if return_type_str else None)
            
            is_suspend = 'suspend' in match.group(0)[:match.group(0).find('fun')]
            
            func = UniversalFunction(
                name=func_name,
                parameters=parameters,
                return_type=return_type,
                source_language="kotlin",
                source_code=match.group(0),
                implementation_hints={
                    'is_suspend': is_suspend,
                    'control_flow': self._extract_control_flow(body)
                }
            )
            
            if self.current_module is not None:
                self.current_module.functions.append(func)
    
    def _parse_kotlin_parameters(self, params_str: str) -> List[Parameter]:
        """Parse Kotlin function/constructor parameters."""
        parameters = []
        if not params_str.strip():
            return parameters
        
        parts = [p.strip() for p in params_str.split(',') if p.strip()]
        
        for part in parts:
            # Handle val/var in constructor parameters
            part = re.sub(r'^(val|var)\s+', '', part)
            
            if ':' in part:
                name_part, type_part = part.split(':', 1)
                name = name_part.strip()
                
                # Check for default value
                default = None
                if '=' in type_part:
                    type_str, default = type_part.split('=', 1)
                    type_str = type_str.strip()
                    default = default.strip()
                else:
                    type_str = type_part.strip()
                
                # Handle vararg
                if name.startswith('vararg'):
                    name = name.replace('vararg', '').strip()
                
                parameters.append(Parameter(
                    name=name,
                    type_sig=self._parse_kotlin_type(type_str),
                    required=default is None,
                    default_value=default
                ))
        
        return parameters
    def _parse_kotlin_type(self, type_str: Optional[str]) -> TypeSignature:
        """Parse Kotlin type into UIR TypeSignature."""
        if not type_str:
            return TypeSignature(DataType.VOID)
        
        type_str = type_str.strip()
        type_str = type_str.strip()
        
        # Handle nullable types
        if type_str.endswith('?'):
            type_str = type_str[:-1]
        
        # Handle generics
        if '<' in type_str:
            base_type = type_str.split('<')[0]
            if base_type in ['List', 'MutableList', 'Set', 'MutableSet', 'Array']:
                return TypeSignature(DataType.ARRAY)
            if base_type in ['Map', 'MutableMap', 'HashMap']:
                return TypeSignature(DataType.OBJECT)
        
        type_mapping = {
            'Unit': DataType.VOID,
            'Boolean': DataType.BOOLEAN,
            'Byte': DataType.INTEGER,
            'Short': DataType.INTEGER,
            'Int': DataType.INTEGER,
            'Long': DataType.INTEGER,
            'Float': DataType.FLOAT,
            'Double': DataType.FLOAT,
            'Char': DataType.STRING,
            'String': DataType.STRING,
            'Any': DataType.ANY,
            'Nothing': DataType.VOID,
        }
        
        return TypeSignature(type_mapping.get(type_str, DataType.OBJECT))
    
    def _extract_control_flow(self, body: str) -> List[Dict[str, Any]]:
        """Extract control flow structures from function body."""
        control_flow = []
        
        if not body:
            return control_flow
        
        patterns = [
            (r'if\s*\([^)]+\)', 'if_condition'),
            (r'when\s*(?:\([^)]+\))?\s*\{', 'switch'),
            (r'for\s*\([^)]+\)', 'for_loop'),
            (r'while\s*\([^)]+\)', 'while_loop'),
            (r'try\s*\{', 'try_catch'),
        ]
        
        for pattern, kind in patterns:
            for match in re.finditer(pattern, body):
                control_flow.append({
                    'kind': kind,
                    'source_code': match.group(0),
                    'lineno': body[:match.start()].count('\n') + 1
                })
        
        return control_flow


class KotlinTypeInference:
    """Infers types from Kotlin code patterns."""
    
    def infer_type(self, value: str) -> TypeSignature:
        """Infer type from a value expression."""
        if not value:
            return TypeSignature(DataType.ANY)
        
        value = value.strip()
        
        if value.startswith('"') or value.startswith('"""'):
            return TypeSignature(DataType.STRING)
        if value.startswith("'"):
            return TypeSignature(DataType.STRING)
        if value in ['true', 'false']:
            return TypeSignature(DataType.BOOLEAN)
        if value == 'null':
            return TypeSignature(DataType.ANY)
        if re.match(r'^-?\d+[Ll]?$', value):
            return TypeSignature(DataType.INTEGER)
        if re.match(r'^-?\d+\.\d+[fF]?$', value):
            return TypeSignature(DataType.FLOAT)
        
        return TypeSignature(DataType.ANY)
