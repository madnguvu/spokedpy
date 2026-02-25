"""
C# Code Generator from Universal IR.

This module generates C# code from Universal Intermediate Representation.
"""

from typing import List, Dict, Any, Optional
from .universal_ir import (
    UniversalProject, UniversalModule, UniversalFunction, UniversalClass,
    UniversalVariable, Parameter, TypeSignature, DataType, LanguageMapping
)


class CSharpGenerator:
    """Generates C# code from Universal IR."""
    
    def __init__(self):
        self.mapping = LanguageMapping("universal", "csharp")
        self.indent_level = 0
        self.indent_size = 4
    
    def generate_module(self, module: UniversalModule) -> str:
        """Generate C# code for a Universal Module."""
        lines = []
        
        # Using directives
        usings = self._collect_usings(module)
        for using in usings:
            lines.append(f"using {using};")
        
        if usings:
            lines.append("")
        
        # Namespace
        namespace = getattr(module, 'csharp_namespace', None) or 'VPyD.Generated'
        lines.append(f"namespace {namespace}")
        lines.append("{")
        self.indent_level += 1
        
        # Generate classes, interfaces, enums
        for cls in module.classes:
            class_code = self._generate_type(cls)
            lines.extend(class_code)
            lines.append("")
        
        # Generate static class for standalone functions if any
        if module.functions:
            lines.append(self._indent("public static class Functions"))
            lines.append(self._indent("{"))
            self.indent_level += 1
            
            for func in module.functions:
                func_code = self._generate_method(func, is_static=True)
                lines.extend(func_code)
                lines.append("")
            
            self.indent_level -= 1
            lines.append(self._indent("}"))
            lines.append("")
        
        self.indent_level -= 1
        lines.append("}")
        
        return "\n".join(lines)
    
    def generate_project(self, project: UniversalProject) -> Dict[str, str]:
        """Generate C# code for an entire project."""
        files = {}
        
        for module in project.modules:
            filename = f"{module.name}.cs"
            files[filename] = self.generate_module(module)
        
        # Generate .csproj file
        csproj = self._generate_csproj(project)
        files["VPyD.Generated.csproj"] = csproj
        
        return files
    
    def _indent(self, text: str = "") -> str:
        """Return properly indented text."""
        return " " * (self.indent_level * self.indent_size) + text
    
    def _collect_usings(self, module: UniversalModule) -> List[str]:
        """Collect necessary using directives."""
        from .import_translator import translate_import

        usings = {'System'}
        
        # Include usings from parsed source
        for imp in module.imports:
            translated = translate_import(imp, 'csharp')
            # Stored as "using System.Linq;" — extract the namespace
            stripped = translated.strip().rstrip(';')
            if stripped.startswith('using '):
                usings.add(stripped[6:].strip())
            elif stripped.startswith('// Python dep:'):
                # Foreign import – keep the comment as-is (won't be wrapped)
                usings.add(translated.strip())
            else:
                usings.add(stripped)
        
        for cls in module.classes:
            for method in cls.methods:
                if method.implementation_hints.get('is_async'):
                    usings.add('System.Threading.Tasks')
        
        return sorted(usings)
    
    def _generate_type(self, cls: UniversalClass) -> List[str]:
        """Generate C# type (class, interface, struct, or enum)."""
        hints = cls.implementation_hints
        
        if hints.get('is_interface'):
            return self._generate_interface(cls)
        elif hints.get('is_enum'):
            return self._generate_enum(cls)
        elif hints.get('is_struct'):
            return self._generate_struct(cls)
        else:
            return self._generate_class(cls)
    
    def _generate_interface(self, cls: UniversalClass) -> List[str]:
        """Generate C# interface."""
        lines = []
        
        base_str = ""
        if cls.base_classes:
            base_str = f" : {', '.join(cls.base_classes)}"
        
        lines.append(self._indent(f"public interface {cls.name}{base_str}"))
        lines.append(self._indent("{"))
        self.indent_level += 1
        
        for method in cls.methods:
            params = self._generate_parameters(method.parameters)
            return_type = self._map_type_to_csharp(method.return_type)
            lines.append(self._indent(f"{return_type} {method.name}({params});"))
        
        self.indent_level -= 1
        lines.append(self._indent("}"))
        
        return lines
    
    def _generate_enum(self, cls: UniversalClass) -> List[str]:
        """Generate C# enum."""
        lines = []
        
        lines.append(self._indent(f"public enum {cls.name}"))
        lines.append(self._indent("{"))
        self.indent_level += 1
        
        values = cls.implementation_hints.get('values', ['Value1', 'Value2'])
        for i, value in enumerate(values):
            comma = "," if i < len(values) - 1 else ""
            lines.append(self._indent(f"{value}{comma}"))
        
        self.indent_level -= 1
        lines.append(self._indent("}"))
        
        return lines
    
    def _generate_struct(self, cls: UniversalClass) -> List[str]:
        """Generate C# struct."""
        lines = []
        
        lines.append(self._indent(f"public struct {cls.name}"))
        lines.append(self._indent("{"))
        self.indent_level += 1
        
        # Generate fields from constructor if available
        constructor = None
        for method in cls.methods:
            if method.implementation_hints.get('is_constructor'):
                constructor = method
                break
        
        if constructor:
            for param in constructor.parameters:
                type_str = self._map_type_to_csharp(param.type_sig)
                prop_name = param.name[0].upper() + param.name[1:] if param.name else param.name
                lines.append(self._indent(f"public {type_str} {prop_name} {{ get; set; }}"))
            lines.append("")
        
        for method in cls.methods:
            method_code = self._generate_method(method)
            lines.extend(method_code)
            lines.append("")
        
        self.indent_level -= 1
        lines.append(self._indent("}"))
        
        return lines
    
    def _generate_class(self, cls: UniversalClass) -> List[str]:
        """Generate C# class."""
        lines = []
        
        base_str = ""
        if cls.base_classes:
            base_str = f" : {', '.join(cls.base_classes)}"
        
        lines.append(self._indent(f"public class {cls.name}{base_str}"))
        lines.append(self._indent("{"))
        self.indent_level += 1
        
        # Generate properties from constructor parameters
        constructor = None
        for method in cls.methods:
            if method.implementation_hints.get('is_constructor'):
                constructor = method
                break
        
        if constructor:
            for param in constructor.parameters:
                type_str = self._map_type_to_csharp(param.type_sig)
                prop_name = param.name[0].upper() + param.name[1:] if param.name else param.name
                lines.append(self._indent(f"public {type_str} {prop_name} {{ get; set; }}"))
            lines.append("")
        
        # Generate methods
        for method in cls.methods:
            method_code = self._generate_method(method)
            lines.extend(method_code)
            lines.append("")
        
        self.indent_level -= 1
        lines.append(self._indent("}"))
        
        return lines
    
    def _generate_method(self, method: UniversalFunction, is_static: bool = False) -> List[str]:
        """Generate C# method."""
        lines = []
        
        hints = method.implementation_hints
        
        modifiers = ["public"]
        if is_static or hints.get('is_static'):
            modifiers.append("static")
        if hints.get('is_async'):
            modifiers.append("async")
        
        params = self._generate_parameters(method.parameters)
        
        if hints.get('is_constructor'):
            lines.append(self._indent(f"public {method.name}({params})"))
            lines.append(self._indent("{"))
            self.indent_level += 1
            
            for param in method.parameters:
                prop_name = param.name[0].upper() + param.name[1:] if param.name else param.name
                lines.append(self._indent(f"{prop_name} = {param.name};"))
            
            self.indent_level -= 1
            lines.append(self._indent("}"))
        else:
            return_type = self._map_type_to_csharp(method.return_type)
            modifier_str = " ".join(modifiers)
            
            lines.append(self._indent(f"{modifier_str} {return_type} {method.name}({params})"))
            lines.append(self._indent("{"))
            self.indent_level += 1
            
            lines.append(self._indent("// TODO: Implement"))
            
            if method.return_type.base_type != DataType.VOID:
                default_return = self._get_default_return(method.return_type)
                lines.append(self._indent(f"return {default_return};"))
            
            self.indent_level -= 1
            lines.append(self._indent("}"))
        
        return lines
    
    def _generate_parameters(self, parameters: List[Parameter]) -> str:
        """Generate C# parameter list."""
        param_strs = []
        
        for param in parameters:
            type_str = self._map_type_to_csharp(param.type_sig)
            if param.default_value:
                param_strs.append(f"{type_str} {param.name} = {param.default_value}")
            else:
                param_strs.append(f"{type_str} {param.name}")
        
        return ", ".join(param_strs)
    
    def _map_type_to_csharp(self, type_sig: TypeSignature) -> str:
        """Map UIR type signature to C# type."""
        type_mapping = {
            DataType.VOID: 'void',
            DataType.BOOLEAN: 'bool',
            DataType.INTEGER: 'int',
            DataType.FLOAT: 'double',
            DataType.STRING: 'string',
            DataType.ARRAY: 'List<object>',
            DataType.OBJECT: 'Dictionary<string, object>',
            DataType.FUNCTION: 'Action',
            DataType.ANY: 'object',
        }
        
        return type_mapping.get(type_sig.base_type, 'object')
    
    def _get_default_return(self, type_sig: TypeSignature) -> str:
        """Get default return value for a type."""
        defaults = {
            DataType.BOOLEAN: 'false',
            DataType.INTEGER: '0',
            DataType.FLOAT: '0.0',
            DataType.STRING: '""',
            DataType.ARRAY: 'new List<object>()',
            DataType.OBJECT: 'new Dictionary<string, object>()',
            DataType.ANY: 'null',
        }
        return defaults.get(type_sig.base_type, 'null')
    
    def _generate_csproj(self, project: UniversalProject) -> str:
        """Generate .csproj file."""
        return """<Project Sdk="Microsoft.NET.Sdk">

  <PropertyGroup>
    <OutputType>Library</OutputType>
    <TargetFramework>net8.0</TargetFramework>
    <ImplicitUsings>enable</ImplicitUsings>
    <Nullable>enable</Nullable>
  </PropertyGroup>

</Project>
"""
