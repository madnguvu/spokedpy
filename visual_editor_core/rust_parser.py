"""
Rust to Universal IR Parser.

This module parses Rust code and converts it to Universal Intermediate Representation.
"""

import re
from typing import Dict, List, Optional, Any
from .universal_ir import (
    UniversalProject, UniversalModule, UniversalFunction, UniversalClass,
    UniversalVariable, Parameter, TypeSignature, DataType, SemanticDescription,
    Contract, PurityLevel
)


class RustParser:
    """Parses Rust code into Universal IR."""
    
    def __init__(self):
        self.current_module: Optional[UniversalModule] = None
        self.type_inference = RustTypeInference()
    
    def parse_code(self, rust_code: str, filename: str = "lib.rs") -> UniversalModule:
        """Parse Rust code into a Universal Module."""
        module = UniversalModule(
            name=filename.replace('.rs', ''),
            source_language="rust",
            source_file=filename
        )
        
        self.current_module = module
        
        # Parse Rust constructs
        self._parse_crate_info(rust_code)
        self._parse_use_statements(rust_code)
        self._parse_traits(rust_code)
        self._parse_structs(rust_code)
        self._parse_enums(rust_code)
        self._parse_impl_blocks(rust_code)
        self._parse_functions(rust_code)
        self._parse_constants(rust_code)
        
        return module
    
    def _parse_crate_info(self, code: str):
        """Parse crate-level attributes."""
        crate_pattern = r'//!\s*(.+)'
        matches = re.findall(crate_pattern, code)
        if matches:
            pass  # Documentation
    
    def _parse_use_statements(self, code: str):
        """Parse use statements."""
        use_pattern = r'use\s+([^;]+);'
        uses = re.findall(use_pattern, code)
        # Store for dependency strategy pipeline
        if uses and self.current_module is not None:
            for u in uses:
                self.current_module.imports.append(f"use {u.strip()};")
    
    def _parse_traits(self, code: str):
        """Parse Rust trait declarations."""
        trait_pattern = r'(?:pub\s+)?trait\s+(\w+)(?:<[^>]+>)?(?:\s*:\s*[^{]+)?\s*\{([^}]*(?:\{[^}]*\}[^}]*)*)\}'
        traits = re.finditer(trait_pattern, code, re.MULTILINE | re.DOTALL)
        
        for match in traits:
            trait_name = match.group(1)
            body = match.group(2)
            
            cls = UniversalClass(
                name=trait_name,
                source_language="rust"
            )
            
            cls.implementation_hints = {'is_trait': True}
            
            # Parse trait methods
            method_pattern = r'fn\s+(\w+)\s*\(([^)]*)\)(?:\s*->\s*([^;{]+))?'
            methods = re.finditer(method_pattern, body)
            
            for method_match in methods:
                method_name = method_match.group(1)
                params_str = method_match.group(2)
                return_type_str = method_match.group(3)
                
                parameters = self._parse_rust_parameters(params_str)
                return_type = self._parse_rust_type(return_type_str.strip() if return_type_str else None)
                
                method = UniversalFunction(
                    name=method_name,
                    parameters=parameters,
                    return_type=return_type,
                    source_language="rust",
                    implementation_hints={'is_trait_method': True}
                )
                
                cls.methods.append(method)
            
            if self.current_module is not None:
                self.current_module.classes.append(cls)
    
    def _parse_structs(self, code: str):
        """Parse Rust struct declarations."""
        struct_pattern = r'(?:pub(?:\([^)]+\))?\s+)?struct\s+(\w+)(?:<[^>]+>)?\s*\{([^}]*)\}'
        structs = re.finditer(struct_pattern, code, re.MULTILINE | re.DOTALL)
        
        for match in structs:
            struct_name = match.group(1)
            body = match.group(2)
            
            cls = UniversalClass(
                name=struct_name,
                source_language="rust"
            )
            
            cls.implementation_hints = {'is_struct': True}
            
            # Parse struct fields
            field_pattern = r'(?:pub(?:\([^)]+\))?\s+)?(\w+)\s*:\s*([^,\n]+)'
            fields = re.finditer(field_pattern, body)
            
            for field_match in fields:
                field_name = field_match.group(1)
                field_type = field_match.group(2).strip().rstrip(',')
            
            if self.current_module is not None:
                self.current_module.classes.append(cls)
    
    def _parse_enums(self, code: str):
        """Parse Rust enum declarations."""
        enum_pattern = r'(?:pub(?:\([^)]+\))?\s+)?enum\s+(\w+)(?:<[^>]+>)?\s*\{([^}]*)\}'
        enums = re.finditer(enum_pattern, code, re.MULTILINE | re.DOTALL)
        
        for match in enums:
            enum_name = match.group(1)
            body = match.group(2)
            
            cls = UniversalClass(
                name=enum_name,
                source_language="rust"
            )
            
            cls.implementation_hints = {'is_enum': True}
            
            # Parse enum variants
            variant_pattern = r'(\w+)(?:\s*\{[^}]*\}|\s*\([^)]*\))?'
            variants = re.findall(variant_pattern, body)
            cls.implementation_hints['variants'] = [v for v in variants if v]
            
            if self.current_module is not None:
                self.current_module.classes.append(cls)
    
    def _parse_impl_blocks(self, code: str):
        """Parse Rust impl blocks."""
        impl_pattern = r'impl(?:<[^>]+>)?\s+(?:(\w+)\s+for\s+)?(\w+)(?:<[^>]+>)?\s*\{([^}]*(?:\{[^}]*\}[^}]*)*)\}'
        impls = re.finditer(impl_pattern, code, re.MULTILINE | re.DOTALL)
        
        for match in impls:
            trait_name = match.group(1)
            struct_name = match.group(2)
            body = match.group(3)
            
            # Parse methods in impl block
            method_pattern = r'(?:pub(?:\([^)]+\))?\s+)?fn\s+(\w+)\s*\(([^)]*)\)(?:\s*->\s*([^{]+))?\s*\{([^}]*(?:\{[^}]*\}[^}]*)*)\}'
            methods = re.finditer(method_pattern, body, re.MULTILINE | re.DOTALL)
            
            for method_match in methods:
                method_name = method_match.group(1)
                params_str = method_match.group(2)
                return_type_str = method_match.group(3)
                method_body = method_match.group(4)
                
                parameters = self._parse_rust_parameters(params_str)
                return_type = self._parse_rust_type(return_type_str.strip() if return_type_str else None)
                
                # Check if it's a constructor (new method)
                is_constructor = method_name == 'new'
                
                # Check if first param is self
                has_self = any(p.name in ['self', '&self', '&mut self'] for p in parameters)
                
                method = UniversalFunction(
                    name=method_name,
                    parameters=[p for p in parameters if p.name not in ['self', '&self', '&mut self']],
                    return_type=return_type,
                    source_language="rust",
                    source_code=method_match.group(0),
                    implementation_hints={
                        'is_constructor': is_constructor,
                        'is_method': has_self,
                        'trait_impl': trait_name,
                        'control_flow': self._extract_control_flow(method_body)
                    }
                )
                
                # Find the struct and add method
                if self.current_module is not None:
                    for cls in self.current_module.classes:
                        if cls.name == struct_name:
                            cls.methods.append(method)
                            break
    
    def _parse_functions(self, code: str):
        """Parse Rust standalone function declarations."""
        func_pattern = r'(?:pub(?:\([^)]+\))?\s+)?fn\s+(\w+)\s*\(([^)]*)\)(?:\s*->\s*([^{]+))?\s*\{([^}]*(?:\{[^}]*\}[^}]*)*)\}'
        functions = re.finditer(func_pattern, code, re.MULTILINE | re.DOTALL)
        
        for match in functions:
            func_name = match.group(1)
            params_str = match.group(2)
            return_type_str = match.group(3)
            body = match.group(4)
            
            # Skip if this is inside an impl block (heuristic: check if 'self' in params)
            if '&self' in params_str or '&mut self' in params_str or params_str.strip().startswith('self'):
                continue
            
            parameters = self._parse_rust_parameters(params_str)
            return_type = self._parse_rust_type(return_type_str.strip() if return_type_str else None)
            
            func = UniversalFunction(
                name=func_name,
                parameters=parameters,
                return_type=return_type,
                source_language="rust",
                source_code=match.group(0),
                implementation_hints={
                    'control_flow': self._extract_control_flow(body)
                }
            )
            
            if self.current_module is not None:
                self.current_module.functions.append(func)
    
    def _parse_constants(self, code: str):
        """Parse Rust constant declarations."""
        const_pattern = r'const\s+(\w+)\s*:\s*([^=]+)\s*=\s*([^;]+);'
        constants = re.finditer(const_pattern, code)
        
        for match in constants:
            const_name = match.group(1)
            const_type = match.group(2).strip()
            value = match.group(3).strip()
            
            var = UniversalVariable(
                name=const_name,
                type_sig=self._parse_rust_type(const_type),
                value=value,
                is_constant=True,
                source_language="rust"
            )
            
            if self.current_module is not None:
                self.current_module.variables.append(var)
    
    def _parse_rust_parameters(self, params_str: str) -> List[Parameter]:
        """Parse Rust function parameters."""
        parameters = []
        if not params_str.strip():
            return parameters
        
        # Handle self parameter
        if '&mut self' in params_str:
            parameters.append(Parameter(
                name='&mut self',
                type_sig=TypeSignature(DataType.OBJECT),
                required=True
            ))
            params_str = params_str.replace('&mut self', '').strip().lstrip(',')
        elif '&self' in params_str:
            parameters.append(Parameter(
                name='&self',
                type_sig=TypeSignature(DataType.OBJECT),
                required=True
            ))
            params_str = params_str.replace('&self', '').strip().lstrip(',')
        elif params_str.strip().startswith('self'):
            parameters.append(Parameter(
                name='self',
                type_sig=TypeSignature(DataType.OBJECT),
                required=True
            ))
            params_str = params_str.replace('self', '', 1).strip().lstrip(',')
        
        # Parse remaining parameters
        if params_str.strip():
            parts = [p.strip() for p in params_str.split(',') if p.strip()]
            
            for part in parts:
                if ':' in part:
                    name_part, type_part = part.split(':', 1)
                    name = name_part.strip()
                    type_str = type_part.strip()
                    
                    parameters.append(Parameter(
                        name=name,
                        type_sig=self._parse_rust_type(type_str),
                        required=True
                    ))
        
        return parameters
    
    def _parse_rust_type(self, type_str: Optional[str]) -> TypeSignature:
        """Parse Rust type into UIR TypeSignature."""
        if not type_str:
            return TypeSignature(DataType.VOID)
        
        type_str = type_str.strip()
        
        # Handle references
        if type_str.startswith('&'):
            type_str = type_str.lstrip('&').strip()
            if type_str.startswith('mut '):
                type_str = type_str[4:].strip()
        
        # Handle Result/Option
        if type_str.startswith('Result<') or type_str.startswith('Option<'):
            return TypeSignature(DataType.ANY)
        
        # Handle Vec
        if type_str.startswith('Vec<'):
            return TypeSignature(DataType.ARRAY)
        
        # Handle HashMap/BTreeMap
        if 'Map<' in type_str:
            return TypeSignature(DataType.OBJECT)
        
        type_mapping = {
            'bool': DataType.BOOLEAN,
            'i8': DataType.INTEGER,
            'i16': DataType.INTEGER,
            'i32': DataType.INTEGER,
            'i64': DataType.INTEGER,
            'i128': DataType.INTEGER,
            'isize': DataType.INTEGER,
            'u8': DataType.INTEGER,
            'u16': DataType.INTEGER,
            'u32': DataType.INTEGER,
            'u64': DataType.INTEGER,
            'u128': DataType.INTEGER,
            'usize': DataType.INTEGER,
            'f32': DataType.FLOAT,
            'f64': DataType.FLOAT,
            'str': DataType.STRING,
            'String': DataType.STRING,
            '()': DataType.VOID,
            'Self': DataType.OBJECT,
        }
        
        return TypeSignature(type_mapping.get(type_str, DataType.OBJECT))
    
    def _extract_control_flow(self, body: str) -> List[Dict[str, Any]]:
        """Extract control flow structures from function body."""
        control_flow = []
        
        if not body:
            return control_flow
        
        patterns = [
            (r'if\s+[^{]+\{', 'if_condition'),
            (r'for\s+[^{]+\{', 'for_loop'),
            (r'while\s+[^{]+\{', 'while_loop'),
            (r'loop\s*\{', 'infinite_loop'),
            (r'match\s+[^{]+\{', 'switch'),
        ]
        
        for pattern, kind in patterns:
            for match in re.finditer(pattern, body):
                control_flow.append({
                    'kind': kind,
                    'source_code': match.group(0),
                    'lineno': body[:match.start()].count('\n') + 1
                })
        
        return control_flow


class RustTypeInference:
    """Infers types from Rust code patterns."""
    
    def infer_type(self, value: str) -> TypeSignature:
        """Infer type from a value expression."""
        if not value:
            return TypeSignature(DataType.ANY)
        
        value = value.strip()
        
        if value.startswith('"'):
            return TypeSignature(DataType.STRING)
        if value in ['true', 'false']:
            return TypeSignature(DataType.BOOLEAN)
        if re.match(r'^-?\d+$', value):
            return TypeSignature(DataType.INTEGER)
        if re.match(r'^-?\d+\.\d+$', value):
            return TypeSignature(DataType.FLOAT)
        
        return TypeSignature(DataType.ANY)
