"""
R to Universal IR Parser.

This module parses R code and converts it to Universal Intermediate Representation.
R is a statistical computing language popular in data science.
"""

import re
from typing import Dict, List, Optional, Any
from .universal_ir import (
    UniversalProject, UniversalModule, UniversalFunction, UniversalClass,
    UniversalVariable, Parameter, TypeSignature, DataType, SemanticDescription,
    Contract, PurityLevel
)


class RParser:
    """Parses R code into Universal IR."""
    
    def __init__(self):
        self.current_module: Optional[UniversalModule] = None
        self.type_inference = RTypeInference()
    
    def parse_code(self, r_code: str, filename: str = "unknown.R") -> UniversalModule:
        """Parse R code into a Universal Module."""
        module = UniversalModule(
            name=filename.replace('.R', '').replace('.r', ''),
            source_language="r",
            source_file=filename
        )
        
        self.current_module = module
        
        # Parse R constructs
        self._parse_library_calls(r_code)
        self._parse_functions(r_code)
        self._parse_s4_classes(r_code)
        self._parse_r6_classes(r_code)
        self._parse_variables(r_code)
        
        return module

    def _parse_library_calls(self, code: str):
        """Parse library() / require() / source() calls — R's import mechanism."""
        if self.current_module is None:
            return
        # library(ggplot2)  or  library("ggplot2")
        lib_pattern = r'^\s*(library\s*\(\s*["\']?\w+["\']?\s*\))'
        for m in re.finditer(lib_pattern, code, re.MULTILINE):
            self.current_module.imports.append(m.group(1).strip())
        # require(dplyr)
        req_pattern = r'^\s*(require\s*\(\s*["\']?\w+["\']?\s*\))'
        for m in re.finditer(req_pattern, code, re.MULTILINE):
            self.current_module.imports.append(m.group(1).strip())
        # source("helpers.R")
        src_pattern = r"""^\s*(source\s*\(\s*['\"][^'\"]+['\"]\s*\))"""
        for m in re.finditer(src_pattern, code, re.MULTILINE):
            self.current_module.imports.append(m.group(1).strip())
    
    def _parse_functions(self, code: str):
        """Parse R function declarations."""
        # Match: name <- function(params) { body }
        func_pattern = r'(\w+)\s*<-\s*function\s*\(([^)]*)\)\s*\{([^}]*(?:\{[^}]*\}[^}]*)*)\}'
        functions = re.finditer(func_pattern, code, re.MULTILINE | re.DOTALL)
        
        for match in functions:
            func_name = match.group(1)
            params_str = match.group(2)
            body = match.group(3)
            
            parameters = self._parse_r_parameters(params_str)
            return_type = self.type_inference.infer_return_type(body)
            
            func = UniversalFunction(
                name=func_name,
                parameters=parameters,
                return_type=return_type,
                source_language="r",
                source_code=match.group(0),
                implementation_hints={
                    'control_flow': self._extract_control_flow(body),
                    'uses_tidyverse': self._detect_tidyverse(body)
                }
            )
            
            if self.current_module is not None:
                self.current_module.functions.append(func)
        
        # Also match = assignment style
        func_pattern_eq = r'(\w+)\s*=\s*function\s*\(([^)]*)\)\s*\{([^}]*(?:\{[^}]*\}[^}]*)*)\}'
        functions_eq = re.finditer(func_pattern_eq, code, re.MULTILINE | re.DOTALL)
        
        for match in functions_eq:
            func_name = match.group(1)
            params_str = match.group(2)
            body = match.group(3)
            
            # Skip if already parsed with <- or if module is None
            if self.current_module is None:
                continue
            if any(f.name == func_name for f in self.current_module.functions):
                continue
            
            parameters = self._parse_r_parameters(params_str)
            return_type = self.type_inference.infer_return_type(body)
            
            func = UniversalFunction(
                name=func_name,
                parameters=parameters,
                return_type=return_type,
                source_language="r",
                source_code=match.group(0),
                implementation_hints={
                    'control_flow': self._extract_control_flow(body),
                    'uses_tidyverse': self._detect_tidyverse(body)
                }
            )
            
            if self.current_module is not None:
                self.current_module.functions.append(func)
    
    def _parse_s4_classes(self, code: str):
        """Parse R S4 class definitions."""
        # Match: setClass("ClassName", ...)
        s4_pattern = r'setClass\s*\(\s*["\'](\w+)["\']\s*,([^)]+(?:\([^)]*\)[^)]*)*)\)'
        classes = re.finditer(s4_pattern, code, re.MULTILINE | re.DOTALL)
        
        for match in classes:
            class_name = match.group(1)
            class_def = match.group(2)
            
            cls = UniversalClass(
                name=class_name,
                source_language="r"
            )
            
            cls.implementation_hints = {'class_system': 'S4'}
            
            # Parse slots (like properties)
            slots_match = re.search(r'slots\s*=\s*c\(([^)]+)\)', class_def)
            if slots_match:
                slots_str = slots_match.group(1)
                slot_pattern = r'(\w+)\s*=\s*["\'](\w+)["\']'
                for slot_match in re.finditer(slot_pattern, slots_str):
                    slot_name = slot_match.group(1)
                    slot_type = slot_match.group(2)
                    # Store slot info in hints
            
            # Parse contains (inheritance)
            contains_match = re.search(r'contains\s*=\s*["\'](\w+)["\']', class_def)
            if contains_match:
                cls.base_classes.append(contains_match.group(1))
            
            if self.current_module is not None:
                self.current_module.classes.append(cls)
        
        # Parse setMethod definitions
        method_pattern = r'setMethod\s*\(\s*["\'](\w+)["\']\s*,\s*["\'](\w+)["\']\s*,\s*function\s*\(([^)]*)\)\s*\{([^}]*(?:\{[^}]*\}[^}]*)*)\}\s*\)'
        methods = re.finditer(method_pattern, code, re.MULTILINE | re.DOTALL)
        
        for match in methods:
            method_name = match.group(1)
            class_name = match.group(2)
            params_str = match.group(3)
            body = match.group(4)
            
            if self.current_module is None:
                continue
            
            # Find the class and add the method
            for cls in self.current_module.classes:
                if cls.name == class_name:
                    parameters = self._parse_r_parameters(params_str)
                    return_type = self.type_inference.infer_return_type(body)
                    
                    method = UniversalFunction(
                        name=method_name,
                        parameters=parameters,
                        return_type=return_type,
                        source_language="r",
                        source_code=match.group(0),
                        implementation_hints={'class_system': 'S4'}
                    )
                    
                    cls.methods.append(method)
                    break
    
    def _parse_r6_classes(self, code: str):
        """Parse R6 class definitions."""
        # Match: ClassName <- R6Class("ClassName", ...)
        r6_pattern = r'(\w+)\s*<-\s*R6Class\s*\(\s*["\'](\w+)["\']\s*,([^)]+(?:\([^)]*\)[^)]*)*)\)'
        classes = re.finditer(r6_pattern, code, re.MULTILINE | re.DOTALL)
        
        for match in classes:
            var_name = match.group(1)
            class_name = match.group(2)
            class_def = match.group(3)
            
            cls = UniversalClass(
                name=class_name,
                source_language="r"
            )
            
            cls.implementation_hints = {'class_system': 'R6'}
            
            # Parse inherit
            inherit_match = re.search(r'inherit\s*=\s*(\w+)', class_def)
            if inherit_match:
                cls.base_classes.append(inherit_match.group(1))
            
            # Parse public methods
            public_match = re.search(r'public\s*=\s*list\s*\(([^)]+(?:\([^)]*\)[^)]*)*)\)', class_def, re.DOTALL)
            if public_match:
                self._parse_r6_members(cls, public_match.group(1), 'public')
            
            # Parse private methods
            private_match = re.search(r'private\s*=\s*list\s*\(([^)]+(?:\([^)]*\)[^)]*)*)\)', class_def, re.DOTALL)
            if private_match:
                self._parse_r6_members(cls, private_match.group(1), 'private')
            
            if self.current_module is not None:
                self.current_module.classes.append(cls)
    
    def _parse_r6_members(self, cls: UniversalClass, members_str: str, visibility: str):
        """Parse R6 class members (methods and fields)."""
        # Parse methods: name = function(...) { ... }
        method_pattern = r'(\w+)\s*=\s*function\s*\(([^)]*)\)\s*\{([^}]*(?:\{[^}]*\}[^}]*)*)\}'
        methods = re.finditer(method_pattern, members_str, re.MULTILINE | re.DOTALL)
        
        for match in methods:
            method_name = match.group(1)
            params_str = match.group(2)
            body = match.group(3)
            
            parameters = self._parse_r_parameters(params_str)
            return_type = self.type_inference.infer_return_type(body)
            
            method = UniversalFunction(
                name=method_name,
                parameters=parameters,
                return_type=return_type,
                source_language="r",
                source_code=match.group(0),
                implementation_hints={
                    'visibility': visibility,
                    'is_constructor': method_name == 'initialize',
                    'class_system': 'R6',
                    'control_flow': self._extract_control_flow(body)
                }
            )
            
            cls.methods.append(method)
    
    def _parse_variables(self, code: str):
        """Parse R variable declarations."""
        # Match: name <- value or name = value (excluding functions)
        var_pattern = r'^(\w+)\s*(?:<-|=)\s*([^\n{]+)$'
        
        for match in re.finditer(var_pattern, code, re.MULTILINE):
            var_name = match.group(1)
            value = match.group(2).strip()
            
            # Skip function definitions
            if value.startswith('function') or 'R6Class' in value or 'setClass' in value:
                continue
            
            # Skip control keywords
            if var_name in ['if', 'else', 'for', 'while', 'repeat', 'function', 'in', 'next', 'break']:
                continue
            
            var = UniversalVariable(
                name=var_name,
                type_sig=self.type_inference.infer_type(value),
                value=value,
                is_constant=False,
                source_language="r"
            )
            
            if self.current_module is not None:
                self.current_module.variables.append(var)
    
    def _parse_r_parameters(self, params_str: str) -> List[Parameter]:
        """Parse R function parameters."""
        parameters = []
        if not params_str.strip():
            return parameters
        
        for param in params_str.split(','):
            param = param.strip()
            if not param:
                continue
            
            # Handle ... (varargs)
            if param == '...':
                p = Parameter(
                    name='...',
                    type_sig=TypeSignature(DataType.ARRAY),
                    required=False
                )
                parameters.append(p)
                continue
            
            # Handle default values
            if '=' in param:
                name, default = param.split('=', 1)
                default_val = default.strip()
                
                parameters.append(Parameter(
                    name=name.strip(),
                    type_sig=self.type_inference.infer_type(default_val),
                    required=False,
                    default_value=default_val
                ))
            else:
                parameters.append(Parameter(
                    name=param,
                    type_sig=TypeSignature(DataType.ANY),
                    required=True
                ))
        
        return parameters
    
    def _detect_tidyverse(self, body: str) -> bool:
        """Detect if function uses tidyverse packages."""
        tidyverse_patterns = [
            r'%>%',  # pipe operator
            r'\|>',  # native pipe
            r'mutate\s*\(',
            r'filter\s*\(',
            r'select\s*\(',
            r'group_by\s*\(',
            r'summarize\s*\(',
            r'summarise\s*\(',
            r'ggplot\s*\(',
        ]
        
        for pattern in tidyverse_patterns:
            if re.search(pattern, body):
                return True
        return False
    
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
        
        # Find repeat loops
        repeat_pattern = r'repeat\s*\{'
        for match in re.finditer(repeat_pattern, body):
            control_flow.append({
                'kind': 'while_loop',
                'source_code': match.group(0),
                'lineno': body[:match.start()].count('\n') + 1
            })
        
        # Find tryCatch
        try_pattern = r'tryCatch\s*\('
        for match in re.finditer(try_pattern, body):
            control_flow.append({
                'kind': 'try_except',
                'source_code': match.group(0),
                'lineno': body[:match.start()].count('\n') + 1
            })
        
        return control_flow


class RTypeInference:
    """Infers types from R code patterns."""
    
    def infer_return_type(self, body: str) -> TypeSignature:
        """Infer return type from function body."""
        if not body:
            return TypeSignature(DataType.ANY)
        
        # R returns the last expression or explicit return()
        # Check for explicit return
        return_pattern = r'return\s*\(([^)]+)\)'
        returns = re.findall(return_pattern, body)
        
        if returns:
            return self.infer_type(returns[-1].strip())
        
        # Check for invisible return
        invisible_pattern = r'invisible\s*\(([^)]+)\)'
        invisibles = re.findall(invisible_pattern, body)
        
        if invisibles:
            return self.infer_type(invisibles[-1].strip())
        
        # Get last expression (simplified)
        lines = [l.strip() for l in body.split('\n') if l.strip() and not l.strip().startswith('#')]
        if lines:
            return self.infer_type(lines[-1])
        
        return TypeSignature(DataType.ANY)
    
    def infer_type(self, value: str) -> TypeSignature:
        """Infer type from a value expression."""
        if not value:
            return TypeSignature(DataType.ANY)
        
        value = value.strip()
        
        # String literals
        if value.startswith('"') or value.startswith("'"):
            return TypeSignature(DataType.STRING)
        
        # Boolean
        if value in ['TRUE', 'FALSE', 'T', 'F']:
            return TypeSignature(DataType.BOOLEAN)
        
        # NULL/NA
        if value in ['NULL', 'NA', 'NA_integer_', 'NA_real_', 'NA_character_', 'NA_complex_']:
            return TypeSignature(DataType.ANY)
        
        # Vector construction
        if value.startswith('c(') or value.startswith('vector('):
            return TypeSignature(DataType.ARRAY)
        
        # List
        if value.startswith('list('):
            return TypeSignature(DataType.OBJECT)
        
        # Data frame
        if 'data.frame(' in value or 'tibble(' in value or 'read.' in value:
            return TypeSignature(DataType.OBJECT)
        
        # Number
        if re.match(r'^-?\d+L?$', value):
            return TypeSignature(DataType.INTEGER)
        if re.match(r'^-?\d+\.?\d*(?:e[+-]?\d+)?$', value, re.IGNORECASE):
            return TypeSignature(DataType.FLOAT)
        
        # Function
        if value.startswith('function('):
            return TypeSignature(DataType.FUNCTION)
        
        return TypeSignature(DataType.ANY)
