"""
Rust Code Generator from Universal IR.

This module generates Rust code from Universal Intermediate Representation.
"""

from typing import List, Dict, Any, Optional
from .universal_ir import (
    UniversalProject, UniversalModule, UniversalFunction, UniversalClass,
    UniversalVariable, Parameter, TypeSignature, DataType, LanguageMapping
)


class RustGenerator:
    """Generates Rust code from Universal IR."""
    
    def __init__(self):
        self.mapping = LanguageMapping("universal", "rust")
        self.indent_level = 0
        self.indent_size = 4
    
    def generate_module(self, module: UniversalModule) -> str:
        """Generate Rust code for a Universal Module."""
        lines = []
        
        # Module documentation
        lines.append(f"//! {module.name} module")
        lines.append("")
        
        # Use statements from parsed source
        from .import_translator import translate_imports
        translated = translate_imports(module.imports, 'rust')
        for imp in translated:
            if imp not in lines:
                lines.append(imp)
        if module.imports:
            lines.append("")
        
        # Generate constants
        for var in module.variables:
            if var.is_constant:
                type_str = self._map_type_to_rust(var.type_sig)
                lines.append(f"const {var.name.upper()}: {type_str} = {var.value};")
        
        if any(v.is_constant for v in module.variables):
            lines.append("")
        
        # Generate structs, enums, traits
        for cls in module.classes:
            class_code = self._generate_type(cls)
            lines.extend(class_code)
            lines.append("")
        
        # Generate impl blocks for structs
        for cls in module.classes:
            if cls.implementation_hints.get('is_struct') and cls.methods:
                impl_code = self._generate_impl(cls)
                lines.extend(impl_code)
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
        """Generate Rust code for an entire project."""
        files = {}
        
        for module in project.modules:
            filename = f"{module.name}.rs"
            files[filename] = self.generate_module(module)
        
        # Generate Cargo.toml
        cargo_toml = self._generate_cargo_toml(project)
        files["Cargo.toml"] = cargo_toml
        
        return files
    
    def _indent(self, text: str = "") -> str:
        """Return properly indented text."""
        return " " * (self.indent_level * self.indent_size) + text
    
    def _generate_type(self, cls: UniversalClass) -> List[str]:
        """Generate Rust type (struct, enum, or trait)."""
        hints = cls.implementation_hints
        
        if hints.get('is_trait'):
            return self._generate_trait(cls)
        elif hints.get('is_enum'):
            return self._generate_enum(cls)
        else:
            return self._generate_struct(cls)
    
    def _generate_trait(self, cls: UniversalClass) -> List[str]:
        """Generate Rust trait."""
        lines = []
        
        lines.append(f"pub trait {cls.name} {{")
        self.indent_level += 1
        
        for method in cls.methods:
            params = self._generate_parameters(method.parameters, include_self=True)
            return_type = self._map_type_to_rust(method.return_type)
            
            if return_type:
                lines.append(self._indent(f"fn {method.name}({params}) -> {return_type};"))
            else:
                lines.append(self._indent(f"fn {method.name}({params});"))
        
        self.indent_level -= 1
        lines.append("}")
        
        return lines
    
    def _generate_enum(self, cls: UniversalClass) -> List[str]:
        """Generate Rust enum."""
        lines = []
        
        lines.append(f"pub enum {cls.name} {{")
        self.indent_level += 1
        
        variants = cls.implementation_hints.get('variants', ['Variant1', 'Variant2'])
        for variant in variants:
            if variant:
                lines.append(self._indent(f"{variant},"))
        
        self.indent_level -= 1
        lines.append("}")
        
        return lines
    
    def _generate_struct(self, cls: UniversalClass) -> List[str]:
        """Generate Rust struct."""
        lines = []
        
        lines.append(f"pub struct {cls.name} {{")
        self.indent_level += 1
        
        # Generate fields from constructor parameters if available
        constructor = None
        for method in cls.methods:
            if method.implementation_hints.get('is_constructor'):
                constructor = method
                break
        
        if constructor:
            for param in constructor.parameters:
                type_str = self._map_type_to_rust(param.type_sig)
                lines.append(self._indent(f"pub {param.name}: {type_str},"))
        else:
            lines.append(self._indent("// Add struct fields here"))
        
        self.indent_level -= 1
        lines.append("}")
        
        return lines
    
    def _generate_impl(self, cls: UniversalClass) -> List[str]:
        """Generate Rust impl block."""
        lines = []
        
        lines.append(f"impl {cls.name} {{")
        self.indent_level += 1
        
        for method in cls.methods:
            hints = method.implementation_hints
            
            # Determine method visibility
            visibility = "pub "
            
            params = self._generate_parameters(method.parameters, include_self=hints.get('is_method', True))
            return_type = self._map_type_to_rust(method.return_type)
            
            if hints.get('is_constructor'):
                lines.append(self._indent(f"{visibility}fn new({params}) -> Self {{"))
            elif return_type:
                lines.append(self._indent(f"{visibility}fn {method.name}({params}) -> {return_type} {{"))
            else:
                lines.append(self._indent(f"{visibility}fn {method.name}({params}) {{"))
            
            self.indent_level += 1
            
            if hints.get('is_constructor'):
                lines.append(self._indent("Self {"))
                self.indent_level += 1
                for param in method.parameters:
                    lines.append(self._indent(f"{param.name},"))
                self.indent_level -= 1
                lines.append(self._indent("}"))
            else:
                lines.append(self._indent("// TODO: Implement"))
                if method.return_type.base_type != DataType.VOID:
                    default_return = self._get_default_return(method.return_type)
                    lines.append(self._indent(f"{default_return}"))
            
            self.indent_level -= 1
            lines.append(self._indent("}"))
            lines.append("")
        
        self.indent_level -= 1
        lines.append("}")
        
        return lines
    
    def _generate_function(self, func: UniversalFunction) -> List[str]:
        """Generate Rust standalone function."""
        lines = []
        
        params = self._generate_parameters(func.parameters, include_self=False)
        return_type = self._map_type_to_rust(func.return_type)
        
        if return_type:
            lines.append(f"pub fn {func.name}({params}) -> {return_type} {{")
        else:
            lines.append(f"pub fn {func.name}({params}) {{")
        
        self.indent_level += 1
        lines.append(self._indent("// TODO: Implement"))
        
        if func.return_type.base_type != DataType.VOID:
            default_return = self._get_default_return(func.return_type)
            lines.append(self._indent(f"{default_return}"))
        
        self.indent_level -= 1
        lines.append("}")
        
        return lines
    
    def _generate_parameters(self, parameters: List[Parameter], include_self: bool = False) -> str:
        """Generate Rust parameter list."""
        param_strs = []
        
        if include_self:
            param_strs.append("&self")
        
        for param in parameters:
            type_str = self._map_type_to_rust(param.type_sig)
            param_strs.append(f"{param.name}: {type_str}")
        
        return ", ".join(param_strs)
    
    def _map_type_to_rust(self, type_sig: TypeSignature) -> str:
        """Map UIR type signature to Rust type."""
        type_mapping = {
            DataType.VOID: '',
            DataType.BOOLEAN: 'bool',
            DataType.INTEGER: 'i64',
            DataType.FLOAT: 'f64',
            DataType.STRING: 'String',
            DataType.ARRAY: 'Vec<Box<dyn std::any::Any>>',
            DataType.OBJECT: 'Box<dyn std::any::Any>',
            DataType.FUNCTION: 'Box<dyn Fn()>',
            DataType.ANY: 'Box<dyn std::any::Any>',
        }
        
        return type_mapping.get(type_sig.base_type, 'Box<dyn std::any::Any>')
    
    def _get_default_return(self, type_sig: TypeSignature) -> str:
        """Get default return value for a type."""
        defaults = {
            DataType.BOOLEAN: 'false',
            DataType.INTEGER: '0',
            DataType.FLOAT: '0.0',
            DataType.STRING: 'String::new()',
            DataType.ARRAY: 'Vec::new()',
            DataType.OBJECT: 'todo!()',
            DataType.ANY: 'todo!()',
        }
        return defaults.get(type_sig.base_type, 'todo!()')
    
    def _generate_cargo_toml(self, project: UniversalProject) -> str:
        """Generate Cargo.toml file."""
        return """[package]
name = "vpyd_generated"
version = "0.1.0"
edition = "2021"

[dependencies]
"""
