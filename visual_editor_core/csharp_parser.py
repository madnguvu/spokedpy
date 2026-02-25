"""
C# to Universal IR Parser.

This module parses C# code and converts it to Universal Intermediate Representation.
"""

import re
from typing import Dict, List, Optional, Any
from .universal_ir import (
    UniversalProject, UniversalModule, UniversalFunction, UniversalClass,
    UniversalVariable, Parameter, TypeSignature, DataType, SemanticDescription,
    Contract, PurityLevel
)


# Extend UniversalModule to include an optional C# namespace attribute
if not hasattr(UniversalModule, 'csharp_namespace'):
    setattr(UniversalModule, 'csharp_namespace', None)


class CSharpParser:
    """Parses C# code into Universal IR."""
    
    def __init__(self):
        self.current_module = None
        self.type_inference = CSharpTypeInference()
    
    def parse_code(self, csharp_code: str, filename: str = "Program.cs") -> UniversalModule:
        """Parse C# code into a Universal Module."""
        module = UniversalModule(
            name=filename.replace('.cs', ''),
            source_language="csharp",
            source_file=filename
        )

        # Ensure the module has a classes collection
        if not hasattr(module, "classes") or module.classes is None:
            module.classes = []

        self.current_module = module
        
        # Parse C# constructs
        self._parse_using_directives(csharp_code)
        self._parse_namespace(csharp_code)
        self._parse_interfaces(csharp_code)
        self._parse_classes(csharp_code)
        self._parse_structs(csharp_code)
        self._parse_enums(csharp_code)
        
        return module
    
    def _parse_using_directives(self, code: str):
        """Parse using directives and store in module.imports."""
        if self.current_module is None:
            return
        # Match: using System; using System.Collections.Generic; using static X; using X = Y;
        using_pattern = r'^\s*(using\s+(?:static\s+)?[\w.=\s]+)\s*;'
        for m in re.finditer(using_pattern, code, re.MULTILINE):
            stmt = m.group(1).strip()
            self.current_module.imports.append(f"{stmt};")

    def _parse_namespace(self, code: str):
        """Parse namespace declaration."""
        namespace_pattern = r'namespace\s+([\w.]+)'
        match = re.search(namespace_pattern, code)
        if match and self.current_module is not None:
            # Use setattr to avoid static analyzer complaints about dynamic attributes.
            if not hasattr(self.current_module, 'csharp_namespace') or getattr(self.current_module, 'csharp_namespace', None) is None:
                setattr(self.current_module, 'csharp_namespace', match.group(1))
    
    def _parse_interfaces(self, code: str):
        """Parse C# interface declarations."""
        interface_pattern = r'(?:public\s+)?interface\s+(\w+)(?:<[^>]+>)?(?:\s*:\s*([^{]+))?\s*\{([^}]*(?:\{[^}]*\}[^}]*)*)\}'
        interfaces = re.finditer(interface_pattern, code, re.MULTILINE | re.DOTALL)
        
        for match in interfaces:
            interface_name = match.group(1)
            base_interfaces = match.group(2)
            body = match.group(3)
            
            cls = UniversalClass(
                name=interface_name,
                source_language="csharp"
            )
            
            cls.implementation_hints = {'is_interface': True}
            
            if base_interfaces:
                cls.base_classes = [b.strip() for b in base_interfaces.split(',')]
            
            # Parse interface methods
            method_pattern = r'(\w+(?:<[^>]+>)?)\s+(\w+)\s*\(([^)]*)\)\s*;'
            methods = re.finditer(method_pattern, body)
            
            for method_match in methods:
                return_type_str = method_match.group(1)
                method_name = method_match.group(2)
                params_str = method_match.group(3)
                
                parameters = self._parse_csharp_parameters(params_str)
                return_type = self._parse_csharp_type(return_type_str)
                
                method = UniversalFunction(
                    name=method_name,
                    parameters=parameters,
                    return_type=return_type,
                    source_language="csharp",
                    implementation_hints={'is_interface_method': True}
                )
                
                cls.methods.append(method)
            
            if self.current_module is not None and hasattr(self.current_module, "classes"):
                self.current_module.classes.append(cls)
    
    def _parse_classes(self, code: str):
        """Parse C# class declarations."""
        class_pattern = r'(?:(?:public|internal|private|protected)\s+)?(?:abstract\s+)?(?:sealed\s+)?(?:partial\s+)?class\s+(\w+)(?:<[^>]+>)?(?:\s*:\s*([^{]+))?\s*\{([^}]*(?:\{[^}]*\}[^}]*)*)\}'
        classes = re.finditer(class_pattern, code, re.MULTILINE | re.DOTALL)
        
        for match in classes:
            class_name = match.group(1)
            inheritance = match.group(2)
            body = match.group(3)
            
            cls = UniversalClass(
                name=class_name,
                source_language="csharp"
            )
            
            cls.implementation_hints = {'is_class': True}
            
            if inheritance:
                bases = [b.strip() for b in inheritance.split(',')]
                cls.base_classes = bases
            
            # Parse constructors
            self._parse_constructors(body, cls)
            
            # Parse methods
            self._parse_methods(body, cls)
            
            # Parse properties
            self._parse_properties(body, cls)
            
            # Parse fields
            self._parse_fields(body, cls)
            
            if self.current_module is not None and hasattr(self.current_module, "classes"):
                self.current_module.classes.append(cls)
    
    def _parse_structs(self, code: str):
        """Parse C# struct declarations."""
        struct_pattern = r'(?:public\s+)?struct\s+(\w+)(?:<[^>]+>)?\s*\{([^}]*)\}'
        structs = re.finditer(struct_pattern, code, re.MULTILINE | re.DOTALL)
        
        for match in structs:
            struct_name = match.group(1)
            body = match.group(2)
            
            cls = UniversalClass(
                name=struct_name,
                source_language="csharp"
            )
            
            cls.implementation_hints = {'is_struct': True}
            
            # Parse constructors (structs can have constructors)
            self._parse_constructors(body, cls)
            
            # Parse methods
            self._parse_methods(body, cls)
            
            # Parse properties
            self._parse_properties(body, cls)
            
            # Parse fields
            self._parse_fields(body, cls)
            
            if self.current_module is not None and hasattr(self.current_module, "classes"):
                self.current_module.classes.append(cls)
    
    def _parse_enums(self, code: str):
        """Parse C# enum declarations."""
        enum_pattern = r'(?:public\s+)?enum\s+(\w+)(?:\s*:\s*(\w+))?\s*\{([^}]*)\}'
        enums = re.finditer(enum_pattern, code, re.MULTILINE | re.DOTALL)
        
        for match in enums:
            enum_name = match.group(1)
            base_type = match.group(2)
            body = match.group(3)
            
            cls = UniversalClass(
                name=enum_name,
                source_language="csharp"
            )
            
            cls.implementation_hints = {'is_enum': True}
            
            if base_type:
                cls.base_classes = [base_type]
            
            # Parse enum values
            values = [v.strip().split('=')[0].strip() for v in body.split(',') if v.strip()]
            cls.implementation_hints['values'] = values
            
            if self.current_module is not None and hasattr(self.current_module, "classes"):
                self.current_module.classes.append(cls)
    
    def _parse_constructors(self, body: str, cls: UniversalClass):
        """Parse constructors from class body."""
        constructor_pattern = rf'(?:public|private|protected|internal)\s+{cls.name}\s*\(([^)]*)\)\s*(?::\s*(?:base|this)\s*\([^)]*\))?\s*\{{([^}}]*(?:\{{[^}}]*\}}[^}}]*)*)\}}'
        constructors = re.finditer(constructor_pattern, body, re.MULTILINE | re.DOTALL)
        
        for match in constructors:
            params_str = match.group(1)
            ctor_body = match.group(2)
            
            parameters = self._parse_csharp_parameters(params_str)
            
            method = UniversalFunction(
                name=cls.name,
                parameters=parameters,
                return_type=TypeSignature(DataType.VOID),
                source_language="csharp",
                source_code=match.group(0),
                implementation_hints={'is_constructor': True}
            )
            
            cls.methods.append(method)
    
    def _parse_methods(self, body: str, cls: UniversalClass):
        """Parse methods from class body."""
        method_pattern = r'(?:(?:public|private|protected|internal)\s+)?(?:static\s+)?(?:virtual\s+)?(?:override\s+)?(?:async\s+)?(\w+(?:<[^>]+>)?)\s+(\w+)\s*\(([^)]*)\)\s*\{([^}]*(?:\{[^}]*\}[^}]*)*)\}'
        methods = re.finditer(method_pattern, body, re.MULTILINE | re.DOTALL)
        
        for match in methods:
            return_type_str = match.group(1)
            method_name = match.group(2)
            params_str = match.group(3)
            method_body = match.group(4)
            
            # Skip constructors (already parsed)
            if method_name == cls.name:
                continue
            
            parameters = self._parse_csharp_parameters(params_str)
            return_type = self._parse_csharp_type(return_type_str)
            
            is_static = 'static' in match.group(0)[:match.group(0).find(return_type_str)]
            is_async = 'async' in match.group(0)[:match.group(0).find(return_type_str)]
            
            method = UniversalFunction(
                name=method_name,
                parameters=parameters,
                return_type=return_type,
                source_language="csharp",
                source_code=match.group(0),
                implementation_hints={
                    'is_method': True,
                    'is_static': is_static,
                    'is_async': is_async,
                    'control_flow': self._extract_control_flow(method_body)
                }
            )
            
            cls.methods.append(method)
    
    def _parse_properties(self, body: str, cls: UniversalClass):
        """Parse properties from class body."""
        prop_pattern = r'(?:public|private|protected|internal)\s+(?:static\s+)?(\w+(?:<[^>]+>)?)\s+(\w+)\s*\{\s*(?:get\s*(?:\{[^}]*\}|;))\s*(?:set\s*(?:\{[^}]*\}|;))?\s*\}'
        properties = re.finditer(prop_pattern, body, re.MULTILINE | re.DOTALL)
        
        for match in properties:
            prop_type = match.group(1)
            prop_name = match.group(2)
            # Currently, properties are not stored explicitly in UniversalClass;
            # this is a placeholder for future extension.
            _ = (prop_type, prop_name)
    
    def _parse_fields(self, body: str, cls: UniversalClass):
        """Parse fields from class body."""
        field_pattern = r'(?:public|private|protected|internal)\s+(?:readonly\s+)?(?:static\s+)?(\w+(?:<[^>]+>)?)\s+(\w+)\s*(?:=\s*([^;]+))?;'
        fields = re.finditer(field_pattern, body)
        
        for match in fields:
            field_type = match.group(1)
            field_name = match.group(2)
            field_value = match.group(3)
            # Currently, fields are not stored explicitly in UniversalClass;
            # this is a placeholder for future extension.
            _ = (field_type, field_name, field_value)
    
    def _parse_csharp_parameters(self, params_str: str) -> List[Parameter]:
        """Parse C# method parameters."""
        parameters = []
        if not params_str.strip():
            return parameters
        
        parts = [p.strip() for p in params_str.split(',') if p.strip()]
        
        for part in parts:
            tokens = part.split()
            
            # Handle modifiers like 'ref', 'out', 'in', 'params'
            modifiers = []
            while tokens and tokens[0] in ['ref', 'out', 'in', 'params', 'this']:
                modifiers.append(tokens.pop(0))
            
            if len(tokens) >= 2:
                type_str = tokens[0]
                name = tokens[1]
                default = None
                
                if '=' in name:
                    name, default = name.split('=', 1)
                    default = default.strip()
                elif len(tokens) > 3 and tokens[2] == '=':
                    default = tokens[3]
                
                parameters.append(Parameter(
                    name=name,
                    type_sig=self._parse_csharp_type(type_str),
                    required=default is None,
                    default_value=default
                ))
        
        return parameters
    
    def _parse_csharp_type(self, type_str: str) -> TypeSignature:
        """Parse C# type into UIR TypeSignature."""
        if not type_str:
            return TypeSignature(DataType.VOID)
        
        type_str = type_str.strip()
        
        # Handle nullable types
        if type_str.endswith('?'):
            type_str = type_str[:-1]
        
        # Handle arrays
        if type_str.endswith('[]'):
            return TypeSignature(DataType.ARRAY)
        
        # Handle generics like List<T>, Dictionary<K,V>
        if '<' in type_str:
            base_type = type_str.split('<')[0]
            if base_type in ['List', 'IList', 'IEnumerable', 'ICollection', 'HashSet']:
                return TypeSignature(DataType.ARRAY)
            if base_type in ['Dictionary', 'IDictionary', 'SortedDictionary']:
                return TypeSignature(DataType.OBJECT)
            if base_type in ['Task', 'ValueTask']:
                return TypeSignature(DataType.ANY)
        
        type_mapping = {
            'void': DataType.VOID,
            'bool': DataType.BOOLEAN,
            'Boolean': DataType.BOOLEAN,
            'byte': DataType.INTEGER,
            'sbyte': DataType.INTEGER,
            'short': DataType.INTEGER,
            'ushort': DataType.INTEGER,
            'int': DataType.INTEGER,
            'Int32': DataType.INTEGER,
            'uint': DataType.INTEGER,
            'long': DataType.INTEGER,
            'Int64': DataType.INTEGER,
            'ulong': DataType.INTEGER,
            'float': DataType.FLOAT,
            'Single': DataType.FLOAT,
            'double': DataType.FLOAT,
            'Double': DataType.FLOAT,
            'decimal': DataType.FLOAT,
            'Decimal': DataType.FLOAT,
            'char': DataType.STRING,
            'string': DataType.STRING,
            'String': DataType.STRING,
            'object': DataType.ANY,
            'dynamic': DataType.ANY,
            'var': DataType.ANY,
        }
        
        return TypeSignature(type_mapping.get(type_str, DataType.OBJECT))
    
    def _extract_control_flow(self, body: str) -> List[Dict[str, Any]]:
        """Extract control flow structures from method body."""
        control_flow = []
        
        if not body:
            return control_flow
        
        patterns = [
            (r'if\s*\([^)]+\)', 'if_condition'),
            (r'else\s+if\s*\([^)]+\)', 'else_if'),
            (r'else\s*\{', 'else'),
            (r'for\s*\([^)]+\)', 'for_loop'),
            (r'foreach\s*\([^)]+\)', 'foreach_loop'),
            (r'while\s*\([^)]+\)', 'while_loop'),
            (r'do\s*\{', 'do_while_loop'),
            (r'switch\s*\([^)]+\)', 'switch'),
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


class CSharpTypeInference:
    """Infers types from C# code patterns."""
    
    def infer_type(self, value: str) -> TypeSignature:
        """Infer type from a value expression."""
        if not value:
            return TypeSignature(DataType.ANY)
        
        value = value.strip()
        
        if value.startswith('"') or value.startswith('@"') or value.startswith('$"'):
            return TypeSignature(DataType.STRING)
        if value.startswith("'"):
            return TypeSignature(DataType.STRING)
        if value in ['true', 'false']:
            return TypeSignature(DataType.BOOLEAN)
        if value == 'null':
            return TypeSignature(DataType.ANY)
        if re.match(r'^-?\d+[lL]?$', value):
            return TypeSignature(DataType.INTEGER)
        if re.match(r'^-?\d+\.\d+[fdmFDM]?$', value):
            return TypeSignature(DataType.FLOAT)
        
        return TypeSignature(DataType.ANY)
