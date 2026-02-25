"""
Java Code Generator from Universal IR.

This module generates Java code from Universal Intermediate Representation.
"""

from typing import List, Dict, Any, Optional
from .universal_ir import (
    UniversalProject, UniversalModule, UniversalFunction, UniversalClass,
    UniversalVariable, Parameter, TypeSignature, DataType, LanguageMapping
)


class JavaGenerator:
    """Generates Java code from Universal IR."""
    
    def __init__(self):
        self.mapping = LanguageMapping("universal", "java")
        self.indent_level = 0
        self.indent_size = 4
    
    def generate_module(self, module: UniversalModule) -> str:
        """Generate Java code for a Universal Module."""
        lines = []
        
        # Package declaration
        java_package = getattr(module, "implementation_hints", {}).get("java_package")
        if java_package:
            lines.append(f"package {java_package};")
            lines.append("")
        
        # Imports
        imports = self._generate_imports(module)
        if imports:
            lines.extend(imports)
            lines.append("")
        
        # Generate classes
        for cls in module.classes:
            class_code = self._generate_class(cls)
            lines.extend(class_code)
            lines.append("")
        
        # If no classes, wrap functions in a utility class
        if module.functions and not module.classes:
            lines.append(f"public class {module.name} {{")
            self.indent_level += 1
            
            for func in module.functions:
                func_code = self._generate_method(func, force_static=True)
                lines.extend(func_code)
                lines.append("")
            
            self.indent_level -= 1
            lines.append("}")
        
        while lines and lines[-1] == "":
            lines.pop()
        
        return "\n".join(lines)
    
    def generate_project(self, project: UniversalProject) -> Dict[str, str]:
        """Generate Java code for an entire project."""
        files = {}
        
        for module in project.modules:
            filename = f"{module.name}.java"
            files[filename] = self.generate_module(module)
        
        # Generate pom.xml
        pom = self._generate_pom(project)
        files["pom.xml"] = pom
        
        return files
    
    def _indent(self, text: str = "") -> str:
        """Return properly indented text."""
        return " " * (self.indent_level * self.indent_size) + text
    
    def _generate_imports(self, module: UniversalModule) -> List[str]:
        """Generate import statements."""
        from .import_translator import translate_imports

        # Translate any foreign-language imports to Java syntax
        imports = translate_imports(module.imports, 'java')

        # Read external libraries from implementation_hints to avoid relying on a missing attribute
        external_libs = getattr(module, "implementation_hints", {}).get("external_libraries", [])
        for lib in external_libs:
            stmt = f"import {lib};"
            if stmt not in imports:
                imports.append(stmt)
        
        return imports
    
    def _generate_class(self, cls: UniversalClass) -> List[str]:
        """Generate Java class definition."""
        lines = []
        hints = cls.implementation_hints
        
        # Handle interfaces
        if hints.get('is_interface'):
            return self._generate_interface(cls)
        
        # Handle enums
        if hints.get('is_enum'):
            return self._generate_enum(cls)
        
        # Class declaration
        modifiers = []
        visibility = hints.get('visibility', 'public')
        if visibility != 'package':
            modifiers.append(visibility)
        if hints.get('is_abstract'):
            modifiers.append('abstract')
        if hints.get('is_final'):
            modifiers.append('final')
        modifiers.append('class')
        
        class_decl = ' '.join(modifiers) + f" {cls.name}"
        
        if cls.base_classes:
            class_decl += f" extends {cls.base_classes[0]}"
        
        implements = hints.get('implements', [])
        if implements:
            class_decl += f" implements {', '.join(implements)}"
        
        lines.append(class_decl + " {")
        self.indent_level += 1
        
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
        """Generate Java interface."""
        lines = []
        
        interface_decl = f"public interface {cls.name}"
        if cls.base_classes:
            interface_decl += f" extends {', '.join(cls.base_classes)}"
        
        lines.append(interface_decl + " {")
        self.indent_level += 1
        
        for method in cls.methods:
            params = self._generate_parameters(method.parameters)
            return_type = self._map_type_to_java(method.return_type)
            lines.append(self._indent(f"{return_type} {method.name}({params});"))
            lines.append("")
        
        if lines and lines[-1] == "":
            lines.pop()
        
        self.indent_level -= 1
        lines.append("}")
        
        return lines
    
    def _generate_enum(self, cls: UniversalClass) -> List[str]:
        """Generate Java enum."""
        lines = []
        
        enum_decl = f"public enum {cls.name}"
        implements = cls.implementation_hints.get('implements', [])
        if implements:
            enum_decl += f" implements {', '.join(implements)}"
        
        lines.append(enum_decl + " {")
        self.indent_level += 1
        lines.append(self._indent("// TODO: Add enum constants"))
        self.indent_level -= 1
        lines.append("}")
        
        return lines
    
    def _generate_method(self, func: UniversalFunction, force_static: bool = False) -> List[str]:
        """Generate Java method."""
        lines = []
        hints = func.implementation_hints
        
        # Build modifiers
        modifiers = []
        visibility = hints.get('visibility', 'public')
        if visibility != 'package':
            modifiers.append(visibility)
        if hints.get('is_static') or force_static:
            modifiers.append('static')
        if hints.get('is_abstract'):
            modifiers.append('abstract')
        if hints.get('is_final'):
            modifiers.append('final')
        if hints.get('is_synchronized'):
            modifiers.append('synchronized')
        
        params = self._generate_parameters(func.parameters)
        return_type = self._map_type_to_java(func.return_type)
        
        modifier_str = ' '.join(modifiers) + ' ' if modifiers else ''
        
        # Constructor handling
        if hints.get('is_constructor'):
            signature = f"{modifier_str}{func.name}({params})"
        else:
            signature = f"{modifier_str}{return_type} {func.name}({params})"
        
        # Throws clause
        throws = hints.get('throws', [])
        if throws:
            signature += f" throws {', '.join(throws)}"
        
        # Abstract methods have no body
        if hints.get('is_abstract'):
            lines.append(self._indent(signature + ";"))
            return lines
        
        lines.append(self._indent(signature + " {"))
        self.indent_level += 1
        
        if hints.get('is_constructor'):
            for param in func.parameters:
                lines.append(self._indent(f"this.{param.name} = {param.name};"))
        else:
            lines.append(self._indent("// TODO: Implement"))
            if func.return_type.base_type != DataType.VOID:
                default_return = self._get_default_return(func.return_type)
                lines.append(self._indent(f"return {default_return};"))
        
        self.indent_level -= 1
        lines.append(self._indent("}"))
        
        return lines
    
    def _generate_parameters(self, parameters: List[Parameter]) -> str:
        """Generate Java parameter list."""
        param_strs = []
        
        for param in parameters:
            type_str = self._map_type_to_java(param.type_sig)
            param_strs.append(f"{type_str} {param.name}")
        
        return ", ".join(param_strs)
    
    def _map_type_to_java(self, type_sig: TypeSignature) -> str:
        """Map UIR type signature to Java type."""
        type_mapping = {
            DataType.VOID: 'void',
            DataType.BOOLEAN: 'boolean',
            DataType.INTEGER: 'int',
            DataType.FLOAT: 'double',
            DataType.STRING: 'String',
            DataType.ARRAY: 'List<Object>',
            DataType.OBJECT: 'Object',
            DataType.FUNCTION: 'Runnable',
            DataType.ANY: 'Object',
        }
        
        return type_mapping.get(type_sig.base_type, 'Object')
    
    def _get_default_return(self, type_sig: TypeSignature) -> str:
        """Get default return value for a type."""
        defaults = {
            DataType.BOOLEAN: 'false',
            DataType.INTEGER: '0',
            DataType.FLOAT: '0.0',
            DataType.STRING: '""',
            DataType.ARRAY: 'new ArrayList<>()',
            DataType.OBJECT: 'null',
            DataType.ANY: 'null',
        }
        return defaults.get(type_sig.base_type, 'null')
    
    def _generate_pom(self, project: UniversalProject) -> str:
        """Generate Maven pom.xml."""
        return '''<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 http://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>
    
    <groupId>com.vpyd.generated</groupId>
    <artifactId>generated-project</artifactId>
    <version>1.0-SNAPSHOT</version>
    <packaging>jar</packaging>
    
    <properties>
        <maven.compiler.source>17</maven.compiler.source>
        <maven.compiler.target>17</maven.compiler.target>
        <project.build.sourceEncoding>UTF-8</project.build.sourceEncoding>
    </properties>
</project>'''
