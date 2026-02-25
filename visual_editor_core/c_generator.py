"""
C Code Generator from Universal IR.

This module generates C code from Universal Intermediate Representation.
"""

from typing import List, Dict, Any, Optional
from .universal_ir import (
    UniversalProject, UniversalModule, UniversalFunction, UniversalClass,
    UniversalVariable, Parameter, TypeSignature, DataType, LanguageMapping
)


class CGenerator:
    """Generates C code from Universal IR."""
    
    def __init__(self):
        self.mapping = LanguageMapping("universal", "c")
        self.indent_level = 0
        self.indent_size = 4
    
    def generate_module(self, module: UniversalModule) -> str:
        """Generate C code for a Universal Module."""
        lines = []
        
        # Include guards for header
        guard_name = f"{module.name.upper()}_H"
        
        # Includes from parsed source (user's original #include directives)
        from .import_translator import translate_imports
        translated = translate_imports(module.imports, 'c')
        parsed_includes = set()
        for imp in translated:
            lines.append(imp)
            # Track what's already included to avoid duplicates with defaults
            parsed_includes.add(imp.strip())
        
        # Standard includes (only add if not already present)
        defaults = ["#include <stdio.h>", "#include <stdlib.h>",
                     "#include <stdbool.h>", "#include <string.h>"]
        for d in defaults:
            if d not in parsed_includes:
                lines.append(d)
        lines.append("")
        
        # Generate macros/defines for constants
        constants = [v for v in module.variables if v.is_constant]
        for var in constants:
            lines.append(f"#define {var.name} {var.value}")
        
        if constants:
            lines.append("")
        
        # Generate struct declarations
        for cls in module.classes:
            if cls.implementation_hints.get('is_struct'):
                struct_code = self._generate_struct(cls)
                lines.extend(struct_code)
                lines.append("")
        
        # Generate enum declarations
        for cls in module.classes:
            if cls.implementation_hints.get('is_enum'):
                enum_code = self._generate_enum(cls)
                lines.extend(enum_code)
                lines.append("")
        
        # Generate function prototypes
        for func in module.functions:
            proto = self._generate_prototype(func)
            lines.append(proto)
        
        if module.functions:
            lines.append("")
        
        # Generate function implementations
        for func in module.functions:
            func_code = self._generate_function(func)
            lines.extend(func_code)
            lines.append("")
        
        while lines and lines[-1] == "":
            lines.pop()
        
        return "\n".join(lines)
    
    def generate_project(self, project: UniversalProject) -> Dict[str, str]:
        """Generate C code for an entire project."""
        files = {}
        
        for module in project.modules:
            # Generate .c file
            c_filename = f"{module.name}.c"
            files[c_filename] = self.generate_module(module)
            
            # Generate .h file
            h_filename = f"{module.name}.h"
            files[h_filename] = self._generate_header(module)
        
        # Generate Makefile
        files["Makefile"] = self._generate_makefile(project)
        
        return files
    
    def _indent(self, text: str = "") -> str:
        """Return properly indented text."""
        return " " * (self.indent_level * self.indent_size) + text
    
    def _generate_struct(self, cls: UniversalClass) -> List[str]:
        """Generate C struct."""
        lines = []
        
        typedef_name = cls.implementation_hints.get('typedef_name')
        
        if typedef_name:
            lines.append(f"typedef struct {cls.name} {{")
        else:
            lines.append(f"struct {cls.name} {{")
        
        self.indent_level += 1
        
        # Generate fields from constructor if available
        constructor = None
        for method in cls.methods:
            if method.implementation_hints.get('is_constructor'):
                constructor = method
                break
        
        if constructor:
            for param in constructor.parameters:
                type_str = self._map_type_to_c(param.type_sig)
                lines.append(self._indent(f"{type_str} {param.name};"))
        else:
            lines.append(self._indent("/* Add struct fields here */"))
        
        self.indent_level -= 1
        
        if typedef_name:
            lines.append(f"}} {typedef_name};")
        else:
            lines.append("};")
        
        return lines
    
    def _generate_enum(self, cls: UniversalClass) -> List[str]:
        """Generate C enum."""
        lines = []
        
        lines.append(f"typedef enum {{")
        self.indent_level += 1
        
        values = cls.implementation_hints.get('values', ['VALUE1', 'VALUE2'])
        for i, value in enumerate(values):
            comma = "," if i < len(values) - 1 else ""
            lines.append(self._indent(f"{value}{comma}"))
        
        self.indent_level -= 1
        lines.append(f"}} {cls.name};")
        
        return lines
    
    def _generate_prototype(self, func: UniversalFunction) -> str:
        """Generate C function prototype."""
        return_type = self._map_type_to_c(func.return_type)
        params = self._generate_parameters(func.parameters)
        
        return f"{return_type} {func.name}({params});"
    
    def _generate_function(self, func: UniversalFunction) -> List[str]:
        """Generate C function implementation."""
        lines = []
        
        return_type = self._map_type_to_c(func.return_type)
        params = self._generate_parameters(func.parameters)
        
        lines.append(f"{return_type} {func.name}({params}) {{")
        self.indent_level += 1
        
        lines.append(self._indent("/* TODO: Implement */"))
        
        if func.return_type.base_type != DataType.VOID:
            default_return = self._get_default_return(func.return_type)
            lines.append(self._indent(f"return {default_return};"))
        
        self.indent_level -= 1
        lines.append("}")
        
        return lines
    
    def _generate_parameters(self, parameters: List[Parameter]) -> str:
        """Generate C parameter list."""
        if not parameters:
            return "void"
        
        param_strs = []
        
        for param in parameters:
            if param.name == '...':
                param_strs.append('...')
            else:
                type_str = self._map_type_to_c(param.type_sig)
                param_strs.append(f"{type_str} {param.name}")
        
        return ", ".join(param_strs)
    
    def _map_type_to_c(self, type_sig: TypeSignature) -> str:
        """Map UIR type signature to C type."""
        type_mapping = {
            DataType.VOID: 'void',
            DataType.BOOLEAN: 'bool',
            DataType.INTEGER: 'int',
            DataType.FLOAT: 'double',
            DataType.STRING: 'char*',
            DataType.ARRAY: 'void*',
            DataType.OBJECT: 'void*',
            DataType.FUNCTION: 'void*',
            DataType.ANY: 'void*',
        }
        
        return type_mapping.get(type_sig.base_type, 'void*')
    
    def _get_default_return(self, type_sig: TypeSignature) -> str:
        """Get default return value for a type."""
        defaults = {
            DataType.BOOLEAN: 'false',
            DataType.INTEGER: '0',
            DataType.FLOAT: '0.0',
            DataType.STRING: 'NULL',
            DataType.ARRAY: 'NULL',
            DataType.OBJECT: 'NULL',
            DataType.ANY: 'NULL',
        }
        return defaults.get(type_sig.base_type, 'NULL')
    
    def _generate_header(self, module: UniversalModule) -> str:
        """Generate C header file."""
        guard_name = f"{module.name.upper()}_H"
        
        lines = [
            f"#ifndef {guard_name}",
            f"#define {guard_name}",
            "",
            "#include <stdbool.h>",
            "",
        ]
        
        # Struct forward declarations
        for cls in module.classes:
            if cls.implementation_hints.get('is_struct'):
                lines.append(f"typedef struct {cls.name} {cls.name};")
        
        if any(cls.implementation_hints.get('is_struct') for cls in module.classes):
            lines.append("")
        
        # Function prototypes
        for func in module.functions:
            proto = self._generate_prototype(func)
            lines.append(proto)
        
        lines.extend(["", f"#endif /* {guard_name} */", ""])
        
        return "\n".join(lines)
    
    def _generate_makefile(self, project: UniversalProject) -> str:
        """Generate Makefile."""
        return """CC = gcc
CFLAGS = -Wall -Wextra -std=c11
LDFLAGS =

SRCS = $(wildcard *.c)
OBJS = $(SRCS:.c=.o)
TARGET = program

all: $(TARGET)

$(TARGET): $(OBJS)
\t$(CC) $(LDFLAGS) -o $@ $^

%.o: %.c
\t$(CC) $(CFLAGS) -c -o $@ $<

clean:
\trm -f $(OBJS) $(TARGET)

.PHONY: all clean
"""
