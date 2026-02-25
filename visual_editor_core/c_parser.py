"""
C to Universal IR Parser.

This module parses C code and converts it to Universal Intermediate Representation.
"""

import re
from typing import Dict, List, Optional, Any
from .universal_ir import (
    UniversalProject, UniversalModule, UniversalFunction, UniversalClass,
    UniversalVariable, Parameter, TypeSignature, DataType, SemanticDescription,
    Contract, PurityLevel
)


class CParser:
    """Parses C code into Universal IR."""
    
    def __init__(self):
        self.current_module = None
        self.type_inference = CTypeInference()
    
    def parse_code(self, c_code: str, filename: str = "main.c") -> UniversalModule:
        """Parse C code into a Universal Module."""
        module = UniversalModule(
            name=filename.replace('.c', '').replace('.h', ''),
            source_language="c",
            source_file=filename
        )
        
        self.current_module = module
        
        # Parse C constructs
        self._parse_includes(c_code)
        self._parse_defines(c_code)
        self._parse_typedefs(c_code)
        self._parse_structs(c_code)
        self._parse_enums(c_code)
        self._parse_functions(c_code)
        self._parse_global_variables(c_code)
        
        return module
    
    def _parse_includes(self, code: str):
        """Parse #include directives."""
        include_pattern = r'#include\s*[<"]([^>"]+)[>"]'
        includes = re.findall(include_pattern, code)
        # Store in module.imports, preserving angle-bracket vs quote distinction
        if includes and self.current_module is not None:
            # Re-scan with a more detailed pattern to keep <> vs "" info
            detail_pattern = r'(#include\s*[<"][^>"]+[>"])'
            for m in re.finditer(detail_pattern, code):
                self.current_module.imports.append(m.group(1).strip())
    
    def _parse_defines(self, code: str):
        """Parse #define macros."""
        define_pattern = r'#define\s+(\w+)(?:\s+([^\n\\]+))?'
        defines = re.finditer(define_pattern, code)
        
        for match in defines:
            name = match.group(1)
            value = match.group(2)
            
            if value and self.current_module is not None:
                var = UniversalVariable(
                    name=name,
                    type_sig=self.type_inference.infer_type(value.strip()),
                    value=value.strip(),
                    is_constant=True,
                    source_language="c"
                )
                self.current_module.variables.append(var)
    
    def _parse_typedefs(self, code: str):
        """Parse typedef declarations."""
        typedef_pattern = r'typedef\s+(?:struct\s+)?(\w+)\s+(\w+)\s*;'
        typedefs = re.finditer(typedef_pattern, code)
    
    def _parse_structs(self, code: str):
        """Parse C struct declarations."""
        struct_pattern = r'(?:typedef\s+)?struct\s+(\w+)?\s*\{([^}]*)\}\s*(\w+)?;'
        structs = re.finditer(struct_pattern, code, re.MULTILINE | re.DOTALL)
        
        for match in structs:
            struct_name = match.group(1) or match.group(3)
            body = match.group(2)
            typedef_name = match.group(3)
            
            if not struct_name:
                continue
            
            cls = UniversalClass(
                name=struct_name,
                source_language="c"
            )
            
            cls.implementation_hints = {'is_struct': True}
            if typedef_name:
                cls.implementation_hints['typedef_name'] = typedef_name
            # always keep a list of fields in implementation_hints
            cls.implementation_hints["fields"] = []
            
            # Parse struct fields
            field_pattern = r'(\w+(?:\s*\*)*)\s+(\w+)(?:\[(\d+)\])?;'
            fields = re.finditer(field_pattern, body)
            
            for field_match in fields:
                field_type = field_match.group(1).strip()
                field_name = field_match.group(2)
                array_size = field_match.group(3)
                
                # Create UniversalVariable for each struct field
                field_var = UniversalVariable(
                    name=field_name,
                    type_sig=self._parse_c_type(field_type),
                    source_language="c"
                )
                # Store array size as an implementation hint if present
                if array_size is not None:
                    if field_var.implementation_hints is None:
                        field_var.implementation_hints = {}
                    field_var.implementation_hints["array_size"] = int(array_size)
                
                cls.implementation_hints["fields"].append(field_var)
            
            if self.current_module is not None:
                self.current_module.classes.append(cls)
    
    def _parse_enums(self, code: str):
        """Parse C enum declarations."""
        enum_pattern = r'(?:typedef\s+)?enum\s+(\w+)?\s*\{([^}]*)\}\s*(\w+)?;'
        enums = re.finditer(enum_pattern, code, re.MULTILINE | re.DOTALL)
        
        for match in enums:
            enum_name = match.group(1) or match.group(3)
            body = match.group(2)
            
            if not enum_name:
                continue
            
            cls = UniversalClass(
                name=enum_name,
                source_language="c"
            )
            
            cls.implementation_hints = {'is_enum': True}
            
            # Parse enum values
            value_pattern = r'(\w+)(?:\s*=\s*([^,\n]+))?'
            values = re.findall(value_pattern, body)
            cls.implementation_hints['values'] = [v[0] for v in values if v[0]]
            
            if self.current_module is not None:
                self.current_module.classes.append(cls)
    
    def _parse_functions(self, code: str):
        """Parse C function declarations and definitions."""
        # Function definition
        func_pattern = r'(?:static\s+)?(?:inline\s+)?(\w+(?:\s*\*)*)\s+(\w+)\s*\(([^)]*)\)\s*\{([^}]*(?:\{[^}]*\}[^}]*)*)\}'
        functions = re.finditer(func_pattern, code, re.MULTILINE | re.DOTALL)
        for match in functions:
            return_type_str = match.group(1).strip()
            func_name = match.group(2)
            params_str = match.group(3)
            body = match.group(4)
            
            parameters = self._parse_c_parameters(params_str)
            return_type = self._parse_c_type(return_type_str)
            
            is_static = 'static' in match.group(0)[:match.group(0).find(return_type_str)]
            
            func = UniversalFunction(
                name=func_name,
                parameters=parameters,
                return_type=return_type,
                source_language="c",
                source_code=match.group(0),
                implementation_hints={
                    'is_static': is_static,
                    'control_flow': self._extract_control_flow(body)
                }
            )
            
            if self.current_module is not None:
                self.current_module.functions.append(func)
    
    def _parse_global_variables(self, code: str):
        """Parse global variable declarations."""
        var_pattern = r'^(?:static\s+)?(?:const\s+)?(\w+(?:\s*\*)*)\s+(\w+)(?:\s*=\s*([^;]+))?;'
        variables = re.finditer(var_pattern, code, re.MULTILINE)
        for match in variables:
            type_str = match.group(1).strip()
            name = match.group(2)
            value = match.group(3)
            
            # Skip function-like matches
            if '(' in type_str:
                continue
            
            is_const = 'const' in match.group(0)
            
            if self.current_module is not None:
                var = UniversalVariable(
                    name=name,
                    type_sig=self._parse_c_type(type_str),
                    value=value.strip() if value is not None else None,
                    is_constant=is_const,
                    source_language="c"
                )
                self.current_module.variables.append(var)
    
    def _parse_c_parameters(self, params_str: str) -> List[Parameter]:
        """Parse C function parameters."""
        parameters = []
        if not params_str.strip() or params_str.strip() == 'void':
            return parameters
        
        parts = [p.strip() for p in params_str.split(',') if p.strip()]
        
        for part in parts:
            # Handle variadic
            if part == '...':
                parameters.append(Parameter(
                    name='...',
                    type_sig=TypeSignature(DataType.ANY),
                    required=False
                ))
                continue
            
            # Parse "type name" or "type *name"
            tokens = part.split()
            if len(tokens) >= 2:
                type_str = ' '.join(tokens[:-1])
                name = tokens[-1].lstrip('*')
                
                # Handle array notation
                if '[' in name:
                    name = name.split('[')[0]
                
                parameters.append(Parameter(
                    name=name,
                    type_sig=self._parse_c_type(type_str),
                    required=True
                ))
        
        return parameters
    
    def _parse_c_type(self, type_str: str) -> TypeSignature:
        """Parse C type into UIR TypeSignature."""
        if not type_str:
            return TypeSignature(DataType.VOID)
        
        type_str = type_str.strip()
        
        # Handle pointers
        is_pointer = '*' in type_str
        type_str = type_str.replace('*', '').strip()
        
        # Remove qualifiers
        for qualifier in ['const', 'static', 'volatile', 'unsigned', 'signed']:
            type_str = type_str.replace(qualifier, '').strip()
        
        type_mapping = {
            'void': DataType.VOID,
            'bool': DataType.BOOLEAN,
            '_Bool': DataType.BOOLEAN,
            'char': DataType.STRING if is_pointer else DataType.INTEGER,
            'short': DataType.INTEGER,
            'int': DataType.INTEGER,
            'long': DataType.INTEGER,
            'size_t': DataType.INTEGER,
            'float': DataType.FLOAT,
            'double': DataType.FLOAT,
        }
        
        return TypeSignature(type_mapping.get(type_str, DataType.OBJECT))
    
    def _extract_control_flow(self, body: str) -> List[Dict[str, Any]]:
        """Extract control flow structures from function body."""
        control_flow = []
        
        if not body:
            return control_flow
        
        patterns = [
            (r'if\s*\([^)]+\)', 'if_condition'),
            (r'else\s+if\s*\([^)]+\)', 'else_if'),
            (r'else\s*\{', 'else'),
            (r'for\s*\([^)]+\)', 'for_loop'),
            (r'while\s*\([^)]+\)', 'while_loop'),
            (r'do\s*\{', 'do_while_loop'),
            (r'switch\s*\([^)]+\)', 'switch'),
        ]
        
        for pattern, kind in patterns:
            for match in re.finditer(pattern, body):
                control_flow.append({
                    'kind': kind,
                    'source_code': match.group(0),
                    'lineno': body[:match.start()].count('\n') + 1
                })
        
        return control_flow


class CTypeInference:
    """Infers types from C code patterns."""
    
    def infer_type(self, value: str) -> TypeSignature:
        """Infer type from a value expression."""
        if not value:
            return TypeSignature(DataType.ANY)
        
        value = value.strip()
        
        if value.startswith('"'):
            return TypeSignature(DataType.STRING)
        if value.startswith("'"):
            return TypeSignature(DataType.INTEGER)
        if value in ['true', 'false', '1', '0']:
            return TypeSignature(DataType.BOOLEAN)
        if value == 'NULL':
            return TypeSignature(DataType.ANY)
        if re.match(r'^-?\d+[lLuU]*$', value):
            return TypeSignature(DataType.INTEGER)
        if re.match(r'^-?\d+\.\d+[fF]?$', value):
            return TypeSignature(DataType.FLOAT)
        if re.match(r'^0x[0-9a-fA-F]+$', value):
            return TypeSignature(DataType.INTEGER)
        
        return TypeSignature(DataType.ANY)
