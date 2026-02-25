"""
Scala Code Generator from Universal IR.

This module generates Scala code from Universal Intermediate Representation.
"""

from typing import List, Dict, Any, Optional
from .universal_ir import (
    UniversalProject, UniversalModule, UniversalFunction, UniversalClass,
    UniversalVariable, Parameter, TypeSignature, DataType, LanguageMapping
)


class ScalaGenerator:
    """Generates Scala code from Universal IR."""
    
    def __init__(self):
        self.mapping = LanguageMapping("universal", "scala")
        self.indent_level = 0
        self.indent_size = 2  # Scala convention is 2 spaces
    
    def generate_module(self, module: UniversalModule) -> str:
        """Generate Scala code for a Universal Module."""
        lines = []
        
        # Package declaration
        package = getattr(module, 'scala_package', None) or 'com.vpyd.generated'
        lines.append(f"package {package}")
        lines.append("")
        
        # Imports from parsed source
        from .import_translator import translate_imports
        raw_imports = [imp for imp in module.imports if not imp.startswith('package:')]
        translated = translate_imports(raw_imports, 'scala')
        for imp in translated:
            if imp not in lines:
                lines.append(imp)
        if any(not imp.startswith('package:') for imp in module.imports):
            lines.append("")
        
        # Generate types
        for cls in module.classes:
            class_code = self._generate_type(cls)
            lines.extend(class_code)
            lines.append("")
        
        while lines and lines[-1] == "":
            lines.pop()
        
        return "\n".join(lines)
    
    def generate_project(self, project: UniversalProject) -> Dict[str, str]:
        """Generate Scala code for an entire project."""
        files = {}
        
        for module in project.modules:
            filename = f"{module.name}.scala"
            files[filename] = self.generate_module(module)
        
        # Generate build.sbt
        build_sbt = self._generate_build_sbt(project)
        files["build.sbt"] = build_sbt
        
        return files
    
    def _indent(self, text: str = "") -> str:
        """Return properly indented text."""
        return " " * (self.indent_level * self.indent_size) + text
    
    def _generate_type(self, cls: UniversalClass) -> List[str]:
        """Generate Scala type (class, trait, case class, or object)."""
        hints = cls.implementation_hints
        
        if hints.get('is_trait'):
            return self._generate_trait(cls)
        elif hints.get('is_case_class'):
            return self._generate_case_class(cls)
        elif hints.get('is_object') or hints.get('is_singleton'):
            return self._generate_object(cls)
        else:
            return self._generate_class(cls)
    
    def _generate_trait(self, cls: UniversalClass) -> List[str]:
        """Generate Scala trait."""
        lines = []
        
        type_params = ""
        if cls.implementation_hints.get('type_params'):
            type_params = f"[{cls.implementation_hints['type_params']}]"
        
        extends_str = ""
        if cls.base_classes:
            extends_str = f" extends {cls.base_classes[0]}"
            if len(cls.base_classes) > 1:
                extends_str += " with " + " with ".join(cls.base_classes[1:])
        
        lines.append(f"trait {cls.name}{type_params}{extends_str} {{")
        self.indent_level += 1
        
        for method in cls.methods:
            method_code = self._generate_method(method, is_abstract=True)
            lines.extend(method_code)
            lines.append("")
        
        self.indent_level -= 1
        lines.append("}")
        
        return lines
    
    def _generate_case_class(self, cls: UniversalClass) -> List[str]:
        """Generate Scala case class."""
        lines = []
        
        # Find constructor
        constructor = None
        for method in cls.methods:
            if method.implementation_hints.get('is_constructor'):
                constructor = method
                break
        
        type_params = ""
        if cls.implementation_hints.get('type_params'):
            type_params = f"[{cls.implementation_hints['type_params']}]"
        
        extends_str = ""
        if cls.base_classes:
            extends_str = f" extends {cls.base_classes[0]}"
            if len(cls.base_classes) > 1:
                extends_str += " with " + " with ".join(cls.base_classes[1:])
        
        if constructor:
            params = self._generate_parameters(constructor.parameters)
            lines.append(f"case class {cls.name}{type_params}({params}){extends_str}")
        else:
            lines.append(f"case class {cls.name}{type_params}(){extends_str}")
        
        # Check for additional methods
        other_methods = [m for m in cls.methods if not m.implementation_hints.get('is_constructor')]
        if other_methods:
            lines[-1] += " {"
            self.indent_level += 1
            
            for method in other_methods:
                method_code = self._generate_method(method)
                lines.extend(method_code)
                lines.append("")
            
            self.indent_level -= 1
            lines.append("}")
        
        return lines
    
    def _generate_object(self, cls: UniversalClass) -> List[str]:
        """Generate Scala object (singleton)."""
        lines = []
        
        extends_str = ""
        if cls.base_classes:
            extends_str = f" extends {cls.base_classes[0]}"
            if len(cls.base_classes) > 1:
                extends_str += " with " + " with ".join(cls.base_classes[1:])
        
        lines.append(f"object {cls.name}{extends_str} {{")
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
        """Generate Scala class."""
        lines = []
        
        # Find constructor
        constructor = None
        for method in cls.methods:
            if method.implementation_hints.get('is_constructor'):
                constructor = method
                break
        
        type_params = ""
        if cls.implementation_hints.get('type_params'):
            type_params = f"[{cls.implementation_hints['type_params']}]"
        
        extends_str = ""
        if cls.base_classes:
            extends_str = f" extends {cls.base_classes[0]}"
            if len(cls.base_classes) > 1:
                extends_str += " with " + " with ".join(cls.base_classes[1:])
        
        if constructor:
            params = self._generate_constructor_parameters(constructor.parameters)
            lines.append(f"class {cls.name}{type_params}({params}){extends_str} {{")
        else:
            lines.append(f"class {cls.name}{type_params}{extends_str} {{")
        
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
    
    def _generate_method(self, method: UniversalFunction, is_abstract: bool = False) -> List[str]:
        """Generate Scala method."""
        lines = []
        
        hints = method.implementation_hints
        type_params = ""
        if hints.get('type_params'):
            type_params = f"[{hints['type_params']}]"
        
        params = self._generate_parameters(method.parameters)
        return_type = self._map_type_to_scala(method.return_type)
        
        if is_abstract:
            if return_type == "Unit":
                lines.append(self._indent(f"def {method.name}{type_params}({params}): Unit"))
            else:
                lines.append(self._indent(f"def {method.name}{type_params}({params}): {return_type}"))
        else:
            if return_type == "Unit":
                lines.append(self._indent(f"def {method.name}{type_params}({params}): Unit = {{"))
            else:
                lines.append(self._indent(f"def {method.name}{type_params}({params}): {return_type} = {{"))
            
            self.indent_level += 1
            lines.append(self._indent("// TODO: Implement"))
            
            if method.return_type.base_type != DataType.VOID:
                default_return = self._get_default_return(method.return_type)
                lines.append(self._indent(f"{default_return}"))
            
            self.indent_level -= 1
            lines.append(self._indent("}"))
        
        return lines
    
    def _generate_parameters(self, parameters: List[Parameter]) -> str:
        """Generate Scala parameter list."""
        param_strs = []
        
        for param in parameters:
            type_str = self._map_type_to_scala(param.type_sig)
            if param.default_value:
                param_strs.append(f"{param.name}: {type_str} = {param.default_value}")
            else:
                param_strs.append(f"{param.name}: {type_str}")
        
        return ", ".join(param_strs)
    
    def _generate_constructor_parameters(self, parameters: List[Parameter]) -> str:
        """Generate Scala constructor parameters with val."""
        param_strs = []
        
        for param in parameters:
            type_str = self._map_type_to_scala(param.type_sig)
            if param.default_value:
                param_strs.append(f"val {param.name}: {type_str} = {param.default_value}")
            else:
                param_strs.append(f"val {param.name}: {type_str}")
        
        return ", ".join(param_strs)
    
    def _map_type_to_scala(self, type_sig: TypeSignature) -> str:
        """Map UIR type signature to Scala type."""
        type_mapping = {
            DataType.VOID: 'Unit',
            DataType.BOOLEAN: 'Boolean',
            DataType.INTEGER: 'Int',
            DataType.FLOAT: 'Double',
            DataType.STRING: 'String',
            DataType.ARRAY: 'List[Any]',
            DataType.OBJECT: 'Map[String, Any]',
            DataType.FUNCTION: '() => Unit',
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
            DataType.ARRAY: 'List.empty',
            DataType.OBJECT: 'Map.empty',
            DataType.ANY: '()',
        }
        return defaults.get(type_sig.base_type, '()')
    
    def _generate_build_sbt(self, project: UniversalProject) -> str:
        """Generate build.sbt file."""
        return """name := "vpyd-generated"

version := "0.1.0"

scalaVersion := "3.3.1"

libraryDependencies ++= Seq(
  "org.scalatest" %% "scalatest" % "3.2.17" % Test
)
"""
