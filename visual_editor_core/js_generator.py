"""
JavaScript Code Generator from Universal IR.

This module generates JavaScript code from Universal Intermediate Representation.
"""

from typing import List, Dict, Any, Optional
from .universal_ir import (
    UniversalProject, UniversalModule, UniversalFunction, UniversalClass,
    UniversalVariable, Parameter, TypeSignature, DataType, LanguageMapping
)


class JavaScriptGenerator:
    """Generates JavaScript code from Universal IR."""
    
    def __init__(self):
        self.mapping = LanguageMapping("universal", "javascript")
        self.indent_level = 0
        self.indent_size = 2
    
    def generate_module(self, module: UniversalModule) -> str:
        """Generate JavaScript code for a Universal Module."""
        lines = []
        
        # Add module comment if available
        if hasattr(module, 'description') and module.description:
            lines.append('/**')
            lines.append(f' * {module.description}')
            lines.append(' */')
            lines.append('')
        
        # Add imports
        imports = self._generate_imports(module)
        if imports:
            lines.extend(imports)
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
        
        # Remove trailing empty lines
        while lines and lines[-1] == "":
            lines.pop()
        
        return "\n".join(lines)
    
    def generate_project(self, project: UniversalProject) -> Dict[str, str]:
        """Generate JavaScript code for an entire project."""
        files = {}
        
        for module in project.modules:
            filename = f"{module.name}.js"
            files[filename] = self.generate_module(module)
        
        # Generate package.json if needed
        if len(project.modules) > 1:
            package_json = self._generate_package_json(project)
            files["package.json"] = package_json
        
        return files
    
    def _generate_imports(self, module: UniversalModule) -> List[str]:
        """Generate import statements."""
        from .import_translator import translate_imports

        # Translate any foreign-language imports to JS syntax
        imports = translate_imports(module.imports, 'javascript')

        # External library imports (fallback heuristic)
        for func in module.functions:
            for lib in func.external_libraries:
                stmt = f"const {lib} = require('{lib}');"
                if stmt not in imports:
                    imports.append(stmt)
        
        return imports
    
    def _generate_variable(self, var: UniversalVariable) -> str:
        """Generate JavaScript variable declaration."""
        keyword = "const" if var.is_constant else "let"
        
        if var.value is not None:
            if isinstance(var.value, str) and not var.value.startswith('"') and not var.value.startswith("'"):
                # Add quotes for string literals
                if var.type_sig.base_type == DataType.STRING:
                    value = f'"{var.value}"'
                else:
                    value = str(var.value)
            else:
                value = str(var.value)
            
            return f"{keyword} {var.name} = {value};"
        else:
            # Declaration without value
            return f"{keyword} {var.name};"
    
    def _generate_class(self, cls: UniversalClass) -> List[str]:
        """Generate JavaScript class definition."""
        lines = []
        
        # Class declaration
        if cls.base_classes:
            base = cls.base_classes[0]  # JavaScript only supports single inheritance
            lines.append(f"class {cls.name} extends {base} {{")
        else:
            lines.append(f"class {cls.name} {{")
        
        self.indent_level += 1
        
        # Constructor
        constructor_method = None
        for method in cls.methods:
            if method.implementation_hints.get('is_constructor', False):
                constructor_method = method
                break
        
        if constructor_method:
            constructor_lines = self._generate_constructor(constructor_method)
            lines.extend(constructor_lines)
            lines.append("")
        
        # Properties as constructor assignments (if no constructor exists)
        if not constructor_method and cls.properties:
            lines.append(self._indent("constructor() {"))
            self.indent_level += 1
            for prop in cls.properties:
                lines.append(self._indent(f"this.{prop.name} = null;"))
            self.indent_level -= 1
            lines.append(self._indent("}"))
            lines.append("")
        
        # Methods
        for method in cls.methods:
            if method.implementation_hints.get('is_constructor', False):
                continue  # Skip constructor, already handled
            
            method_lines = self._generate_method(method)
            lines.extend(method_lines)
            lines.append("")
        
        # If class is empty, add comment
        if len(lines) == 1:
            lines.append(self._indent("// Empty class"))
        
        self.indent_level -= 1
        lines.append("}")
        
        return lines
    
    def _generate_constructor(self, constructor: UniversalFunction) -> List[str]:
        """Generate JavaScript constructor method."""
        lines = []
        
        # Parameters
        params = []
        for param in constructor.parameters:
            param_str = param.name
            if not param.required and param.default_value is not None:
                if isinstance(param.default_value, str) and param.type_sig.base_type == DataType.STRING:
                    param_str += f' = "{param.default_value}"'
                else:
                    param_str += f" = {param.default_value}"
            params.append(param_str)
        
        params_str = ", ".join(params)
        lines.append(self._indent(f"constructor({params_str}) {{"))
        
        self.indent_level += 1
        
        # Constructor body
        if constructor.source_code and constructor.source_language == "javascript":
            body_lines = self._extract_js_method_body(constructor.source_code)
            for line in body_lines:
                lines.append(self._indent(line))
        else:
            # Generate placeholder body
            lines.append(self._indent("// TODO: Implement constructor"))
        
        self.indent_level -= 1
        lines.append(self._indent("}"))
        
        return lines
    
    def _generate_method(self, method: UniversalFunction) -> List[str]:
        """Generate JavaScript class method."""
        lines = []
        
        # Method signature
        is_async = method.implementation_hints.get('is_async', False)
        async_keyword = "async " if is_async else ""
        
        # Parameters
        params = []
        for param in method.parameters:
            param_str = param.name
            if not param.required and param.default_value is not None:
                if isinstance(param.default_value, str) and param.type_sig.base_type == DataType.STRING:
                    param_str += f' = "{param.default_value}"'
                else:
                    param_str += f" = {param.default_value}"
            params.append(param_str)
        
        params_str = ", ".join(params)
        lines.append(self._indent(f"{async_keyword}{method.name}({params_str}) {{"))
        
        self.indent_level += 1
        
        # Method body
        if method.source_code and method.source_language == "javascript":
            body_lines = self._extract_js_method_body(method.source_code)
            for line in body_lines:
                lines.append(self._indent(line))
        elif method.source_code and method.source_language == "python":
            # Convert Python body to JavaScript
            body_lines = self._convert_python_body_to_js(method.source_code, method)
            for line in body_lines:
                lines.append(self._indent(line))
        else:
            # Generate placeholder body
            if method.semantics and method.semantics.purpose:
                lines.append(self._indent(f'// TODO: Implement {method.semantics.purpose}'))
            else:
                lines.append(self._indent(f'// TODO: Implement {method.name}'))
            
            if method.return_type.base_type != DataType.VOID:
                if method.return_type.base_type == DataType.STRING:
                    lines.append(self._indent('return "";'))
                elif method.return_type.base_type == DataType.INTEGER:
                    lines.append(self._indent('return 0;'))
                elif method.return_type.base_type == DataType.BOOLEAN:
                    lines.append(self._indent('return false;'))
                elif method.return_type.base_type == DataType.ARRAY:
                    lines.append(self._indent('return [];'))
                elif method.return_type.base_type == DataType.OBJECT:
                    lines.append(self._indent('return {};'))
                else:
                    lines.append(self._indent('return null;'))
        
        self.indent_level -= 1
        lines.append(self._indent("}"))
        
        return lines
    
    def _generate_function(self, func: UniversalFunction) -> List[str]:
        """Generate JavaScript function definition."""
        lines = []
        
        # Function signature
        is_async = func.implementation_hints.get('is_async', False)
        is_arrow = func.implementation_hints.get('is_arrow_function', False)
        async_keyword = "async " if is_async else ""
        
        # Parameters
        params = []
        for param in func.parameters:
            param_str = param.name
            if not param.required and param.default_value is not None:
                if isinstance(param.default_value, str) and param.type_sig.base_type == DataType.STRING:
                    param_str += f' = "{param.default_value}"'
                else:
                    param_str += f" = {param.default_value}"
            params.append(param_str)
        
        params_str = ", ".join(params)
        
        # JSDoc comment
        if func.semantics and func.semantics.purpose:
            lines.append("/**")
            lines.append(f" * {func.semantics.purpose}")
            
            # Add parameter documentation
            if func.parameters:
                for param in func.parameters:
                    js_type = self.mapping.map_type(param.type_sig)
                    lines.append(f" * @param {{{js_type}}} {param.name}")
            
            # Add return documentation
            if func.return_type.base_type != DataType.VOID:
                js_return_type = self.mapping.map_type(func.return_type)
                lines.append(f" * @returns {{{js_return_type}}}")
            
            lines.append(" */")
        
        # Function declaration
        if is_arrow:
            lines.append(f"const {func.name} = {async_keyword}({params_str}) => {{")
        else:
            lines.append(f"{async_keyword}function {func.name}({params_str}) {{")
        
        self.indent_level += 1
        
        # Function body
        if func.source_code and func.source_language == "javascript":
            # Extract body from existing JavaScript code
            body_lines = self._extract_js_function_body(func.source_code)
            for line in body_lines:
                lines.append(self._indent(line))
        elif func.source_code and func.source_language == "python":
            # Convert Python body to JavaScript
            body_lines = self._convert_python_body_to_js(func.source_code, func)
            for line in body_lines:
                lines.append(self._indent(line))
        else:
            # Generate placeholder body
            if func.semantics and func.semantics.purpose:
                lines.append(self._indent(f'// TODO: Implement {func.semantics.purpose}'))
            else:
                lines.append(self._indent(f'// TODO: Implement {func.name}'))
            
            if func.return_type.base_type != DataType.VOID:
                if func.return_type.base_type == DataType.STRING:
                    lines.append(self._indent('return "";'))
                elif func.return_type.base_type == DataType.INTEGER:
                    lines.append(self._indent('return 0;'))
                elif func.return_type.base_type == DataType.BOOLEAN:
                    lines.append(self._indent('return false;'))
                elif func.return_type.base_type == DataType.ARRAY:
                    lines.append(self._indent('return [];'))
                elif func.return_type.base_type == DataType.OBJECT:
                    lines.append(self._indent('return {};'))
                else:
                    lines.append(self._indent('return null;'))
        
        self.indent_level -= 1
        
        if is_arrow:
            lines.append("};")
        else:
            lines.append("}")
        
        return lines
    
    def _convert_python_body_to_js(self, python_code: str, func: UniversalFunction) -> List[str]:
        """Convert Python function body to JavaScript."""
        # Extract function body from Python code
        if 'def ' in python_code:
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
        else:
            body_lines = python_code.strip().split('\n')
        
        js_lines = []
        
        # Simple Python to JavaScript conversions
        for line in body_lines:
            if not line.strip():
                js_lines.append('')
                continue
            
            # Convert common Python patterns to JavaScript
            line = line.replace('print(', 'console.log(')
            line = line.replace(' and ', ' && ')
            line = line.replace(' or ', ' || ')
            line = line.replace(' not ', ' !')
            line = line.replace('True', 'true')
            line = line.replace('False', 'false')
            line = line.replace('None', 'null')
            line = line.replace('elif', 'else if')
            line = line.replace('==', '===')
            line = line.replace('!=', '!==')
            
            # Handle Python-specific syntax
            if line.strip().startswith('if ') and line.strip().endswith(':'):
                line = line.replace(':', ' {')
            elif line.strip().startswith('else:'):
                line = line.replace(':', ' {')
            elif line.strip().startswith('elif '):
                line = line.replace('elif ', 'else if ').replace(':', ' {')
            elif line.strip().startswith('for ') and ' in ' in line and line.strip().endswith(':'):
                # Convert Python for loop to JavaScript
                parts = line.strip()[4:-1].split(' in ', 1)
                if len(parts) == 2:
                    var_name = parts[0].strip()
                    iterable = parts[1].strip()
                    line = f"for (const {var_name} of {iterable}) {{"
            elif line.strip().startswith('while ') and line.strip().endswith(':'):
                line = line.replace(':', ' {')
            
            # Add semicolons to statements that need them
            if line.strip() and not line.strip().endswith(('{', '}', ';')) and not line.strip().startswith(('if', 'else', 'for', 'while', 'function', '//')):
                line += ';'
            
            js_lines.append(line)
        
        # Add closing braces for control structures
        brace_count = 0
        for line in js_lines:
            brace_count += line.count('{') - line.count('}')
        
        for _ in range(brace_count):
            js_lines.append('}')
        
        if not js_lines or all(not line.strip() for line in js_lines):
            js_lines = ['// Converted from Python', 'return null;']
        
        return js_lines
    
    def _extract_js_function_body(self, js_code: str) -> List[str]:
        """Extract function body from JavaScript source code."""
        if '{' in js_code and '}' in js_code:
            start = js_code.find('{') + 1
            end = js_code.rfind('}')
            body = js_code[start:end].strip()
            
            if body:
                return [line for line in body.split('\n') if line.strip()]
            else:
                return ['// Empty function body']
        else:
            return ['// Could not extract function body']
    
    def _extract_js_method_body(self, js_code: str) -> List[str]:
        """Extract method body from JavaScript source code."""
        return self._extract_js_function_body(js_code)
    
    def _generate_exports(self, module: UniversalModule) -> List[str]:
        """Generate export statements."""
        exports = []
        
        # Export functions
        if module.functions:
            exports.append("")
            exports.append("// Exports")
            for func in module.functions:
                exports.append(f"module.exports.{func.name} = {func.name};")
        
        # Export classes
        if module.classes:
            if not exports:
                exports.append("")
                exports.append("// Exports")
            for cls in module.classes:
                exports.append(f"module.exports.{cls.name} = {cls.name};")
        
        return exports
    
    def _generate_package_json(self, project: UniversalProject) -> str:
        """Generate package.json for multi-module projects."""
        package_data = {
            "name": project.name.lower().replace(' ', '-'),
            "version": "1.0.0",
            "description": f"Generated from Universal IR project: {project.name}",
            "main": "index.js",
            "scripts": {
                "start": "node index.js",
                "test": "echo \"Error: no test specified\" && exit 1"
            },
            "keywords": ["universal-ir", "generated"],
            "author": "",
            "license": "ISC"
        }
        
        import json
        return json.dumps(package_data, indent=2)
    
    def _indent(self, line: str) -> str:
        """Add indentation to a line."""
        if not line.strip():
            return ""
        return " " * (self.indent_level * self.indent_size) + line


def generate_javascript_from_uir(module: UniversalModule) -> str:
    """Generate JavaScript code from a Universal Module."""
    generator = JavaScriptGenerator()
    return generator.generate_module(module)


def generate_javascript_project_from_uir(project: UniversalProject) -> Dict[str, str]:
    """Generate JavaScript files from a Universal Project."""
    generator = JavaScriptGenerator()
    return generator.generate_project(project)