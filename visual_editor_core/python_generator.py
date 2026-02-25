"""
Python Code Generator from Universal IR.

This module generates Python code from Universal Intermediate Representation.
"""

from typing import List, Dict, Any, Optional
from .universal_ir import (
    UniversalProject, UniversalModule, UniversalFunction, UniversalClass,
    UniversalVariable, Parameter, TypeSignature, DataType, LanguageMapping
)


class PythonGenerator:
    """Generates Python code from Universal IR."""
    
    def __init__(self):
        self.mapping = LanguageMapping("universal", "python")
        self.indent_level = 0
        self.indent_size = 4
    
    def generate_module(self, module: UniversalModule) -> str:
        """Generate Python code for a Universal Module."""
        lines = []
        
        # Add module docstring if available
        if hasattr(module, 'description') and module.description:
            lines.append(f'"""')
            lines.append(module.description)
            lines.append(f'"""')
            lines.append("")
        
        # Add imports
        imports = self._generate_imports(module)
        if imports:
            lines.extend(imports)
            lines.append("")
        
        # Generate variables/constants
        for var in module.variables:
            var_code = self._generate_variable(var)
            if var_code:
                lines.append(var_code)
        
        if module.variables:
            lines.append("")
        
        # Generate classes
        for cls in module.classes:
            class_code = self._generate_class(cls)
            lines.extend(class_code)
            lines.append("")
        
        # Generate functions
        for func in module.functions:
            func_code = self._generate_function(func)
            lines.extend(func_code)
            lines.append("")
        
        # Remove trailing empty lines
        while lines and lines[-1] == "":
            lines.pop()
        
        return "\n".join(lines)
    
    def generate_project(self, project: UniversalProject) -> Dict[str, str]:
        """Generate Python code for an entire project."""
        files = {}
        
        for module in project.modules:
            filename = f"{module.name}.py"
            files[filename] = self.generate_module(module)
        
        # Generate main file if needed
        if len(project.modules) > 1:
            main_content = self._generate_main_file(project)
            files["main.py"] = main_content
        
        return files
    
    def _generate_imports(self, module: UniversalModule) -> List[str]:
        """Generate import statements."""
        imports = []
        seen = set()
        
        # 1) Parsed imports from module.imports (populated by parser / ledger)
        for imp in module.imports:
            stripped = imp.strip()
            if not stripped:
                continue
            if stripped not in seen:
                seen.add(stripped)
                imports.append(stripped)
        
        # 2) Heuristic: async functions need asyncio
        needs_asyncio = any(
            func.implementation_hints.get('is_async', False) 
            for func in module.functions
        )
        if needs_asyncio:
            stmt = "import asyncio"
            if stmt not in seen:
                seen.add(stmt)
                imports.append(stmt)
        
        # 3) Heuristic: typed parameters need typing
        needs_typing = any(
            param.type_sig.base_type != DataType.ANY 
            for func in module.functions 
            for param in func.parameters
        )
        if needs_typing:
            stmt = "from typing import List, Dict, Any, Optional, Callable"
            if stmt not in seen:
                seen.add(stmt)
                imports.append(stmt)
        
        # 4) Fallback: external_libraries
        for func in module.functions:
            for lib in func.external_libraries:
                stmt = f"import {lib}"
                if stmt not in seen:
                    seen.add(stmt)
                    imports.append(stmt)
        
        return imports
    
    def _generate_variable(self, var: UniversalVariable) -> str:
        """Generate Python variable declaration."""
        if var.is_constant:
            # Constants in uppercase
            name = var.name.upper()
        else:
            name = var.name
        
        if var.value is not None:
            if isinstance(var.value, str) and not var.value.startswith('"') and not var.value.startswith("'"):
                # Add quotes for string literals
                if var.type_sig.base_type == DataType.STRING:
                    value = f'"{var.value}"'
                else:
                    value = str(var.value)
            else:
                value = str(var.value)
            
            return f"{name} = {value}"
        else:
            # Type annotation without value
            py_type = self.mapping.map_type(var.type_sig)
            return f"{name}: {py_type}"
    
    def _generate_class(self, cls: UniversalClass) -> List[str]:
        """Generate Python class definition."""
        lines = []
        
        # Class declaration
        if cls.base_classes:
            bases = ", ".join(cls.base_classes)
            lines.append(f"class {cls.name}({bases}):")
        else:
            lines.append(f"class {cls.name}:")
        
        self.indent_level += 1
        
        # Class docstring
        if hasattr(cls, 'description') and cls.description:
            lines.append(self._indent(f'"""'))
            lines.append(self._indent(cls.description))
            lines.append(self._indent(f'"""'))
            lines.append("")
        
        # Properties as class variables
        for prop in cls.properties:
            prop_type = self.mapping.map_type(prop.type_sig)
            lines.append(self._indent(f"{prop.name}: {prop_type}"))
        
        if cls.properties:
            lines.append("")
        
        # Methods
        for method in cls.methods:
            method_lines = self._generate_function(method, is_method=True)
            lines.extend(method_lines)
            lines.append("")
        
        # If class is empty, add pass
        if len(lines) == 1:
            lines.append(self._indent("pass"))
        
        self.indent_level -= 1
        
        return lines
    
    def _generate_function(self, func: UniversalFunction, is_method: bool = False) -> List[str]:
        """Generate Python function definition."""
        lines = []
        
        # Function signature
        is_async = func.implementation_hints.get('is_async', False)
        async_keyword = "async " if is_async else ""
        
        # Parameters
        params = []
        if is_method:
            params.append("self")
        
        for param in func.parameters:
            param_str = param.name
            
            # Add type annotation
            if param.type_sig.base_type != DataType.ANY:
                py_type = self.mapping.map_type(param.type_sig)
                param_str += f": {py_type}"
            
            # Add default value
            if not param.required and param.default_value is not None:
                if isinstance(param.default_value, str) and param.type_sig.base_type == DataType.STRING:
                    param_str += f' = "{param.default_value}"'
                else:
                    param_str += f" = {param.default_value}"
            
            params.append(param_str)
        
        params_str = ", ".join(params)
        
        # Return type annotation
        return_annotation = ""
        if func.return_type.base_type != DataType.VOID:
            py_return_type = self.mapping.map_type(func.return_type)
            return_annotation = f" -> {py_return_type}"
        
        # Function declaration
        func_line = f"{async_keyword}def {func.name}({params_str}){return_annotation}:"
        lines.append(self._indent(func_line))
        
        self.indent_level += 1
        
        # Docstring
        if func.semantics and func.semantics.purpose:
            lines.append(self._indent(f'"""'))
            lines.append(self._indent(func.semantics.purpose))
            
            # Add parameter documentation
            if func.parameters:
                lines.append(self._indent(""))
                lines.append(self._indent("Args:"))
                for param in func.parameters:
                    param_doc = f"    {param.name}: {param.type_sig}"
                    lines.append(self._indent(param_doc))
            
            # Add return documentation
            if func.return_type.base_type != DataType.VOID:
                lines.append(self._indent(""))
                lines.append(self._indent("Returns:"))
                lines.append(self._indent(f"    {func.return_type}"))
            
            lines.append(self._indent(f'"""'))
        
        # Function body
        if func.source_code and func.source_language == "python":
            # Extract body from existing Python code
            body_lines = self._extract_python_function_body(func.source_code)
            for line in body_lines:
                lines.append(self._indent(line))
        elif func.source_code and func.source_language == "javascript":
            # Convert JavaScript body to Python
            body_lines = self._convert_js_body_to_python(func.source_code, func)
            for line in body_lines:
                lines.append(self._indent(line))
        else:
            # Generate placeholder body
            if func.semantics and func.semantics.purpose:
                lines.append(self._indent(f'# TODO: Implement {func.semantics.purpose}'))
            else:
                lines.append(self._indent(f'# TODO: Implement {func.name}'))
            
            if func.return_type.base_type != DataType.VOID:
                if func.return_type.base_type == DataType.STRING:
                    lines.append(self._indent('return ""'))
                elif func.return_type.base_type == DataType.INTEGER:
                    lines.append(self._indent('return 0'))
                elif func.return_type.base_type == DataType.BOOLEAN:
                    lines.append(self._indent('return False'))
                elif func.return_type.base_type == DataType.ARRAY:
                    lines.append(self._indent('return []'))
                elif func.return_type.base_type == DataType.OBJECT:
                    lines.append(self._indent('return {}'))
                else:
                    lines.append(self._indent('return None'))
            else:
                lines.append(self._indent('pass'))
        
        self.indent_level -= 1
        
        return lines
    
    def _convert_js_body_to_python(self, js_code: str, func: UniversalFunction) -> List[str]:
        """Convert JavaScript function body to Python."""
        # Extract function body from JavaScript code
        if '{' in js_code and '}' in js_code:
            start = js_code.find('{') + 1
            end = js_code.rfind('}')
            body = js_code[start:end].strip()
        else:
            body = js_code.strip()
        
        lines = []
        
        # Simple JavaScript to Python conversions
        for line in body.split('\n'):
            line = line.strip()
            if not line:
                continue
            
            # Convert common JavaScript patterns to Python
            line = line.replace('console.log(', 'print(')
            line = line.replace('let ', '')
            line = line.replace('const ', '')
            line = line.replace('var ', '')
            line = line.replace('===', '==')
            line = line.replace('!==', '!=')
            line = line.replace('&&', ' and ')
            line = line.replace('||', ' or ')
            line = line.replace('!', ' not ')
            line = line.replace('true', 'True')
            line = line.replace('false', 'False')
            line = line.replace('null', 'None')
            line = line.replace('undefined', 'None')
            
            # Remove semicolons
            if line.endswith(';'):
                line = line[:-1]
            
            lines.append(line)
        
        if not lines:
            lines.append('# Converted from JavaScript')
            lines.append('pass')
        
        return lines
    
    def _extract_python_function_body(self, python_code: str) -> List[str]:
        """Extract function body from Python source code."""
        lines = python_code.split('\n')
        body_lines = []
        in_body = False
        
        for line in lines:
            if line.strip().startswith('def ') or line.strip().startswith('async def '):
                in_body = True
                continue
            elif in_body:
                if line.strip() and not line.startswith('    ') and not line.startswith('\t'):
                    # End of function body
                    break
                elif line.strip():
                    # Remove one level of indentation
                    if line.startswith('    '):
                        body_lines.append(line[4:])
                    elif line.startswith('\t'):
                        body_lines.append(line[1:])
                    else:
                        body_lines.append(line)
                else:
                    body_lines.append('')
        
        if not body_lines or all(not line.strip() for line in body_lines):
            body_lines = ['pass']
        
        return body_lines
    
    def _generate_main_file(self, project: UniversalProject) -> str:
        """Generate a main.py file for multi-module projects."""
        lines = []
        
        lines.append('"""')
        lines.append(f'Main entry point for {project.name} project.')
        lines.append('"""')
        lines.append('')
        
        # Import all modules
        for module in project.modules:
            lines.append(f'import {module.name}')
        
        lines.append('')
        lines.append('def main():')
        lines.append('    """Main function."""')
        lines.append('    # TODO: Implement main logic')
        lines.append('    pass')
        lines.append('')
        lines.append('if __name__ == "__main__":')
        lines.append('    main()')
        
        return '\n'.join(lines)
    
    def _indent(self, line: str) -> str:
        """Add indentation to a line."""
        if not line.strip():
            return ""
        return " " * (self.indent_level * self.indent_size) + line


def generate_python_from_uir(module: UniversalModule) -> str:
    """Generate Python code from a Universal Module."""
    generator = PythonGenerator()
    return generator.generate_module(module)


def generate_python_project_from_uir(project: UniversalProject) -> Dict[str, str]:
    """Generate Python files from a Universal Project."""
    generator = PythonGenerator()
    return generator.generate_project(project)