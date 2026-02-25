"""
Bash to Universal IR Parser.

This module parses Bash shell scripts and converts them to Universal Intermediate Representation.
"""

import re
from typing import Dict, List, Optional, Any
from .universal_ir import (
    UniversalProject, UniversalModule, UniversalFunction, UniversalClass,
    UniversalVariable, Parameter, TypeSignature, DataType, SemanticDescription,
    Contract, PurityLevel
)


class BashParser:
    """Parses Bash scripts into Universal IR."""
    
    def __init__(self):
        self.current_module = None
    
    def parse_code(self, bash_code: str, filename: str = "script.sh") -> UniversalModule:
        """Parse Bash code into a Universal Module."""
        module = UniversalModule(
            name=filename.replace('.sh', '').replace('.bash', ''),
            source_language="bash",
            source_file=filename
        )
        
        self.current_module = module
        
        # Parse Bash constructs
        self._parse_shebang(bash_code)
        self._parse_source_commands(bash_code)
        self._parse_variables(bash_code)
        self._parse_functions(bash_code)
        
        return module

    def _parse_source_commands(self, code: str):
        """Parse source / . (dot) commands — Bash's file inclusion mechanism."""
        if self.current_module is None:
            return
        # source /path/to/file  or  source ./file.sh
        source_pattern = r'^\s*(source\s+\S+)'
        for m in re.finditer(source_pattern, code, re.MULTILINE):
            self.current_module.imports.append(m.group(1).strip())
        # . /path/to/file  (dot-space form)
        dot_pattern = r'^\s*(\.\s+\S+)'
        for m in re.finditer(dot_pattern, code, re.MULTILINE):
            stmt = m.group(1).strip()
            # Avoid matching lines that are just comments
            if not stmt.startswith('#'):
                self.current_module.imports.append(stmt)
    
    def _parse_shebang(self, code: str):
        """Parse shebang line."""
        shebang_pattern = r'^#!(.+)$'
        match = re.search(shebang_pattern, code, re.MULTILINE)
        if not match:
            return

        # Ensure current_module exists before assigning attributes to it
        if self.current_module is None:
            return

        # Use a dynamic-typed reference to avoid static-type complaints about unknown attributes
        module_any: Any = self.current_module
        if not hasattr(module_any, 'bash_shebang'):
            module_any.bash_shebang = match.group(1).strip()
    
    def _parse_variables(self, code: str):
        """Parse variable assignments."""
        # Simple variable assignment
        var_pattern = r'^(?:export\s+)?(\w+)=([^\n]+)'
        variables = re.finditer(var_pattern, code, re.MULTILINE)
        
        # Ensure current_module exists before modifying it
        if self.current_module is None:
            return
        module_any: Any = self.current_module
        
        for match in variables:
            var_name = match.group(1)
            value = match.group(2).strip()
            
            # Skip function-like patterns
            if value.startswith('(') and ')' in value:
                continue
            
            is_export = 'export' in match.group(0)
            
            var = UniversalVariable(
                name=var_name,
                type_sig=self._infer_type(value),
                value=value,
                is_constant=var_name.isupper(),
            )
            
            if not hasattr(module_any, 'variables'):
                module_any.variables = []
            module_any.variables.append(var)
    
    def _parse_functions(self, code: str):
        """Parse Bash function declarations."""
        # Two formats: 'function name { }' and 'name() { }'
        func_pattern1 = r'function\s+(\w+)\s*(?:\(\s*\))?\s*\{([^}]*(?:\{[^}]*\}[^}]*)*)\}'
        func_pattern2 = r'(\w+)\s*\(\s*\)\s*\{([^}]*(?:\{[^}]*\}[^}]*)*)\}'
        
        # Ensure current_module exists before modifying it
        if self.current_module is None:
            return
        module_any: Any = self.current_module
        
        if not hasattr(module_any, 'functions'):
            module_any.functions = []
        
        # Parse 'function name { }' style
        for match in re.finditer(func_pattern1, code, re.MULTILINE | re.DOTALL):
            func_name = match.group(1)
            body = match.group(2)
            
            func = UniversalFunction(
                name=func_name,
                parameters=self._extract_parameters(body),
                return_type=TypeSignature(DataType.ANY),
                source_language="bash",
                source_code=match.group(0),
                implementation_hints={
                    'control_flow': self._extract_control_flow(body)
                }
            )
            
            module_any.functions.append(func)
        
        # Parse 'name()' style
        for match in re.finditer(func_pattern2, code, re.MULTILINE | re.DOTALL):
            func_name = match.group(1)
            body = match.group(2)
            
            # Skip if already parsed
            if any(f.name == func_name for f in module_any.functions):
                continue
            
            func = UniversalFunction(
                name=func_name,
                parameters=self._extract_parameters(body),
                return_type=TypeSignature(DataType.ANY),
                source_language="bash",
                source_code=match.group(0),
                implementation_hints={
                    'control_flow': self._extract_control_flow(body)
                }
            )
            
            module_any.functions.append(func)
    
    def _extract_parameters(self, body: str) -> List[Parameter]:
        """Extract parameters from function body based on $1, $2, etc. usage."""
        parameters = []
        
        # Find all positional parameters used
        param_pattern = r'\$(\d+)'
        params_used = set(re.findall(param_pattern, body))
        
        for i in range(1, max([int(p) for p in params_used], default=0) + 1):
            parameters.append(Parameter(
                name=f'arg{i}',
                type_sig=TypeSignature(DataType.STRING),
                required=True
            ))
        
        # Check for $@ or $* (variable arguments)
        if '$@' in body or '$*' in body:
            parameters.append(Parameter(
                name='args',
                type_sig=TypeSignature(DataType.ARRAY),
                required=False
            ))
        
        return parameters
    
    def _infer_type(self, value: str) -> TypeSignature:
        """Infer type from value."""
        value = value.strip().strip('"').strip("'")
        
        if re.match(r'^-?\d+$', value):
            return TypeSignature(DataType.INTEGER)
        if re.match(r'^-?\d+\.\d+$', value):
            return TypeSignature(DataType.FLOAT)
        if value.lower() in ['true', 'false', '0', '1']:
            return TypeSignature(DataType.BOOLEAN)
        if value.startswith('(') and value.endswith(')'):
            return TypeSignature(DataType.ARRAY)
        
        return TypeSignature(DataType.STRING)
    
    def _extract_control_flow(self, body: str) -> List[Dict[str, Any]]:
        """Extract control flow structures from function body."""
        control_flow = []
        
        if not body:
            return control_flow
        
        patterns = [
            (r'if\s+\[', 'if_condition'),
            (r'if\s+\[\[', 'if_condition'),
            (r'elif\s+\[', 'else_if'),
            (r'else\s*$', 'else'),
            (r'for\s+\w+\s+in', 'for_loop'),
            (r'while\s+\[', 'while_loop'),
            (r'until\s+\[', 'until_loop'),
            (r'case\s+', 'switch'),
            (r'select\s+', 'select'),
        ]
        
        for pattern, kind in patterns:
            for match in re.finditer(pattern, body, re.MULTILINE):
                control_flow.append({
                    'kind': kind,
                    'source_code': match.group(0),
                    'lineno': body[:match.start()].count('\n') + 1
                })
        
        return control_flow
