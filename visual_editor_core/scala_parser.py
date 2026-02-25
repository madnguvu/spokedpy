"""
Scala to Universal IR Parser.

This module parses Scala code and converts it to Universal Intermediate Representation.
"""

import re
from typing import Dict, List, Optional, Any
from .universal_ir import (
    UniversalProject, UniversalModule, UniversalFunction, UniversalClass,
    UniversalVariable, Parameter, TypeSignature, DataType, SemanticDescription,
    Contract, PurityLevel
)


class ScalaParser:
    """Parses Scala code into Universal IR."""
    
    def __init__(self):
        self.current_module: Optional[UniversalModule] = None
        self.type_inference = ScalaTypeInference()
    
    def parse_code(self, scala_code: str, filename: str = "Main.scala") -> UniversalModule:
        """Parse Scala code into a Universal Module."""
        module = UniversalModule(
            name=filename.replace('.scala', ''),
            source_language="scala",
            source_file=filename
        )
        
        self.current_module = module
        
        # Parse Scala constructs
        self._parse_package(scala_code)
        self._parse_imports(scala_code)
        self._parse_traits(scala_code)
        self._parse_classes(scala_code)
        self._parse_case_classes(scala_code)
        self._parse_objects(scala_code)
        self._parse_functions(scala_code)
        
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
        import_pattern = r'import\s+([\w._{}]+)'
        imports = re.findall(import_pattern, code)
        if imports and self.current_module is not None:
            for imp in imports:
                self.current_module.imports.append(f"import {imp}")
    
    def _parse_traits(self, code: str):
        """Parse Scala trait declarations."""
        trait_pattern = r'(?:sealed\s+)?trait\s+(\w+)(?:\[([^\]]+)\])?(?:\s+extends\s+([^{]+))?\s*\{([^}]*(?:\{[^}]*\}[^}]*)*)\}'
        traits = re.finditer(trait_pattern, code, re.MULTILINE | re.DOTALL)
        
        for match in traits:
            trait_name = match.group(1)
            type_params = match.group(2)
            extends = match.group(3)
            body = match.group(4)
            
            cls = UniversalClass(
                name=trait_name,
                source_language="scala"
            )
            
            cls.implementation_hints = {'is_trait': True}
            
            if type_params:
                cls.implementation_hints['type_params'] = type_params
            
            if extends:
                cls.base_classes = [e.strip().split('[')[0] for e in extends.split('with')]
            
            # Parse trait methods
            self._parse_class_methods(body, cls)
            
            if self.current_module is not None:
                self.current_module.classes.append(cls)
    
    def _parse_classes(self, code: str):
        """Parse Scala class declarations."""
        class_pattern = r'(?:abstract\s+)?class\s+(\w+)(?:\[([^\]]+)\])?(?:\s*\(([^)]*)\))?(?:\s+extends\s+([^{]+))?\s*\{([^}]*(?:\{[^}]*\}[^}]*)*)\}'
        classes = re.finditer(class_pattern, code, re.MULTILINE | re.DOTALL)
        
        for match in classes:
            class_name = match.group(1)
            type_params = match.group(2)
            constructor_params = match.group(3)
            extends = match.group(4)
            body = match.group(5)
            
            cls = UniversalClass(
                name=class_name,
                source_language="scala"
            )
            
            cls.implementation_hints = {'is_class': True}
            
            if type_params:
                cls.implementation_hints['type_params'] = type_params
            
            if extends:
                cls.base_classes = [e.strip().split('[')[0].split('(')[0] for e in extends.split('with')]
            
            # Parse constructor parameters
            if constructor_params:
                params = self._parse_scala_parameters(constructor_params)
                constructor = UniversalFunction(
                    name=class_name,
                    parameters=params,
                    return_type=TypeSignature(DataType.VOID),
                    source_language="scala",
                    implementation_hints={'is_constructor': True}
                )
                cls.methods.append(constructor)
            
            # Parse methods
            self._parse_class_methods(body, cls)
            
            if self.current_module is not None:
                self.current_module.classes.append(cls)
    
    def _parse_case_classes(self, code: str):
        """Parse Scala case class declarations."""
        case_class_pattern = r'case\s+class\s+(\w+)(?:\[([^\]]+)\])?\s*\(([^)]*)\)(?:\s+extends\s+([^{]+))?(?:\s*\{([^}]*)\})?'
        case_classes = re.finditer(case_class_pattern, code, re.MULTILINE | re.DOTALL)
        
        for match in case_classes:
            class_name = match.group(1)
            type_params = match.group(2)
            params_str = match.group(3)
            extends = match.group(4)
            body = match.group(5) or ""
            
            cls = UniversalClass(
                name=class_name,
                source_language="scala"
            )
            
            cls.implementation_hints = {'is_case_class': True}
            
            if type_params:
                cls.implementation_hints['type_params'] = type_params
            
            if extends:
                cls.base_classes = [e.strip().split('[')[0].split('(')[0] for e in extends.split('with')]
            
            # Parse constructor parameters
            params = self._parse_scala_parameters(params_str)
            constructor = UniversalFunction(
                name=class_name,
                parameters=params,
                return_type=TypeSignature(DataType.VOID),
                source_language="scala",
                implementation_hints={'is_constructor': True}
            )
            cls.methods.append(constructor)
            
            # Parse any additional methods
            if body:
                self._parse_class_methods(body, cls)
            
            if self.current_module is not None:
                self.current_module.classes.append(cls)
    
    def _parse_objects(self, code: str):
        """Parse Scala object declarations (singletons)."""
        object_pattern = r'(?:case\s+)?object\s+(\w+)(?:\s+extends\s+([^{]+))?\s*\{([^}]*(?:\{[^}]*\}[^}]*)*)\}'
        objects = re.finditer(object_pattern, code, re.MULTILINE | re.DOTALL)
        
        for match in objects:
            object_name = match.group(1)
            extends = match.group(2)
            body = match.group(3)
            
            cls = UniversalClass(
                name=object_name,
                source_language="scala"
            )
            
            cls.implementation_hints = {'is_object': True, 'is_singleton': True}
            
            if extends:
                cls.base_classes = [e.strip().split('[')[0].split('(')[0] for e in extends.split('with')]
            
            self._parse_class_methods(body, cls)
            
            if self.current_module is not None:
                self.current_module.classes.append(cls)
    
    def _parse_class_methods(self, body: str, cls: UniversalClass):
        """Parse methods from class/trait/object body."""
        method_pattern = r'(?:override\s+)?def\s+(\w+)(?:\[([^\]]+)\])?\s*(?:\(([^)]*)\))?(?:\s*:\s*([^={\n]+))?\s*=\s*(?:\{([^}]*(?:\{[^}]*\}[^}]*)*)\}|([^\n]+))'
        methods = re.finditer(method_pattern, body, re.MULTILINE | re.DOTALL)
        
        for match in methods:
            method_name = match.group(1)
            type_params = match.group(2)
            params_str = match.group(3)
            return_type_str = match.group(4)
            method_body_block = match.group(5)
            method_body_inline = match.group(6)
            
            parameters = self._parse_scala_parameters(params_str) if params_str else []
            return_type = self._parse_scala_type(return_type_str.strip() if return_type_str else None)
            
            method = UniversalFunction(
                name=method_name,
                parameters=parameters,
                return_type=return_type,
                source_language="scala",
                source_code=match.group(0),
                implementation_hints={
                    'type_params': type_params,
                    'control_flow': self._extract_control_flow(method_body_block or method_body_inline or "")
                }
            )
            
            cls.methods.append(method)
    
    def _parse_functions(self, code: str):
        """Parse Scala top-level function declarations (inside objects)."""
        # In Scala, top-level functions are actually methods in package objects
        pass
    
    def _parse_scala_parameters(self, params_str: str) -> List[Parameter]:
        """Parse Scala function/constructor parameters."""
        parameters = []
        if not params_str or not params_str.strip():
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
                
                # Handle implicit parameters
                if name.startswith('implicit'):
                    name = name.replace('implicit', '').strip()
                
                parameters.append(Parameter(
                    name=name,
                    type_sig=self._parse_scala_type(type_str),
                    required=default is None,
                    default_value=default
                ))
        
        return parameters
    
    def _parse_scala_type(self, type_str: Optional[str]) -> TypeSignature:
        """Parse Scala type into UIR TypeSignature."""
        if not type_str:
            return TypeSignature(DataType.VOID)
        
        type_str = type_str.strip()
        
        # Handle Option types
        if type_str.startswith('Option['):
            return TypeSignature(DataType.ANY)
        
        # Handle collections
        if any(type_str.startswith(c) for c in ['List[', 'Seq[', 'Vector[', 'Array[', 'Set[']):
            return TypeSignature(DataType.ARRAY)
        
        if type_str.startswith('Map['):
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
            'AnyRef': DataType.OBJECT,
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
            (r'match\s*\{', 'switch'),
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


class ScalaTypeInference:
    """Infers types from Scala code patterns."""
    
    def infer_type(self, value: str) -> TypeSignature:
        """Infer type from a value expression."""
        if not value:
            return TypeSignature(DataType.ANY)
        
        value = value.strip()
        
        if value.startswith('"') or value.startswith('"""') or value.startswith('s"'):
            return TypeSignature(DataType.STRING)
        if value.startswith("'"):
            return TypeSignature(DataType.STRING)
        if value in ['true', 'false']:
            return TypeSignature(DataType.BOOLEAN)
        if value in ['null', 'None']:
            return TypeSignature(DataType.ANY)
        if re.match(r'^-?\d+[Ll]?$', value):
            return TypeSignature(DataType.INTEGER)
        if re.match(r'^-?\d+\.\d+[fFdD]?$', value):
            return TypeSignature(DataType.FLOAT)
        
        return TypeSignature(DataType.ANY)
