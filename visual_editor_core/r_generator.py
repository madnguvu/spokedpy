"""
R Code Generator from Universal IR.

This module generates R code from Universal Intermediate Representation.
"""

from typing import List, Dict, Any, Optional
from .universal_ir import (
    UniversalProject, UniversalModule, UniversalFunction, UniversalClass,
    UniversalVariable, Parameter, TypeSignature, DataType, LanguageMapping
)


class RGenerator:
    """Generates R code from Universal IR."""
    
    def __init__(self):
        self.mapping = LanguageMapping("universal", "r")
        self.indent_level = 0
        self.indent_size = 2
    
    def generate_module(self, module: UniversalModule) -> str:
        """Generate R code for a Universal Module."""
        lines = []
        
        # Add module comment with name
        if module.name:
            lines.append(f"# Module: {module.name}")
            lines.append("")
        
        # Add library calls
        libraries = self._generate_libraries(module)
        if libraries:
            lines.extend(libraries)
            lines.append("")
        
        # Generate global variables/constants
        for var in module.variables:
            var_code = self._generate_variable(var)
            if var_code:
                lines.append(var_code)
        
        if module.variables:
            lines.append("")
        
        # Generate R6/S4 classes
        for cls in module.classes:
            class_code = self._generate_class(cls)
            lines.extend(class_code)
            lines.append("")
        
        # Generate standalone functions
        for func in module.functions:
            func_code = self._generate_function(func)
            lines.extend(func_code)
            lines.append("")
        
        while lines and lines[-1] == "":
            lines.pop()
        
        return "\n".join(lines)
    
    def generate_project(self, project: UniversalProject) -> Dict[str, str]:
        """Generate R code for an entire project."""
        files = {}
        
        for module in project.modules:
            filename = f"{module.name}.R"
            files[filename] = self.generate_module(module)
        
        # Generate DESCRIPTION file for R package
        if len(project.modules) > 1:
            description = self._generate_description(project)
            files["DESCRIPTION"] = description
        
        return files
    
    def _indent(self, text: str = "") -> str:
        """Return properly indented text."""
        return " " * (self.indent_level * self.indent_size) + text
    
    def _generate_libraries(self, module: UniversalModule) -> List[str]:
        """Generate library() calls."""
        from .import_translator import translate_imports

        # Translate any foreign-language imports to R syntax
        libraries = translate_imports(module.imports, 'r')

        seen = set(libraries)

        # Check for R6 classes (only add if not already present)
        for cls in module.classes:
            if cls.implementation_hints.get('class_system') == 'R6':
                lib = 'library(R6)'
                if lib not in seen:
                    seen.add(lib)
                    libraries.append(lib)
        
        # Fallback: heuristic from external_libraries
        for func in module.functions:
            for lib in func.external_libraries:
                lib_call = f'library({lib})'
                if lib_call not in seen:
                    seen.add(lib_call)
                    libraries.append(lib_call)
        
        return libraries
    
    def _generate_variable(self, var: UniversalVariable) -> str:
        """Generate R variable declaration."""
        value = self._format_value(var.value, var.type_sig)
        return f"{var.name} <- {value}"
    
    def _generate_class(self, cls: UniversalClass) -> List[str]:
        """Generate R class definition."""
        hints = cls.implementation_hints
        class_system = hints.get('class_system', 'R6')
        
        if class_system == 'S4':
            return self._generate_s4_class(cls)
        else:
            return self._generate_r6_class(cls)
    
    def _generate_r6_class(self, cls: UniversalClass) -> List[str]:
        """Generate R6 class definition."""
        lines = []
        
        lines.append(f'{cls.name} <- R6Class("{cls.name}",')
        
        self.indent_level += 1
        
        # Inherit
        if cls.base_classes:
            lines.append(self._indent(f"inherit = {cls.base_classes[0]},"))
        
        # Split methods by visibility
        public_methods = [m for m in cls.methods if m.implementation_hints.get('visibility', 'public') == 'public']
        private_methods = [m for m in cls.methods if m.implementation_hints.get('visibility') == 'private']
        
        # Public members
        if public_methods:
            lines.append(self._indent("public = list("))
            self.indent_level += 1
            
            for i, method in enumerate(public_methods):
                method_lines = self._generate_r6_method(method)
                # Add comma except for last method
                if i < len(public_methods) - 1:
                    method_lines[-1] += ","
                lines.extend(method_lines)
            
            self.indent_level -= 1
            
            if private_methods:
                lines.append(self._indent("),"))
            else:
                lines.append(self._indent(")"))
        
        # Private members
        if private_methods:
            lines.append(self._indent("private = list("))
            self.indent_level += 1
            
            for i, method in enumerate(private_methods):
                method_lines = self._generate_r6_method(method)
                if i < len(private_methods) - 1:
                    method_lines[-1] += ","
                lines.extend(method_lines)
            
            self.indent_level -= 1
            lines.append(self._indent(")"))
        
        self.indent_level -= 1
        lines.append(")")
        
        return lines
    
    def _generate_r6_method(self, method: UniversalFunction) -> List[str]:
        """Generate R6 method definition."""
        lines = []
        
        params = self._generate_parameters(method.parameters)
        
        lines.append(self._indent(f"{method.name} = function({params}) {{"))
        
        self.indent_level += 1
        
        if method.implementation_hints.get('is_constructor'):
            # Initialize self with parameters
            for param in method.parameters:
                lines.append(self._indent(f"self${param.name} <- {param.name}"))
            lines.append(self._indent("invisible(self)"))
        else:
            lines.append(self._indent("# TODO: Implement"))
            
            if method.return_type.base_type != DataType.VOID:
                default_return = self._get_default_return(method.return_type)
                lines.append(self._indent(default_return))
        
        self.indent_level -= 1
        lines.append(self._indent("}"))
        
        return lines
    
    def _generate_s4_class(self, cls: UniversalClass) -> List[str]:
        """Generate S4 class definition."""
        lines = []
        
        # setClass definition
        lines.append(f'setClass("{cls.name}",')
        
        self.indent_level += 1
        
        # Slots (from parameters of constructor)
        constructor = None
        for method in cls.methods:
            if method.implementation_hints.get('is_constructor'):
                constructor = method
                break
        
        if constructor and constructor.parameters:
            slots = ', '.join(f'{p.name} = "ANY"' for p in constructor.parameters)
            lines.append(self._indent(f"slots = c({slots})"))
        
        if cls.base_classes:
            lines[-1] += ","
            lines.append(self._indent(f'contains = "{cls.base_classes[0]}"'))
        
        self.indent_level -= 1
        lines.append(")")
        lines.append("")
        
        # Generate setMethod for each method
        for method in cls.methods:
            if method.implementation_hints.get('is_constructor'):
                continue
            
            method_lines = self._generate_s4_method(cls.name, method)
            lines.extend(method_lines)
            lines.append("")
        
        return lines
    
    def _generate_s4_method(self, class_name: str, method: UniversalFunction) -> List[str]:
        """Generate S4 setMethod definition."""
        lines = []
        
        params = self._generate_parameters(method.parameters)
        if params:
            params = f"object, {params}"
        else:
            params = "object"
        
        lines.append(f'setMethod("{method.name}", "{class_name}",')
        
        self.indent_level += 1
        lines.append(self._indent(f"function({params}) {{"))
        
        self.indent_level += 1
        lines.append(self._indent("# TODO: Implement"))
        
        if method.return_type.base_type != DataType.VOID:
            default_return = self._get_default_return(method.return_type)
            lines.append(self._indent(default_return))
        
        self.indent_level -= 1
        lines.append(self._indent("}"))
        
        self.indent_level -= 1
        lines.append(")")
        
        return lines
    
    def _generate_function(self, func: UniversalFunction) -> List[str]:
        """Generate R standalone function."""
        lines = []
        
        params = self._generate_parameters(func.parameters)
        
        lines.append(f"{func.name} <- function({params}) {{")
        
        self.indent_level += 1
        lines.append(self._indent("# TODO: Implement"))
        
        if func.return_type.base_type != DataType.VOID:
            default_return = self._get_default_return(func.return_type)
            lines.append(self._indent(default_return))
        
        self.indent_level -= 1
        lines.append("}")
        
        return lines
    
    def _generate_parameters(self, parameters: List[Parameter]) -> str:
        """Generate R parameter list."""
        param_strs = []
        
        for param in parameters:
            # Check for varargs by name pattern
            if param.name == '...':
                param_strs.append('...')
            elif param.default_value is not None:
                param_strs.append(f"{param.name} = {param.default_value}")
            elif not param.required:
                default = self._get_default_return(param.type_sig)
                param_strs.append(f"{param.name} = {default}")
            else:
                param_strs.append(param.name)
        
        return ", ".join(param_strs)
    
    def _format_value(self, value: Any, type_sig: TypeSignature) -> str:
        """Format a value for R output."""
        if value is None:
            return "NULL"
        
        if isinstance(value, str):
            if value.startswith('"') or value.startswith("'"):
                return value
            if type_sig.base_type == DataType.STRING:
                return f'"{value}"'
            if value.upper() in ['TRUE', 'FALSE', 'T', 'F', 'NULL', 'NA']:
                return value.upper()
            return str(value)
        
        if isinstance(value, bool):
            return 'TRUE' if value else 'FALSE'
        
        return str(value)
    
    def _get_default_return(self, type_sig: TypeSignature) -> str:
        """Get default return value for a type."""
        defaults = {
            DataType.BOOLEAN: 'FALSE',
            DataType.INTEGER: '0L',
            DataType.FLOAT: '0.0',
            DataType.STRING: '""',
            DataType.ARRAY: 'c()',
            DataType.OBJECT: 'list()',
            DataType.ANY: 'NULL',
            DataType.VOID: 'invisible(NULL)',
        }
        return defaults.get(type_sig.base_type, 'NULL')
    
    def _generate_description(self, project: UniversalProject) -> str:
        """Generate R package DESCRIPTION file."""
        return """Package: GeneratedPackage
Title: Generated by VPyD
Version: 0.1.0
Authors@R: person("VPyD", "Generator", email = "vpyd@example.com", role = c("aut", "cre"))
Description: Auto-generated R package from Universal IR.
License: MIT
Encoding: UTF-8
LazyData: true
Imports:
    R6
RoxygenNote: 7.2.0"""
