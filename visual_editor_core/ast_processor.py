"""
AST Processor for bidirectional conversion between visual models and Python ASTs.
"""

import ast
from typing import Dict, Type, Callable, List, Any, Optional
from .models import VisualModel, VisualNode, NodeType, Connection


class NodeMapper:
    """Base class for mapping visual nodes to AST nodes."""
    
    def __init__(self, node_type: NodeType):
        self.node_type = node_type
    
    def to_ast(self, node: VisualNode, context: Dict[str, Any]) -> ast.AST:
        """Convert a visual node to an AST node."""
        raise NotImplementedError("Subclasses must implement to_ast")


class FunctionNodeMapper(NodeMapper):
    """Maps function visual nodes to AST function calls."""
    
    def __init__(self):
        super().__init__(NodeType.FUNCTION)
    
    def to_ast(self, node: VisualNode, context: Dict[str, Any]) -> ast.AST:
        """Convert a function node to an AST Call node."""
        function_name = node.parameters.get('function_name', 'unknown_function')
        
        # Create function call
        func = ast.Name(id=function_name, ctx=ast.Load())
        
        # Convert input connections to arguments
        args = []
        keywords = []
        
        for input_port in node.inputs:
            # Find connections to this input port
            connected_value = context.get(f"{node.id}.{input_port.name}")
            if connected_value is not None:
                if input_port.name == 'args':
                    # Positional arguments
                    if isinstance(connected_value, list):
                        args.extend(connected_value)
                    else:
                        args.append(connected_value)
                else:
                    # Keyword arguments
                    keywords.append(ast.keyword(arg=input_port.name, value=connected_value))
            elif input_port.default_value is not None:
                # Use default value
                default_ast = self._value_to_ast(input_port.default_value)
                keywords.append(ast.keyword(arg=input_port.name, value=default_ast))
        
        return ast.Call(func=func, args=args, keywords=keywords)
    
    def _value_to_ast(self, value: Any) -> ast.AST:
        """Convert a Python value to an AST node."""
        if isinstance(value, str):
            return ast.Constant(value=value)
        elif isinstance(value, (int, float, bool)):
            return ast.Constant(value=value)
        elif value is None:
            return ast.Constant(value=None)
        else:
            # For complex values, create a name reference
            return ast.Name(id=str(value), ctx=ast.Load())


class VariableNodeMapper(NodeMapper):
    """Maps variable visual nodes to AST assignments."""
    
    def __init__(self):
        super().__init__(NodeType.VARIABLE)
    
    def to_ast(self, node: VisualNode, context: Dict[str, Any]) -> ast.AST:
        """Convert a variable node to an AST Assign node."""
        var_name = node.parameters.get('variable_name', f'var_{node.id[:8]}')
        
        # Get the value from input connection or default
        value_ast = context.get(f"{node.id}.value")
        if value_ast is None:
            default_value = node.parameters.get('default_value', 0)
            value_ast = ast.Constant(value=default_value)
        
        # Create assignment
        target = ast.Name(id=var_name, ctx=ast.Store())
        return ast.Assign(targets=[target], value=value_ast)


class ClassNodeMapper(NodeMapper):
    """Maps class visual nodes to AST class definitions."""
    
    def __init__(self):
        super().__init__(NodeType.CLASS)
    
    def to_ast(self, node: VisualNode, context: Dict[str, Any]) -> ast.AST:
        """Convert a class node to an AST ClassDef node."""
        class_name = node.parameters.get('class_name', 'UnnamedClass')
        
        # Get base classes from parameters or connections
        base_classes = node.parameters.get('base_classes', [])
        bases = []
        for base_name in base_classes:
            bases.append(ast.Name(id=base_name, ctx=ast.Load()))
        
        # Handle advanced OOP patterns
        class_type = node.parameters.get('class_type', 'basic')
        
        if class_type == 'abstract':
            return self._create_abstract_class(class_name, bases, node, context)
        elif class_type == 'dataclass':
            return self._create_dataclass(class_name, bases, node, context)
        elif class_type == 'singleton':
            return self._create_singleton_class(class_name, bases, node, context)
        else:
            return self._create_basic_class(class_name, bases, node, context)
    
    def _create_basic_class(self, class_name: str, bases: List[ast.AST], node: VisualNode, context: Dict[str, Any]) -> ast.ClassDef:
        """Create a basic class definition."""
        body = [ast.Pass()]
        
        return ast.ClassDef(
            name=class_name,
            bases=bases,
            keywords=[],
            decorator_list=[],
            body=body
        )
    
    def _create_abstract_class(self, class_name: str, bases: List[ast.AST], node: VisualNode, context: Dict[str, Any]) -> ast.ClassDef:
        """Create an abstract class with ABC."""
        # Add ABC to bases if not present
        if not any(isinstance(base, ast.Name) and base.id == 'ABC' for base in bases):
            bases.append(ast.Name(id='ABC', ctx=ast.Load()))
        
        # Create abstract method
        abstract_method = ast.FunctionDef(
            name='abstract_method',
            args=ast.arguments(
                posonlyargs=[],
                args=[ast.arg(arg='self', annotation=None)],
                vararg=None, kwonlyargs=[], kw_defaults=[], kwarg=None, defaults=[]
            ),
            body=[ast.Pass()],
            decorator_list=[ast.Name(id='abstractmethod', ctx=ast.Load())],
            returns=None
        )
        
        return ast.ClassDef(
            name=class_name,
            bases=bases,
            keywords=[],
            decorator_list=[],
            body=[abstract_method]
        )
    
    def _create_dataclass(self, class_name: str, bases: List[ast.AST], node: VisualNode, context: Dict[str, Any]) -> ast.ClassDef:
        """Create a dataclass."""
        # Create field annotations
        fields = node.parameters.get('fields', [])
        body = []
        
        for field in fields:
            field_name = field.get('name', 'field')
            field_type = field.get('type', 'Any')
            
            # Create annotated assignment
            annotation = ast.Name(id=field_type, ctx=ast.Load())
            target = ast.Name(id=field_name, ctx=ast.Store())
            
            ann_assign = ast.AnnAssign(
                target=target,
                annotation=annotation,
                value=None,
                simple=1
            )
            body.append(ann_assign)
        
        if not body:
            body = [ast.Pass()]
        
        return ast.ClassDef(
            name=class_name,
            bases=bases,
            keywords=[],
            decorator_list=[ast.Name(id='dataclass', ctx=ast.Load())],
            body=body
        )
    
    def _create_singleton_class(self, class_name: str, bases: List[ast.AST], node: VisualNode, context: Dict[str, Any]) -> ast.ClassDef:
        """Create a singleton class pattern."""
        # Create __new__ method for singleton pattern
        new_method = ast.FunctionDef(
            name='__new__',
            args=ast.arguments(
                posonlyargs=[],
                args=[ast.arg(arg='cls', annotation=None)],
                vararg=None, kwonlyargs=[], kw_defaults=[], kwarg=None, defaults=[]
            ),
            body=[
                ast.If(
                    test=ast.UnaryOp(
                        op=ast.Not(),
                        operand=ast.Call(
                            func=ast.Name(id='hasattr', ctx=ast.Load()),
                            args=[
                                ast.Name(id='cls', ctx=ast.Load()),
                                ast.Constant(value='_instance')
                            ],
                            keywords=[]
                        )
                    ),
                    body=[
                        ast.Assign(
                            targets=[ast.Attribute(
                                value=ast.Name(id='cls', ctx=ast.Load()),
                                attr='_instance',
                                ctx=ast.Store()
                            )],
                            value=ast.Call(
                                func=ast.Attribute(
                                    value=ast.Name(id='super', ctx=ast.Load()),
                                    attr='__new__',
                                    ctx=ast.Load()
                                ),
                                args=[ast.Name(id='cls', ctx=ast.Load())],
                                keywords=[]
                            )
                        )
                    ],
                    orelse=[]
                ),
                ast.Return(value=ast.Attribute(
                    value=ast.Name(id='cls', ctx=ast.Load()),
                    attr='_instance',
                    ctx=ast.Load()
                ))
            ],
            decorator_list=[],
            returns=None
        )
        
        return ast.ClassDef(
            name=class_name,
            bases=bases,
            keywords=[],
            decorator_list=[],
            body=[new_method]
        )


class ControlFlowNodeMapper(NodeMapper):
    """Maps control flow visual nodes to AST control structures."""
    
    def __init__(self):
        super().__init__(NodeType.CONTROL_FLOW)
    
    def to_ast(self, node: VisualNode, context: Dict[str, Any]) -> ast.AST:
        """Convert a control flow node to appropriate AST node."""
        control_type = node.parameters.get('control_type', 'if')
        
        if control_type == 'if':
            return self._create_if_statement(node, context)
        elif control_type == 'for':
            return self._create_for_loop(node, context)
        elif control_type == 'while':
            return self._create_while_loop(node, context)
        elif control_type == 'try':
            return self._create_try_statement(node, context)
        elif control_type == 'with':
            return self._create_with_statement(node, context)
        else:
            # Default to pass statement
            return ast.Pass()
    
    def _create_if_statement(self, node: VisualNode, context: Dict[str, Any]) -> ast.If:
        """Create an If AST node."""
        # Get condition from input
        test = context.get(f"{node.id}.condition", ast.Constant(value=True))
        
        # Get body statements (placeholder)
        body = [ast.Pass()]
        orelse = []
        
        return ast.If(test=test, body=body, orelse=orelse)
    
    def _create_for_loop(self, node: VisualNode, context: Dict[str, Any]) -> ast.For:
        """Create a For AST node."""
        # Default for loop structure
        target = ast.Name(id='i', ctx=ast.Store())
        iter_expr = context.get(f"{node.id}.iterable", ast.Call(
            func=ast.Name(id='range', ctx=ast.Load()),
            args=[ast.Constant(value=10)],
            keywords=[]
        ))
        body = [ast.Pass()]
        
        return ast.For(target=target, iter=iter_expr, body=body, orelse=[])
    
    def _create_while_loop(self, node: VisualNode, context: Dict[str, Any]) -> ast.While:
        """Create a While AST node."""
        test = context.get(f"{node.id}.condition", ast.Constant(value=True))
        body = [ast.Pass()]
        
        return ast.While(test=test, body=body, orelse=[])
    
    def _create_try_statement(self, node: VisualNode, context: Dict[str, Any]) -> ast.Try:
        """Create a Try AST node for exception handling."""
        body = [ast.Pass()]
        handlers = []
        orelse = []
        finalbody = []
        
        # Create a basic exception handler
        exception_type = node.parameters.get('exception_type', 'Exception')
        handler = ast.ExceptHandler(
            type=ast.Name(id=exception_type, ctx=ast.Load()),
            name='e',
            body=[ast.Pass()]
        )
        handlers.append(handler)
        
        return ast.Try(body=body, handlers=handlers, orelse=orelse, finalbody=finalbody)
    
    def _create_with_statement(self, node: VisualNode, context: Dict[str, Any]) -> ast.With:
        """Create a With AST node for context managers."""
        context_expr = context.get(f"{node.id}.context_manager", 
                                 ast.Call(func=ast.Name(id='open', ctx=ast.Load()),
                                         args=[ast.Constant(value='file.txt')],
                                         keywords=[]))
        
        with_item = ast.withitem(
            context_expr=context_expr,
            optional_vars=ast.Name(id='f', ctx=ast.Store())
        )
        
        return ast.With(items=[with_item], body=[ast.Pass()])


class DecoratorNodeMapper(NodeMapper):
    """Maps decorator visual nodes to AST decorators."""
    
    def __init__(self):
        super().__init__(NodeType.DECORATOR)
    
    def to_ast(self, node: VisualNode, context: Dict[str, Any]) -> ast.AST:
        """Convert a decorator node to an AST decorator."""
        decorator_name = node.parameters.get('decorator_name', 'decorator')
        
        # Handle simple decorator
        if '.' in decorator_name:
            # Attribute decorator (e.g., @property.setter)
            parts = decorator_name.split('.')
            value = ast.Name(id=parts[0], ctx=ast.Load())
            for part in parts[1:]:
                value = ast.Attribute(value=value, attr=part, ctx=ast.Load())
            return value
        else:
            # Simple name decorator
            return ast.Name(id=decorator_name, ctx=ast.Load())
    
    def create_decorated_function(self, decorator_node: VisualNode, function_node: VisualNode, context: Dict[str, Any]) -> ast.FunctionDef:
        """Create a function definition with decorators applied."""
        function_name = function_node.parameters.get('function_name', 'decorated_function')
        
        # Create the decorator
        decorator_ast = self.to_ast(decorator_node, context)
        
        # Create function with decorator
        return ast.FunctionDef(
            name=function_name,
            args=ast.arguments(
                posonlyargs=[], args=[], vararg=None, kwonlyargs=[],
                kw_defaults=[], kwarg=None, defaults=[]
            ),
            body=[ast.Pass()],
            decorator_list=[decorator_ast],
            returns=None
        )


class AsyncNodeMapper(NodeMapper):
    """Maps async/await visual nodes to AST async constructs."""
    
    def __init__(self):
        super().__init__(NodeType.ASYNC)
    
    def to_ast(self, node: VisualNode, context: Dict[str, Any]) -> ast.AST:
        """Convert an async node to appropriate AST node."""
        async_type = node.parameters.get('async_type', 'await')
        
        if async_type == 'await':
            return self._create_await_expression(node, context)
        elif async_type == 'async_function':
            return self._create_async_function(node, context)
        elif async_type == 'async_for':
            return self._create_async_for(node, context)
        elif async_type == 'async_with':
            return self._create_async_with(node, context)
        else:
            return ast.Pass()
    
    def _create_await_expression(self, node: VisualNode, context: Dict[str, Any]) -> ast.Await:
        """Create an Await AST node."""
        value = context.get(f"{node.id}.awaitable", 
                          ast.Call(func=ast.Name(id='async_function', ctx=ast.Load()),
                                  args=[], keywords=[]))
        return ast.Await(value=value)
    
    def _create_async_function(self, node: VisualNode, context: Dict[str, Any]) -> ast.AsyncFunctionDef:
        """Create an AsyncFunctionDef AST node."""
        function_name = node.parameters.get('function_name', 'async_function')
        
        return ast.AsyncFunctionDef(
            name=function_name,
            args=ast.arguments(
                posonlyargs=[], args=[], vararg=None, kwonlyargs=[],
                kw_defaults=[], kwarg=None, defaults=[]
            ),
            body=[ast.Pass()],
            decorator_list=[],
            returns=None
        )
    
    def _create_async_for(self, node: VisualNode, context: Dict[str, Any]) -> ast.AsyncFor:
        """Create an AsyncFor AST node."""
        target = ast.Name(id='item', ctx=ast.Store())
        iter_expr = context.get(f"{node.id}.async_iterable",
                              ast.Name(id='async_iterable', ctx=ast.Load()))
        
        return ast.AsyncFor(target=target, iter=iter_expr, body=[ast.Pass()], orelse=[])
    
    def _create_async_with(self, node: VisualNode, context: Dict[str, Any]) -> ast.AsyncWith:
        """Create an AsyncWith AST node."""
        context_expr = context.get(f"{node.id}.async_context_manager",
                                 ast.Name(id='async_context_manager', ctx=ast.Load()))
        
        with_item = ast.withitem(
            context_expr=context_expr,
            optional_vars=ast.Name(id='ctx', ctx=ast.Store())
        )
        
        return ast.AsyncWith(items=[with_item], body=[ast.Pass()])


class GeneratorNodeMapper(NodeMapper):
    """Maps generator visual nodes to AST generator constructs."""
    
    def __init__(self):
        super().__init__(NodeType.GENERATOR)
    
    def to_ast(self, node: VisualNode, context: Dict[str, Any]) -> ast.AST:
        """Convert a generator node to appropriate AST node."""
        generator_type = node.parameters.get('generator_type', 'yield')
        
        if generator_type == 'yield':
            return self._create_yield_expression(node, context)
        elif generator_type == 'yield_from':
            return self._create_yield_from_expression(node, context)
        elif generator_type == 'generator_function':
            return self._create_generator_function(node, context)
        elif generator_type == 'list_comprehension':
            return self._create_list_comprehension(node, context)
        elif generator_type == 'iterator_protocol':
            return self._create_iterator_protocol(node, context)
        else:
            return ast.Pass()
    
    def _create_yield_expression(self, node: VisualNode, context: Dict[str, Any]) -> ast.Yield:
        """Create a Yield AST node."""
        value = context.get(f"{node.id}.value", ast.Constant(value=None))
        return ast.Yield(value=value)
    
    def _create_yield_from_expression(self, node: VisualNode, context: Dict[str, Any]) -> ast.YieldFrom:
        """Create a YieldFrom AST node."""
        value = context.get(f"{node.id}.iterable", ast.Name(id='iterable', ctx=ast.Load()))
        return ast.YieldFrom(value=value)
    
    def _create_generator_function(self, node: VisualNode, context: Dict[str, Any]) -> ast.FunctionDef:
        """Create a generator function with yield."""
        function_name = node.parameters.get('function_name', 'generator_function')
        
        # Create function with yield statement
        yield_stmt = ast.Expr(value=ast.Yield(value=ast.Constant(value=1)))
        
        return ast.FunctionDef(
            name=function_name,
            args=ast.arguments(
                posonlyargs=[], args=[], vararg=None, kwonlyargs=[],
                kw_defaults=[], kwarg=None, defaults=[]
            ),
            body=[yield_stmt],
            decorator_list=[],
            returns=None
        )
    
    def _create_list_comprehension(self, node: VisualNode, context: Dict[str, Any]) -> ast.ListComp:
        """Create a list comprehension AST node."""
        # [x for x in iterable]
        elt = ast.Name(id='x', ctx=ast.Load())
        target = ast.Name(id='x', ctx=ast.Store())
        iter_expr = context.get(f"{node.id}.iterable", ast.Name(id='iterable', ctx=ast.Load()))
        
        comprehension = ast.comprehension(target=target, iter=iter_expr, ifs=[], is_async=0)
        
        return ast.ListComp(elt=elt, generators=[comprehension])
    
    def _create_iterator_protocol(self, node: VisualNode, context: Dict[str, Any]) -> ast.ClassDef:
        """Create a class implementing the iterator protocol."""
        class_name = node.parameters.get('class_name', 'Iterator')
        
        # Create __iter__ method
        iter_method = ast.FunctionDef(
            name='__iter__',
            args=ast.arguments(
                posonlyargs=[],
                args=[ast.arg(arg='self', annotation=None)],
                vararg=None, kwonlyargs=[], kw_defaults=[], kwarg=None, defaults=[]
            ),
            body=[ast.Return(value=ast.Name(id='self', ctx=ast.Load()))],
            decorator_list=[],
            returns=None
        )
        
        # Create __next__ method
        next_method = ast.FunctionDef(
            name='__next__',
            args=ast.arguments(
                posonlyargs=[],
                args=[ast.arg(arg='self', annotation=None)],
                vararg=None, kwonlyargs=[], kw_defaults=[], kwarg=None, defaults=[]
            ),
            body=[
                ast.Raise(exc=ast.Call(
                    func=ast.Name(id='StopIteration', ctx=ast.Load()),
                    args=[], keywords=[]
                ))
            ],
            decorator_list=[],
            returns=None
        )
        
        return ast.ClassDef(
            name=class_name,
            bases=[],
            keywords=[],
            decorator_list=[],
            body=[iter_method, next_method]
        )


class MetaclassNodeMapper(NodeMapper):
    """Maps metaclass visual nodes to AST metaclass constructs."""
    
    def __init__(self):
        super().__init__(NodeType.METACLASS)
    
    def to_ast(self, node: VisualNode, context: Dict[str, Any]) -> ast.AST:
        """Convert a metaclass node to appropriate AST node."""
        metaclass_type = node.parameters.get('metaclass_type', 'class_with_metaclass')
        
        if metaclass_type == 'class_with_metaclass':
            return self._create_class_with_metaclass(node, context)
        elif metaclass_type == 'metaclass_definition':
            return self._create_metaclass_definition(node, context)
        else:
            return ast.Pass()
    
    def _create_class_with_metaclass(self, node: VisualNode, context: Dict[str, Any]) -> ast.ClassDef:
        """Create a class definition with metaclass."""
        class_name = node.parameters.get('class_name', 'MetaClass')
        metaclass_name = node.parameters.get('metaclass_name', 'type')
        
        # Create metaclass keyword argument
        metaclass_keyword = ast.keyword(
            arg='metaclass',
            value=ast.Name(id=metaclass_name, ctx=ast.Load())
        )
        
        return ast.ClassDef(
            name=class_name,
            bases=[],
            keywords=[metaclass_keyword],
            decorator_list=[],
            body=[ast.Pass()]
        )
    
    def _create_metaclass_definition(self, node: VisualNode, context: Dict[str, Any]) -> ast.ClassDef:
        """Create a metaclass definition."""
        metaclass_name = node.parameters.get('metaclass_name', 'CustomMeta')
        
        # Create __new__ method
        new_method = ast.FunctionDef(
            name='__new__',
            args=ast.arguments(
                posonlyargs=[],
                args=[
                    ast.arg(arg='cls', annotation=None),
                    ast.arg(arg='name', annotation=None),
                    ast.arg(arg='bases', annotation=None),
                    ast.arg(arg='attrs', annotation=None)
                ],
                vararg=None, kwonlyargs=[], kw_defaults=[], kwarg=None, defaults=[]
            ),
            body=[
                ast.Return(value=ast.Call(
                    func=ast.Attribute(
                        value=ast.Name(id='super', ctx=ast.Load()),
                        attr='__new__',
                        ctx=ast.Load()
                    ),
                    args=[
                        ast.Name(id='cls', ctx=ast.Load()),
                        ast.Name(id='name', ctx=ast.Load()),
                        ast.Name(id='bases', ctx=ast.Load()),
                        ast.Name(id='attrs', ctx=ast.Load())
                    ],
                    keywords=[]
                ))
            ],
            decorator_list=[],
            returns=None
        )
        
        return ast.ClassDef(
            name=metaclass_name,
            bases=[ast.Name(id='type', ctx=ast.Load())],
            keywords=[],
            decorator_list=[],
            body=[new_method]
        )


class ASTVisitor:
    """Base class for visiting AST nodes during conversion."""
    
    def visit(self, node: ast.AST) -> Any:
        """Visit an AST node and return processed result."""
        method_name = f'visit_{type(node).__name__}'
        visitor = getattr(self, method_name, self.generic_visit)
        return visitor(node)
    
    def generic_visit(self, node: ast.AST) -> Any:
        """Default visitor for unhandled node types."""
        return node


class ASTProcessor:
    """Handles bidirectional conversion between visual models and Python ASTs."""
    
    def __init__(self):
        self.node_mappers: Dict[NodeType, NodeMapper] = {}
        self.ast_visitors: Dict[Type, ASTVisitor] = {}
        
        # Register default mappers
        self._register_default_mappers()
    
    def _register_default_mappers(self):
        """Register the default node mappers."""
        self.register_mapper(NodeType.FUNCTION, FunctionNodeMapper())
        self.register_mapper(NodeType.VARIABLE, VariableNodeMapper())
        self.register_mapper(NodeType.CLASS, ClassNodeMapper())
        self.register_mapper(NodeType.CONTROL_FLOW, ControlFlowNodeMapper())
        self.register_mapper(NodeType.DECORATOR, DecoratorNodeMapper())
        self.register_mapper(NodeType.ASYNC, AsyncNodeMapper())
        self.register_mapper(NodeType.GENERATOR, GeneratorNodeMapper())
        self.register_mapper(NodeType.METACLASS, MetaclassNodeMapper())
    
    def visual_to_ast(self, model: VisualModel) -> ast.Module:
        """Convert a visual model to an AST module."""
        # Get execution order for nodes
        execution_order = model.get_execution_order()
        if not execution_order:
            # Handle cycles or empty model
            execution_order = list(model.nodes.keys())
        
        # Build context for node connections
        context = self._build_connection_context(model)
        
        # Convert nodes to AST statements
        statements = []
        for node_id in execution_order:
            node = model.nodes[node_id]
            mapper = self.node_mappers.get(node.type)
            
            if mapper:
                try:
                    ast_node = mapper.to_ast(node, context)
                    if isinstance(ast_node, ast.stmt):
                        statements.append(ast_node)
                    elif isinstance(ast_node, ast.expr):
                        # Wrap expressions in Expr statement
                        statements.append(ast.Expr(value=ast_node))
                except Exception as e:
                    # Add error handling - create a comment for failed conversions
                    error_comment = f"# Error converting node {node_id}: {str(e)}"
                    statements.append(ast.Expr(value=ast.Constant(value=error_comment)))
            else:
                # Unknown node type - add placeholder
                placeholder = f"# Unsupported node type: {node.type.value}"
                statements.append(ast.Expr(value=ast.Constant(value=placeholder)))
        
        # Create module
        return ast.Module(body=statements, type_ignores=[])
    
    def _build_connection_context(self, model: VisualModel) -> Dict[str, Any]:
        """Build context mapping for node connections."""
        context = {}
        
        for connection in model.connections:
            # Map output to input
            source_key = f"{connection.source_node_id}.{connection.source_port}"
            target_key = f"{connection.target_node_id}.{connection.target_port}"
            
            # For now, create a simple name reference
            source_node = model.nodes[connection.source_node_id]
            if source_node.type == NodeType.VARIABLE:
                var_name = source_node.parameters.get('variable_name', f'var_{source_node.id[:8]}')
                context[target_key] = ast.Name(id=var_name, ctx=ast.Load())
            else:
                # Create a placeholder name
                context[target_key] = ast.Name(id=f'output_{connection.source_node_id[:8]}', ctx=ast.Load())
        
        return context
    
    def ast_to_visual(self, tree: ast.Module) -> VisualModel:
        """Convert an AST module to a visual model."""
        model = VisualModel()
        
        # Basic implementation - convert each statement to a node
        for i, stmt in enumerate(tree.body):
            node = self._ast_statement_to_node(stmt, i)
            if node:
                model.add_node(node)
        
        return model
    
    def _ast_statement_to_node(self, stmt: ast.stmt, index: int) -> Optional[VisualNode]:
        """Convert an AST statement to a visual node."""
        if isinstance(stmt, ast.Assign):
            # Variable assignment
            if len(stmt.targets) == 1 and isinstance(stmt.targets[0], ast.Name):
                var_name = stmt.targets[0].id
                node = VisualNode(
                    type=NodeType.VARIABLE,
                    position=(100.0, 50.0 * index),
                    parameters={'variable_name': var_name}
                )
                return node
        
        elif isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
            # Function call
            if isinstance(stmt.value.func, ast.Name):
                func_name = stmt.value.func.id
                node = VisualNode(
                    type=NodeType.FUNCTION,
                    position=(200.0, 50.0 * index),
                    parameters={'function_name': func_name}
                )
                return node
        
        elif isinstance(stmt, (ast.If, ast.For, ast.While)):
            # Control flow
            control_type = type(stmt).__name__.lower()
            node = VisualNode(
                type=NodeType.CONTROL_FLOW,
                position=(300.0, 50.0 * index),
                parameters={'control_type': control_type}
            )
            return node
        
        return None
    
    def validate_round_trip(self, model: VisualModel) -> bool:
        """Validate that a model can be converted to AST and back without loss."""
        try:
            # Convert to AST
            ast_tree = self.visual_to_ast(model)
            
            # Convert back to visual
            new_model = self.ast_to_visual(ast_tree)
            
            # Basic validation - check if we have the same number of nodes
            return len(model.nodes) == len(new_model.nodes)
        
        except Exception:
            return False
    
    def register_mapper(self, node_type: NodeType, mapper: NodeMapper):
        """Register a mapper for a specific node type."""
        self.node_mappers[node_type] = mapper
    
    def get_generated_code(self, model: VisualModel) -> str:
        """Generate Python code from a visual model."""
        ast_tree = self.visual_to_ast(model)
        
        # Fix AST nodes by adding required attributes
        ast.fix_missing_locations(ast_tree)
        
        try:
            return ast.unparse(ast_tree)
        except (AttributeError, Exception):
            # Fallback - create a simple string representation
            statements = []
            for node_id in model.nodes:
                node = model.nodes[node_id]
                if node.type == NodeType.VARIABLE:
                    var_name = node.parameters.get('variable_name', f'var_{node_id[:8]}')
                    default_val = node.parameters.get('default_value', 0)
                    statements.append(f"{var_name} = {repr(default_val)}")
                elif node.type == NodeType.FUNCTION:
                    func_name = node.parameters.get('function_name', 'unknown')
                    statements.append(f"{func_name}()")
                else:
                    statements.append(f"# {node.type.value} node")
            
            return "\n".join(statements) if statements else "# Empty model"