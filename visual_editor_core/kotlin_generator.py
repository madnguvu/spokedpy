"""
Kotlin Code Generator from Universal IR.

This module generates Kotlin code from Universal Intermediate Representation.
"""

from typing import List, Dict, Any, Optional
from .universal_ir import (
    UniversalProject, UniversalModule, UniversalFunction, UniversalClass,
    UniversalVariable, Parameter, TypeSignature, DataType, LanguageMapping
)


class KotlinGenerator:
    """Generates Kotlin code from Universal IR."""
    
    def __init__(self):
        self.mapping = LanguageMapping("universal", "kotlin")
        self.indent_level = 0
        self.indent_size = 4
    
    def generate_module(self, module: UniversalModule) -> str:
        """Generate Kotlin code for a Universal Module."""
        lines = []
        
        # Package declaration
        package = getattr(module, 'kotlin_package', None) or 'com.vpyd.generated'
        lines.append(f"package {package}")
        lines.append("")
        
        # Imports from parsed source
        from .import_translator import translate_imports
        raw_imports = [imp for imp in module.imports if not imp.startswith('package:')]
        translated = translate_imports(raw_imports, 'kotlin')
        for imp in translated:
            if imp not in lines:
                lines.append(imp)
        if any(not imp.startswith('package:') for imp in module.imports):
            lines.append("")
        
        # Generate classes, interfaces, objects
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
        """Generate Kotlin code for an entire project."""
        files = {}
        
        for module in project.modules:
            filename = f"{module.name}.kt"
            files[filename] = self.generate_module(module)
        
        # Generate build.gradle.kts
        build_gradle = self._generate_build_gradle(project)
        files["build.gradle.kts"] = build_gradle
        
        return files
    
    def _indent(self, text: str = "") -> str:
        """Return properly indented text."""
        return " " * (self.indent_level * self.indent_size) + text
    
    def _generate_type(self, cls: UniversalClass) -> List[str]:
        """Generate Kotlin type (class, interface, data class, or object)."""
        hints = cls.implementation_hints
        
        if hints.get('is_interface'):
            return self._generate_interface(cls)
        elif hints.get('is_data_class'):
            return self._generate_data_class(cls)
        elif hints.get('is_object') or hints.get('is_singleton'):
            return self._generate_object(cls)
        else:
            return self._generate_class(cls)
    
    def _generate_interface(self, cls: UniversalClass) -> List[str]:
        """Generate Kotlin interface."""
        lines = []
        
        base_str = ""
        if cls.base_classes:
            base_str = f" : {', '.join(cls.base_classes)}"
        
        lines.append(f"interface {cls.name}{base_str} {{")
        self.indent_level += 1
        
        for method in cls.methods:
            params = self._generate_parameters(method.parameters)
            return_type = self._map_type_to_kotlin(method.return_type)
            
            if return_type == "Unit":
                lines.append(self._indent(f"fun {method.name}({params})"))
            else:
                lines.append(self._indent(f"fun {method.name}({params}): {return_type}"))
        
        self.indent_level -= 1
        lines.append("}")
        
        return lines
    
    def _generate_data_class(self, cls: UniversalClass) -> List[str]:
        """Generate Kotlin data class."""
        lines = []
        
        # Find constructor
        constructor = None
        for method in cls.methods:
            if method.implementation_hints.get('is_constructor'):
                constructor = method
                break
        
        if constructor:
            params = self._generate_constructor_parameters(constructor.parameters)
            base_str = ""
            if cls.base_classes:
                base_str = f" : {cls.base_classes[0]}()"
            
            if len(params) > 80:
                lines.append(f"data class {cls.name}(")
                self.indent_level += 1
                for i, param in enumerate(constructor.parameters):
                    type_str = self._map_type_to_kotlin(param.type_sig)
                    comma = "," if i < len(constructor.parameters) - 1 else ""
                    lines.append(self._indent(f"val {param.name}: {type_str}{comma}"))
                self.indent_level -= 1
                lines.append(f"){base_str}")
            else:
                lines.append(f"data class {cls.name}({params}){base_str}")
        else:
            lines.append(f"data class {cls.name}()")
        
        return lines
    
    def _generate_object(self, cls: UniversalClass) -> List[str]:
        """Generate Kotlin object (singleton)."""
        lines = []
        
        base_str = ""
        if cls.base_classes:
            base_str = f" : {', '.join(cls.base_classes)}"
        
        lines.append(f"object {cls.name}{base_str} {{")
        self.indent_level += 1
        
        for method in cls.methods:
            if not method.implementation_hints.get('is_constructor'):
                method_code = self._generate_method(method)
                lines.extend(method_code)
                lines.append("")
        
        self.indent_level -= 1
        lines.append("}")
        
        return lines
    
    def _generate_class(self, cls: UniversalClass) -> List[str]:
        """Generate Kotlin class."""
        lines = []
        
        # Find constructor
        constructor = None
        for method in cls.methods:
            if method.implementation_hints.get('is_constructor'):
                constructor = method
                break
        
        base_str = ""
        if cls.base_classes:
            base_str = f" : {cls.base_classes[0]}()"
        
        if constructor:
            params = self._generate_constructor_parameters(constructor.parameters)
            lines.append(f"class {cls.name}({params}){base_str} {{")
        else:
            lines.append(f"class {cls.name}{base_str} {{")
        
        self.indent_level += 1
        
        # Generate methods (skip constructor)
        for method in cls.methods:
            if not method.implementation_hints.get('is_constructor'):
                method_code = self._generate_method(method)
                lines.extend(method_code)
                lines.append("")
        
        self.indent_level -= 1
        lines.append("}")
        
        return lines
    
    def _generate_method(self, method: UniversalFunction) -> List[str]:
        """Generate Kotlin method."""
        lines = []
        
        hints = method.implementation_hints
        
        modifiers = []
        if hints.get('is_suspend'):
            modifiers.append("suspend")
        
        params = self._generate_parameters(method.parameters)
        return_type = self._map_type_to_kotlin(method.return_type)
        
        modifier_str = " ".join(modifiers) + " " if modifiers else ""
        
        if return_type == "Unit":
            lines.append(self._indent(f"{modifier_str}fun {method.name}({params}) {{"))
        else:
            lines.append(self._indent(f"{modifier_str}fun {method.name}({params}): {return_type} {{"))
        
        self.indent_level += 1
        lines.append(self._indent("// TODO: Implement"))
        
        if method.return_type.base_type != DataType.VOID:
            default_return = self._get_default_return(method.return_type)
            lines.append(self._indent(f"return {default_return}"))
        
        self.indent_level -= 1
        lines.append(self._indent("}"))
        
        return lines
    
    def _generate_function(self, func: UniversalFunction) -> List[str]:
        """Generate Kotlin top-level function."""
        lines = []
        
        hints = func.implementation_hints
        
        modifiers = []
        if hints.get('is_suspend'):
            modifiers.append("suspend")
        
        params = self._generate_parameters(func.parameters)
        return_type = self._map_type_to_kotlin(func.return_type)
        
        modifier_str = " ".join(modifiers) + " " if modifiers else ""
        
        if return_type == "Unit":
            lines.append(f"{modifier_str}fun {func.name}({params}) {{")
        else:
            lines.append(f"{modifier_str}fun {func.name}({params}): {return_type} {{")
        
        self.indent_level += 1
        lines.append(self._indent("// TODO: Implement"))
        
        if func.return_type.base_type != DataType.VOID:
            default_return = self._get_default_return(func.return_type)
            lines.append(self._indent(f"return {default_return}"))
        
        self.indent_level -= 1
        lines.append("}")
        
        return lines
    
    def _generate_parameters(self, parameters: List[Parameter]) -> str:
        """Generate Kotlin parameter list."""
        param_strs = []
        
        for param in parameters:
            type_str = self._map_type_to_kotlin(param.type_sig)
            if param.default_value:
                param_strs.append(f"{param.name}: {type_str} = {param.default_value}")
            else:
                param_strs.append(f"{param.name}: {type_str}")
        
        return ", ".join(param_strs)
    
    def _generate_constructor_parameters(self, parameters: List[Parameter]) -> str:
        """Generate Kotlin constructor parameters with val."""
        param_strs = []
        
        for param in parameters:
            type_str = self._map_type_to_kotlin(param.type_sig)
            if param.default_value:
                param_strs.append(f"val {param.name}: {type_str} = {param.default_value}")
            else:
                param_strs.append(f"val {param.name}: {type_str}")
        
        return ", ".join(param_strs)
    
    def _map_type_to_kotlin(self, type_sig: TypeSignature) -> str:
        """Map UIR type signature to Kotlin type."""
        type_mapping = {
            DataType.VOID: 'Unit',
            DataType.BOOLEAN: 'Boolean',
            DataType.INTEGER: 'Int',
            DataType.FLOAT: 'Double',
            DataType.STRING: 'String',
            DataType.ARRAY: 'List<Any>',
            DataType.OBJECT: 'Map<String, Any>',
            DataType.FUNCTION: '() -> Unit',
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
            DataType.ARRAY: 'emptyList()',
            DataType.OBJECT: 'emptyMap()',
            DataType.ANY: 'Unit',
        }
        return defaults.get(type_sig.base_type, 'Unit')
    
    def _generate_build_gradle(self, project: UniversalProject) -> str:
        """Generate build.gradle.kts file."""
        return """plugins {
    kotlin("jvm") version "1.9.0"
}

group = "com.vpyd.generated"
version = "1.0-SNAPSHOT"

repositories {
    mavenCentral()
}

dependencies {
    testImplementation(kotlin("test"))
}

tasks.test {
    useJUnitPlatform()
}

kotlin {
    jvmToolchain(17)
}
"""
