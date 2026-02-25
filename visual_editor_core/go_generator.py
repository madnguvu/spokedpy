"""
Go Code Generator from Universal IR.

This module generates Go code from Universal Intermediate Representation.
"""

from typing import List, Dict, Any, Optional
from .universal_ir import (
    UniversalProject, UniversalModule, UniversalFunction, UniversalClass,
    UniversalVariable, Parameter, TypeSignature, DataType, LanguageMapping
)


class GoGenerator:
    """Generates Go code from Universal IR."""
    
    def __init__(self):
        self.mapping = LanguageMapping("universal", "go")
        self.indent_level = 0
        self.indent_size = 4  # Go uses tabs, but we'll use 4 spaces
    
    def generate_module(self, module: UniversalModule) -> str:
        """Generate Go code for a Universal Module."""
        lines = []
        
        # Package declaration
        package_name = getattr(module, 'go_package', None) or 'main'
        lines.append(f"package {package_name}")
        lines.append("")
        
        # Imports
        imports = self._collect_imports(module)
        if imports:
            if len(imports) == 1:
                lines.append(f'import "{imports[0]}"')
            else:
                lines.append("import (")
                for imp in imports:
                    lines.append(f'    "{imp}"')
                lines.append(")")
            lines.append("")
        
        # Generate constants
        constants = [v for v in module.variables if v.is_constant]
        if constants:
            lines.append("const (")
            self.indent_level += 1
            for var in constants:
                lines.append(self._indent(f"{var.name} = {var.value}"))
            self.indent_level -= 1
            lines.append(")")
            lines.append("")
        
        # Generate variables
        variables = [v for v in module.variables if not v.is_constant]
        if variables:
            lines.append("var (")
            self.indent_level += 1
            for var in variables:
                type_str = self._map_type_to_go(var.type_sig)
                if var.value:
                    lines.append(self._indent(f"{var.name} {type_str} = {var.value}"))
                else:
                    lines.append(self._indent(f"{var.name} {type_str}"))
            self.indent_level -= 1
            lines.append(")")
            lines.append("")
        
        # Generate structs and interfaces
        for cls in module.classes:
            class_code = self._generate_type(cls)
            lines.extend(class_code)
            lines.append("")
        
        # Generate methods for structs
        for cls in module.classes:
            if not cls.implementation_hints.get('is_interface'):
                for method in cls.methods:
                    method_lines = self._generate_method(cls.name, method)
                    lines.extend(method_lines)
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
        """Generate Go code for an entire project."""
        files = {}
        
        for module in project.modules:
            filename = f"{module.name}.go"
            files[filename] = self.generate_module(module)
        
        # Generate go.mod
        go_mod = self._generate_go_mod(project)
        files["go.mod"] = go_mod
        
        return files
    
    def _indent(self, text: str = "") -> str:
        """Return properly indented text."""
        return " " * (self.indent_level * self.indent_size) + text
    
    def _collect_imports(self, module: UniversalModule) -> List[str]:
        """Collect necessary imports."""
        from .import_translator import translate_import

        imports = set()
        
        # First: include imports captured from the parsed source
        for imp in module.imports:
            translated = translate_import(imp, 'go')
            # Go imports are stored as: import "fmt"  — extract the path
            if translated.startswith('import "') and translated.endswith('"'):
                imports.add(translated[8:-1])
            elif translated.startswith('import '):
                imports.add(translated[7:].strip().strip('"'))
            elif translated.startswith('// Python dep:'):
                # Keep as a comment; won't be wrapped in import block
                imports.add(translated)
            else:
                imports.add(translated)
        
        # Add fmt if there are functions (likely need it) and no imports yet
        if module.functions and not imports:
            imports.add("fmt")
        
        return sorted(imports)
    
    def _generate_type(self, cls: UniversalClass) -> List[str]:
        """Generate Go type (struct or interface)."""
        hints = cls.implementation_hints
        
        if hints.get('is_interface'):
            return self._generate_interface(cls)
        else:
            return self._generate_struct(cls)
    
    def _generate_interface(self, cls: UniversalClass) -> List[str]:
        """Generate Go interface."""
        lines = []
        
        lines.append(f"type {cls.name} interface {{")
        self.indent_level += 1
        
        for method in cls.methods:
            params = self._generate_parameters(method.parameters)
            return_type = self._map_type_to_go(method.return_type)
            
            if return_type == "":
                lines.append(self._indent(f"{method.name}({params})"))
            else:
                lines.append(self._indent(f"{method.name}({params}) {return_type}"))
        
        self.indent_level -= 1
        lines.append("}")
        
        return lines
    
    def _generate_struct(self, cls: UniversalClass) -> List[str]:
        """Generate Go struct."""
        lines = []
        
        lines.append(f"type {cls.name} struct {{")
        self.indent_level += 1
        
        # Generate fields from constructor parameters if available
        constructor = None
        for method in cls.methods:
            if method.implementation_hints.get('is_constructor'):
                constructor = method
                break
        
        if constructor:
            for param in constructor.parameters:
                type_str = self._map_type_to_go(param.type_sig)
                # Capitalize first letter for export
                field_name = param.name[0].upper() + param.name[1:] if param.name else param.name
                lines.append(self._indent(f"{field_name} {type_str}"))
        else:
            lines.append(self._indent("// Add struct fields here"))
        
        self.indent_level -= 1
        lines.append("}")
        
        return lines
    
    def _generate_method(self, struct_name: str, method: UniversalFunction) -> List[str]:
        """Generate Go method with receiver."""
        lines = []
        
        hints = method.implementation_hints
        receiver = hints.get('receiver', 's')
        
        params = self._generate_parameters(method.parameters)
        return_type = self._map_type_to_go(method.return_type)
        
        if return_type:
            lines.append(f"func ({receiver} *{struct_name}) {method.name}({params}) {return_type} {{")
        else:
            lines.append(f"func ({receiver} *{struct_name}) {method.name}({params}) {{")
        
        self.indent_level += 1
        
        if hints.get('is_constructor'):
            lines.append(self._indent(f"// Initialize {struct_name}"))
        else:
            lines.append(self._indent("// TODO: Implement"))
            
            if method.return_type.base_type != DataType.VOID:
                default_return = self._get_default_return(method.return_type)
                lines.append(self._indent(f"return {default_return}"))
        
        self.indent_level -= 1
        lines.append("}")
        
        return lines
    
    def _generate_function(self, func: UniversalFunction) -> List[str]:
        """Generate Go standalone function."""
        lines = []
        
        params = self._generate_parameters(func.parameters)
        return_type = self._map_type_to_go(func.return_type)
        
        if return_type:
            lines.append(f"func {func.name}({params}) {return_type} {{")
        else:
            lines.append(f"func {func.name}({params}) {{")
        
        self.indent_level += 1
        lines.append(self._indent("// TODO: Implement"))
        
        if func.return_type.base_type != DataType.VOID:
            default_return = self._get_default_return(func.return_type)
            lines.append(self._indent(f"return {default_return}"))
        
        self.indent_level -= 1
        lines.append("}")
        
        return lines
    
    def _generate_parameters(self, parameters: List[Parameter]) -> str:
        """Generate Go parameter list."""
        param_strs = []
        
        for param in parameters:
            type_str = self._map_type_to_go(param.type_sig)
            param_strs.append(f"{param.name} {type_str}")
        
        return ", ".join(param_strs)
    
    def _map_type_to_go(self, type_sig: TypeSignature) -> str:
        """Map UIR type signature to Go type."""
        type_mapping = {
            DataType.VOID: '',
            DataType.BOOLEAN: 'bool',
            DataType.INTEGER: 'int',
            DataType.FLOAT: 'float64',
            DataType.STRING: 'string',
            DataType.ARRAY: '[]interface{}',
            DataType.OBJECT: 'map[string]interface{}',
            DataType.FUNCTION: 'func()',
            DataType.ANY: 'interface{}',
        }
        
        return type_mapping.get(type_sig.base_type, 'interface{}')
    
    def _get_default_return(self, type_sig: TypeSignature) -> str:
        """Get default return value for a type."""
        defaults = {
            DataType.BOOLEAN: 'false',
            DataType.INTEGER: '0',
            DataType.FLOAT: '0.0',
            DataType.STRING: '""',
            DataType.ARRAY: 'nil',
            DataType.OBJECT: 'nil',
            DataType.ANY: 'nil',
        }
        return defaults.get(type_sig.base_type, 'nil')
    
    def _generate_go_mod(self, project: UniversalProject) -> str:
        """Generate go.mod file."""
        return """module github.com/vpyd/generated

go 1.21
"""
