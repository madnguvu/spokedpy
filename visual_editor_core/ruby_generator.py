"""
Ruby Code Generator from Universal IR.

This module generates Ruby code from Universal Intermediate Representation.
"""

from typing import List, Dict, Any, Optional
from .universal_ir import (
    UniversalProject, UniversalModule, UniversalFunction, UniversalClass,
    UniversalVariable, Parameter, TypeSignature, DataType, LanguageMapping
)


class RubyGenerator:
    """Generates Ruby code from Universal IR."""
    
    def __init__(self):
        self.mapping = LanguageMapping("universal", "ruby")
        self.indent_level = 0
        self.indent_size = 2
    
    def generate_module(self, module: UniversalModule) -> str:
        """Generate Ruby code for a Universal Module."""
        lines = []
        
        # Add frozen string literal pragma
        lines.append("# frozen_string_literal: true")
        lines.append("")
        
        # Add module comment with name
        if module.name:
            lines.append(f"# Module: {module.name}")
            lines.append("")
        
        # Add requires
        requires = self._generate_requires(module)
        if requires:
            lines.extend(requires)
            lines.append("")
        
        # Generate constants
        for var in module.variables:
            if var.is_constant:
                var_code = self._generate_constant(var)
                if var_code:
                    lines.append(var_code)
        
        if module.variables:
            lines.append("")
        
        # Generate classes
        for cls in module.classes:
            class_code = self._generate_class(cls)
            lines.extend(class_code)
            lines.append("")
        
        # Generate standalone methods
        for func in module.functions:
            func_code = self._generate_method(func)
            lines.extend(func_code)
            lines.append("")
        
        while lines and lines[-1] == "":
            lines.pop()
        
        return "\n".join(lines)
    
    def generate_project(self, project: UniversalProject) -> Dict[str, str]:
        """Generate Ruby code for an entire project."""
        files = {}
        
        for module in project.modules:
            filename = f"{self._to_snake_case(module.name)}.rb"
            files[filename] = self.generate_module(module)
        
        # Generate Gemfile if needed
        if len(project.modules) > 1:
            gemfile = self._generate_gemfile(project)
            files["Gemfile"] = gemfile
        
        return files
    
    def _indent(self, text: str = "") -> str:
        """Return properly indented text."""
        return " " * (self.indent_level * self.indent_size) + text
    
    def _to_snake_case(self, name: str) -> str:
        """Convert CamelCase to snake_case."""
        import re
        s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
        return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()
    
    def _generate_requires(self, module: UniversalModule) -> List[str]:
        """Generate require statements."""
        from .import_translator import translate_imports

        # Filter metadata markers, then translate foreign imports
        raw = [imp for imp in module.imports if not imp.startswith('module:')]
        requires = translate_imports(raw, 'ruby')

        # External library imports (fallback heuristic)
        for func in module.functions:
            for lib in func.external_libraries:
                req = f"require '{lib}'"
                if req not in requires:
                    requires.append(req)
        
        return requires
    
    def _generate_constant(self, var: UniversalVariable) -> str:
        """Generate Ruby constant declaration."""
        value = self._format_value(var.value, var.type_sig)
        return f"{var.name.upper()} = {value}"
    
    def _generate_class(self, cls: UniversalClass) -> List[str]:
        """Generate Ruby class definition."""
        lines = []
        
        # Class declaration
        if cls.base_classes:
            lines.append(f"class {cls.name} < {cls.base_classes[0]}")
        else:
            lines.append(f"class {cls.name}")
        
        self.indent_level += 1
        
        # Collect accessors from methods
        getters = set()
        setters = set()
        
        for method in cls.methods:
            hints = method.implementation_hints
            if hints.get('is_accessor'):
                if hints.get('accessor_type') == 'getter':
                    getters.add(method.name)
                elif hints.get('accessor_type') == 'setter':
                    setters.add(method.name.rstrip('='))
        
        # Generate attr_accessor, attr_reader, attr_writer
        accessors = getters & setters
        readers = getters - setters
        writers = setters - getters
        
        if accessors:
            lines.append(self._indent(f"attr_accessor {', '.join(':' + a for a in sorted(accessors))}"))
        if readers:
            lines.append(self._indent(f"attr_reader {', '.join(':' + r for r in sorted(readers))}"))
        if writers:
            lines.append(self._indent(f"attr_writer {', '.join(':' + w for w in sorted(writers))}"))
        
        if accessors or readers or writers:
            lines.append("")
        
        # Generate methods (skip accessors)
        for method in cls.methods:
            hints = method.implementation_hints
            if hints.get('is_accessor'):
                continue
            
            method_lines = self._generate_method(method, is_class_method=hints.get('is_static', False))
            lines.extend(method_lines)
            lines.append("")
        
        # Remove last empty line inside class
        if lines and lines[-1] == "":
            lines.pop()
        
        self.indent_level -= 1
        lines.append("end")
        
        return lines
    
    def _generate_method(self, func: UniversalFunction, is_class_method: bool = False) -> List[str]:
        """Generate Ruby method."""
        lines = []
        
        hints = func.implementation_hints
        visibility = hints.get('visibility', 'public')
        is_constructor = hints.get('is_constructor', False)
        
        # Method name
        method_name = 'initialize' if is_constructor else func.name
        if is_class_method:
            method_name = f"self.{method_name}"
        
        # Parameters
        params = self._generate_parameters(func.parameters)
        
        if params:
            lines.append(self._indent(f"def {method_name}({params})"))
        else:
            lines.append(self._indent(f"def {method_name}"))
        
        # Method body
        self.indent_level += 1
        
        if is_constructor:
            # Initialize instance variables from parameters
            for param in func.parameters:
                lines.append(self._indent(f"@{param.name} = {param.name}"))
        else:
            lines.append(self._indent("# TODO: Implement"))
            
            if func.return_type.base_type != DataType.VOID:
                default_return = self._get_default_return(func.return_type)
                lines.append(self._indent(default_return))
        
        self.indent_level -= 1
        lines.append(self._indent("end"))
        
        # Add visibility modifier if needed
        if visibility == 'private' and not is_class_method:
            lines.insert(0, self._indent("private"))
        elif visibility == 'protected' and not is_class_method:
            lines.insert(0, self._indent("protected"))
        
        return lines
    
    def _generate_parameters(self, parameters: List[Parameter]) -> str:
        """Generate Ruby parameter list."""
        param_strs = []
        
        for param in parameters:
            # Check for variadic parameters by name pattern
            if param.name.startswith('**'):
                param_strs.append(param.name)
            elif param.name.startswith('*'):
                param_strs.append(param.name)
            elif param.name.startswith('&'):
                param_strs.append(param.name)
            elif param.type_sig.base_type == DataType.FUNCTION:
                param_strs.append(f"&{param.name}")
            elif param.default_value is not None:
                param_strs.append(f"{param.name} = {param.default_value}")
            elif not param.required:
                param_strs.append(f"{param.name} = nil")
            else:
                param_strs.append(param.name)
        
        return ", ".join(param_strs)
    
    def _format_value(self, value: Any, type_sig: TypeSignature) -> str:
        """Format a value for Ruby output."""
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
            DataType.ARRAY: '[]',
            DataType.OBJECT: '{}',
            DataType.ANY: 'nil',
        }
        return defaults.get(type_sig.base_type, 'nil')
    
    def _generate_gemfile(self, project: UniversalProject) -> str:
        """Generate Gemfile for the project."""
        lines = ['source "https://rubygems.org"', '', 'ruby ">= 3.0"', '']
        
        # Collect external libraries
        libs = set()
        for module in project.modules:
            for func in module.functions:
                libs.update(func.external_libraries)
        
        for lib in sorted(libs):
            lines.append(f'gem "{lib}"')
        
        return "\n".join(lines)
