"""
Lua to Universal IR Parser.

This module parses Lua code and converts it to Universal Intermediate Representation.
"""

import re
from typing import Dict, List, Optional, Any
from .universal_ir import (
    UniversalProject, UniversalModule, UniversalFunction, UniversalClass,
    UniversalVariable, Parameter, TypeSignature, DataType, SemanticDescription,
    Contract, PurityLevel
)


class LuaParser:
    """Parses Lua code into Universal IR."""
    
    def __init__(self):
        self.current_module: Optional[UniversalModule] = None
        self.type_inference = LuaTypeInference()
    
    def parse_code(self, lua_code: str, filename: str = "unknown.lua") -> UniversalModule:
        """Parse Lua code into a Universal Module."""
        module = UniversalModule(
            name=filename.replace('.lua', ''),
            source_language="lua",
            source_file=filename
        )
        
        self.current_module = module
        
        # Parse Lua constructs
        self._parse_requires(lua_code)
        self._parse_functions(lua_code)
        self._parse_local_functions(lua_code)
        self._parse_table_constructors(lua_code)
        self._parse_variables(lua_code)
        
        return module

    def _parse_requires(self, code: str):
        """Parse require statements (Lua's module import mechanism)."""
        if self.current_module is None:
            return
        # local X = require("module")  or  local X = require 'module'  or  local X = require "module"
        req_assign_pattern = r'''^\s*(local\s+\w+\s*=\s*require\s*\(\s*['"][^'"]+['"]\s*\))'''
        for m in re.finditer(req_assign_pattern, code, re.MULTILINE):
            self.current_module.imports.append(m.group(1).strip())
        # local X = require 'module' (no parens)
        req_assign_noparen = r"""^\s*(local\s+\w+\s*=\s*require\s+['"][^'"]+['"])"""
        for m in re.finditer(req_assign_noparen, code, re.MULTILINE):
            stmt = m.group(1).strip()
            if stmt not in self.current_module.imports:
                self.current_module.imports.append(stmt)
        # Bare require("module") or require 'module'
        req_bare_pattern = r'''^\s*(require\s*\(\s*['"][^'"]+['"]\s*\))'''
        for m in re.finditer(req_bare_pattern, code, re.MULTILINE):
            stmt = m.group(1).strip()
            if stmt not in self.current_module.imports:
                self.current_module.imports.append(stmt)
        req_bare_noparen = r"""^\s*(require\s+['"][^'"]+['"])"""
        for m in re.finditer(req_bare_noparen, code, re.MULTILINE):
            stmt = m.group(1).strip()
            if stmt not in self.current_module.imports:
                self.current_module.imports.append(stmt)
    
    def _parse_functions(self, code: str):
        """Parse Lua function declarations."""
        # Match: function name(params) body end
        func_pattern = r'function\s+(\w+(?:\.\w+)*)\s*\(([^)]*)\)(.*?)end'
        functions = re.finditer(func_pattern, code, re.MULTILINE | re.DOTALL)
        
        for match in functions:
            func_name = match.group(1)
            params_str = match.group(2)
            body = match.group(3)
            
            # Check if this is a method (contains : or is inside a table)
            is_method = ':' in func_name or ('.' in func_name and 'self' in params_str)
            
            parameters = self._parse_lua_parameters(params_str)
            return_type = self.type_inference.infer_return_type(body)
            
            func = UniversalFunction(
                name=func_name,
                parameters=parameters,
                return_type=return_type,
                source_language="lua",
                source_code=match.group(0),
                implementation_hints={
                    'is_method': is_method,
                    'is_local': False,
                    'control_flow': self._extract_control_flow(body)
                }
            )
            
            if self.current_module is not None:
                self.current_module.functions.append(func)
    
    def _parse_local_functions(self, code: str):
        """Parse local function declarations."""
        # Match: local function name(params) body end
        local_func_pattern = r'local\s+function\s+(\w+)\s*\(([^)]*)\)(.*?)end'
        functions = re.finditer(local_func_pattern, code, re.MULTILINE | re.DOTALL)
        
        for match in functions:
            func_name = match.group(1)
            params_str = match.group(2)
            body = match.group(3)
            
            parameters = self._parse_lua_parameters(params_str)
            return_type = self.type_inference.infer_return_type(body)
            
            func = UniversalFunction(
                name=func_name,
                parameters=parameters,
                return_type=return_type,
                source_language="lua",
                source_code=match.group(0),
                implementation_hints={
                    'is_local': True,
                    'control_flow': self._extract_control_flow(body)
                }
            )
            
            if self.current_module is not None:
                self.current_module.functions.append(func)
        
        # Also match: local name = function(params) body end
        anon_func_pattern = r'local\s+(\w+)\s*=\s*function\s*\(([^)]*)\)(.*?)end'
        anon_functions = re.finditer(anon_func_pattern, code, re.MULTILINE | re.DOTALL)
        
        for match in anon_functions:
            func_name = match.group(1)
            params_str = match.group(2)
            body = match.group(3)
            
            parameters = self._parse_lua_parameters(params_str)
            return_type = self.type_inference.infer_return_type(body)
            
            func = UniversalFunction(
                name=func_name,
                parameters=parameters,
                return_type=return_type,
                source_language="lua",
                source_code=match.group(0),
                implementation_hints={
                    'is_local': True,
                    'is_anonymous': True,
                    'control_flow': self._extract_control_flow(body)
                }
            )
            
            if self.current_module is not None:
                self.current_module.functions.append(func)
    
    def _parse_table_constructors(self, code: str):
        """Parse Lua table constructors that act as classes/objects."""
        # Match: Name = {} followed by methods
        table_pattern = r'(\w+)\s*=\s*\{\s*\}'
        tables = list(re.finditer(table_pattern, code))
        
        for match in tables:
            table_name = match.group(1)
            
            # Skip if it's a local variable assignment without methods
            if not re.search(rf'function\s+{table_name}[.:]', code):
                continue
            
            # Create a class for table-based OOP
            cls = UniversalClass(
                name=table_name,
                source_language="lua"
            )
            
            cls.implementation_hints = {'is_table_class': True}
            
            # Find all methods attached to this table
            method_pattern = rf'function\s+{table_name}[.:](\w+)\s*\(([^)]*)\)(.*?)end'
            methods = re.finditer(method_pattern, code, re.MULTILINE | re.DOTALL)
            
            for method_match in methods:
                method_name = method_match.group(1)
                params_str = method_match.group(2)
                body = method_match.group(3)
                
                # Colon syntax implies self parameter
                is_colon_method = f'{table_name}:{method_name}' in code
                
                parameters = self._parse_lua_parameters(params_str)
                return_type = self.type_inference.infer_return_type(body)
                
                method = UniversalFunction(
                    name=method_name,
                    parameters=parameters,
                    return_type=return_type,
                    source_language="lua",
                    source_code=method_match.group(0),
                    implementation_hints={
                        'is_colon_method': is_colon_method,
                        'is_constructor': method_name == 'new' or method_name == 'create',
                        'control_flow': self._extract_control_flow(body)
                    }
                )
                
                cls.methods.append(method)
            
            if cls.methods:
                if self.current_module is not None:
                    self.current_module.classes.append(cls)
    
    def _parse_variables(self, code: str):
        """Parse Lua variable declarations."""
        # Global variables
        global_var_pattern = r'^(\w+)\s*=\s*([^=\n][^\n]*)(?:\n|$)'
        
        for match in re.finditer(global_var_pattern, code, re.MULTILINE):
            var_name = match.group(1)
            value = match.group(2).strip()
            
            # Skip function definitions and table classes
            if value.startswith('function') or value == '{}':
                continue
            
            # Skip if this looks like a control statement
            if var_name in ['if', 'for', 'while', 'repeat', 'end', 'else', 'elseif', 'then', 'do', 'local', 'return']:
                continue
            
            var = UniversalVariable(
                name=var_name,
                type_sig=self.type_inference.infer_type(value),
                value=value,
                is_constant=False,
                source_language="lua"
            )
            
            if self.current_module is not None:
                self.current_module.variables.append(var)
        
        # Local variables  
        local_var_pattern = r'local\s+(\w+)\s*=\s*([^\n]+)'
        
        for match in re.finditer(local_var_pattern, code):
            var_name = match.group(1)
            value = match.group(2).strip()
            
            # Skip function definitions
            if value.startswith('function'):
                continue
            
            var = UniversalVariable(
                name=var_name,
                type_sig=self.type_inference.infer_type(value),
                value=value,
                is_constant=False,
                source_language="lua"
            )
            var.implementation_hints = {'is_local': True}
            
            if self.current_module is not None:
                self.current_module.variables.append(var)
    
    def _parse_lua_parameters(self, params_str: str) -> List[Parameter]:
        """Parse Lua function parameters."""
        parameters = []
        if not params_str.strip():
            return parameters
        
        for param in params_str.split(','):
            param = param.strip()
            if not param:
                continue
            
            # Handle varargs
            if param == '...':
                parameters.append(Parameter(
                    name='...',
                    type_sig=TypeSignature(DataType.ARRAY),
                    required=False
                ))
            else:
                # Lua parameters don't have types
                parameters.append(Parameter(
                    name=param,
                    type_sig=TypeSignature(DataType.ANY),
                    required=True
                ))
        
        return parameters
    
    def _extract_control_flow(self, body: str) -> List[Dict[str, Any]]:
        """Extract control flow structures from function body."""
        control_flow = []
        
        if not body:
            return control_flow
        
        # Find if statements
        if_pattern = r'if\s+.+\s+then'
        for match in re.finditer(if_pattern, body):
            control_flow.append({
                'kind': 'if_condition',
                'source_code': match.group(0),
                'lineno': body[:match.start()].count('\n') + 1
            })
        
        # Find for loops
        for_patterns = [
            (r'for\s+\w+\s*=\s*[^,]+,\s*[^,]+(?:,\s*[^\s]+)?\s+do', 'for_loop'),  # numeric for
            (r'for\s+\w+(?:\s*,\s*\w+)?\s+in\s+.+\s+do', 'for_loop'),  # generic for
        ]
        
        for pattern, kind in for_patterns:
            for match in re.finditer(pattern, body):
                control_flow.append({
                    'kind': kind,
                    'source_code': match.group(0),
                    'lineno': body[:match.start()].count('\n') + 1
                })
        
        # Find while loops
        while_pattern = r'while\s+.+\s+do'
        for match in re.finditer(while_pattern, body):
            control_flow.append({
                'kind': 'while_loop',
                'source_code': match.group(0),
                'lineno': body[:match.start()].count('\n') + 1
            })
        
        # Find repeat-until
        repeat_pattern = r'repeat\s'
        for match in re.finditer(repeat_pattern, body):
            control_flow.append({
                'kind': 'while_loop',
                'source_code': match.group(0),
                'lineno': body[:match.start()].count('\n') + 1
            })
        
        return control_flow


class LuaTypeInference:
    """Infers types from Lua code patterns."""
    
    def infer_return_type(self, body: str) -> TypeSignature:
        """Infer return type from function body."""
        if not body:
            return TypeSignature(DataType.ANY)
        
        # Check for return statements
        return_pattern = r'return\s+([^\n]+)'
        returns = re.findall(return_pattern, body)
        
        if not returns:
            return TypeSignature(DataType.VOID)
        
        last_return = returns[-1].strip()
        
        # Multiple return values
        if ',' in last_return:
            return TypeSignature(DataType.ARRAY)
        
        return self.infer_type(last_return)
    
    def infer_type(self, value: str) -> TypeSignature:
        """Infer type from a value expression."""
        if not value:
            return TypeSignature(DataType.ANY)
        
        value = value.strip()
        
        # String literals
        if value.startswith('"') or value.startswith("'") or value.startswith('[['):
            return TypeSignature(DataType.STRING)
        
        # Boolean
        if value in ['true', 'false']:
            return TypeSignature(DataType.BOOLEAN)
        
        # Nil
        if value == 'nil':
            return TypeSignature(DataType.ANY)
        
        # Table constructor
        if value.startswith('{'):
            return TypeSignature(DataType.OBJECT)
        
        # Number
        if re.match(r'^-?\d+(\.\d+)?$', value):
            if '.' in value:
                return TypeSignature(DataType.FLOAT)
            return TypeSignature(DataType.INTEGER)
        
        # Hexadecimal
        if re.match(r'^0x[0-9a-fA-F]+$', value):
            return TypeSignature(DataType.INTEGER)
        
        # Function
        if value.startswith('function'):
            return TypeSignature(DataType.FUNCTION)
        
        return TypeSignature(DataType.ANY)
