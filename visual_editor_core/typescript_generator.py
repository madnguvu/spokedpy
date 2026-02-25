"""
TypeScript Code Generator from Universal IR.

This module generates TypeScript code from Universal Intermediate Representation.
"""

from typing import List, Dict, Any, Optional
from .universal_ir import (
    UniversalProject, UniversalModule, UniversalFunction, UniversalClass,
    UniversalVariable, Parameter, TypeSignature, DataType, LanguageMapping
)


class TypeScriptGenerator:
    """Generates TypeScript code from Universal IR."""
    
    def __init__(self):
        self.mapping = LanguageMapping("universal", "typescript")
        self.indent_level = 0
        self.indent_size = 2
    
    def generate_module(self, module: UniversalModule) -> str:
        """Generate TypeScript code for a Universal Module."""
        lines = []
        
        # Add module comment with name
        if module.name:
            lines.append('/**')
            lines.append(f' * Module: {module.name}')
            lines.append(' */')
            lines.append('')
        
        # Add imports
        imports = self._generate_imports(module)
        if imports:
            lines.extend(imports)
            lines.append('')
        
        # Generate interfaces (from metadata)
        interfaces = self._generate_interfaces(module)
        if interfaces:
            lines.extend(interfaces)
            lines.append('')
        
        # Generate type aliases (from metadata)
        type_aliases = self._generate_type_aliases(module)
        if type_aliases:
            lines.extend(type_aliases)
            lines.append('')
        
        # Generate variables/constants
        for var in module.variables:
            var_code = self._generate_variable(var)
            if var_code:
                lines.append(var_code)
        
        if module.variables:
            lines.append('')
        
        # Generate classes
        for cls in module.classes:
            class_code = self._generate_class(cls)
            lines.extend(class_code)
            lines.append('')
        
        # Generate functions
        for func in module.functions:
            func_code = self._generate_function(func)
            lines.extend(func_code)
            lines.append('')
        
        # Add exports
        exports = self._generate_exports(module)
        if exports:
            lines.extend(exports)
        
        while lines and lines[-1] == "":
            lines.pop()
        
        return "\n".join(lines)
    
    def generate_project(self, project: UniversalProject) -> Dict[str, str]:
        """Generate TypeScript code for an entire project."""
        files = {}
        
        for module in project.modules:
            filename = f"{module.name}.ts"
            files[filename] = self.generate_module(module)
        
        # Generate tsconfig.json
        tsconfig = self._generate_tsconfig(project)
        files["tsconfig.json"] = tsconfig
        
        return files
    
    def _indent(self, text: str = "") -> str:
        """Return properly indented text."""
        return " " * (self.indent_level * self.indent_size) + text
    
    def _generate_imports(self, module: UniversalModule) -> List[str]:
        """Generate import statements."""
        from .import_translator import translate_imports

        # Filter metadata markers, then translate foreign imports
        raw = [imp for imp in module.imports
               if not imp.startswith(('interface:', 'type:'))]
        imports = translate_imports(raw, 'typescript')

        # External library imports (fallback heuristic)
        for func in module.functions:
            for lib in func.external_libraries:
                stmt = f"import * as {lib} from '{lib}';"
                if stmt not in imports:
                    imports.append(stmt)
        
        return imports
    
    def _generate_interfaces(self, module: UniversalModule) -> List[str]:
        """Generate interface declarations from metadata."""
        lines = []
        metadata = getattr(module, 'implementation_metadata', {})
        
        for key, info in metadata.items():
            if key.startswith('interface_'):
                name = info.get('name', '')
                extends = info.get('extends', [])
                body = info.get('body', '')
                
                if extends:
                    lines.append(f"interface {name} extends {', '.join(extends)} {{")
                else:
                    lines.append(f"interface {name} {{")
                
                # Add body with proper indentation
                for line in body.strip().split('\n'):
                    lines.append(f"  {line.strip()}")
                
                lines.append("}")
                lines.append("")
        
        return lines
    
    def _generate_type_aliases(self, module: UniversalModule) -> List[str]:
        """Generate type alias declarations from metadata."""
        lines = []
        metadata = getattr(module, 'implementation_metadata', {})
        
        for key, info in metadata.items():
            if key.startswith('type_'):
                name = info.get('name', '')
                definition = info.get('definition', '')
                lines.append(f"type {name} = {definition};")
        
        return lines
    
    def _generate_variable(self, var: UniversalVariable) -> str:
        """Generate TypeScript variable declaration."""
        keyword = "const" if var.is_constant else "let"
        type_annotation = self._map_type_to_typescript(var.type_sig)
        
        if var.value is not None:
            value = self._format_value(var.value, var.type_sig)
            return f"{keyword} {var.name}: {type_annotation} = {value};"
        else:
            return f"{keyword} {var.name}: {type_annotation};"
    
    def _generate_class(self, cls: UniversalClass) -> List[str]:
        """Generate TypeScript class definition."""
        lines = []
        
        # Class declaration
        class_decl = "class " + cls.name
        if cls.base_classes:
            class_decl += f" extends {cls.base_classes[0]}"
        
        implements = cls.implementation_hints.get('implements', [])
        if implements:
            class_decl += f" implements {', '.join(implements)}"
        
        class_decl += " {"
        
        if cls.implementation_hints.get('is_abstract'):
            lines.append(f"abstract {class_decl}")
        else:
            lines.append(class_decl)
        
        self.indent_level += 1
        
        # Properties (Parameter objects)
        for prop in cls.properties:
            visibility = "public"  # Default visibility
            readonly = ""
            type_annotation = self._map_type_to_typescript(prop.type_sig)
            
            if prop.default_value is not None:
                value = self._format_value(prop.default_value, prop.type_sig)
                lines.append(self._indent(f"{visibility} {readonly}{prop.name}: {type_annotation} = {value};"))
            else:
                lines.append(self._indent(f"{visibility} {prop.name}: {type_annotation};"))
        
        if cls.properties:
            lines.append("")
        
        # Methods
        for method in cls.methods:
            method_lines = self._generate_method(method)
            lines.extend(method_lines)
            lines.append("")
        
        self.indent_level -= 1
        lines.append("}")
        
        return lines
    
    def _generate_method(self, method: UniversalFunction) -> List[str]:
        """Generate TypeScript method."""
        lines = []
        
        visibility = method.implementation_hints.get('visibility', 'public')
        is_static = method.implementation_hints.get('is_static', False)
        is_async = method.implementation_hints.get('is_async', False)
        
        # Build method signature
        modifiers = []
        if visibility != 'public':
            modifiers.append(visibility)
        if is_static:
            modifiers.append('static')
        if is_async:
            modifiers.append('async')
        
        params = self._generate_parameters(method.parameters)
        return_type = self._map_type_to_typescript(method.return_type)
        
        modifier_str = ' '.join(modifiers) + ' ' if modifiers else ''
        
        if method.name == 'constructor':
            lines.append(self._indent(f"constructor({params}) {{"))
        else:
            lines.append(self._indent(f"{modifier_str}{method.name}({params}): {return_type} {{"))
        
        # Add method body placeholder
        self.indent_level += 1
        lines.append(self._indent("// TODO: Implement"))
        
        if method.return_type.base_type != DataType.VOID:
            default_return = self._get_default_return(method.return_type)
            lines.append(self._indent(f"return {default_return};"))
        
        self.indent_level -= 1
        lines.append(self._indent("}"))
        
        return lines
    
    def _generate_function(self, func: UniversalFunction) -> List[str]:
        """Generate TypeScript function."""
        lines = []
        
        is_async = func.implementation_hints.get('is_async', False)
        is_export = func.implementation_hints.get('is_export', True)
        is_arrow = func.implementation_hints.get('is_arrow_function', False)
        
        params = self._generate_parameters(func.parameters)
        return_type = self._map_type_to_typescript(func.return_type)
        
        if is_arrow:
            # Arrow function style
            async_prefix = 'async ' if is_async else ''
            export_prefix = 'export ' if is_export else ''
            lines.append(f"{export_prefix}const {func.name} = {async_prefix}({params}): {return_type} => {{")
        else:
            # Regular function style
            async_prefix = 'async ' if is_async else ''
            export_prefix = 'export ' if is_export else ''
            lines.append(f"{export_prefix}{async_prefix}function {func.name}({params}): {return_type} {{")
        
        # Add function body
        self.indent_level += 1
        lines.append(self._indent("// TODO: Implement"))
        
        if func.return_type.base_type != DataType.VOID:
            default_return = self._get_default_return(func.return_type)
            lines.append(self._indent(f"return {default_return};"))
        
        self.indent_level -= 1
        
        if is_arrow:
            lines.append("};")
        else:
            lines.append("}")
        
        return lines
    
    def _generate_parameters(self, parameters: List[Parameter]) -> str:
        """Generate TypeScript parameter list."""
        param_strs = []
        
        for param in parameters:
            type_annotation = self._map_type_to_typescript(param.type_sig)
            optional = '?' if not param.required and param.default_value is None else ''
            
            if param.default_value is not None:
                param_strs.append(f"{param.name}: {type_annotation} = {param.default_value}")
            else:
                param_strs.append(f"{param.name}{optional}: {type_annotation}")
        
        return ", ".join(param_strs)
    
    def _map_type_to_typescript(self, type_sig: TypeSignature) -> str:
        """Map UIR type signature to TypeScript type."""
        type_mapping = {
            DataType.VOID: 'void',
            DataType.BOOLEAN: 'boolean',
            DataType.INTEGER: 'number',
            DataType.FLOAT: 'number',
            DataType.STRING: 'string',
            DataType.ARRAY: 'any[]',
            DataType.OBJECT: 'object',
            DataType.FUNCTION: 'Function',
            DataType.ANY: 'any',
        }
        
        base = type_mapping.get(type_sig.base_type, 'any')
        
        if getattr(type_sig, 'is_async', False):
            return f"Promise<{base}>"
        
        return base
    
    def _format_value(self, value: Any, type_sig: TypeSignature) -> str:
        """Format a value for TypeScript output."""
        if isinstance(value, str):
            if value.startswith('"') or value.startswith("'"):
                return value
            if type_sig.base_type == DataType.STRING:
                return f'"{value}"'
            return str(value)
        return str(value)
    
    def _get_default_return(self, type_sig: TypeSignature) -> str:
        """Get default return value for a type."""
        defaults = {
            DataType.BOOLEAN: 'false',
            DataType.INTEGER: '0',
            DataType.FLOAT: '0',
            DataType.STRING: '""',
            DataType.ARRAY: '[]',
            DataType.OBJECT: '{}',
            DataType.ANY: 'null',
        }
        return defaults.get(type_sig.base_type, 'null')
    
    def _generate_exports(self, module: UniversalModule) -> List[str]:
        """Generate export statements."""
        exports = []
        
        # Collect non-exported items
        to_export = []
        for func in module.functions:
            if not func.implementation_hints.get('is_export', False):
                to_export.append(func.name)
        
        for cls in module.classes:
            to_export.append(cls.name)
        
        if to_export:
            exports.append(f"export {{ {', '.join(to_export)} }};")
        
        return exports
    
    def _generate_tsconfig(self, project: UniversalProject) -> str:
        """Generate tsconfig.json for the project."""
        return """{
  "compilerOptions": {
    "target": "ES2020",
    "module": "ESNext",
    "moduleResolution": "node",
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "forceConsistentCasingInFileNames": true,
    "declaration": true,
    "outDir": "./dist"
  },
  "include": ["*.ts"],
  "exclude": ["node_modules"]
}"""
