"""
Visual Paradigms System for supporting multiple programming interfaces.

This module provides different visual programming paradigms:
- Node-based programming (dataflow)
- Block-based programming (Scratch-style)
- Diagram-based programming (UML-style)
- Timeline-based programming (for async/real-time)
"""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from .models import VisualNode, Connection, VisualModel, NodeType


class ParadigmType(Enum):
    """Types of visual programming paradigms."""
    NODE_BASED = "node_based"
    BLOCK_BASED = "block_based"
    DIAGRAM_BASED = "diagram_based"
    TIMELINE_BASED = "timeline_based"


class ExtendedNodeType(Enum):
    """Extended node types for different paradigms."""
    # Core programming constructs
    FUNCTION = "function"
    VARIABLE = "variable"
    CONSTANT = "constant"
    CLASS = "class"
    METHOD = "method"
    PROPERTY = "property"
    
    # Control flow
    IF_CONDITION = "if_condition"
    WHILE_LOOP = "while_loop"
    FOR_LOOP = "for_loop"
    BREAK = "break"
    CONTINUE = "continue"
    RETURN = "return"
    YIELD = "yield"
    RAISE = "raise"
    TRY_EXCEPT = "try_except"
    
    # Data structures
    LIST = "list"
    DICT = "dict"
    SET = "set"
    TUPLE = "tuple"
    STRING = "string"
    NUMBER = "number"
    BOOLEAN = "boolean"
    
    # Advanced constructs
    DECORATOR = "decorator"
    ASYNC_FUNCTION = "async_function"
    AWAIT = "await"
    GENERATOR = "generator"
    CONTEXT_MANAGER = "context_manager"
    LAMBDA = "lambda"
    COMPREHENSION = "comprehension"
    
    # Object-oriented
    INHERITANCE = "inheritance"
    COMPOSITION = "composition"
    INTERFACE = "interface"
    ABSTRACT_CLASS = "abstract_class"
    METACLASS = "metaclass"
    
    # Functional programming
    MAP = "map"
    FILTER = "filter"
    REDUCE = "reduce"
    PARTIAL = "partial"
    CURRY = "curry"
    
    # I/O and external
    FILE_READ = "file_read"
    FILE_WRITE = "file_write"
    HTTP_REQUEST = "http_request"
    DATABASE_QUERY = "database_query"
    API_CALL = "api_call"
    
    # Timeline-specific
    EVENT = "event"
    TIMER = "timer"
    DELAY = "delay"
    SCHEDULE = "schedule"
    PARALLEL = "parallel"
    SEQUENCE = "sequence"
    
    # Block-specific
    STATEMENT = "statement"
    EXPRESSION = "expression"
    BLOCK_CONTAINER = "block_container"
    
    # Diagram-specific
    PACKAGE = "package"
    MODULE = "module"
    NAMESPACE = "namespace"
    RELATIONSHIP = "relationship"
    
    # Custom and extensible
    CUSTOM = "custom"
    PLUGIN = "plugin"
    TEMPLATE = "template"


@dataclass
class ParadigmElement:
    """Base class for elements in different paradigms."""
    id: str
    position: Tuple[float, float]
    size: Tuple[float, float]
    properties: Dict[str, Any]
    metadata: Dict[str, Any]


@dataclass
class NodeElement(ParadigmElement):
    """Node-based paradigm element."""
    node_type: NodeType
    inputs: List[str]
    outputs: List[str]
    connections: List[str]


@dataclass
class BlockElement(ParadigmElement):
    """Block-based paradigm element."""
    block_type: str
    parent_block: Optional[str]
    child_blocks: List[str]
    parameters: Dict[str, Any]


@dataclass
class DiagramElement(ParadigmElement):
    """Diagram-based paradigm element."""
    diagram_type: str  # class, interface, package, etc.
    relationships: List[str]
    members: List[str]
    visibility: str


@dataclass
class TimelineElement(ParadigmElement):
    """Timeline-based paradigm element."""
    start_time: float
    duration: float
    timeline_type: str  # event, process, delay, etc.
    dependencies: List[str]


class VisualParadigm(ABC):
    """Abstract base class for visual programming paradigms."""
    
    def __init__(self, paradigm_type: ParadigmType):
        self.paradigm_type = paradigm_type
        self.elements: Dict[str, ParadigmElement] = {}
        self.connections: List[Connection] = []
        self.properties: Dict[str, Any] = {}
    
    @abstractmethod
    def create_element(self, element_type: str, position: Tuple[float, float], **kwargs) -> str:
        """Create a new element in this paradigm."""
        pass
    
    @abstractmethod
    def connect_elements(self, source_id: str, target_id: str, **kwargs) -> bool:
        """Connect two elements."""
        pass
    
    @abstractmethod
    def to_visual_model(self) -> VisualModel:
        """Convert paradigm representation to VisualModel."""
        pass
    
    @abstractmethod
    def from_visual_model(self, model: VisualModel) -> bool:
        """Load paradigm from VisualModel."""
        pass
    
    @abstractmethod
    def validate(self) -> List[str]:
        """Validate the paradigm structure."""
        pass
    
    def get_element(self, element_id: str) -> Optional[ParadigmElement]:
        """Get an element by ID."""
        return self.elements.get(element_id)
    
    def remove_element(self, element_id: str) -> bool:
        """Remove an element."""
        if element_id in self.elements:
            del self.elements[element_id]
            # Remove connections involving this element
            self.connections = [c for c in self.connections 
                              if c.source_node_id != element_id and c.target_node_id != element_id]
            return True
        return False
    
    def get_elements_by_type(self, element_type: str) -> List[ParadigmElement]:
        """Get all elements of a specific type."""
        return [elem for elem in self.elements.values() 
                if getattr(elem, 'node_type', None) == element_type or
                   getattr(elem, 'block_type', None) == element_type or
                   getattr(elem, 'diagram_type', None) == element_type or
                   getattr(elem, 'timeline_type', None) == element_type]


class NodeBasedParadigm(VisualParadigm):
    """Node-based visual programming paradigm (dataflow)."""
    
    def __init__(self):
        super().__init__(ParadigmType.NODE_BASED)
        self.properties.update({
            'supports_dataflow': True,
            'supports_feedback_loops': True,
            'execution_model': 'dataflow'
        })
    
    def create_element(self, element_type: str, position: Tuple[float, float], **kwargs) -> str:
        """Create a new node element with enhanced type support."""
        element_id = f"node_{len(self.elements)}"
        
        # Enhanced mapping from element_type to NodeType
        node_type_map = {
            # Core constructs
            'function': NodeType.FUNCTION,
            'variable': NodeType.VARIABLE,
            'class': NodeType.CLASS,
            'control_flow': NodeType.CONTROL_FLOW,
            'custom': NodeType.CUSTOM,
            
            # Extended types mapped to base types
            'method': NodeType.FUNCTION,
            'property': NodeType.VARIABLE,
            'constant': NodeType.VARIABLE,
            'if_condition': NodeType.CONTROL_FLOW,
            'while_loop': NodeType.CONTROL_FLOW,
            'for_loop': NodeType.CONTROL_FLOW,
            'try_except': NodeType.CONTROL_FLOW,
            'decorator': NodeType.DECORATOR,
            'async_function': NodeType.ASYNC,
            'generator': NodeType.GENERATOR,
            'context_manager': NodeType.CONTEXT_MANAGER,
            'metaclass': NodeType.METACLASS,
            
            # Data structures
            'list': NodeType.VARIABLE,
            'dict': NodeType.VARIABLE,
            'set': NodeType.VARIABLE,
            'tuple': NodeType.VARIABLE,
            'string': NodeType.VARIABLE,
            'number': NodeType.VARIABLE,
            'boolean': NodeType.VARIABLE,
        }
        
        node_type = node_type_map.get(element_type, NodeType.FUNCTION)
        
        # Generate appropriate inputs/outputs based on element type
        inputs, outputs = self._generate_ports_for_type(element_type, kwargs)
        
        element = NodeElement(
            id=element_id,
            position=position,
            size=kwargs.get('size', self._get_default_size(element_type)),
            properties=kwargs.get('properties', {}),
            metadata={
                **kwargs.get('metadata', {}),
                'extended_type': element_type,
                'paradigm': 'node_based'
            },
            node_type=node_type,
            inputs=inputs,
            outputs=outputs,
            connections=[]
        )
        
        self.elements[element_id] = element
        return element_id
    
    def _generate_ports_for_type(self, element_type: str, kwargs: Dict[str, Any]) -> Tuple[List[str], List[str]]:
        """Generate appropriate input/output ports based on element type."""
        port_definitions = {
            # Control flow
            'if_condition': (['condition'], ['true_branch', 'false_branch']),
            'while_loop': (['condition', 'body'], ['output']),
            'for_loop': (['iterable', 'body'], ['output']),
            'try_except': (['try_block'], ['result', 'exception']),
            
            # Functions
            'function': (['args'], ['result']),
            'async_function': (['args'], ['result']),
            'lambda': (['args'], ['result']),
            'method': (['self', 'args'], ['result']),
            
            # Data structures
            'list': (['items'], ['list']),
            'dict': (['keys', 'values'], ['dict']),
            'set': (['items'], ['set']),
            'tuple': (['items'], ['tuple']),
            
            # I/O operations
            'file_read': (['filename'], ['content']),
            'file_write': (['filename', 'content'], ['success']),
            'http_request': (['url', 'method', 'data'], ['response']),
            'database_query': (['query', 'params'], ['result']),
            
            # Functional programming
            'map': (['function', 'iterable'], ['result']),
            'filter': (['function', 'iterable'], ['result']),
            'reduce': (['function', 'iterable', 'initial'], ['result']),
            
            # Default
            'default': (['input'], ['output'])
        }
        
        inputs, outputs = port_definitions.get(element_type, port_definitions['default'])
        
        # Allow override from kwargs
        if 'inputs' in kwargs:
            inputs = kwargs['inputs']
        if 'outputs' in kwargs:
            outputs = kwargs['outputs']
            
        return inputs, outputs
    
    def _get_default_size(self, element_type: str) -> Tuple[float, float]:
        """Get default size based on element type."""
        size_map = {
            'if_condition': (120, 80),
            'while_loop': (100, 60),
            'for_loop': (100, 60),
            'try_except': (140, 100),
            'class': (150, 120),
            'function': (100, 60),
            'variable': (80, 40),
            'list': (90, 50),
            'dict': (90, 50),
            'http_request': (120, 70),
            'database_query': (130, 70),
        }
        return size_map.get(element_type, (100, 60))
    
    def connect_elements(self, source_id: str, target_id: str, **kwargs) -> bool:
        """Connect two nodes with dataflow."""
        source = self.elements.get(source_id)
        target = self.elements.get(target_id)
        
        if not source or not target:
            return False
        
        # Create connection
        connection = Connection(
            id=f"conn_{len(self.connections)}",
            source_node_id=source_id,
            source_port=kwargs.get('source_port', 'output'),
            target_node_id=target_id,
            target_port=kwargs.get('target_port', 'input'),
            data_type=kwargs.get('data_type', object)
        )
        
        self.connections.append(connection)
        
        # Update element connections
        if isinstance(source, NodeElement):
            source.connections.append(connection.id)
        if isinstance(target, NodeElement):
            target.connections.append(connection.id)
        
        return True
    
    def to_visual_model(self) -> VisualModel:
        """Convert to VisualModel."""
        model = VisualModel()
        
        # Convert elements to VisualNodes
        for elem_id, elem in self.elements.items():
            if isinstance(elem, NodeElement):
                node = VisualNode(
                    id=elem_id,
                    type=elem.node_type,
                    position=elem.position,
                    parameters=elem.properties,
                    metadata=elem.metadata
                )
                model.nodes[elem_id] = node
        
        # Add connections
        for conn in self.connections:
            model.connections.append(conn)
        
        return model
    
    def from_visual_model(self, model: VisualModel) -> bool:
        """Load from VisualModel."""
        try:
            self.elements.clear()
            self.connections.clear()
            
            # Convert nodes to elements
            for node_id, node in model.nodes.items():
                element = NodeElement(
                    id=node_id,
                    position=node.position,
                    size=(100, 60),  # Default size
                    properties=node.parameters,
                    metadata=node.metadata,
                    node_type=node.type,
                    inputs=[inp.name for inp in node.inputs],
                    outputs=[out.name for out in node.outputs],
                    connections=[]
                )
                self.elements[node_id] = element
            
            # Add connections
            for conn in model.connections:
                self.connections.append(conn)
                
                # Update element connections
                source = self.elements.get(conn.source_node_id)
                target = self.elements.get(conn.target_node_id)
                if isinstance(source, NodeElement):
                    source.connections.append(conn.id)
                if isinstance(target, NodeElement):
                    target.connections.append(conn.id)
                    target.connections.append(conn.id)
            
            return True
        except Exception:
            return False
    
    def validate(self) -> List[str]:
        """Validate node-based paradigm."""
        errors = []
        
        # Check for cycles in dataflow
        visited = set()
        rec_stack = set()
        
        def has_cycle(node_id: str) -> bool:
            visited.add(node_id)
            rec_stack.add(node_id)
            
            # Get outgoing connections
            for conn in self.connections:
                if conn.source_node_id == node_id:
                    target = conn.target_node_id
                    if target not in visited:
                        if has_cycle(target):
                            return True
                    elif target in rec_stack:
                        return True
            
            rec_stack.remove(node_id)
            return False
        
        for elem_id in self.elements:
            if elem_id not in visited:
                if has_cycle(elem_id):
                    errors.append(f"Cycle detected involving node {elem_id}")
        
        # Check connection validity
        for conn in self.connections:
            if conn.source_node_id not in self.elements:
                errors.append(f"Connection {conn.id} references missing source node {conn.source_node_id}")
            if conn.target_node_id not in self.elements:
                errors.append(f"Connection {conn.id} references missing target node {conn.target_node_id}")
        
        return errors


class BlockBasedParadigm(VisualParadigm):
    """Block-based visual programming paradigm (Scratch-style)."""
    
    def __init__(self):
        super().__init__(ParadigmType.BLOCK_BASED)
        self.properties.update({
            'supports_nesting': True,
            'supports_loops': True,
            'execution_model': 'sequential'
        })
    
    def create_element(self, element_type: str, position: Tuple[float, float], **kwargs) -> str:
        """Create a new block element with enhanced block types."""
        element_id = f"block_{len(self.elements)}"
        
        # Enhanced block type properties
        block_properties = self._get_block_properties(element_type)
        
        element = BlockElement(
            id=element_id,
            position=position,
            size=kwargs.get('size', block_properties['size']),
            properties={
                **kwargs.get('properties', {}),
                **block_properties['properties']
            },
            metadata={
                **kwargs.get('metadata', {}),
                'extended_type': element_type,
                'paradigm': 'block_based',
                'shape': block_properties['shape'],
                'color': block_properties['color']
            },
            block_type=element_type,
            parent_block=kwargs.get('parent_block'),
            child_blocks=kwargs.get('child_blocks', []),
            parameters=kwargs.get('parameters', {})
        )
        
        self.elements[element_id] = element
        
        # Update parent-child relationships
        parent_id = kwargs.get('parent_block')
        if parent_id and parent_id in self.elements:
            parent = self.elements[parent_id]
            if isinstance(parent, BlockElement):
                parent.child_blocks.append(element_id)
        
        return element_id
    
    def _get_block_properties(self, block_type: str) -> Dict[str, Any]:
        """Get visual and behavioral properties for different block types."""
        properties = {
            # Control flow blocks
            'if_statement': {
                'size': (140, 60),
                'shape': 'diamond',
                'color': '#FFA500',
                'properties': {
                    'has_condition': True,
                    'branches': ['true', 'false'],
                    'nestable': True
                }
            },
            'while_loop': {
                'size': (120, 50),
                'shape': 'hexagon',
                'color': '#FF6B6B',
                'properties': {
                    'has_condition': True,
                    'repeatable': True,
                    'nestable': True
                }
            },
            'for_loop': {
                'size': (120, 50),
                'shape': 'hexagon',
                'color': '#4ECDC4',
                'properties': {
                    'has_iterator': True,
                    'repeatable': True,
                    'nestable': True
                }
            },
            'try_except': {
                'size': (140, 80),
                'shape': 'rounded_rect',
                'color': '#FFE66D',
                'properties': {
                    'has_exception_handling': True,
                    'nestable': True
                }
            },
            
            # Function blocks
            'function_def': {
                'size': (130, 60),
                'shape': 'rounded_rect',
                'color': '#95E1D3',
                'properties': {
                    'has_parameters': True,
                    'has_return': True,
                    'nestable': True
                }
            },
            'function_call': {
                'size': (110, 40),
                'shape': 'rounded_rect',
                'color': '#A8E6CF',
                'properties': {
                    'has_arguments': True,
                    'returns_value': True
                }
            },
            
            # Variable blocks
            'variable_set': {
                'size': (100, 35),
                'shape': 'rect',
                'color': '#DDA0DD',
                'properties': {
                    'has_value': True,
                    'assignable': True
                }
            },
            'variable_get': {
                'size': (80, 30),
                'shape': 'oval',
                'color': '#E6E6FA',
                'properties': {
                    'returns_value': True
                }
            },
            
            # Data structure blocks
            'list_create': {
                'size': (90, 40),
                'shape': 'rect',
                'color': '#87CEEB',
                'properties': {
                    'has_items': True,
                    'returns_list': True
                }
            },
            'dict_create': {
                'size': (90, 40),
                'shape': 'rect',
                'color': '#98FB98',
                'properties': {
                    'has_key_value_pairs': True,
                    'returns_dict': True
                }
            },
            
            # I/O blocks
            'print_statement': {
                'size': (80, 35),
                'shape': 'rect',
                'color': '#F0E68C',
                'properties': {
                    'has_message': True,
                    'side_effect': True
                }
            },
            'input_statement': {
                'size': (80, 35),
                'shape': 'rect',
                'color': '#FFB6C1',
                'properties': {
                    'has_prompt': True,
                    'returns_string': True
                }
            },
            
            # Math and logic blocks
            'math_operation': {
                'size': (70, 30),
                'shape': 'oval',
                'color': '#FFA07A',
                'properties': {
                    'has_operands': True,
                    'returns_number': True
                }
            },
            'comparison': {
                'size': (80, 30),
                'shape': 'diamond',
                'color': '#20B2AA',
                'properties': {
                    'has_operands': True,
                    'returns_boolean': True
                }
            },
            'logic_operation': {
                'size': (70, 30),
                'shape': 'diamond',
                'color': '#9370DB',
                'properties': {
                    'has_operands': True,
                    'returns_boolean': True
                }
            },
            
            # Default
            'statement': {
                'size': (100, 40),
                'shape': 'rect',
                'color': '#D3D3D3',
                'properties': {}
            }
        }
        
        return properties.get(block_type, properties['statement'])
    
    def connect_elements(self, source_id: str, target_id: str, **kwargs) -> bool:
        """Connect blocks in sequence."""
        source = self.elements.get(source_id)
        target = self.elements.get(target_id)
        
        if not source or not target:
            return False
        
        # In block-based paradigm, connections represent sequence
        connection = Connection(
            id=f"seq_{len(self.connections)}",
            source_node_id=source_id,
            source_port="next",
            target_node_id=target_id,
            target_port="previous",
            data_type=object
        )
        
        self.connections.append(connection)
        return True
    
    def to_visual_model(self) -> VisualModel:
        """Convert to VisualModel."""
        model = VisualModel()
        
        # Convert blocks to nodes
        for elem_id, elem in self.elements.items():
            if isinstance(elem, BlockElement):
                # Map block types to node types
                node_type_map = {
                    'statement': NodeType.FUNCTION,
                    'expression': NodeType.VARIABLE,
                    'control': NodeType.CONTROL_FLOW,
                    'loop': NodeType.CONTROL_FLOW,
                    'condition': NodeType.CONTROL_FLOW
                }
                
                node_type = node_type_map.get(elem.block_type, NodeType.FUNCTION)
                
                node = VisualNode(
                    id=elem_id,
                    type=node_type,
                    position=elem.position,
                    parameters=elem.parameters,
                    metadata={**elem.metadata, 'block_type': elem.block_type}
                )
                model.nodes[elem_id] = node
        
        # Add connections
        for conn in self.connections:
            model.connections.append(conn)
        
        return model
    
    def from_visual_model(self, model: VisualModel) -> bool:
        """Load from VisualModel."""
        try:
            self.elements.clear()
            self.connections.clear()
            
            # Convert nodes to blocks
            for node_id, node in model.nodes.items():
                block_type = node.metadata.get('block_type', 'statement')
                
                element = BlockElement(
                    id=node_id,
                    position=node.position,
                    size=(120, 40),
                    properties=node.parameters,
                    metadata=node.metadata,
                    block_type=block_type,
                    parent_block=None,
                    child_blocks=[],
                    parameters=node.parameters
                )
                self.elements[node_id] = element
            
            # Add connections
            self.connections = list(model.connections)
            
            return True
        except Exception:
            return False
    
    def validate(self) -> List[str]:
        """Validate block-based paradigm."""
        errors = []
        
        # Check parent-child relationships
        for elem_id, elem in self.elements.items():
            if isinstance(elem, BlockElement):
                # Check parent exists
                if elem.parent_block and elem.parent_block not in self.elements:
                    errors.append(f"Block {elem_id} references missing parent {elem.parent_block}")
                
                # Check children exist
                for child_id in elem.child_blocks:
                    if child_id not in self.elements:
                        errors.append(f"Block {elem_id} references missing child {child_id}")
        
        return errors


class DiagramBasedParadigm(VisualParadigm):
    """Diagram-based visual programming paradigm (UML-style)."""
    
    def __init__(self):
        super().__init__(ParadigmType.DIAGRAM_BASED)
        self.properties.update({
            'supports_inheritance': True,
            'supports_composition': True,
            'execution_model': 'object_oriented'
        })
    
    def create_element(self, element_type: str, position: Tuple[float, float], **kwargs) -> str:
        """Create a new diagram element with enhanced UML support."""
        element_id = f"diagram_{len(self.elements)}"
        
        # Enhanced diagram element properties
        diagram_properties = self._get_diagram_properties(element_type)
        
        element = DiagramElement(
            id=element_id,
            position=position,
            size=kwargs.get('size', diagram_properties['size']),
            properties={
                **kwargs.get('properties', {}),
                **diagram_properties['properties']
            },
            metadata={
                **kwargs.get('metadata', {}),
                'extended_type': element_type,
                'paradigm': 'diagram_based',
                'stereotype': diagram_properties.get('stereotype'),
                'notation': diagram_properties.get('notation', 'UML')
            },
            diagram_type=element_type,
            relationships=kwargs.get('relationships', []),
            members=kwargs.get('members', []),
            visibility=kwargs.get('visibility', diagram_properties.get('default_visibility', 'public'))
        )
        
        self.elements[element_id] = element
        return element_id
    
    def _get_diagram_properties(self, diagram_type: str) -> Dict[str, Any]:
        """Get properties for different diagram element types."""
        properties = {
            # Class diagram elements
            'class': {
                'size': (150, 120),
                'stereotype': None,
                'default_visibility': 'public',
                'properties': {
                    'has_attributes': True,
                    'has_methods': True,
                    'can_inherit': True,
                    'can_implement': True
                }
            },
            'abstract_class': {
                'size': (150, 120),
                'stereotype': '<<abstract>>',
                'default_visibility': 'public',
                'properties': {
                    'has_attributes': True,
                    'has_methods': True,
                    'can_inherit': True,
                    'is_abstract': True
                }
            },
            'interface': {
                'size': (150, 100),
                'stereotype': '<<interface>>',
                'default_visibility': 'public',
                'properties': {
                    'has_methods': True,
                    'methods_abstract': True,
                    'can_implement': True
                }
            },
            'enum': {
                'size': (120, 100),
                'stereotype': '<<enumeration>>',
                'default_visibility': 'public',
                'properties': {
                    'has_values': True,
                    'immutable': True
                }
            },
            
            # Package and module elements
            'package': {
                'size': (200, 150),
                'stereotype': '<<package>>',
                'default_visibility': 'public',
                'properties': {
                    'contains_classes': True,
                    'has_namespace': True
                }
            },
            'module': {
                'size': (180, 120),
                'stereotype': '<<module>>',
                'default_visibility': 'public',
                'properties': {
                    'contains_functions': True,
                    'contains_classes': True,
                    'has_imports': True
                }
            },
            
            # Component diagram elements
            'component': {
                'size': (140, 80),
                'stereotype': '<<component>>',
                'default_visibility': 'public',
                'properties': {
                    'has_interfaces': True,
                    'deployable': True
                }
            },
            'service': {
                'size': (130, 70),
                'stereotype': '<<service>>',
                'default_visibility': 'public',
                'properties': {
                    'has_operations': True,
                    'stateless': True
                }
            },
            
            # Use case diagram elements
            'actor': {
                'size': (80, 100),
                'stereotype': '<<actor>>',
                'default_visibility': 'public',
                'properties': {
                    'external_entity': True,
                    'initiates_use_cases': True
                }
            },
            'use_case': {
                'size': (120, 60),
                'stereotype': None,
                'default_visibility': 'public',
                'properties': {
                    'has_description': True,
                    'has_preconditions': True,
                    'has_postconditions': True
                }
            },
            
            # Sequence diagram elements
            'lifeline': {
                'size': (80, 300),
                'stereotype': None,
                'default_visibility': 'public',
                'properties': {
                    'represents_object': True,
                    'has_timeline': True
                }
            },
            'activation': {
                'size': (20, 60),
                'stereotype': None,
                'default_visibility': 'public',
                'properties': {
                    'represents_execution': True,
                    'has_duration': True
                }
            },
            
            # State diagram elements
            'state': {
                'size': (100, 60),
                'stereotype': None,
                'default_visibility': 'public',
                'properties': {
                    'has_entry_action': True,
                    'has_exit_action': True,
                    'has_internal_transitions': True
                }
            },
            'initial_state': {
                'size': (20, 20),
                'stereotype': None,
                'default_visibility': 'public',
                'properties': {
                    'is_initial': True
                }
            },
            'final_state': {
                'size': (20, 20),
                'stereotype': None,
                'default_visibility': 'public',
                'properties': {
                    'is_final': True
                }
            },
            
            # Activity diagram elements
            'activity': {
                'size': (100, 50),
                'stereotype': None,
                'default_visibility': 'public',
                'properties': {
                    'has_action': True,
                    'can_fork': True,
                    'can_join': True
                }
            },
            'decision': {
                'size': (40, 40),
                'stereotype': None,
                'default_visibility': 'public',
                'properties': {
                    'has_condition': True,
                    'has_branches': True
                }
            },
            
            # Default
            'element': {
                'size': (100, 60),
                'stereotype': None,
                'default_visibility': 'public',
                'properties': {}
            }
        }
        
        return properties.get(diagram_type, properties['element'])
    
    def create_relationship(self, source_id: str, target_id: str, relationship_type: str, **kwargs) -> bool:
        """Create a relationship between diagram elements."""
        if not self.connect_elements(source_id, target_id, relationship_type=relationship_type, **kwargs):
            return False
        
        # Store relationship metadata
        relationship_properties = self._get_relationship_properties(relationship_type)
        
        # Find the connection we just created
        for connection in reversed(self.connections):
            if connection.source_node_id == source_id and connection.target_node_id == target_id:
                meta = {
                    **kwargs.get('metadata', {}),
                    'relationship_type': relationship_type,
                    **relationship_properties
                }
                # Safely attach metadata without assuming Connection has a 'metadata' attribute
                if hasattr(connection, '__dict__'):
                    connection.__dict__['metadata'] = meta
                else:
                    try:
                        setattr(connection, 'metadata', meta)
                    except Exception:
                        # fallback: store metadata in a local mapping on this paradigm
                        if not hasattr(self, '_connection_metadata'):
                            self._connection_metadata = {}
                        self._connection_metadata[connection.id] = meta
                break
        
        return True
    
    def _get_relationship_properties(self, relationship_type: str) -> Dict[str, Any]:
        """Get properties for different relationship types."""
        properties = {
            'inheritance': {
                'arrow_type': 'hollow_triangle',
                'line_style': 'solid',
                'multiplicity': False,
                'navigable': True
            },
            'implementation': {
                'arrow_type': 'hollow_triangle',
                'line_style': 'dashed',
                'multiplicity': False,
                'navigable': True
            },
            'composition': {
                'arrow_type': 'filled_diamond',
                'line_style': 'solid',
                'multiplicity': True,
                'navigable': True,
                'strong_ownership': True
            },
            'aggregation': {
                'arrow_type': 'hollow_diamond',
                'line_style': 'solid',
                'multiplicity': True,
                'navigable': True,
                'weak_ownership': True
            },
            'association': {
                'arrow_type': 'arrow',
                'line_style': 'solid',
                'multiplicity': True,
                'navigable': True
            },
            'dependency': {
                'arrow_type': 'arrow',
                'line_style': 'dashed',
                'multiplicity': False,
                'navigable': True
            },
            'realization': {
                'arrow_type': 'hollow_triangle',
                'line_style': 'dashed',
                'multiplicity': False,
                'navigable': True
            }
        }
        
        return properties.get(relationship_type, properties['association'])
    
    def connect_elements(self, source_id: str, target_id: str, **kwargs) -> bool:
        """Connect diagram elements with relationships."""
        source = self.elements.get(source_id)
        target = self.elements.get(target_id)
        
        if not source or not target:
            return False
        
        relationship_type = kwargs.get('relationship_type', 'association')
        
        connection = Connection(
            id=f"rel_{len(self.connections)}",
            source_node_id=source_id,
            source_port="out",
            target_node_id=target_id,
            target_port="in",
            data_type=object
        )
        
        self.connections.append(connection)
        
        # Update element relationships
        if isinstance(source, DiagramElement):
            source.relationships.append(connection.id)
        if isinstance(target, DiagramElement):
            target.relationships.append(connection.id)
        
        return True
    
    def to_visual_model(self) -> VisualModel:
        """Convert to VisualModel."""
        model = VisualModel()
        
        # Convert diagram elements to nodes
        for elem_id, elem in self.elements.items():
            if isinstance(elem, DiagramElement):
                node_type = NodeType.CLASS if elem.diagram_type == 'class' else NodeType.FUNCTION
                
                node = VisualNode(
                    id=elem_id,
                    type=node_type,
                    position=elem.position,
                    parameters=elem.properties,
                    metadata={
                        **elem.metadata,
                        'diagram_type': elem.diagram_type,
                        'visibility': elem.visibility,
                        'members': elem.members
                    }
                )
                model.nodes[elem_id] = node
        
        # Add connections
        for conn in self.connections:
            model.connections.append(conn)
        
        return model
    
    def from_visual_model(self, model: VisualModel) -> bool:
        """Load from VisualModel."""
        try:
            self.elements.clear()
            self.connections.clear()
            
            # Convert nodes to diagram elements
            for node_id, node in model.nodes.items():
                diagram_type = node.metadata.get('diagram_type', 'class')
                
                element = DiagramElement(
                    id=node_id,
                    position=node.position,
                    size=(150, 100),
                    properties=node.parameters,
                    metadata=node.metadata,
                    diagram_type=diagram_type,
                    relationships=[],
                    members=node.metadata.get('members', []),
                    visibility=node.metadata.get('visibility', 'public')
                )
                self.elements[node_id] = element
            
            # Add connections
            for conn in model.connections:
                self.connections.append(conn)
                
                # Update element relationships
                source = self.elements.get(conn.source_node_id)
                target = self.elements.get(conn.target_node_id)
                if isinstance(source, DiagramElement):
                    source.relationships.append(conn.id)
                if isinstance(target, DiagramElement):
                    target.relationships.append(conn.id)
            
            return True
        except Exception:
            return False
    
    def validate(self) -> List[str]:
        """Validate diagram-based paradigm."""
        errors = []
        
        # Check for circular inheritance
        def has_inheritance_cycle(elem_id: str, visited: set) -> bool:
            if elem_id in visited:
                return True
            
            visited.add(elem_id)
            
            # Find inheritance relationships (we'll store this info differently)
            for conn in self.connections:
                if conn.source_node_id == elem_id:
                    # For now, assume all connections from classes are inheritance
                    # In a real implementation, we'd store relationship type elsewhere
                    if has_inheritance_cycle(conn.target_node_id, visited.copy()):
                        return True
            
            return False
        
        for elem_id in self.elements:
            if has_inheritance_cycle(elem_id, set()):
                errors.append(f"Circular inheritance detected involving {elem_id}")
        
        return errors


class TimelineBasedParadigm(VisualParadigm):
    """Timeline-based visual programming paradigm (for async/real-time)."""
    
    def __init__(self):
        super().__init__(ParadigmType.TIMELINE_BASED)
        self.properties.update({
            'supports_timing': True,
            'supports_async': True,
            'execution_model': 'temporal'
        })
    
    def create_element(self, element_type: str, position: Tuple[float, float], **kwargs) -> str:
        """Create a new timeline element with enhanced temporal support."""
        element_id = f"timeline_{len(self.elements)}"
        
        # Enhanced timeline element properties
        timeline_properties = self._get_timeline_properties(element_type)
        
        element = TimelineElement(
            id=element_id,
            position=position,
            size=kwargs.get('size', timeline_properties['size']),
            properties={
                **kwargs.get('properties', {}),
                **timeline_properties['properties']
            },
            metadata={
                **kwargs.get('metadata', {}),
                'extended_type': element_type,
                'paradigm': 'timeline_based',
                'temporal_type': timeline_properties.get('temporal_type'),
                'execution_model': timeline_properties.get('execution_model')
            },
            start_time=kwargs.get('start_time', timeline_properties.get('default_start_time', 0.0)),
            duration=kwargs.get('duration', timeline_properties.get('default_duration', 1.0)),
            timeline_type=element_type,
            dependencies=kwargs.get('dependencies', [])
        )
        
        self.elements[element_id] = element
        return element_id
    
    def _get_timeline_properties(self, timeline_type: str) -> Dict[str, Any]:
        """Get properties for different timeline element types."""
        properties = {
            # Basic temporal elements
            'event': {
                'size': (80, 30),
                'temporal_type': 'instant',
                'execution_model': 'trigger',
                'default_start_time': 0.0,
                'default_duration': 0.0,
                'properties': {
                    'instantaneous': True,
                    'can_trigger': True,
                    'has_data': True
                }
            },
            'process': {
                'size': (120, 40),
                'temporal_type': 'duration',
                'execution_model': 'continuous',
                'default_start_time': 0.0,
                'default_duration': 5.0,
                'properties': {
                    'has_duration': True,
                    'can_be_interrupted': True,
                    'has_progress': True
                }
            },
            'timer': {
                'size': (90, 35),
                'temporal_type': 'duration',
                'execution_model': 'countdown',
                'default_start_time': 0.0,
                'default_duration': 10.0,
                'properties': {
                    'countdown': True,
                    'repeatable': True,
                    'can_pause': True
                }
            },
            'delay': {
                'size': (70, 25),
                'temporal_type': 'duration',
                'execution_model': 'wait',
                'default_start_time': 0.0,
                'default_duration': 1.0,
                'properties': {
                    'blocking': True,
                    'passive': True
                }
            },
            
            # Scheduling elements
            'schedule': {
                'size': (100, 50),
                'temporal_type': 'recurring',
                'execution_model': 'scheduled',
                'default_start_time': 0.0,
                'default_duration': 0.0,
                'properties': {
                    'recurring': True,
                    'has_pattern': True,
                    'can_skip': True
                }
            },
            'cron_job': {
                'size': (110, 45),
                'temporal_type': 'recurring',
                'execution_model': 'cron',
                'default_start_time': 0.0,
                'default_duration': 0.0,
                'properties': {
                    'cron_expression': True,
                    'system_scheduled': True
                }
            },
            
            # Concurrency elements
            'parallel': {
                'size': (140, 60),
                'temporal_type': 'concurrent',
                'execution_model': 'parallel',
                'default_start_time': 0.0,
                'default_duration': 0.0,
                'properties': {
                    'concurrent_execution': True,
                    'has_branches': True,
                    'synchronization_point': False
                }
            },
            'sequence': {
                'size': (120, 40),
                'temporal_type': 'sequential',
                'execution_model': 'sequential',
                'default_start_time': 0.0,
                'default_duration': 0.0,
                'properties': {
                    'sequential_execution': True,
                    'ordered': True,
                    'blocking': True
                }
            },
            'fork': {
                'size': (60, 60),
                'temporal_type': 'control',
                'execution_model': 'fork',
                'default_start_time': 0.0,
                'default_duration': 0.0,
                'properties': {
                    'creates_branches': True,
                    'concurrent_start': True
                }
            },
            'join': {
                'size': (60, 60),
                'temporal_type': 'control',
                'execution_model': 'join',
                'default_start_time': 0.0,
                'default_duration': 0.0,
                'properties': {
                    'waits_for_all': True,
                    'synchronization_point': True
                }
            },
            
            # Async/await elements
            'async_function': {
                'size': (130, 50),
                'temporal_type': 'async',
                'execution_model': 'async',
                'default_start_time': 0.0,
                'default_duration': 0.0,
                'properties': {
                    'non_blocking': True,
                    'returns_future': True,
                    'awaitable': True
                }
            },
            'await': {
                'size': (80, 30),
                'temporal_type': 'sync_point',
                'execution_model': 'await',
                'default_start_time': 0.0,
                'default_duration': 0.0,
                'properties': {
                    'blocking': True,
                    'waits_for_completion': True
                }
            },
            
            # State machine elements
            'state_entry': {
                'size': (90, 40),
                'temporal_type': 'state',
                'execution_model': 'state_machine',
                'default_start_time': 0.0,
                'default_duration': 0.0,
                'properties': {
                    'state_change': True,
                    'has_entry_action': True
                }
            },
            'state_exit': {
                'size': (90, 40),
                'temporal_type': 'state',
                'execution_model': 'state_machine',
                'default_start_time': 0.0,
                'default_duration': 0.0,
                'properties': {
                    'state_change': True,
                    'has_exit_action': True
                }
            },
            'transition': {
                'size': (100, 30),
                'temporal_type': 'transition',
                'execution_model': 'state_machine',
                'default_start_time': 0.0,
                'default_duration': 0.1,
                'properties': {
                    'has_condition': True,
                    'has_action': True,
                    'instantaneous': True
                }
            },
            
            # Real-time elements
            'real_time_task': {
                'size': (140, 50),
                'temporal_type': 'real_time',
                'execution_model': 'real_time',
                'default_start_time': 0.0,
                'default_duration': 1.0,
                'properties': {
                    'deadline': True,
                    'priority': True,
                    'preemptible': True
                }
            },
            'interrupt': {
                'size': (80, 35),
                'temporal_type': 'interrupt',
                'execution_model': 'interrupt',
                'default_start_time': 0.0,
                'default_duration': 0.0,
                'properties': {
                    'high_priority': True,
                    'preempts_execution': True,
                    'has_handler': True
                }
            },
            
            # Default
            'temporal_element': {
                'size': (100, 40),
                'temporal_type': 'generic',
                'execution_model': 'sequential',
                'default_start_time': 0.0,
                'default_duration': 1.0,
                'properties': {}
            }
        }
        # (removed stray duplicated block that referenced undefined names such as
        # source_id/target_id/kwargs/dependency_type; dependency metadata handling
        # is implemented in the connection management methods elsewhere)
        return properties.get(timeline_type, properties['temporal_element'])
    
    def _get_dependency_properties(self, dependency_type: str) -> Dict[str, Any]:
        """Get properties for different temporal dependency types."""
        properties = {
            'finish_to_start': {
                'constraint': 'source must finish before target starts',
                'delay_allowed': True,
                'overlap_allowed': False
            },
            'start_to_start': {
                'constraint': 'source must start before target starts',
                'delay_allowed': True,
                'overlap_allowed': True
            },
            'finish_to_finish': {
                'constraint': 'source must finish before target finishes',
                'delay_allowed': True,
                'overlap_allowed': True
            },
            'start_to_finish': {
                'constraint': 'source must start before target finishes',
                'delay_allowed': True,
                'overlap_allowed': True
            },
            'synchronous': {
                'constraint': 'source and target must execute simultaneously',
                'delay_allowed': False,
                'overlap_allowed': True
            },
            'trigger': {
                'constraint': 'source triggers target execution',
                'delay_allowed': False,
                'overlap_allowed': False
            }
        }
        
        return properties.get(dependency_type, properties['finish_to_start'])
    
    def connect_elements(self, source_id: str, target_id: str, **kwargs) -> bool:
        """Connect timeline elements with temporal dependencies."""
        source = self.elements.get(source_id)
        target = self.elements.get(target_id)
        
        if not source or not target:
            return False
        
        # Timeline connections represent temporal dependencies
        connection = Connection(
            id=f"dep_{len(self.connections)}",
            source_node_id=source_id,
            source_port="end",
            target_node_id=target_id,
            target_port="start",
            data_type=object
        )
        
        self.connections.append(connection)
        
        # Update element dependencies
        if isinstance(target, TimelineElement):
            target.dependencies.append(source_id)
        
        return True
    
    def to_visual_model(self) -> VisualModel:
        """Convert to VisualModel."""
        model = VisualModel()
        
        # Convert timeline elements to nodes
        for elem_id, elem in self.elements.items():
            if isinstance(elem, TimelineElement):
                node_type = NodeType.FUNCTION  # Default for timeline elements
                
                node = VisualNode(
                    id=elem_id,
                    type=node_type,
                    position=elem.position,
                    parameters=elem.properties,
                    metadata={
                        **elem.metadata,
                        'timeline_type': elem.timeline_type,
                        'start_time': elem.start_time,
                        'duration': elem.duration,
                        'dependencies': elem.dependencies
                    }
                )
                model.nodes[elem_id] = node
        
        # Add connections
        for conn in self.connections:
            model.connections.append(conn)
        
        return model
    
    def from_visual_model(self, model: VisualModel) -> bool:
        """Load from VisualModel."""
        try:
            self.elements.clear()
            self.connections.clear()
            
            # Convert nodes to timeline elements
            for node_id, node in model.nodes.items():
                timeline_type = node.metadata.get('timeline_type', 'event')
                
                element = TimelineElement(
                    id=node_id,
                    position=node.position,
                    size=(100, 30),
                    properties=node.parameters,
                    metadata=node.metadata,
                    start_time=node.metadata.get('start_time', 0.0),
                    duration=node.metadata.get('duration', 1.0),
                    timeline_type=timeline_type,
                    dependencies=node.metadata.get('dependencies', [])
                )
                self.elements[node_id] = element
            
            # Add connections
            self.connections = list(model.connections)
            
            return True
        except Exception:
            return False
    
    def validate(self) -> List[str]:
        """Validate timeline-based paradigm."""
        errors = []
        
        # Check temporal consistency
        for elem_id, elem in self.elements.items():
            if isinstance(elem, TimelineElement):
                # Check dependencies have earlier start times
                for dep_id in elem.dependencies:
                    dep_elem = self.elements.get(dep_id)
                    if isinstance(dep_elem, TimelineElement):
                        if dep_elem.start_time + dep_elem.duration > elem.start_time:
                            errors.append(f"Temporal conflict: {dep_id} ends after {elem_id} starts")
        
        return errors


class ParadigmManager:
    """Manages multiple visual programming paradigms."""
    
    def __init__(self):
        self.paradigms: Dict[ParadigmType, VisualParadigm] = {
            ParadigmType.NODE_BASED: NodeBasedParadigm(),
            ParadigmType.BLOCK_BASED: BlockBasedParadigm(),
            ParadigmType.DIAGRAM_BASED: DiagramBasedParadigm(),
            ParadigmType.TIMELINE_BASED: TimelineBasedParadigm()
        }
        self.active_paradigm: Optional[ParadigmType] = ParadigmType.NODE_BASED
        self.node_factory = NodeFactory()
    
    def get_paradigm(self, paradigm_type: ParadigmType) -> Optional[VisualParadigm]:
        """Get a specific paradigm."""
        return self.paradigms.get(paradigm_type)
    
    def set_active_paradigm(self, paradigm_type: ParadigmType) -> bool:
        """Set the active paradigm."""
        if paradigm_type in self.paradigms:
            self.active_paradigm = paradigm_type
            return True
        return False
    
    def get_active_paradigm(self) -> Optional[VisualParadigm]:
        """Get the currently active paradigm."""
        if self.active_paradigm:
            return self.paradigms[self.active_paradigm]
        return None
    
    def create_element_in_active_paradigm(self, element_type: str, position: Tuple[float, float], **kwargs) -> Optional[str]:
        """Create an element in the currently active paradigm."""
        active = self.get_active_paradigm()
        if active:
            return active.create_element(element_type, position, **kwargs)
        return None
    
    def create_element_in_paradigm(self, paradigm_type: ParadigmType, element_type: str, 
                                 position: Tuple[float, float], **kwargs) -> Optional[str]:
        """Create an element in a specific paradigm."""
        paradigm = self.paradigms.get(paradigm_type)
        if paradigm:
            return paradigm.create_element(element_type, position, **kwargs)
        return None
    
    def get_available_element_types(self, paradigm_type: ParadigmType) -> List[Dict[str, Any]]:
        """Get all available element types for a specific paradigm."""
        return self.node_factory.get_element_types_for_paradigm(paradigm_type)
    
    def convert_between_paradigms(self, source_type: ParadigmType, 
                                 target_type: ParadigmType) -> bool:
        """Convert between different paradigms."""
        source_paradigm = self.paradigms.get(source_type)
        target_paradigm = self.paradigms.get(target_type)
        
        if not source_paradigm or not target_paradigm:
            return False
        
        try:
            # Convert source to VisualModel
            model = source_paradigm.to_visual_model()
            
            # Load into target paradigm
            return target_paradigm.from_visual_model(model)
        except Exception:
            return False
    
    def validate_all_paradigms(self) -> Dict[ParadigmType, List[str]]:
        """Validate all paradigms."""
        results = {}
        for paradigm_type, paradigm in self.paradigms.items():
            results[paradigm_type] = paradigm.validate()
        return results
    
    def get_paradigm_capabilities(self, paradigm_type: ParadigmType) -> Dict[str, Any]:
        """Get capabilities of a specific paradigm."""
        paradigm = self.paradigms.get(paradigm_type)
        if paradigm:
            return paradigm.properties.copy()
        return {}
    
    def export_paradigm_state(self, paradigm_type: ParadigmType) -> Optional[Dict[str, Any]]:
        """Export paradigm state for persistence."""
        paradigm = self.paradigms.get(paradigm_type)
        if not paradigm:
            return None
        
        return {
            'paradigm_type': paradigm_type.value,
            'elements': {
                elem_id: {
                    'type': type(elem).__name__,
                    'data': elem.__dict__
                }
                for elem_id, elem in paradigm.elements.items()
            },
            'connections': [conn.__dict__ for conn in paradigm.connections],
            'properties': paradigm.properties
        }
    
    def import_paradigm_state(self, state_data: Dict[str, Any]) -> bool:
        """Import paradigm state from persistence."""
        try:
            paradigm_type = ParadigmType(state_data['paradigm_type'])
            paradigm = self.paradigms.get(paradigm_type)
            
            if not paradigm:
                return False
            
            # Clear existing state
            paradigm.elements.clear()
            paradigm.connections.clear()
            
            # Restore elements
            element_classes = {
                'NodeElement': NodeElement,
                'BlockElement': BlockElement,
                'DiagramElement': DiagramElement,
                'TimelineElement': TimelineElement
            }
            
            for elem_id, elem_data in state_data['elements'].items():
                elem_class = element_classes.get(elem_data['type'])
                if elem_class:
                    element = elem_class(**elem_data['data'])
                    paradigm.elements[elem_id] = element
            
            # Restore connections
            for conn_data in state_data['connections']:
                connection = Connection(**conn_data)
                paradigm.connections.append(connection)
            
            # Restore properties
            paradigm.properties.update(state_data.get('properties', {}))
            
            return True
        except Exception:
            return False


class NodeFactory:
    """Factory for creating different types of visual nodes across paradigms."""
    
    def __init__(self):
        self.element_definitions = self._initialize_element_definitions()
    
    def _initialize_element_definitions(self) -> Dict[ParadigmType, Dict[str, Dict[str, Any]]]:
        """Initialize comprehensive element definitions for all paradigms."""
        return {
            ParadigmType.NODE_BASED: {
                # ============ FUNCTIONS ============
                'function': {
                    'name': 'Function',
                    'description': 'A reusable block of code',
                    'category': 'Functions',
                    'icon': 'function-square',
                    'image': '/static/images/function_node.png',
                    'inputs': ['args'],
                    'outputs': ['result'],
                    'properties': {'function_name': '', 'parameters': []}
                },
                'async_function': {
                    'name': 'Async Function',
                    'description': 'An asynchronous function',
                    'category': 'Functions',
                    'icon': 'clock',
                    'image': '/static/images/async_function_node.png',
                    'inputs': ['args'],
                    'outputs': ['promise'],
                    'properties': {'function_name': '', 'parameters': [], 'is_async': True}
                },
                'lambda': {
                    'name': 'Lambda',
                    'description': 'Anonymous function',
                    'category': 'Functions',
                    'icon': 'zap',
                    'image': '/static/images/lambda_node.png',
                    'inputs': ['args'],
                    'outputs': ['result'],
                    'properties': {'expression': ''}
                },
                'generator': {
                    'name': 'Generator',
                    'description': 'Lazy iterator using yield',
                    'category': 'Functions',
                    'icon': 'repeat',
                    'inputs': ['args'],
                    'outputs': ['iterator'],
                    'properties': {'function_name': '', 'yield_expression': ''}
                },
                'decorator': {
                    'name': 'Decorator',
                    'description': 'Function wrapper/modifier',
                    'category': 'Functions',
                    'icon': 'at-sign',
                    'inputs': ['function'],
                    'outputs': ['wrapped_function'],
                    'properties': {'decorator_name': ''}
                },
                'method': {
                    'name': 'Method',
                    'description': 'Class instance method',
                    'category': 'Functions',
                    'icon': 'code',
                    'inputs': ['self', 'args'],
                    'outputs': ['result'],
                    'properties': {'method_name': ''}
                },
                'classmethod': {
                    'name': 'Class Method',
                    'description': 'Method bound to class',
                    'category': 'Functions',
                    'icon': 'layers',
                    'inputs': ['cls', 'args'],
                    'outputs': ['result'],
                    'properties': {'method_name': ''}
                },
                'staticmethod': {
                    'name': 'Static Method',
                    'description': 'Method without instance binding',
                    'category': 'Functions',
                    'icon': 'anchor',
                    'inputs': ['args'],
                    'outputs': ['result'],
                    'properties': {'method_name': ''}
                },
                
                # ============ VARIABLES ============
                'variable': {
                    'name': 'Variable',
                    'description': 'Store and retrieve values',
                    'category': 'Variables',
                    'icon': 'variable',
                    'image': '/static/images/variable_node.png',
                    'inputs': ['value'],
                    'outputs': ['value'],
                    'properties': {'variable_name': '', 'initial_value': None}
                },
                'constant': {
                    'name': 'Constant',
                    'description': 'Immutable value',
                    'category': 'Variables',
                    'icon': 'lock',
                    'image': '/static/images/constant_node.png',
                    'inputs': [],
                    'outputs': ['value'],
                    'properties': {'constant_name': '', 'value': None}
                },
                'global_var': {
                    'name': 'Global Variable',
                    'description': 'Access global scope variable',
                    'category': 'Variables',
                    'icon': 'globe',
                    'inputs': [],
                    'outputs': ['value'],
                    'properties': {'variable_name': ''}
                },
                'nonlocal_var': {
                    'name': 'Nonlocal Variable',
                    'description': 'Access enclosing scope variable',
                    'category': 'Variables',
                    'icon': 'external-link',
                    'inputs': [],
                    'outputs': ['value'],
                    'properties': {'variable_name': ''}
                },
                
                # ============ CONTROL FLOW ============
                'if_condition': {
                    'name': 'If Condition',
                    'description': 'Conditional execution',
                    'category': 'Control Flow',
                    'icon': 'git-branch',
                    'image': '/static/images/if_node.png',
                    'inputs': ['condition'],
                    'outputs': ['true_branch', 'false_branch'],
                    'properties': {'condition': ''}
                },
                'elif_condition': {
                    'name': 'Elif Condition',
                    'description': 'Additional conditional branch',
                    'category': 'Control Flow',
                    'icon': 'git-branch',
                    'inputs': ['condition'],
                    'outputs': ['true_branch', 'next_branch'],
                    'properties': {'condition': ''}
                },
                'while_loop': {
                    'name': 'While Loop',
                    'description': 'Repeat while condition is true',
                    'category': 'Control Flow',
                    'icon': 'repeat',
                    'image': '/static/images/while_node.png',
                    'inputs': ['condition', 'body'],
                    'outputs': ['output'],
                    'properties': {'condition': ''}
                },
                'for_loop': {
                    'name': 'For Loop',
                    'description': 'Iterate over a sequence',
                    'category': 'Control Flow',
                    'icon': 'repeat',
                    'image': '/static/images/for_node.png',
                    'inputs': ['iterable', 'body'],
                    'outputs': ['output'],
                    'properties': {'iterator_var': 'item'}
                },
                'break': {
                    'name': 'Break',
                    'description': 'Exit loop immediately',
                    'category': 'Control Flow',
                    'icon': 'x-circle',
                    'inputs': ['trigger'],
                    'outputs': [],
                    'properties': {}
                },
                'continue': {
                    'name': 'Continue',
                    'description': 'Skip to next iteration',
                    'category': 'Control Flow',
                    'icon': 'skip-forward',
                    'inputs': ['trigger'],
                    'outputs': [],
                    'properties': {}
                },
                'pass': {
                    'name': 'Pass',
                    'description': 'Null operation placeholder',
                    'category': 'Control Flow',
                    'icon': 'minus',
                    'inputs': ['trigger'],
                    'outputs': ['output'],
                    'properties': {}
                },
                'return': {
                    'name': 'Return',
                    'description': 'Return value from function',
                    'category': 'Control Flow',
                    'icon': 'corner-down-left',
                    'inputs': ['value'],
                    'outputs': [],
                    'properties': {}
                },
                'yield': {
                    'name': 'Yield',
                    'description': 'Yield value from generator',
                    'category': 'Control Flow',
                    'icon': 'arrow-right-circle',
                    'inputs': ['value'],
                    'outputs': ['next'],
                    'properties': {}
                },
                'yield_from': {
                    'name': 'Yield From',
                    'description': 'Delegate to sub-generator',
                    'category': 'Control Flow',
                    'icon': 'git-merge',
                    'inputs': ['iterable'],
                    'outputs': ['next'],
                    'properties': {}
                },
                
                # ============ EXCEPTION HANDLING ============
                'try_except': {
                    'name': 'Try/Except',
                    'description': 'Handle exceptions',
                    'category': 'Exception Handling',
                    'icon': 'shield',
                    'inputs': ['try_block'],
                    'outputs': ['success', 'exception'],
                    'properties': {'exception_types': ['Exception']}
                },
                'try_finally': {
                    'name': 'Try/Finally',
                    'description': 'Cleanup with finally block',
                    'category': 'Exception Handling',
                    'icon': 'shield-check',
                    'inputs': ['try_block', 'finally_block'],
                    'outputs': ['output'],
                    'properties': {}
                },
                'raise': {
                    'name': 'Raise',
                    'description': 'Raise an exception',
                    'category': 'Exception Handling',
                    'icon': 'alert-triangle',
                    'inputs': ['exception'],
                    'outputs': [],
                    'properties': {'exception_type': 'Exception', 'message': ''}
                },
                'assert': {
                    'name': 'Assert',
                    'description': 'Assert condition is true',
                    'category': 'Exception Handling',
                    'icon': 'check-square',
                    'inputs': ['condition', 'message'],
                    'outputs': ['output'],
                    'properties': {}
                },
                
                # ============ CLASSES & OOP ============
                'class': {
                    'name': 'Class',
                    'description': 'Object-oriented class definition',
                    'category': 'Classes & OOP',
                    'icon': 'box',
                    'inputs': ['bases'],
                    'outputs': ['class_type'],
                    'properties': {'class_name': '', 'base_classes': []}
                },
                'init_method': {
                    'name': 'Constructor (__init__)',
                    'description': 'Class constructor method',
                    'category': 'Classes & OOP',
                    'icon': 'plus-circle',
                    'inputs': ['self', 'args'],
                    'outputs': [],
                    'properties': {'parameters': []}
                },
                'property': {
                    'name': 'Property',
                    'description': 'Managed attribute with getter/setter',
                    'category': 'Classes & OOP',
                    'icon': 'tag',
                    'inputs': ['getter', 'setter'],
                    'outputs': ['property'],
                    'properties': {'property_name': ''}
                },
                'inheritance': {
                    'name': 'Inheritance',
                    'description': 'Class inheritance relationship',
                    'category': 'Classes & OOP',
                    'icon': 'git-branch',
                    'inputs': ['child_class', 'parent_class'],
                    'outputs': ['derived_class'],
                    'properties': {}
                },
                'super_call': {
                    'name': 'Super Call',
                    'description': 'Call parent class method',
                    'category': 'Classes & OOP',
                    'icon': 'arrow-up-circle',
                    'inputs': ['args'],
                    'outputs': ['result'],
                    'properties': {'method_name': '__init__'}
                },
                
                # ============ DATA STRUCTURES ============
                'list': {
                    'name': 'List',
                    'description': 'Ordered collection of items',
                    'category': 'Data Structures',
                    'icon': 'list',
                    'image': '/static/images/list_node.png',
                    'inputs': ['items'],
                    'outputs': ['list'],
                    'properties': {'items': []}
                },
                'tuple': {
                    'name': 'Tuple',
                    'description': 'Immutable ordered collection',
                    'category': 'Data Structures',
                    'icon': 'layers',
                    'inputs': ['items'],
                    'outputs': ['tuple'],
                    'properties': {'items': []}
                },
                'dict': {
                    'name': 'Dictionary',
                    'description': 'Key-value pairs',
                    'category': 'Data Structures',
                    'icon': 'hash',
                    'image': '/static/images/dict_node.png',
                    'inputs': ['keys', 'values'],
                    'outputs': ['dict'],
                    'properties': {'pairs': {}}
                },
                'set': {
                    'name': 'Set',
                    'description': 'Unordered unique items',
                    'category': 'Data Structures',
                    'icon': 'circle',
                    'inputs': ['items'],
                    'outputs': ['set'],
                    'properties': {}
                },
                'frozenset': {
                    'name': 'Frozenset',
                    'description': 'Immutable set',
                    'category': 'Data Structures',
                    'icon': 'circle',
                    'inputs': ['items'],
                    'outputs': ['frozenset'],
                    'properties': {}
                },
                'namedtuple': {
                    'name': 'Named Tuple',
                    'description': 'Tuple with named fields',
                    'category': 'Data Structures',
                    'icon': 'tag',
                    'inputs': ['values'],
                    'outputs': ['namedtuple'],
                    'properties': {'type_name': '', 'field_names': []}
                },
                'dataclass': {
                    'name': 'Data Class',
                    'description': 'Structured data container',
                    'category': 'Data Structures',
                    'icon': 'database',
                    'inputs': ['field_values'],
                    'outputs': ['instance'],
                    'properties': {'class_name': '', 'fields': []}
                },
                'enum': {
                    'name': 'Enum',
                    'description': 'Enumeration type',
                    'category': 'Data Structures',
                    'icon': 'menu',
                    'inputs': [],
                    'outputs': ['enum_type'],
                    'properties': {'enum_name': '', 'members': []}
                },
                
                # ============ COMPREHENSIONS ============
                'list_comprehension': {
                    'name': 'List Comprehension',
                    'description': 'Create list from expression',
                    'category': 'Comprehensions',
                    'icon': 'brackets',
                    'inputs': ['iterable', 'condition'],
                    'outputs': ['list'],
                    'properties': {'expression': '', 'variable': 'x'}
                },
                'dict_comprehension': {
                    'name': 'Dict Comprehension',
                    'description': 'Create dict from expression',
                    'category': 'Comprehensions',
                    'icon': 'braces',
                    'inputs': ['iterable', 'condition'],
                    'outputs': ['dict'],
                    'properties': {'key_expr': '', 'value_expr': '', 'variable': 'x'}
                },
                'set_comprehension': {
                    'name': 'Set Comprehension',
                    'description': 'Create set from expression',
                    'category': 'Comprehensions',
                    'icon': 'circle',
                    'inputs': ['iterable', 'condition'],
                    'outputs': ['set'],
                    'properties': {'expression': '', 'variable': 'x'}
                },
                'generator_expression': {
                    'name': 'Generator Expression',
                    'description': 'Lazy iterator expression',
                    'category': 'Comprehensions',
                    'icon': 'repeat',
                    'inputs': ['iterable', 'condition'],
                    'outputs': ['generator'],
                    'properties': {'expression': '', 'variable': 'x'}
                },
                
                # ============ CONTEXT MANAGERS ============
                'with_statement': {
                    'name': 'With Statement',
                    'description': 'Context manager usage',
                    'category': 'Context Managers',
                    'icon': 'folder-open',
                    'inputs': ['context_manager'],
                    'outputs': ['resource', 'body_output'],
                    'properties': {'as_variable': ''}
                },
                'context_manager': {
                    'name': 'Context Manager',
                    'description': 'Custom context manager',
                    'category': 'Context Managers',
                    'icon': 'package',
                    'inputs': ['enter_logic', 'exit_logic'],
                    'outputs': ['context_manager'],
                    'properties': {}
                },
                
                # ============ ASYNC/AWAIT ============
                'await': {
                    'name': 'Await',
                    'description': 'Wait for coroutine result',
                    'category': 'Async/Await',
                    'icon': 'clock',
                    'inputs': ['coroutine'],
                    'outputs': ['result'],
                    'properties': {}
                },
                'async_for': {
                    'name': 'Async For',
                    'description': 'Async iteration',
                    'category': 'Async/Await',
                    'icon': 'repeat',
                    'inputs': ['async_iterable'],
                    'outputs': ['output'],
                    'properties': {'variable': 'item'}
                },
                'async_with': {
                    'name': 'Async With',
                    'description': 'Async context manager',
                    'category': 'Async/Await',
                    'icon': 'folder-open',
                    'inputs': ['async_context_manager'],
                    'outputs': ['resource', 'body_output'],
                    'properties': {'as_variable': ''}
                },
                'task': {
                    'name': 'Task',
                    'description': 'Asyncio task',
                    'category': 'Async/Await',
                    'icon': 'activity',
                    'inputs': ['coroutine'],
                    'outputs': ['task'],
                    'properties': {}
                },
                'gather': {
                    'name': 'Gather',
                    'description': 'Run coroutines concurrently',
                    'category': 'Async/Await',
                    'icon': 'git-merge',
                    'inputs': ['coroutines'],
                    'outputs': ['results'],
                    'properties': {}
                },
                
                # ============ I/O OPERATIONS ============
                'file_read': {
                    'name': 'Read File',
                    'description': 'Read content from a file',
                    'category': 'I/O Operations',
                    'icon': 'file-text',
                    'image': '/static/images/file_read_node.png',
                    'inputs': ['filename'],
                    'outputs': ['content'],
                    'properties': {'encoding': 'utf-8', 'mode': 'r'}
                },
                'file_write': {
                    'name': 'Write File',
                    'description': 'Write content to a file',
                    'category': 'I/O Operations',
                    'icon': 'file-plus',
                    'inputs': ['filename', 'content'],
                    'outputs': ['success'],
                    'properties': {'encoding': 'utf-8', 'mode': 'w'}
                },
                'print': {
                    'name': 'Print',
                    'description': 'Print to console',
                    'category': 'I/O Operations',
                    'icon': 'terminal',
                    'inputs': ['value'],
                    'outputs': [],
                    'properties': {'sep': ' ', 'end': '\\n'}
                },
                'input': {
                    'name': 'Input',
                    'description': 'Read user input',
                    'category': 'I/O Operations',
                    'icon': 'keyboard',
                    'inputs': ['prompt'],
                    'outputs': ['value'],
                    'properties': {}
                },
                'http_request': {
                    'name': 'HTTP Request',
                    'description': 'Make HTTP requests',
                    'category': 'I/O Operations',
                    'icon': 'globe',
                    'image': '/static/images/http_request_node.png',
                    'inputs': ['url', 'method', 'data'],
                    'outputs': ['response'],
                    'properties': {'method': 'GET', 'headers': {}}
                },
                
                # ============ OPERATORS ============
                'arithmetic': {
                    'name': 'Arithmetic',
                    'description': 'Math operations (+, -, *, /, //, %, **)',
                    'category': 'Operators',
                    'icon': 'plus',
                    'inputs': ['left', 'right'],
                    'outputs': ['result'],
                    'properties': {'operator': '+'}
                },
                'comparison': {
                    'name': 'Comparison',
                    'description': 'Compare values (==, !=, <, >, <=, >=)',
                    'category': 'Operators',
                    'icon': 'equal',
                    'inputs': ['left', 'right'],
                    'outputs': ['result'],
                    'properties': {'operator': '=='}
                },
                'logical': {
                    'name': 'Logical',
                    'description': 'Logical operations (and, or, not)',
                    'category': 'Operators',
                    'icon': 'git-branch',
                    'inputs': ['left', 'right'],
                    'outputs': ['result'],
                    'properties': {'operator': 'and'}
                },
                'bitwise': {
                    'name': 'Bitwise',
                    'description': 'Bitwise operations (&, |, ^, ~, <<, >>)',
                    'category': 'Operators',
                    'icon': 'binary',
                    'inputs': ['left', 'right'],
                    'outputs': ['result'],
                    'properties': {'operator': '&'}
                },
                'membership': {
                    'name': 'Membership',
                    'description': 'Check membership (in, not in)',
                    'category': 'Operators',
                    'icon': 'search',
                    'inputs': ['item', 'container'],
                    'outputs': ['result'],
                    'properties': {'operator': 'in'}
                },
                'identity': {
                    'name': 'Identity',
                    'description': 'Check identity (is, is not)',
                    'category': 'Operators',
                    'icon': 'equal',
                    'inputs': ['left', 'right'],
                    'outputs': ['result'],
                    'properties': {'operator': 'is'}
                },
                'ternary': {
                    'name': 'Ternary',
                    'description': 'Conditional expression (x if cond else y)',
                    'category': 'Operators',
                    'icon': 'help-circle',
                    'inputs': ['condition', 'true_value', 'false_value'],
                    'outputs': ['result'],
                    'properties': {}
                },
                'walrus': {
                    'name': 'Walrus Operator',
                    'description': 'Assignment expression (:=)',
                    'category': 'Operators',
                    'icon': 'edit',
                    'inputs': ['expression'],
                    'outputs': ['value'],
                    'properties': {'variable_name': ''}
                },
                
                # ============ STRING OPERATIONS ============
                'string_format': {
                    'name': 'String Format',
                    'description': 'Format string (f-string, .format())',
                    'category': 'String Operations',
                    'icon': 'type',
                    'inputs': ['template', 'values'],
                    'outputs': ['formatted'],
                    'properties': {'format_type': 'fstring'}
                },
                'string_join': {
                    'name': 'String Join',
                    'description': 'Join iterable with separator',
                    'category': 'String Operations',
                    'icon': 'link',
                    'inputs': ['separator', 'items'],
                    'outputs': ['result'],
                    'properties': {}
                },
                'string_split': {
                    'name': 'String Split',
                    'description': 'Split string by separator',
                    'category': 'String Operations',
                    'icon': 'scissors',
                    'inputs': ['string', 'separator'],
                    'outputs': ['parts'],
                    'properties': {}
                },
                'regex': {
                    'name': 'Regex',
                    'description': 'Regular expression operations',
                    'category': 'String Operations',
                    'icon': 'search',
                    'inputs': ['pattern', 'string'],
                    'outputs': ['matches'],
                    'properties': {'operation': 'search'}
                },
                
                # ============ TYPE OPERATIONS ============
                'type_check': {
                    'name': 'Type Check',
                    'description': 'Check type (isinstance, type)',
                    'category': 'Type Operations',
                    'icon': 'check-circle',
                    'inputs': ['value', 'type'],
                    'outputs': ['result'],
                    'properties': {'check_type': 'isinstance'}
                },
                'type_cast': {
                    'name': 'Type Cast',
                    'description': 'Convert between types',
                    'category': 'Type Operations',
                    'icon': 'shuffle',
                    'inputs': ['value'],
                    'outputs': ['result'],
                    'properties': {'target_type': 'str'}
                },
                'type_hint': {
                    'name': 'Type Hint',
                    'description': 'Type annotation',
                    'category': 'Type Operations',
                    'icon': 'tag',
                    'inputs': [],
                    'outputs': ['type'],
                    'properties': {'type_expression': ''}
                },
                
                # ============ IMPORT/MODULE ============
                'import': {
                    'name': 'Import',
                    'description': 'Import module',
                    'category': 'Import/Module',
                    'icon': 'download',
                    'inputs': [],
                    'outputs': ['module'],
                    'properties': {'module_name': ''}
                },
                'from_import': {
                    'name': 'From Import',
                    'description': 'Import specific items from module',
                    'category': 'Import/Module',
                    'icon': 'download',
                    'inputs': [],
                    'outputs': ['imported_items'],
                    'properties': {'module_name': '', 'items': []}
                },
                'module': {
                    'name': 'Module',
                    'description': 'Python module definition',
                    'category': 'Import/Module',
                    'icon': 'package',
                    'inputs': [],
                    'outputs': ['module'],
                    'properties': {'module_name': '', 'docstring': ''}
                },
                
                # ============ BUILTIN FUNCTIONS ============
                'len': {
                    'name': 'Length (len)',
                    'description': 'Get length of sequence',
                    'category': 'Builtin Functions',
                    'icon': 'ruler',
                    'inputs': ['sequence'],
                    'outputs': ['length'],
                    'properties': {}
                },
                'range': {
                    'name': 'Range',
                    'description': 'Generate number sequence',
                    'category': 'Builtin Functions',
                    'icon': 'hash',
                    'inputs': ['start', 'stop', 'step'],
                    'outputs': ['range'],
                    'properties': {}
                },
                'enumerate': {
                    'name': 'Enumerate',
                    'description': 'Add index to iterable',
                    'category': 'Builtin Functions',
                    'icon': 'list-ordered',
                    'inputs': ['iterable'],
                    'outputs': ['enumerated'],
                    'properties': {'start': 0}
                },
                'zip': {
                    'name': 'Zip',
                    'description': 'Combine iterables',
                    'category': 'Builtin Functions',
                    'icon': 'layers',
                    'inputs': ['iterables'],
                    'outputs': ['zipped'],
                    'properties': {}
                },
                'map': {
                    'name': 'Map',
                    'description': 'Apply function to iterable',
                    'category': 'Builtin Functions',
                    'icon': 'map',
                    'inputs': ['function', 'iterable'],
                    'outputs': ['mapped'],
                    'properties': {}
                },
                'filter': {
                    'name': 'Filter',
                    'description': 'Filter iterable by predicate',
                    'category': 'Builtin Functions',
                    'icon': 'filter',
                    'inputs': ['predicate', 'iterable'],
                    'outputs': ['filtered'],
                    'properties': {}
                },
                'reduce': {
                    'name': 'Reduce',
                    'description': 'Reduce iterable to single value',
                    'category': 'Builtin Functions',
                    'icon': 'git-merge',
                    'inputs': ['function', 'iterable', 'initial'],
                    'outputs': ['result'],
                    'properties': {}
                },
                'sorted': {
                    'name': 'Sorted',
                    'description': 'Sort iterable',
                    'category': 'Builtin Functions',
                    'icon': 'arrow-up',
                    'inputs': ['iterable'],
                    'outputs': ['sorted'],
                    'properties': {'reverse': False, 'key': None}
                },
                'reversed': {
                    'name': 'Reversed',
                    'description': 'Reverse sequence',
                    'category': 'Builtin Functions',
                    'icon': 'arrow-left',
                    'inputs': ['sequence'],
                    'outputs': ['reversed'],
                    'properties': {}
                },
                'any_all': {
                    'name': 'Any/All',
                    'description': 'Check any/all items are truthy',
                    'category': 'Builtin Functions',
                    'icon': 'check',
                    'inputs': ['iterable'],
                    'outputs': ['result'],
                    'properties': {'function': 'any'}
                },
                'min_max': {
                    'name': 'Min/Max',
                    'description': 'Get minimum/maximum value',
                    'category': 'Builtin Functions',
                    'icon': 'trending-up',
                    'inputs': ['items'],
                    'outputs': ['result'],
                    'properties': {'function': 'max'}
                },
                'sum': {
                    'name': 'Sum',
                    'description': 'Sum numeric values',
                    'category': 'Builtin Functions',
                    'icon': 'plus-circle',
                    'inputs': ['iterable'],
                    'outputs': ['total'],
                    'properties': {'start': 0}
                },
                'abs': {
                    'name': 'Absolute Value',
                    'description': 'Get absolute value',
                    'category': 'Builtin Functions',
                    'icon': 'maximize-2',
                    'inputs': ['number'],
                    'outputs': ['result'],
                    'properties': {}
                },
                'round': {
                    'name': 'Round',
                    'description': 'Round to precision',
                    'category': 'Builtin Functions',
                    'icon': 'circle',
                    'inputs': ['number', 'digits'],
                    'outputs': ['rounded'],
                    'properties': {}
                },
                
                # ============ CUSTOM/LIBRARY ============
                'custom': {
                    'name': 'Custom Node',
                    'description': 'User-defined custom node',
                    'category': 'Custom',
                    'icon': 'edit-3',
                    'inputs': [],
                    'outputs': [],
                    'properties': {'name': '', 'source_code': ''}
                },
                'library_function': {
                    'name': 'Library Function',
                    'description': 'Function from external library',
                    'category': 'Custom',
                    'icon': 'package',
                    'inputs': ['args'],
                    'outputs': ['result'],
                    'properties': {'module': '', 'function': ''}
                },
                'external_call': {
                    'name': 'External Call',
                    'description': 'Call to external function/API',
                    'category': 'Custom',
                    'icon': 'external-link',
                    'inputs': ['args'],
                    'outputs': ['result'],
                    'properties': {'call_target': ''}
                },
                
                # ============ COMMENTS/DOCS ============
                'comment': {
                    'name': 'Comment',
                    'description': 'Code comment',
                    'category': 'Documentation',
                    'icon': 'message-square',
                    'inputs': [],
                    'outputs': [],
                    'properties': {'text': ''}
                },
                'docstring': {
                    'name': 'Docstring',
                    'description': 'Documentation string',
                    'category': 'Documentation',
                    'icon': 'file-text',
                    'inputs': [],
                    'outputs': [],
                    'properties': {'text': ''}
                },
                'todo': {
                    'name': 'TODO',
                    'description': 'TODO marker',
                    'category': 'Documentation',
                    'icon': 'check-square',
                    'inputs': [],
                    'outputs': [],
                    'properties': {'text': ''}
                }
            },
            
            ParadigmType.BLOCK_BASED: {
                # Control structures
                'if_statement': {
                    'name': 'If',
                    'description': 'If condition block',
                    'category': 'Control',
                    'icon': 'git-branch',
                    'shape': 'diamond',
                    'color': '#FFA500'
                },
                'while_loop': {
                    'name': 'While',
                    'description': 'While loop block',
                    'category': 'Control',
                    'icon': 'repeat',
                    'shape': 'hexagon',
                    'color': '#FF6B6B'
                },
                'for_loop': {
                    'name': 'For',
                    'description': 'For loop block',
                    'category': 'Control',
                    'icon': 'repeat',
                    'shape': 'hexagon',
                    'color': '#4ECDC4'
                },
                
                # Functions
                'function_def': {
                    'name': 'Define Function',
                    'description': 'Define a new function',
                    'category': 'Functions',
                    'icon': 'function-square',
                    'shape': 'rounded_rect',
                    'color': '#95E1D3'
                },
                'function_call': {
                    'name': 'Call Function',
                    'description': 'Call a function',
                    'category': 'Functions',
                    'icon': 'play',
                    'shape': 'rounded_rect',
                    'color': '#A8E6CF'
                },
                
                # Variables
                'variable_set': {
                    'name': 'Set Variable',
                    'description': 'Set variable value',
                    'category': 'Variables',
                    'icon': 'variable',
                    'shape': 'rect',
                    'color': '#DDA0DD'
                },
                'variable_get': {
                    'name': 'Get Variable',
                    'description': 'Get variable value',
                    'category': 'Variables',
                    'icon': 'eye',
                    'shape': 'oval',
                    'color': '#E6E6FA'
                },
                
                # I/O
                'print_statement': {
                    'name': 'Print',
                    'description': 'Print to console',
                    'category': 'I/O',
                    'icon': 'printer',
                    'shape': 'rect',
                    'color': '#F0E68C'
                },
                'input_statement': {
                    'name': 'Input',
                    'description': 'Get user input',
                    'category': 'I/O',
                    'icon': 'keyboard',
                    'shape': 'rect',
                    'color': '#FFB6C1'
                }
            },
            
            ParadigmType.DIAGRAM_BASED: {
                # Class diagram elements
                'class': {
                    'name': 'Class',
                    'description': 'Object-oriented class',
                    'category': 'Classes',
                    'icon': 'box',
                    'stereotype': None,
                    'notation': 'UML'
                },
                'abstract_class': {
                    'name': 'Abstract Class',
                    'description': 'Abstract base class',
                    'category': 'Classes',
                    'icon': 'box',
                    'stereotype': '<<abstract>>',
                    'notation': 'UML'
                },
                'interface': {
                    'name': 'Interface',
                    'description': 'Interface definition',
                    'category': 'Interfaces',
                    'icon': 'circle',
                    'stereotype': '<<interface>>',
                    'notation': 'UML'
                },
                
                # Package elements
                'package': {
                    'name': 'Package',
                    'description': 'Code package/namespace',
                    'category': 'Packages',
                    'icon': 'package',
                    'stereotype': '<<package>>',
                    'notation': 'UML'
                },
                'module': {
                    'name': 'Module',
                    'description': 'Python module',
                    'category': 'Modules',
                    'icon': 'file',
                    'stereotype': '<<module>>',
                    'notation': 'UML'
                },
                
                # Use case elements
                'actor': {
                    'name': 'Actor',
                    'description': 'System actor',
                    'category': 'Use Cases',
                    'icon': 'user',
                    'stereotype': '<<actor>>',
                    'notation': 'UML'
                },
                'use_case': {
                    'name': 'Use Case',
                    'description': 'System use case',
                    'category': 'Use Cases',
                    'icon': 'circle',
                    'stereotype': None,
                    'notation': 'UML'
                }
            },
            
            ParadigmType.TIMELINE_BASED: {
                # Basic temporal elements
                'event': {
                    'name': 'Event',
                    'description': 'Point-in-time event',
                    'category': 'Events',
                    'icon': 'zap',
                    'temporal_type': 'instant'
                },
                'process': {
                    'name': 'Process',
                    'description': 'Long-running process',
                    'category': 'Processes',
                    'icon': 'activity',
                    'temporal_type': 'duration'
                },
                'timer': {
                    'name': 'Timer',
                    'description': 'Countdown timer',
                    'category': 'Timers',
                    'icon': 'clock',
                    'temporal_type': 'duration'
                },
                'delay': {
                    'name': 'Delay',
                    'description': 'Wait/pause execution',
                    'category': 'Control',
                    'icon': 'pause',
                    'temporal_type': 'duration'
                },
                
                # Concurrency
                'parallel': {
                    'name': 'Parallel',
                    'description': 'Parallel execution',
                    'category': 'Concurrency',
                    'icon': 'git-branch',
                    'temporal_type': 'concurrent'
                },
                'sequence': {
                    'name': 'Sequence',
                    'description': 'Sequential execution',
                    'category': 'Control',
                    'icon': 'arrow-right',
                    'temporal_type': 'sequential'
                },
                
                # Async elements
                'async_function': {
                    'name': 'Async Function',
                    'description': 'Asynchronous function',
                    'category': 'Async',
                    'icon': 'function-square',
                    'temporal_type': 'async'
                },
                'await': {
                    'name': 'Await',
                    'description': 'Wait for async result',
                    'category': 'Async',
                    'icon': 'clock',
                    'temporal_type': 'sync_point'
                }
            }
        }
    
    def get_element_types_for_paradigm(self, paradigm_type: ParadigmType) -> List[Dict[str, Any]]:
        """Get all available element types for a specific paradigm."""
        definitions = self.element_definitions.get(paradigm_type, {})
        return [
            {
                'type': element_type,
                **element_def
            }
            for element_type, element_def in definitions.items()
        ]
    
    def get_all_element_types(self) -> List[Dict[str, Any]]:
        """Get all available element types across all paradigms."""
        all_elements = []
        for paradigm_type, definitions in self.element_definitions.items():
            for element_type, element_def in definitions.items():
                element = {
                    'type': element_type,
                    'paradigm': paradigm_type.value,
                    **element_def
                }
                all_elements.append(element)
        return all_elements
    
    def get_element_definition(self, paradigm_type: ParadigmType, element_type: str) -> Optional[Dict[str, Any]]:
        """Get the definition for a specific element type."""
        return self.element_definitions.get(paradigm_type, {}).get(element_type)
    
    def create_element_with_defaults(self, paradigm_type: ParadigmType, element_type: str, 
                                   position: Tuple[float, float], **kwargs) -> Optional[Dict[str, Any]]:
        """Create an element with default properties based on its definition."""
        definition = self.get_element_definition(paradigm_type, element_type)
        if not definition:
            return None
        
        # Merge definition defaults with provided kwargs
        element_data = {
            'element_type': element_type,
            'position': position,
            'properties': {**definition.get('properties', {}), **kwargs.get('properties', {})},
            'metadata': {**definition, **kwargs.get('metadata', {})}
        }
        
        # Add paradigm-specific defaults
        if paradigm_type == ParadigmType.NODE_BASED:
            element_data.update({
                'inputs': definition.get('inputs', []),
                'outputs': definition.get('outputs', [])
            })
        elif paradigm_type == ParadigmType.BLOCK_BASED:
            element_data.update({
                'shape': definition.get('shape', 'rect'),
                'color': definition.get('color', '#D3D3D3')
            })
        elif paradigm_type == ParadigmType.DIAGRAM_BASED:
            element_data.update({
                'stereotype': definition.get('stereotype'),
                'notation': definition.get('notation', 'UML')
            })
        elif paradigm_type == ParadigmType.TIMELINE_BASED:
            element_data.update({
                'temporal_type': definition.get('temporal_type', 'generic'),
                'start_time': kwargs.get('start_time', 0.0),
                'duration': kwargs.get('duration', 1.0)
            })
        
        return element_data