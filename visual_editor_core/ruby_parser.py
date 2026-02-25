"""
Ruby to Universal IR Parser.

This module parses Ruby code and converts it to Universal Intermediate Representation.
"""

import re
from typing import Dict, List, Optional, Any
from .universal_ir import (
    UniversalProject, UniversalModule, UniversalFunction, UniversalClass,
    UniversalVariable, Parameter, TypeSignature, DataType, SemanticDescription,
    Contract, PurityLevel
)


class RubyParser:
    """Parses Ruby code into Universal IR."""
    
    def __init__(self):
        self.current_module: Optional[UniversalModule] = None
        self.type_inference = RubyTypeInference()
    
    def parse_code(self, ruby_code: str, filename: str = "unknown.rb") -> UniversalModule:
        """Parse Ruby code into a Universal Module."""
        module = UniversalModule(
            name=filename.replace('.rb', ''),
            source_language="ruby",
            source_file=filename
        )
        
        self.current_module = module
        
        # Parse Ruby constructs
        self._parse_requires(ruby_code)
        self._parse_modules(ruby_code)
        self._parse_classes(ruby_code)
        self._parse_methods(ruby_code)
        self._parse_constants(ruby_code)
        
        return module

    def _parse_requires(self, code: str):
        """Parse require / require_relative / load statements."""
        if self.current_module is None:
            return
        # require 'json'  or  require "json"
        req_pattern = r"^\s*(require(?:_relative)?\s+['\"][^'\"]+['\"])"
        for m in re.finditer(req_pattern, code, re.MULTILINE):
            self.current_module.imports.append(m.group(1).strip())
        # gem requires: require('json')
        req_paren_pattern = r"^\s*(require(?:_relative)?\s*\(['\"][^'\"]+['\"]\))"
        for m in re.finditer(req_paren_pattern, code, re.MULTILINE):
            self.current_module.imports.append(m.group(1).strip())
        # load 'file.rb'
        load_pattern = r"^\s*(load\s+['\"][^'\"]+['\"])"
        for m in re.finditer(load_pattern, code, re.MULTILINE):
            self.current_module.imports.append(m.group(1).strip())
    
    def _parse_modules(self, code: str):
        """Parse Ruby module declarations."""
        module_pattern = r'module\s+(\w+)\s*(.*?)^end'
        modules = re.finditer(module_pattern, code, re.MULTILINE | re.DOTALL)
        
        for match in modules:
            module_name = match.group(1)
            body = match.group(2)
            
            # Store module info in imports list as a marker
            if self.current_module is not None:
                self.current_module.imports.append(f"module:{module_name}")
    
    def _parse_classes(self, code: str):
        """Parse Ruby class declarations."""
        class_pattern = r'class\s+(\w+)(?:\s*<\s*(\w+(?:::\w+)*))?\s*(.*?)^end'
        classes = re.finditer(class_pattern, code, re.MULTILINE | re.DOTALL)
        
        for match in classes:
            class_name = match.group(1)
            base_class = match.group(2)
            body = match.group(3)
            
            cls = UniversalClass(
                name=class_name,
                source_language="ruby"
            )
            
            if base_class:
                cls.base_classes.append(base_class)
            
            # Parse class methods
            self._parse_class_methods(cls, body)
            
            # Parse attr_accessor, attr_reader, attr_writer
            self._parse_attr_accessors(cls, body)
            
            # Parse instance variables
            self._parse_instance_variables(cls, body)
            
            if self.current_module is not None:
                self.current_module.classes.append(cls)
    
    def _parse_class_methods(self, cls: UniversalClass, body: str):
        """Parse methods within a Ruby class."""
        # Match: def method_name(params) ... end
        method_pattern = r'def\s+(self\.)?(\w+[?!]?)(?:\s*\(([^)]*)\))?\s*(.*?)(?=\s*def\s|\s*end\s*$|\Z)'
        methods = re.finditer(method_pattern, body, re.MULTILINE | re.DOTALL)
        
        for match in methods:
            is_class_method = match.group(1) is not None
            method_name = match.group(2)
            params_str = match.group(3) or ""
            method_body = match.group(4)
            
            parameters = self._parse_ruby_parameters(params_str)
            return_type = self.type_inference.infer_return_type(method_body)
            
            method = UniversalFunction(
                name=method_name,
                parameters=parameters,
                return_type=return_type,
                source_language="ruby",
                source_code=match.group(0),
                implementation_hints={
                    'is_static': is_class_method,
                    'is_constructor': method_name == 'initialize',
                    'is_predicate': method_name.endswith('?'),
                    'is_bang': method_name.endswith('!'),
                    'visibility': self._determine_visibility(method_name, body),
                    'control_flow': self._extract_control_flow(method_body)
                }
            )
            
            cls.methods.append(method)
    
    def _parse_attr_accessors(self, cls: UniversalClass, body: str):
        """Parse attr_accessor, attr_reader, attr_writer declarations."""
        accessor_pattern = r'attr_(accessor|reader|writer)\s+([^\n]+)'
        accessors = re.finditer(accessor_pattern, body)
        
        for match in accessors:
            accessor_type = match.group(1)
            attrs_str = match.group(2)
            
            # Parse attribute symbols
            attr_pattern = r':(\w+)'
            attrs = re.findall(attr_pattern, attrs_str)
            
            for attr in attrs:
                # Create getter method if reader or accessor
                if accessor_type in ['reader', 'accessor']:
                    getter = UniversalFunction(
                        name=attr,
                        parameters=[],
                        return_type=TypeSignature(DataType.ANY),
                        source_language="ruby",
                        implementation_hints={
                            'is_accessor': True,
                            'accessor_type': 'getter'
                        }
                    )
                    cls.methods.append(getter)
                
                # Create setter method if writer or accessor
                if accessor_type in ['writer', 'accessor']:
                    setter = UniversalFunction(
                        name=f"{attr}=",
                        parameters=[Parameter(
                            name='value',
                            type_sig=TypeSignature(DataType.ANY),
                            required=True
                        )],
                        return_type=TypeSignature(DataType.ANY),
                        source_language="ruby",
                        implementation_hints={
                            'is_accessor': True,
                            'accessor_type': 'setter'
                        }
                    )
                    cls.methods.append(setter)
    
    def _parse_instance_variables(self, cls: UniversalClass, body: str):
        """Parse instance variable assignments in initialize method."""
        # Find @variable = assignments
        ivar_pattern = r'@(\w+)\s*='
        ivars = set(re.findall(ivar_pattern, body))
        
        for ivar in ivars:
            # Instance variables become properties
            pass  # Ruby properties are dynamic, tracked via methods
    
    def _parse_methods(self, code: str):
        """Parse top-level Ruby methods (outside classes)."""
        # Remove class bodies first
        code_without_classes = re.sub(r'class\s+\w+.*?^end', '', code, flags=re.MULTILINE | re.DOTALL)
        code_without_modules = re.sub(r'module\s+\w+.*?^end', '', code_without_classes, flags=re.MULTILINE | re.DOTALL)
        
        method_pattern = r'def\s+(\w+[?!]?)(?:\s*\(([^)]*)\))?\s*(.*?)^end'
        methods = re.finditer(method_pattern, code_without_modules, re.MULTILINE | re.DOTALL)
        
        for match in methods:
            method_name = match.group(1)
            params_str = match.group(2) or ""
            method_body = match.group(3)
            
            parameters = self._parse_ruby_parameters(params_str)
            return_type = self.type_inference.infer_return_type(method_body)
            
            func = UniversalFunction(
                name=method_name,
                parameters=parameters,
                return_type=return_type,
                source_language="ruby",
                source_code=match.group(0),
                implementation_hints={
                    'is_predicate': method_name.endswith('?'),
                    'is_bang': method_name.endswith('!'),
                    'control_flow': self._extract_control_flow(method_body)
                }
            )
            
            if self.current_module is not None:
                self.current_module.functions.append(func)
    
    def _parse_constants(self, code: str):
        """Parse Ruby constant declarations."""
        const_pattern = r'^([A-Z][A-Z0-9_]*)\s*=\s*(.+?)(?:\n|$)'
        constants = re.finditer(const_pattern, code, re.MULTILINE)
        
        for match in constants:
            const_name = match.group(1)
            value = match.group(2).strip()
            
            var = UniversalVariable(
                name=const_name,
                type_sig=self.type_inference.infer_type(value),
                value=value,
                is_constant=True,
                source_language="ruby"
            )
            
            if self.current_module is not None:
                self.current_module.variables.append(var)
    
    def _parse_ruby_parameters(self, params_str: str) -> List[Parameter]:
        """Parse Ruby method parameters."""
        parameters = []
        if not params_str.strip():
            return parameters
        
        for param in params_str.split(','):
            param = param.strip()
            if not param:
                continue
            
            # Handle different parameter types
            if param.startswith('**'):
                # Keyword splat
                name = param[2:]
                parameters.append(Parameter(
                    name=f'**{name}',
                    type_sig=TypeSignature(DataType.OBJECT),
                    required=False
                ))
            elif param.startswith('*'):
                # Splat operator
                name = param[1:]
                parameters.append(Parameter(
                    name=f'*{name}',
                    type_sig=TypeSignature(DataType.ARRAY),
                    required=False
                ))
            elif param.startswith('&'):
                # Block parameter
                name = param[1:]
                parameters.append(Parameter(
                    name=f'&{name}',
                    type_sig=TypeSignature(DataType.FUNCTION),
                    required=False
                ))
            elif '=' in param:
                # Default value
                name, default = param.split('=', 1)
                parameters.append(Parameter(
                    name=name.strip(),
                    type_sig=TypeSignature(DataType.ANY),
                    required=False,
                    default_value=default.strip()
                ))
            elif ':' in param:
                # Keyword argument
                name = param.rstrip(':')
                parameters.append(Parameter(
                    name=name,
                    type_sig=TypeSignature(DataType.ANY),
                    required=True
                ))
            else:
                # Regular parameter
                parameters.append(Parameter(
                    name=param,
                    type_sig=TypeSignature(DataType.ANY),
                    required=True
                ))
        
        return parameters
    
    def _determine_visibility(self, method_name: str, body: str) -> str:
        """Determine method visibility from Ruby visibility modifiers."""
        # Check for visibility modifiers before method
        if re.search(rf'private\s+:?{method_name}', body) or re.search(r'private\s+def\s+' + method_name, body):
            return 'private'
        if re.search(rf'protected\s+:?{method_name}', body):
            return 'protected'
        return 'public'
    
    def _extract_control_flow(self, body: str) -> List[Dict[str, Any]]:
        """Extract control flow structures from method body."""
        control_flow = []
        
        if not body:
            return control_flow
        
        # Find if/elsif/else
        if_pattern = r'if\s+.+'
        for match in re.finditer(if_pattern, body):
            control_flow.append({
                'kind': 'if_condition',
                'source_code': match.group(0),
                'lineno': body[:match.start()].count('\n') + 1
            })
        
        # Find unless
        unless_pattern = r'unless\s+.+'
        for match in re.finditer(unless_pattern, body):
            control_flow.append({
                'kind': 'if_condition',
                'source_code': match.group(0),
                'lineno': body[:match.start()].count('\n') + 1
            })
        
        # Find loops
        loop_patterns = [
            (r'while\s+.+', 'while_loop'),
            (r'until\s+.+', 'while_loop'),
            (r'for\s+\w+\s+in\s+.+', 'for_loop'),
            (r'\.each\s+do', 'for_loop'),
            (r'\.map\s+do', 'for_loop'),
            (r'\.times\s+do', 'for_loop'),
        ]
        
        for pattern, kind in loop_patterns:
            for match in re.finditer(pattern, body):
                control_flow.append({
                    'kind': kind,
                    'source_code': match.group(0),
                    'lineno': body[:match.start()].count('\n') + 1
                })
        
        # Find begin/rescue/ensure
        begin_pattern = r'begin\s'
        for match in re.finditer(begin_pattern, body):
            control_flow.append({
                'kind': 'try_except',
                'source_code': match.group(0),
                'lineno': body[:match.start()].count('\n') + 1
            })
        
        return control_flow


class RubyTypeInference:
    """Infers types from Ruby code patterns."""
    
    def infer_return_type(self, body: str) -> TypeSignature:
        """Infer return type from method body."""
        if not body:
            return TypeSignature(DataType.ANY)
        
        body = body.strip()
        
        # Ruby returns last expression - find it
        lines = [l.strip() for l in body.split('\n') if l.strip() and not l.strip().startswith('#')]
        
        if not lines:
            return TypeSignature(DataType.ANY)
        
        last_line = lines[-1]
        
        # Check for explicit return
        if last_line.startswith('return '):
            last_line = last_line[7:].strip()
        
        return self.infer_type(last_line)
    
    def infer_type(self, value: str) -> TypeSignature:
        """Infer type from a value expression."""
        if not value:
            return TypeSignature(DataType.ANY)
        
        value = value.strip()
        
        # String literals
        if value.startswith('"') or value.startswith("'") or value.startswith('%q') or value.startswith('%Q'):
            return TypeSignature(DataType.STRING)
        
        # Boolean
        if value in ['true', 'false']:
            return TypeSignature(DataType.BOOLEAN)
        
        # Nil
        if value == 'nil':
            return TypeSignature(DataType.ANY)
        
        # Array
        if value.startswith('[') or value.startswith('%w') or value.startswith('%i'):
            return TypeSignature(DataType.ARRAY)
        
        # Hash
        if value.startswith('{'):
            return TypeSignature(DataType.OBJECT)
        
        # Number
        if re.match(r'^-?\d+(\.\d+)?$', value):
            if '.' in value:
                return TypeSignature(DataType.FLOAT)
            return TypeSignature(DataType.INTEGER)
        
        # Symbol
        if value.startswith(':'):
            return TypeSignature(DataType.STRING)
        
        return TypeSignature(DataType.ANY)
