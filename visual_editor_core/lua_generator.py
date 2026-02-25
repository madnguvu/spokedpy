"""
Lua Code Generator from Universal IR.

This module generates Lua code from Universal Intermediate Representation.
"""

from typing import List, Dict, Any, Optional
from .universal_ir import (
    UniversalProject, UniversalModule, UniversalFunction, UniversalClass,
    UniversalVariable, Parameter, TypeSignature, DataType, LanguageMapping
)


class LuaGenerator:
    """Generates Lua code from Universal IR."""
    
    def __init__(self):
        self.mapping = LanguageMapping("universal", "lua")
        self.indent_level = 0
        self.indent_size = 2
    
    def generate_module(self, module: UniversalModule) -> str:
        """Generate Lua code for a Universal Module."""
        lines = []
        
        # Add module comment with name
        if module.name:
            lines.append(f"-- Module: {module.name}")
            lines.append("")
        
        # Add requires
        requires = self._generate_requires(module)
        if requires:
            lines.extend(requires)
            lines.append("")
        
        # Generate global variables/constants
        for var in module.variables:
            var_code = self._generate_variable(var)
            if var_code:
                lines.append(var_code)
        
        if module.variables:
            lines.append("")
        
        # Generate table-based classes
        for cls in module.classes:
            class_code = self._generate_class(cls)
            lines.extend(class_code)
            lines.append("")
        
        # Generate standalone functions
        for func in module.functions:
            func_code = self._generate_function(func)
            lines.extend(func_code)
            lines.append("")
        
        # Generate module return (if this is a module)
        exports = self._generate_module_return(module)
        if exports:
            lines.extend(exports)
        
        while lines and lines[-1] == "":
            lines.pop()
        
        return "\n".join(lines)
    
    def generate_project(self, project: UniversalProject) -> Dict[str, str]:
        """Generate Lua code for an entire project."""
        files = {}
        
        for module in project.modules:
            filename = f"{module.name}.lua"
            files[filename] = self.generate_module(module)
        
        return files
    
    def _indent(self, text: str = "") -> str:
        """Return properly indented text."""
        return " " * (self.indent_level * self.indent_size) + text
    
    def _generate_requires(self, module: UniversalModule) -> List[str]:
        """Generate require statements."""
        from .import_translator import translate_imports

        # Translate any foreign-language imports to Lua syntax
        requires = translate_imports(module.imports, 'lua')

        # Fallback: heuristic from external_libraries
        seen = set(requires)
        for func in module.functions:
            for lib in func.external_libraries:
                req = f'local {lib} = require("{lib}")'
                if req not in seen:
                    seen.add(req)
                    requires.append(req)
        
        return requires
    
    def _generate_variable(self, var: UniversalVariable) -> str:
        """Generate Lua variable declaration."""
        value = self._format_value(var.value, var.type_sig)
        is_local = getattr(var, 'implementation_hints', {}).get('is_local', True)
        
        prefix = "local " if is_local else ""
        return f"{prefix}{var.name} = {value}"
    
    def _generate_class(self, cls: UniversalClass) -> List[str]:
        """Generate Lua table-based class definition."""
        lines = []
        
        # Create empty table
        lines.append(f"{cls.name} = {{}}")
        lines.append(f"{cls.name}.__index = {cls.name}")
        lines.append("")
        
        # Check if there's a constructor method
        constructor = None
        for method in cls.methods:
            if method.implementation_hints.get('is_constructor'):
                constructor = method
                break
        
        # Generate constructor if exists or create default
        if constructor:
            lines.extend(self._generate_constructor(cls.name, constructor))
        else:
            # Default constructor
            lines.append(f"function {cls.name}:new()")
            self.indent_level += 1
            lines.append(self._indent("local self = setmetatable({}, " + cls.name + ")"))
            lines.append(self._indent("return self"))
            self.indent_level -= 1
            lines.append("end")
        
        lines.append("")
        
        # Generate other methods
        for method in cls.methods:
            if method.implementation_hints.get('is_constructor'):
                continue
            
            method_lines = self._generate_method(cls.name, method)
            lines.extend(method_lines)
            lines.append("")
        
        if lines and lines[-1] == "":
            lines.pop()
        
        return lines
    
    def _generate_constructor(self, class_name: str, method: UniversalFunction) -> List[str]:
        """Generate Lua constructor method."""
        lines = []
        
        params = self._generate_parameters(method.parameters)
        if params:
            lines.append(f"function {class_name}:new({params})")
        else:
            lines.append(f"function {class_name}:new()")
        
        self.indent_level += 1
        lines.append(self._indent(f"local self = setmetatable({{}}, {class_name})"))
        
        # Initialize from parameters
        for param in method.parameters:
            lines.append(self._indent(f"self.{param.name} = {param.name}"))
        
        lines.append(self._indent("return self"))
        self.indent_level -= 1
        lines.append("end")
        
        return lines
    
    def _generate_method(self, class_name: str, method: UniversalFunction) -> List[str]:
        """Generate Lua method."""
        lines = []
        
        is_colon = method.implementation_hints.get('is_colon_method', True)
        separator = ':' if is_colon else '.'
        
        params = self._generate_parameters(method.parameters)
        
        if params:
            lines.append(f"function {class_name}{separator}{method.name}({params})")
        else:
            lines.append(f"function {class_name}{separator}{method.name}()")
        
        self.indent_level += 1
        lines.append(self._indent("-- TODO: Implement"))
        
        if method.return_type.base_type != DataType.VOID:
            default_return = self._get_default_return(method.return_type)
            lines.append(self._indent(f"return {default_return}"))
        
        self.indent_level -= 1
        lines.append("end")
        
        return lines
    
    def _generate_function(self, func: UniversalFunction) -> List[str]:
        """Generate Lua standalone function."""
        lines = []
        
        is_local = func.implementation_hints.get('is_local', False)
        prefix = "local " if is_local else ""
        
        params = self._generate_parameters(func.parameters)
        
        if params:
            lines.append(f"{prefix}function {func.name}({params})")
        else:
            lines.append(f"{prefix}function {func.name}()")
        
        self.indent_level += 1
        lines.append(self._indent("-- TODO: Implement"))
        
        if func.return_type.base_type != DataType.VOID:
            default_return = self._get_default_return(func.return_type)
            lines.append(self._indent(f"return {default_return}"))
        
        self.indent_level -= 1
        lines.append("end")
        
        return lines
    
    def _generate_parameters(self, parameters: List[Parameter]) -> str:
        """Generate Lua parameter list."""
        param_strs = []
        
        for param in parameters:
            # Check for varargs by name pattern
            if param.name == '...':
                param_strs.append('...')
            else:
                param_strs.append(param.name)
        
        return ", ".join(param_strs)
    
    def _format_value(self, value: Any, type_sig: TypeSignature) -> str:
        """Format a value for Lua output."""
        if value is None:
            return "nil"
        
        if isinstance(value, str):
            if value.startswith('"') or value.startswith("'"):
                return value
            if type_sig.base_type == DataType.STRING:
                return f'"{value}"'
            if value in ['true', 'false', 'nil']:
                return value
            return str(value)
        
        if isinstance(value, bool):
            return 'true' if value else 'false'
        
        return str(value)
    
    def _get_default_return(self, type_sig: TypeSignature) -> str:
        """Get default return value for a type."""
        defaults = {
            DataType.BOOLEAN: 'false',
            DataType.INTEGER: '0',
            DataType.FLOAT: '0.0',
            DataType.STRING: '""',
            DataType.ARRAY: '{}',
            DataType.OBJECT: '{}',
            DataType.ANY: 'nil',
        }
        return defaults.get(type_sig.base_type, 'nil')
    
    def _generate_module_return(self, module: UniversalModule) -> List[str]:
        """Generate module return statement for Lua modules."""
        # If there are classes, return them
        if module.classes:
            class_names = [cls.name for cls in module.classes]
            if len(class_names) == 1:
                return [f"return {class_names[0]}"]
            else:
                exports = ', '.join(f'{name} = {name}' for name in class_names)
                return [f"return {{ {exports} }}"]
        
        # If there are exported functions, create a module table
        exported_funcs = [f for f in module.functions if not f.implementation_hints.get('is_local', False)]
        if exported_funcs:
            func_names = [f.name for f in exported_funcs]
            if len(func_names) == 1:
                return [f"return {func_names[0]}"]
            else:
                exports = ', '.join(f'{name} = {name}' for name in func_names)
                return [f"return {{ {exports} }}"]
        
        return []
