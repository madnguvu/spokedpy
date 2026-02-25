"""
Swift to Universal IR Parser.

This module parses Swift code and converts it to Universal Intermediate Representation.
"""

import re
from typing import Dict, List, Optional, Any
from .universal_ir import (
    UniversalProject, UniversalModule, UniversalFunction, UniversalClass,
    UniversalVariable, Parameter, TypeSignature, DataType, SemanticDescription,
    Contract, PurityLevel
)


class SwiftParser:
    """Parses Swift code into Universal IR."""
    
    def __init__(self):
        self.current_module: Optional[UniversalModule] = None
        self.type_inference = SwiftTypeInference()
    
    def parse_code(self, swift_code: str, filename: str = "main.swift") -> UniversalModule:
        """Parse Swift code into a Universal Module."""
        module = UniversalModule(
            name=filename.replace('.swift', ''),
            source_language="swift",
            source_file=filename
        )
        
        self.current_module = module
        
        # Parse Swift constructs
        self._parse_imports(swift_code)
        self._parse_protocols(swift_code)
        self._parse_classes(swift_code)
        self._parse_structs(swift_code)
        self._parse_enums(swift_code)
        self._parse_extensions(swift_code)
        self._parse_functions(swift_code)
        
        return module
    
    def _parse_imports(self, code: str):
        """Parse import statements."""
        import_pattern = r'import\s+(\w+)'
        imports = re.findall(import_pattern, code)
        if imports and self.current_module is not None:
            for imp in imports:
                self.current_module.imports.append(f"import {imp}")
    
    def _parse_protocols(self, code: str):
        """Parse Swift protocol declarations."""
        protocol_pattern = r'protocol\s+(\w+)(?:\s*:\s*([^{]+))?\s*\{([^}]*(?:\{[^}]*\}[^}]*)*)\}'
        protocols = re.finditer(protocol_pattern, code, re.MULTILINE | re.DOTALL)
        
        for match in protocols:
            protocol_name = match.group(1)
            inherits = match.group(2)
            body = match.group(3)
            
            cls = UniversalClass(
                name=protocol_name,
                source_language="swift"
            )
            
            cls.implementation_hints = {'is_protocol': True}
            
            if inherits:
                cls.base_classes = [i.strip() for i in inherits.split(',')]
            
            # Parse protocol methods
            method_pattern = r'func\s+(\w+)\s*\(([^)]*)\)(?:\s*->\s*([^\n{]+))?'
            methods = re.finditer(method_pattern, body)
            
            for method_match in methods:
                method_name = method_match.group(1)
                params_str = method_match.group(2)
                return_type_str = method_match.group(3)
                
                parameters = self._parse_swift_parameters(params_str)
                return_type = self._parse_swift_type(return_type_str.strip() if return_type_str else None)
                
                method = UniversalFunction(
                    name=method_name,
                    parameters=parameters,
                    return_type=return_type,
                    source_language="swift",
                    implementation_hints={'is_protocol_method': True}
                )
                
                cls.methods.append(method)
            
            if self.current_module is not None:
                self.current_module.classes.append(cls)
    
    def _parse_classes(self, code: str):
        """Parse Swift class declarations."""
        class_pattern = r'(?:final\s+)?class\s+(\w+)(?:<[^>]+>)?(?:\s*:\s*([^{]+))?\s*\{([^}]*(?:\{[^}]*\}[^}]*)*)\}'
        classes = re.finditer(class_pattern, code, re.MULTILINE | re.DOTALL)
        
        for match in classes:
            class_name = match.group(1)
            inherits = match.group(2)
            body = match.group(3)
            
            cls = UniversalClass(
                name=class_name,
                source_language="swift"
            )
            
            cls.implementation_hints = {'is_class': True}
            
            if inherits:
                cls.base_classes = [i.strip() for i in inherits.split(',')]
            
            # Parse initializers
            self._parse_initializers(body, cls)
            
            # Parse methods
            self._parse_class_methods(body, cls)
            
            # Parse properties
            self._parse_properties(body, cls)
            
            if self.current_module is not None:
                self.current_module.classes.append(cls)
    
    def _parse_structs(self, code: str):
        """Parse Swift struct declarations."""
        struct_pattern = r'struct\s+(\w+)(?:<[^>]+>)?(?:\s*:\s*([^{]+))?\s*\{([^}]*(?:\{[^}]*\}[^}]*)*)\}'
        structs = re.finditer(struct_pattern, code, re.MULTILINE | re.DOTALL)
        
        for match in structs:
            struct_name = match.group(1)
            conforms = match.group(2)
            body = match.group(3)
            
            cls = UniversalClass(
                name=struct_name,
                source_language="swift"
            )
            
            cls.implementation_hints = {'is_struct': True}
            
            if conforms:
                cls.base_classes = [c.strip() for c in conforms.split(',')]
            
            self._parse_initializers(body, cls)
            self._parse_class_methods(body, cls)
            self._parse_properties(body, cls)
            
            if self.current_module is not None:
                self.current_module.classes.append(cls)
    
    def _parse_enums(self, code: str):
        """Parse Swift enum declarations."""
        enum_pattern = r'enum\s+(\w+)(?:<[^>]+>)?(?:\s*:\s*([^{]+))?\s*\{([^}]*(?:\{[^}]*\}[^}]*)*)\}'
        enums = re.finditer(enum_pattern, code, re.MULTILINE | re.DOTALL)
        
        for match in enums:
            enum_name = match.group(1)
            raw_type = match.group(2)
            body = match.group(3)
            
            cls = UniversalClass(
                name=enum_name,
                source_language="swift"
            )
            
            cls.implementation_hints = {'is_enum': True}
            
            # Parse enum cases
            case_pattern = r'case\s+(\w+)(?:\([^)]*\))?'
            cases = re.findall(case_pattern, body)
            cls.implementation_hints['cases'] = cases
            
            self._parse_class_methods(body, cls)
            
            if self.current_module is not None:
                self.current_module.classes.append(cls)
    
    def _parse_extensions(self, code: str):
        """Parse Swift extension declarations."""
        extension_pattern = r'extension\s+(\w+)(?:<[^>]+>)?(?:\s*:\s*([^{]+))?\s*\{([^}]*(?:\{[^}]*\}[^}]*)*)\}'
        extensions = re.finditer(extension_pattern, code, re.MULTILINE | re.DOTALL)
        
        for match in extensions:
            extended_type = match.group(1)
            conforms = match.group(2)
            body = match.group(3)
            
            if self.current_module is None:
                continue
            
            # Find existing type or create new one
            existing = None
            for cls in self.current_module.classes:
                if cls.name == extended_type:
                    existing = cls
                    break
            
            if not existing:
                existing = UniversalClass(
                    name=extended_type,
                    source_language="swift"
                )
                existing.implementation_hints = {'is_extension': True}
                self.current_module.classes.append(existing)
            
            self._parse_class_methods(body, existing)
    
    def _parse_initializers(self, body: str, cls: UniversalClass):
        """Parse initializers from class/struct body."""
        init_pattern = r'(?:required\s+)?(?:convenience\s+)?init\s*\(([^)]*)\)\s*(?:throws\s*)?\{([^}]*(?:\{[^}]*\}[^}]*)*)\}'
        inits = re.finditer(init_pattern, body, re.MULTILINE | re.DOTALL)
        
        for match in inits:
            params_str = match.group(1)
            init_body = match.group(2)
            
            parameters = self._parse_swift_parameters(params_str)
            
            method = UniversalFunction(
                name='init',
                parameters=parameters,
                return_type=TypeSignature(DataType.VOID),
                source_language="swift",
                source_code=match.group(0),
                implementation_hints={'is_constructor': True}
            )
            
            cls.methods.append(method)
    
    def _parse_class_methods(self, body: str, cls: UniversalClass):
        """Parse methods from class/struct body."""
        method_pattern = r'(?:@\w+\s+)*(?:static\s+)?(?:class\s+)?(?:override\s+)?(?:mutating\s+)?func\s+(\w+)\s*\(([^)]*)\)(?:\s*(?:throws\s+)?->\s*([^{]+))?\s*\{([^}]*(?:\{[^}]*\}[^}]*)*)\}'
        methods = re.finditer(method_pattern, body, re.MULTILINE | re.DOTALL)
        
        for match in methods:
            method_name = match.group(1)
            params_str = match.group(2)
            return_type_str = match.group(3)
            method_body = match.group(4)
            
            parameters = self._parse_swift_parameters(params_str)
            return_type = self._parse_swift_type(return_type_str.strip() if return_type_str else None)
            
            is_static = 'static' in match.group(0)[:match.group(0).find('func')]
            is_mutating = 'mutating' in match.group(0)[:match.group(0).find('func')]
            
            method = UniversalFunction(
                name=method_name,
                parameters=parameters,
                return_type=return_type,
                source_language="swift",
                source_code=match.group(0),
                implementation_hints={
                    'is_static': is_static,
                    'is_mutating': is_mutating,
                    'control_flow': self._extract_control_flow(method_body)
                }
            )
            
            cls.methods.append(method)
    
    def _parse_properties(self, body: str, cls: UniversalClass):
        """Parse properties from class/struct body."""
        prop_pattern = r'(?:var|let)\s+(\w+)\s*:\s*([^=\n{]+)(?:\s*=\s*([^\n{]+))?'
        properties = re.finditer(prop_pattern, body)
        
        for match in properties:
            prop_name = match.group(1)
            prop_type = match.group(2).strip()
            default_value = match.group(3)
    
    def _parse_functions(self, code: str):
        """Parse Swift top-level function declarations."""
        func_pattern = r'func\s+(\w+)\s*\(([^)]*)\)(?:\s*(?:throws\s+)?->\s*([^{]+))?\s*\{([^}]*(?:\{[^}]*\}[^}]*)*)\}'
        functions = re.finditer(func_pattern, code, re.MULTILINE | re.DOTALL)
        
        for match in functions:
            func_name = match.group(1)
            params_str = match.group(2)
            return_type_str = match.group(3)
            body = match.group(4)
            
            # Skip if inside a type (heuristic)
            start = match.start()
            preceding = code[:start]
            last_type = max(
                preceding.rfind('class '),
                preceding.rfind('struct '),
                preceding.rfind('enum '),
                preceding.rfind('extension '),
                preceding.rfind('protocol ')
            )
            last_close = preceding.rfind('}')
            
            if last_type > last_close and last_type != -1:
                continue
            
            parameters = self._parse_swift_parameters(params_str)
            return_type = self._parse_swift_type(return_type_str.strip() if return_type_str else None)
            
            func = UniversalFunction(
                name=func_name,
                parameters=parameters,
                return_type=return_type,
                source_language="swift",
                source_code=match.group(0),
                implementation_hints={
                    'control_flow': self._extract_control_flow(body)
                }
            )
            
            if self.current_module is not None:
                self.current_module.functions.append(func)
    
    def _parse_swift_parameters(self, params_str: str) -> List[Parameter]:
        """Parse Swift function parameters."""
        parameters = []
        if not params_str.strip():
            return parameters
        
        parts = [p.strip() for p in params_str.split(',') if p.strip()]
        
        for part in parts:
            # Handle external and internal parameter names
            # format: externalName internalName: Type = default
            
            if ':' in part:
                name_part, type_part = part.split(':', 1)
                
                # Extract parameter name(s)
                name_tokens = name_part.strip().split()
                if len(name_tokens) == 1:
                    name = name_tokens[0]
                elif len(name_tokens) == 2:
                    name = name_tokens[1]  # Use internal name
                else:
                    name = name_tokens[-1] if name_tokens else 'param'
                
                # Handle default value
                default = None
                if '=' in type_part:
                    type_str, default = type_part.split('=', 1)
                    type_str = type_str.strip()
                    default = default.strip()
                else:
                    type_str = type_part.strip()
                
                parameters.append(Parameter(
                    name=name,
                    type_sig=self._parse_swift_type(type_str),
                    required=default is None,
                    default_value=default
                ))
        
        return parameters
    
    def _parse_swift_type(self, type_str: Optional[str]) -> TypeSignature:
        """Parse Swift type into UIR TypeSignature."""
        if not type_str:
            return TypeSignature(DataType.VOID)
        
        type_str = type_str.strip()
        
        # Handle optional types
        if type_str.endswith('?') or type_str.endswith('!'):
            type_str = type_str[:-1]
        
        # Handle arrays [Type]
        if type_str.startswith('[') and type_str.endswith(']'):
            return TypeSignature(DataType.ARRAY)
        
        # Handle generics
        if '<' in type_str:
            base_type = type_str.split('<')[0]
            if base_type in ['Array', 'Set']:
                return TypeSignature(DataType.ARRAY)
            if base_type in ['Dictionary', 'Dict']:
                return TypeSignature(DataType.OBJECT)
        
        type_mapping = {
            'Void': DataType.VOID,
            '()': DataType.VOID,
            'Bool': DataType.BOOLEAN,
            'Int': DataType.INTEGER,
            'Int8': DataType.INTEGER,
            'Int16': DataType.INTEGER,
            'Int32': DataType.INTEGER,
            'Int64': DataType.INTEGER,
            'UInt': DataType.INTEGER,
            'UInt8': DataType.INTEGER,
            'UInt16': DataType.INTEGER,
            'UInt32': DataType.INTEGER,
            'UInt64': DataType.INTEGER,
            'Float': DataType.FLOAT,
            'Double': DataType.FLOAT,
            'CGFloat': DataType.FLOAT,
            'String': DataType.STRING,
            'Character': DataType.STRING,
            'Any': DataType.ANY,
            'AnyObject': DataType.OBJECT,
        }
        
        return TypeSignature(type_mapping.get(type_str, DataType.OBJECT))
    
    def _extract_control_flow(self, body: str) -> List[Dict[str, Any]]:
        """Extract control flow structures from function body."""
        control_flow = []
        
        if not body:
            return control_flow
        
        patterns = [
            (r'if\s+[^{]+\{', 'if_condition'),
            (r'guard\s+[^{]+\{', 'guard'),
            (r'switch\s+[^{]+\{', 'switch'),
            (r'for\s+[^{]+\{', 'for_loop'),
            (r'while\s+[^{]+\{', 'while_loop'),
            (r'do\s*\{', 'do_catch'),
        ]
        
        for pattern, kind in patterns:
            for match in re.finditer(pattern, body):
                control_flow.append({
                    'kind': kind,
                    'source_code': match.group(0),
                    'lineno': body[:match.start()].count('\n') + 1
                })
        
        return control_flow


class SwiftTypeInference:
    """Infers types from Swift code patterns."""
    
    def infer_type(self, value: str) -> TypeSignature:
        """Infer type from a value expression."""
        if not value:
            return TypeSignature(DataType.ANY)
        
        value = value.strip()
        
        if value.startswith('"') or value.startswith('"""'):
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
