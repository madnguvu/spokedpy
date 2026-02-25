"""Python to Universal IR Parser."""

import ast
from typing import Dict, List, Optional, Any, Union
from visual_editor_core.universal_ir import (
    UniversalModule, UniversalFunction, UniversalClass,
    UniversalVariable, Parameter, TypeSignature, DataType, SemanticDescription,
    Contract, PurityLevel
)


class PythonTypeInference:
    """Infers types from Python code patterns."""
    
    def infer_type_from_annotation(self, annotation) -> TypeSignature:
        """Infer type from Python type annotation."""
        if annotation is None:
            return TypeSignature(DataType.ANY)
        
        if isinstance(annotation, ast.Name):
            type_name = annotation.id
            if type_name == 'int':
                return TypeSignature(DataType.INTEGER)
            elif type_name == 'str':
                return TypeSignature(DataType.STRING)
            elif type_name == 'bool':
                return TypeSignature(DataType.BOOLEAN)
            else:
                return TypeSignature(DataType.ANY)
        
        return TypeSignature(DataType.ANY)
    
    def infer_type_from_value(self, node: ast.AST) -> TypeSignature:
        """Infer type from an AST value node."""
        if isinstance(node, ast.Constant):
            value = node.value
            if isinstance(value, bool):
                return TypeSignature(DataType.BOOLEAN)
            elif isinstance(value, int):
                return TypeSignature(DataType.INTEGER)
            elif isinstance(value, str):
                return TypeSignature(DataType.STRING)
        
        return TypeSignature(DataType.ANY)
    
    def infer_return_type_from_body(self, node) -> TypeSignature:
        """Infer return type from function body."""
        return TypeSignature(DataType.VOID)

class PythonParser:
    """Parses Python code into Universal IR."""
    
    def __init__(self):
        self.current_module = None
        self.type_inference = PythonTypeInference()
        self.function_nodes = {}
    
    def parse_code(self, python_code: str, filename: str = "unknown.py") -> UniversalModule:
        """Parse Python code into a Universal Module."""
        try:
            tree = ast.parse(python_code)
            
            module = UniversalModule(
                name=filename.replace('.py', ''),
                source_language="python",
                source_file=filename
            )
            
            self.current_module = module
            self.function_nodes = {}
            
            for node in tree.body:
                self._process_node(node, python_code)
            
            self._populate_dependencies()
            
            return module
            
        except SyntaxError as e:
            print(f"Python syntax error: {e}")
            return UniversalModule(
                name=filename.replace('.py', ''),
                source_language="python",
                source_file=filename
            )
    
    def _process_node(self, node: ast.AST, source_code: str):
        """Process an AST node and add to current module."""
        if isinstance(node, ast.FunctionDef):
            self._process_function_def(node, source_code, is_async=False)
        elif isinstance(node, ast.AsyncFunctionDef):
            self._process_function_def(node, source_code, is_async=True)
        elif isinstance(node, ast.ClassDef):
            self._process_class_def(node, source_code)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.asname:
                    self.current_module.imports.append(f"import {alias.name} as {alias.asname}")
                else:
                    self.current_module.imports.append(f"import {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            module_name = node.module or ''
            names = ', '.join(
                f"{alias.name} as {alias.asname}" if alias.asname else alias.name
                for alias in node.names
            )
            self.current_module.imports.append(f"from {module_name} import {names}")
    
    def _process_function_def(self, node: ast.AST, source_code: str, is_async: bool = False, qualname: str = None, class_name: str = None):
        """Process a function definition."""
        if qualname is None:
            qualname = node.name
        func = UniversalFunction(
            name=node.name,
            parameters=self._extract_parameters(node),
            return_type=self._extract_return_type(node),
            source_language="python",
            source_code=self._extract_source_segment(source_code, node),
            implementation_hints={'is_async': is_async}
        )
        func.implementation_hints["control_flow"] = self._extract_control_flow(node, source_code)
        self.current_module.functions.append(func)
        self.function_nodes[qualname] = {
            "function": func,
            "node": node,
            "class_name": class_name
        }
    
    def _process_class_def(self, node: ast.ClassDef, source_code: str):
        """Process a class definition."""
        cls = UniversalClass(
            name=node.name,
            source_language="python",
            source_code=self._extract_source_segment(source_code, node)
        )
        
        # Base classes
        cls.base_classes = [
            base.id for base in node.bases
            if isinstance(base, ast.Name)
        ]
        
        # Methods
        for child in node.body:
            if isinstance(child, ast.FunctionDef):
                method = UniversalFunction(
                    name=child.name,
                    parameters=self._extract_parameters(child),
                    return_type=self._extract_return_type(child),
                    source_language="python",
                    source_code=self._extract_source_segment(source_code, child),
                    implementation_hints={'is_async': False}
                )
                method.implementation_hints["control_flow"] = self._extract_control_flow(child, source_code)
                cls.methods.append(method)
                self.function_nodes[f"{node.name}.{child.name}"] = {
                    "function": method,
                    "node": child,
                    "class_name": node.name
                }
            elif isinstance(child, ast.AsyncFunctionDef):
                method = UniversalFunction(
                    name=child.name,
                    parameters=self._extract_parameters(child),
                    return_type=self._extract_return_type(child),
                    source_language="python",
                    source_code=self._extract_source_segment(source_code, child),
                    implementation_hints={'is_async': True}
                )
                method.implementation_hints["control_flow"] = self._extract_control_flow(child, source_code)
                cls.methods.append(method)
                self.function_nodes[f"{node.name}.{child.name}"] = {
                    "function": method,
                    "node": child,
                    "class_name": node.name
                }
        
        self.current_module.classes.append(cls)

    def _extract_source_segment(self, source_code: str, node: ast.AST) -> str:
        segment = ast.get_source_segment(source_code, node)
        if segment:
            return segment
        if hasattr(node, "lineno") and hasattr(node, "end_lineno"):
            lines = source_code.splitlines()
            start = max(node.lineno - 1, 0)
            end = max(node.end_lineno, start)
            return "\n".join(lines[start:end])
        return ""

    def _extract_parameters(self, node: ast.AST) -> list:
        parameters = []
        args = getattr(node, "args", None)
        if not args:
            return parameters
        
        positional = list(args.posonlyargs) + list(args.args)
        defaults = list(args.defaults)
        default_offset = len(positional) - len(defaults)
        
        for index, arg in enumerate(positional):
            default_value = None
            if index >= default_offset:
                default_value = defaults[index - default_offset]
            parameters.append(Parameter(
                name=arg.arg,
                type_sig=TypeSignature(DataType.ANY),
                default_value=self._literal_or_none(default_value)
            ))
        
        for kw_arg, kw_default in zip(args.kwonlyargs, args.kw_defaults):
            parameters.append(Parameter(
                name=kw_arg.arg,
                type_sig=TypeSignature(DataType.ANY),
                default_value=self._literal_or_none(kw_default)
            ))
        
        if args.vararg:
            parameters.append(Parameter(
                name=args.vararg.arg,
                type_sig=TypeSignature(DataType.ARRAY),
                required=False
            ))
        
        if args.kwarg:
            parameters.append(Parameter(
                name=args.kwarg.arg,
                type_sig=TypeSignature(DataType.OBJECT),
                required=False
            ))
        
        return parameters

    def _extract_return_type(self, node: ast.AST) -> TypeSignature:
        returns = getattr(node, "returns", None)
        if not returns:
            return TypeSignature(DataType.VOID)
        return self._map_annotation(returns)

    def _map_annotation(self, annotation: ast.AST) -> TypeSignature:
        if isinstance(annotation, ast.Name):
            return TypeSignature(self._map_name_to_type(annotation.id))
        if isinstance(annotation, ast.Subscript):
            if isinstance(annotation.value, ast.Name):
                return TypeSignature(self._map_name_to_type(annotation.value.id))
        if isinstance(annotation, ast.Constant) and annotation.value is None:
            return TypeSignature(DataType.VOID)
        return TypeSignature(DataType.ANY)

    def _map_name_to_type(self, name: str) -> DataType:
        name_lower = name.lower()
        mapping = {
            "none": DataType.VOID,
            "bool": DataType.BOOLEAN,
            "boolean": DataType.BOOLEAN,
            "int": DataType.INTEGER,
            "integer": DataType.INTEGER,
            "float": DataType.FLOAT,
            "str": DataType.STRING,
            "string": DataType.STRING,
            "list": DataType.ARRAY,
            "dict": DataType.OBJECT,
            "any": DataType.ANY
        }
        return mapping.get(name_lower, DataType.ANY)

    def _literal_or_none(self, node: ast.AST):
        if node is None:
            return None
        if isinstance(node, ast.Constant):
            return node.value
        return None

    def _extract_control_flow(self, node: ast.AST, source_code: str) -> list:
        control_nodes = []
        for child in ast.walk(node):
            kind = None
            if isinstance(child, ast.If):
                kind = "if_condition"
            elif isinstance(child, ast.For):
                kind = "for_loop"
            elif isinstance(child, ast.While):
                kind = "while_loop"
            elif isinstance(child, ast.Try):
                kind = "try_except"
            elif isinstance(child, ast.With):
                kind = "with"
            
            if not kind:
                continue
            
            control_nodes.append({
                "kind": kind,
                "lineno": getattr(child, "lineno", 0),
                "source_code": self._extract_source_segment(source_code, child)
            })
        
        control_nodes.sort(key=lambda item: item.get("lineno", 0))
        return control_nodes

    def _populate_dependencies(self):
        """Populate function dependencies using a simple call graph."""
        name_to_id = {key: entry["function"].id for key, entry in self.function_nodes.items()}
        
        for qualname, entry in self.function_nodes.items():
            func = entry["function"]
            node = entry["node"]
            class_name = entry.get("class_name")
            local_names = set(param.name for param in func.parameters)
            local_names.update(self._collect_assigned_names(node))
            
            called_ids = set()
            external_calls = set()
            for call in ast.walk(node):
                if not isinstance(call, ast.Call):
                    continue
                
                target_name = None
                if isinstance(call.func, ast.Name):
                    target_name = call.func.id
                elif isinstance(call.func, ast.Attribute):
                    if isinstance(call.func.value, ast.Name):
                        base = call.func.value.id
                        if base in local_names:
                            continue
                        if base in ("self", "cls") and class_name:
                            target_name = f"{class_name}.{call.func.attr}"
                        else:
                            target_name = f"{base}.{call.func.attr}"
                
                if not target_name:
                    continue
                
                if target_name in name_to_id:
                    called_ids.add(name_to_id[target_name])
                else:
                    external_calls.add(target_name)
            
            func.dependencies = list(called_ids)
            func.implementation_hints["external_calls"] = sorted(external_calls)

    def _collect_assigned_names(self, node: ast.AST) -> set:
        names = set()
        for child in ast.walk(node):
            if isinstance(child, ast.Assign):
                for target in child.targets:
                    names.update(self._extract_target_names(target))
            elif isinstance(child, ast.AnnAssign):
                names.update(self._extract_target_names(child.target))
            elif isinstance(child, ast.For):
                names.update(self._extract_target_names(child.target))
            elif isinstance(child, ast.With):
                for item in child.items:
                    if item.optional_vars is not None:
                        names.update(self._extract_target_names(item.optional_vars))
        return names

    def _extract_target_names(self, target: ast.AST) -> set:
        names = set()
        if isinstance(target, ast.Name):
            names.add(target.id)
        elif isinstance(target, (ast.Tuple, ast.List)):
            for elt in target.elts:
                names.update(self._extract_target_names(elt))
        return names

def parse_python_code(python_code: str, filename: str = "code.py") -> UniversalModule:
    """Parse Python code string into Universal IR."""
    parser = PythonParser()
    return parser.parse_code(python_code, filename)
