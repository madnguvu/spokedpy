"""
Swift Code Generator from Universal IR.

This module generates Swift code from Universal Intermediate Representation.
"""

from typing import List, Dict, Any, Optional
from .universal_ir import (
    UniversalProject, UniversalModule, UniversalFunction, UniversalClass,
    UniversalVariable, Parameter, TypeSignature, DataType, LanguageMapping
)


class SwiftGenerator:
    """Generates Swift code from Universal IR."""
    
    def __init__(self):
        self.mapping = LanguageMapping("universal", "swift")
        self.indent_level = 0
        self.indent_size = 4
    
    def generate_module(self, module: UniversalModule) -> str:
        """Generate Swift code for a Universal Module."""
        lines = []
        
        # Import statements from parsed source
        from .import_translator import translate_imports
        translated = translate_imports(module.imports, 'swift')
        seen_imports = set()
        if translated:
            for imp in translated:
                lines.append(imp)
                seen_imports.add(imp.strip())
        # Always ensure Foundation is present
        if 'import Foundation' not in seen_imports:
            lines.insert(0, 'import Foundation')
        lines.append("")
        
        # Generate types
        for cls in module.classes:
            class_code = self._generate_type(cls)
            lines.extend(class_code)
            lines.append("")
        
        # Generate top-level functions
        for func in module.functions:
            func_code = self._generate_function(func)
            lines.extend(func_code)
            lines.append("")
        
        while lines and lines[-1] == "":
            lines.pop()
        
        return "\n".join(lines)
    
    def generate_project(self, project: UniversalProject) -> Dict[str, str]:
        """Generate Swift code for an entire project."""
        files = {}
        
        for module in project.modules:
            filename = f"{module.name}.swift"
            files[filename] = self.generate_module(module)
        
        # Generate Package.swift
        package_swift = self._generate_package_swift(project)
        files["Package.swift"] = package_swift
        
        return files
    
    def _indent(self, text: str = "") -> str:
        """Return properly indented text."""
        return " " * (self.indent_level * self.indent_size) + text
    
    def _generate_type(self, cls: UniversalClass) -> List[str]:
        """Generate Swift type (class, struct, protocol, or enum)."""
        hints = cls.implementation_hints
        
        if hints.get('is_protocol'):
            return self._generate_protocol(cls)
        elif hints.get('is_enum'):
            return self._generate_enum(cls)
        elif hints.get('is_struct'):
            return self._generate_struct(cls)
        else:
            return self._generate_class(cls)
    
    def _generate_protocol(self, cls: UniversalClass) -> List[str]:
        """Generate Swift protocol."""
        lines = []
        
        base_str = ""
        if cls.base_classes:
            base_str = f": {', '.join(cls.base_classes)}"
        
        lines.append(f"protocol {cls.name}{base_str} {{")
        self.indent_level += 1
        
        for method in cls.methods:
            params = self._generate_parameters(method.parameters)
            return_type = self._map_type_to_swift(method.return_type)
            
            if return_type == "Void":
                lines.append(self._indent(f"func {method.name}({params})"))
            else:
                lines.append(self._indent(f"func {method.name}({params}) -> {return_type}"))
        
        self.indent_level -= 1
        lines.append("}")
        
        return lines
    
    def _generate_enum(self, cls: UniversalClass) -> List[str]:
        """Generate Swift enum."""
        lines = []
        
        lines.append(f"enum {cls.name} {{")
        self.indent_level += 1
        
        cases = cls.implementation_hints.get('cases', ['case1', 'case2'])
        for case in cases:
            if case:
                lines.append(self._indent(f"case {case}"))
        
        # Generate methods
        for method in cls.methods:
            if not method.implementation_hints.get('is_constructor'):
                lines.append("")
                method_code = self._generate_method(method)
                lines.extend(method_code)
        
        self.indent_level -= 1
        lines.append("}")
        
        return lines
    
    def _generate_struct(self, cls: UniversalClass) -> List[str]:
        """Generate Swift struct."""
        lines = []
        
        base_str = ""
        if cls.base_classes:
            base_str = f": {', '.join(cls.base_classes)}"
        
        lines.append(f"struct {cls.name}{base_str} {{")
        self.indent_level += 1
        
        # Generate properties from constructor if available
        constructor = None
        for method in cls.methods:
            if method.implementation_hints.get('is_constructor'):
                constructor = method
                break
        
        if constructor:
            for param in constructor.parameters:
                type_str = self._map_type_to_swift(param.type_sig)
                lines.append(self._indent(f"var {param.name}: {type_str}"))
            lines.append("")
        
        # Generate methods (skip constructor for structs - memberwise init is automatic)
        for method in cls.methods:
            if not method.implementation_hints.get('is_constructor'):
                method_code = self._generate_method(method)
                lines.extend(method_code)
                lines.append("")
        
        self.indent_level -= 1
        lines.append("}")
        
        return lines
    
    def _generate_class(self, cls: UniversalClass) -> List[str]:
        """Generate Swift class."""
        lines = []
        
        base_str = ""
        if cls.base_classes:
            base_str = f": {', '.join(cls.base_classes)}"
        
        lines.append(f"class {cls.name}{base_str} {{")
        self.indent_level += 1
        
        # Generate properties from constructor if available
        constructor = None
        for method in cls.methods:
            if method.implementation_hints.get('is_constructor'):
                constructor = method
                break
        
        if constructor:
            for param in constructor.parameters:
                type_str = self._map_type_to_swift(param.type_sig)
                lines.append(self._indent(f"var {param.name}: {type_str}"))
            lines.append("")
            
            # Generate init
            lines.extend(self._generate_init(constructor))
            lines.append("")
        
        # Generate methods
        for method in cls.methods:
            if not method.implementation_hints.get('is_constructor'):
                method_code = self._generate_method(method)
                lines.extend(method_code)
                lines.append("")
        
        self.indent_level -= 1
        lines.append("}")
        
        return lines
    
    def _generate_init(self, constructor: UniversalFunction) -> List[str]:
        """Generate Swift initializer."""
        lines = []
        
        params = self._generate_parameters(constructor.parameters)
        lines.append(self._indent(f"init({params}) {{"))
        self.indent_level += 1
        
        for param in constructor.parameters:
            lines.append(self._indent(f"self.{param.name} = {param.name}"))
        
        self.indent_level -= 1
        lines.append(self._indent("}"))
        
        return lines
    
    def _generate_method(self, method: UniversalFunction) -> List[str]:
        """Generate Swift method."""
        lines = []
        
        hints = method.implementation_hints
        
        modifiers = []
        if hints.get('is_static'):
            modifiers.append("static")
        if hints.get('is_mutating'):
            modifiers.append("mutating")
        
        params = self._generate_parameters(method.parameters)
        return_type = self._map_type_to_swift(method.return_type)
        
        modifier_str = " ".join(modifiers) + " " if modifiers else ""
        
        if return_type == "Void":
            lines.append(self._indent(f"{modifier_str}func {method.name}({params}) {{"))
        else:
            lines.append(self._indent(f"{modifier_str}func {method.name}({params}) -> {return_type} {{"))
        
        self.indent_level += 1
        lines.append(self._indent("// TODO: Implement"))
        
        if method.return_type.base_type != DataType.VOID:
            default_return = self._get_default_return(method.return_type)
            lines.append(self._indent(f"return {default_return}"))
        
        self.indent_level -= 1
        lines.append(self._indent("}"))
        
        return lines
    
    def _generate_function(self, func: UniversalFunction) -> List[str]:
        """Generate Swift top-level function."""
        lines = []
        
        params = self._generate_parameters(func.parameters)
        return_type = self._map_type_to_swift(func.return_type)
        
        if return_type == "Void":
            lines.append(f"func {func.name}({params}) {{")
        else:
            lines.append(f"func {func.name}({params}) -> {return_type} {{")
        
        self.indent_level += 1
        lines.append(self._indent("// TODO: Implement"))
        
        if func.return_type.base_type != DataType.VOID:
            default_return = self._get_default_return(func.return_type)
            lines.append(self._indent(f"return {default_return}"))
        
        self.indent_level -= 1
        lines.append("}")
        
        return lines
    
    def _generate_parameters(self, parameters: List[Parameter]) -> str:
        """Generate Swift parameter list."""
        param_strs = []
        
        for param in parameters:
            type_str = self._map_type_to_swift(param.type_sig)
            if param.default_value:
                param_strs.append(f"{param.name}: {type_str} = {param.default_value}")
            else:
                param_strs.append(f"{param.name}: {type_str}")
        
        return ", ".join(param_strs)
    
    def _map_type_to_swift(self, type_sig: TypeSignature) -> str:
        """Map UIR type signature to Swift type."""
        type_mapping = {
            DataType.VOID: 'Void',
            DataType.BOOLEAN: 'Bool',
            DataType.INTEGER: 'Int',
            DataType.FLOAT: 'Double',
            DataType.STRING: 'String',
            DataType.ARRAY: '[Any]',
            DataType.OBJECT: '[String: Any]',
            DataType.FUNCTION: '() -> Void',
            DataType.ANY: 'Any',
        }
        
        return type_mapping.get(type_sig.base_type, 'Any')
    
    def _get_default_return(self, type_sig: TypeSignature) -> str:
        """Get default return value for a type."""
        defaults = {
            DataType.BOOLEAN: 'false',
            DataType.INTEGER: '0',
            DataType.FLOAT: '0.0',
            DataType.STRING: '""',
            DataType.ARRAY: '[]',
            DataType.OBJECT: '[:]',
            DataType.ANY: '"" as Any',
        }
        return defaults.get(type_sig.base_type, '"" as Any')
    
    def _generate_package_swift(self, project: UniversalProject) -> str:
        """Generate Package.swift file."""
        return """// swift-tools-version:5.9

import PackageDescription

let package = Package(
    name: "VPyDGenerated",
    products: [
        .library(
            name: "VPyDGenerated",
            targets: ["VPyDGenerated"]),
    ],
    dependencies: [],
    targets: [
        .target(
            name: "VPyDGenerated",
            dependencies: []),
        .testTarget(
            name: "VPyDGeneratedTests",
            dependencies: ["VPyDGenerated"]),
    ]
)
"""
