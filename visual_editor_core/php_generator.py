"""
PHP Code Generator from Universal IR.

This module generates PHP code from Universal Intermediate Representation.
"""

from typing import List, Dict, Any, Optional
from .universal_ir import (
    UniversalProject, UniversalModule, UniversalFunction, UniversalClass,
    UniversalVariable, Parameter, TypeSignature, DataType, LanguageMapping
)


class PHPGenerator:
    """Generates PHP code from Universal IR."""
    
    def __init__(self):
        self.mapping = LanguageMapping("universal", "php")
        self.indent_level = 0
        self.indent_size = 4
    
    def generate_module(self, module: UniversalModule) -> str:
        """Generate PHP code for a Universal Module."""
        lines = []
        
        # PHP opening tag
        lines.append("<?php")
        lines.append("")
        
        # Strict types declaration
        lines.append("declare(strict_types=1);")
        lines.append("")
        
        # Add namespace if available (stored in imports as "namespace:xxx")
        namespace = None
        for imp in module.imports:
            if imp.startswith("namespace:"):
                namespace = imp[10:]
                break
        if namespace:
            lines.append(f"namespace {namespace};")
            lines.append("")
        
        # Add use statements
        uses = self._generate_use_statements(module)
        if uses:
            lines.extend(uses)
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
        
        # Generate standalone functions
        for func in module.functions:
            func_code = self._generate_function(func)
            lines.extend(func_code)
            lines.append("")
        
        while lines and lines[-1] == "":
            lines.pop()
        
        return "\n".join(lines)
    
    def generate_project(self, project: UniversalProject) -> Dict[str, str]:
        """Generate PHP code for an entire project."""
        files = {}
        
        for module in project.modules:
            filename = f"{module.name}.php"
            files[filename] = self.generate_module(module)
        
        # Generate composer.json if needed
        if len(project.modules) > 1:
            composer = self._generate_composer_json(project)
            files["composer.json"] = composer
        
        return files
    
    def _indent(self, text: str = "") -> str:
        """Return properly indented text."""
        return " " * (self.indent_level * self.indent_size) + text
    
    def _generate_use_statements(self, module: UniversalModule) -> List[str]:
        """Generate use statements for imports."""
        from .import_translator import translate_imports

        # Filter metadata markers, then translate foreign imports
        raw = [imp for imp in module.imports if not imp.startswith('namespace:')]
        uses = translate_imports(raw, 'php')

        # Ensure every line ends with ';'
        uses = [u if u.rstrip().endswith(';') or u.startswith('//') else f"{u.rstrip()};"
                for u in uses]

        seen = set(uses)

        # Fallback: heuristic from external_libraries
        for func in module.functions:
            for lib in func.external_libraries:
                use = f"use {lib};"
                if use not in seen:
                    seen.add(use)
                    uses.append(use)
        
        return uses
    
    def _generate_constant(self, var: UniversalVariable) -> str:
        """Generate PHP constant declaration."""
        value = self._format_value(var.value, var.type_sig)
        return f"const {var.name} = {value};"
    
    def _generate_class(self, cls: UniversalClass) -> List[str]:
        """Generate PHP class definition."""
        lines = []
        
        hints = cls.implementation_hints
        
        # Handle interfaces
        if hints.get('is_interface'):
            return self._generate_interface(cls)
        
        # Handle traits
        if hints.get('is_trait'):
            return self._generate_trait(cls)
        
        # Class declaration
        modifiers = []
        if hints.get('is_abstract'):
            modifiers.append('abstract')
        if hints.get('is_final'):
            modifiers.append('final')
        
        modifier_str = ' '.join(modifiers) + ' ' if modifiers else ''
        
        class_decl = f"{modifier_str}class {cls.name}"
        
        if cls.base_classes:
            class_decl += f" extends {cls.base_classes[0]}"
        
        implements = hints.get('implements', [])
        if implements:
            class_decl += f" implements {', '.join(implements)}"
        
        lines.append(class_decl)
        lines.append("{")
        
        self.indent_level += 1
        
        # Class constants
        for const in hints.get('constants', []):
            visibility = const.get('visibility', 'public')
            lines.append(self._indent(f"{visibility} const {const['name']} = {const['value']};"))
        
        if hints.get('constants'):
            lines.append("")
        
        # Generate methods
        for method in cls.methods:
            method_lines = self._generate_method(method)
            lines.extend(method_lines)
            lines.append("")
        
        if lines and lines[-1] == "":
            lines.pop()
        
        self.indent_level -= 1
        lines.append("}")
        
        return lines
    
    def _generate_interface(self, cls: UniversalClass) -> List[str]:
        """Generate PHP interface."""
        lines = []
        
        interface_decl = f"interface {cls.name}"
        if cls.base_classes:
            interface_decl += f" extends {', '.join(cls.base_classes)}"
        
        lines.append(interface_decl)
        lines.append("{")
        
        self.indent_level += 1
        
        for method in cls.methods:
            # Interface methods are just signatures
            params = self._generate_parameters(method.parameters)
            return_type = self._map_type_to_php(method.return_type)
            lines.append(self._indent(f"public function {method.name}({params}): {return_type};"))
            lines.append("")
        
        if lines and lines[-1] == "":
            lines.pop()
        
        self.indent_level -= 1
        lines.append("}")
        
        return lines
    
    def _generate_trait(self, cls: UniversalClass) -> List[str]:
        """Generate PHP trait."""
        lines = []
        
        lines.append(f"trait {cls.name}")
        lines.append("{")
        
        self.indent_level += 1
        
        for method in cls.methods:
            method_lines = self._generate_method(method)
            lines.extend(method_lines)
            lines.append("")
        
        if lines and lines[-1] == "":
            lines.pop()
        
        self.indent_level -= 1
        lines.append("}")
        
        return lines
    
    def _generate_method(self, func: UniversalFunction) -> List[str]:
        """Generate PHP method."""
        lines = []
        
        hints = func.implementation_hints
        visibility = hints.get('visibility', 'public')
        is_static = hints.get('is_static', False)
        is_abstract = hints.get('is_abstract', False)
        
        # Build method signature
        modifiers = [visibility]
        if is_static:
            modifiers.append('static')
        if is_abstract:
            modifiers.append('abstract')
        
        params = self._generate_parameters(func.parameters)
        return_type = self._map_type_to_php(func.return_type)
        
        modifier_str = ' '.join(modifiers)
        
        # Abstract methods have no body
        if is_abstract:
            lines.append(self._indent(f"{modifier_str} function {func.name}({params}): {return_type};"))
            return lines
        
        lines.append(self._indent(f"{modifier_str} function {func.name}({params}): {return_type}"))
        lines.append(self._indent("{"))
        
        self.indent_level += 1
        
        # Constructor handling
        if hints.get('is_constructor'):
            for param in func.parameters:
                lines.append(self._indent(f"$this->{param.name} = ${param.name};"))
        else:
            lines.append(self._indent("// TODO: Implement"))
            
            if func.return_type.base_type != DataType.VOID:
                default_return = self._get_default_return(func.return_type)
                lines.append(self._indent(f"return {default_return};"))
        
        self.indent_level -= 1
        lines.append(self._indent("}"))
        
        return lines
    
    def _generate_function(self, func: UniversalFunction) -> List[str]:
        """Generate PHP standalone function."""
        lines = []
        
        params = self._generate_parameters(func.parameters)
        return_type = self._map_type_to_php(func.return_type)
        
        lines.append(f"function {func.name}({params}): {return_type}")
        lines.append("{")
        
        self.indent_level += 1
        lines.append(self._indent("// TODO: Implement"))
        
        if func.return_type.base_type != DataType.VOID:
            default_return = self._get_default_return(func.return_type)
            lines.append(self._indent(f"return {default_return};"))
        
        self.indent_level -= 1
        lines.append("}")
        
        return lines
    
    def _generate_parameters(self, parameters: List[Parameter]) -> str:
        """Generate PHP parameter list."""
        param_strs = []
        
        for param in parameters:
            type_str = self._map_type_to_php(param.type_sig)
            
            if param.default_value is not None:
                param_strs.append(f"{type_str} ${param.name} = {param.default_value}")
            elif not param.required:
                default = self._get_default_return(param.type_sig)
                param_strs.append(f"?{type_str} ${param.name} = null")
            else:
                param_strs.append(f"{type_str} ${param.name}")
        
        return ", ".join(param_strs)
    
    def _map_type_to_php(self, type_sig: TypeSignature) -> str:
        """Map UIR type signature to PHP type."""
        type_mapping = {
            DataType.VOID: 'void',
            DataType.BOOLEAN: 'bool',
            DataType.INTEGER: 'int',
            DataType.FLOAT: 'float',
            DataType.STRING: 'string',
            DataType.ARRAY: 'array',
            DataType.OBJECT: 'object',
            DataType.FUNCTION: 'callable',
            DataType.ANY: 'mixed',
        }
        
        return type_mapping.get(type_sig.base_type, 'mixed')
    
    def _format_value(self, value: Any, type_sig: TypeSignature) -> str:
        """Format a value for PHP output."""
        if value is None:
            return "null"
        
        if isinstance(value, str):
            if value.startswith('"') or value.startswith("'"):
                return value
            if type_sig.base_type == DataType.STRING:
                return f"'{value}'"
            if value.lower() in ['true', 'false', 'null']:
                return value.lower()
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
            DataType.STRING: "''",
            DataType.ARRAY: '[]',
            DataType.OBJECT: 'new stdClass()',
            DataType.ANY: 'null',
        }
        return defaults.get(type_sig.base_type, 'null')
    
    def _generate_composer_json(self, project: UniversalProject) -> str:
        """Generate composer.json for the project."""
        return """{
    "name": "vpyd/generated-project",
    "type": "project",
    "require": {
        "php": ">=8.1"
    },
    "autoload": {
        "psr-4": {
            "App\\\\": "src/"
        }
    }
}"""
