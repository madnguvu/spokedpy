"""
Core data models for the Visual Editor.

This module defines the fundamental data structures used throughout the visual programming system,
including visual nodes, connections, and the overall visual model representation.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Tuple, Type, Optional
from enum import Enum
import uuid
import ast


class ValidationError(Exception):
    """Exception raised when visual model validation fails."""
    pass


class NodeType(Enum):
    """Enumeration of supported visual node types."""
    FUNCTION = "function"
    VARIABLE = "variable"
    CONTROL_FLOW = "control_flow"
    CLASS = "class"
    DECORATOR = "decorator"
    ASYNC = "async"
    GENERATOR = "generator"
    METACLASS = "metaclass"
    CONTEXT_MANAGER = "context_manager"
    CUSTOM = "custom"
    IMPORT = "import"
    COMMENT = "comment"
    EXPRESSION = "expression"
    STATEMENT = "statement"
    MODULE = "module"


@dataclass
class InputPort:
    """Represents an input port on a visual node."""
    name: str
    data_type: Type
    required: bool = True
    default_value: Any = None
    description: str = ""
    
    def validate_value(self, value: Any) -> bool:
        """Validate that a value is compatible with this port's type."""
        if value is None and not self.required:
            return True
        try:
            return isinstance(value, self.data_type)
        except TypeError:
            # Handle complex types that can't be used with isinstance
            return True


@dataclass
class OutputPort:
    """Represents an output port on a visual node."""
    name: str
    data_type: Type
    description: str = ""
    
    def is_compatible_with(self, input_port: InputPort) -> bool:
        """Check if this output port is compatible with an input port."""
        try:
            return issubclass(self.data_type, input_port.data_type) or \
                   issubclass(input_port.data_type, self.data_type)
        except TypeError:
            # Handle complex types
            return self.data_type == input_port.data_type


@dataclass
class VisualNode:
    """Represents a visual programming node in the editor."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    type: NodeType = NodeType.FUNCTION
    name: str = ""  # Display name for the node
    position: Tuple[float, float] = (0.0, 0.0)
    inputs: List[InputPort] = field(default_factory=list)
    outputs: List[OutputPort] = field(default_factory=list)
    parameters: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    comments: List[str] = field(default_factory=list)  # Visual annotations/comments
    docstring: Optional[str] = None  # Custom docstring for this node
    code_snippet: str = ""  # Raw code snippet associated with this node
    
    def validate(self) -> List[ValidationError]:
        """Validate the node configuration and return any errors."""
        errors = []
        
        # Check for duplicate port names
        input_names = [port.name for port in self.inputs]
        if len(input_names) != len(set(input_names)):
            errors.append(ValidationError("Duplicate input port names found"))
            
        output_names = [port.name for port in self.outputs]
        if len(output_names) != len(set(output_names)):
            errors.append(ValidationError("Duplicate output port names found"))
            
        # Validate required parameters based on node type
        if self.type == NodeType.FUNCTION and 'function_name' not in self.parameters:
            # Only require function_name for actual function nodes, not all function-type nodes
            if self.metadata.get('extended_type') == 'function':
                errors.append(ValidationError("Function nodes must have 'function_name' parameter"))
            
        return errors
    
    def to_ast_node(self) -> ast.AST:
        """Convert this visual node to an AST node. To be implemented by ASTProcessor."""
        raise NotImplementedError("AST conversion handled by ASTProcessor")
    
    def get_dependencies(self) -> List[str]:
        """Get list of node IDs that this node depends on."""
        return self.metadata.get('dependencies', [])
    
    def get_input_port(self, name: str) -> Optional[InputPort]:
        """Get an input port by name."""
        for port in self.inputs:
            if port.name == name:
                return port
        return None
    
    def get_output_port(self, name: str) -> Optional[OutputPort]:
        """Get an output port by name."""
        for port in self.outputs:
            if port.name == name:
                return port
        return None


@dataclass
class Connection:
    """Represents a connection between two visual nodes."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source_node_id: str = ""
    source_port: str = ""
    target_node_id: str = ""
    target_port: str = ""
    data_type: Type = type(None)
    
    def validate_compatibility(self, source_node: VisualNode, target_node: VisualNode) -> bool:
        """Validate that this connection is compatible between the given nodes."""
        source_output = source_node.get_output_port(self.source_port)
        target_input = target_node.get_input_port(self.target_port)
        
        if not source_output or not target_input:
            return False
            
        return source_output.is_compatible_with(target_input)
    
    def get_data_flow_info(self) -> Dict[str, Any]:
        """Get information about data flow through this connection."""
        return {
            'connection_id': self.id,
            'data_type': self.data_type.__name__ if self.data_type else 'None',
            'source': f"{self.source_node_id}.{self.source_port}",
            'target': f"{self.target_node_id}.{self.target_port}"
        }


@dataclass
class VisualModel:
    """Represents a complete visual programming model."""
    nodes: Dict[str, VisualNode] = field(default_factory=dict)
    connections: List[Connection] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def add_node(self, node: VisualNode) -> str:
        """Add a node to the model and return its ID."""
        self.nodes[node.id] = node
        return node.id
    
    def add_connection(self, connection: Connection) -> bool:
        """Add an existing connection to the model."""
        # Validate that source and target nodes exist
        if connection.source_node_id not in self.nodes:
            return False
        if connection.target_node_id not in self.nodes:
            return False
        self.connections.append(connection)
        return True
    
    def remove_node(self, node_id: str) -> bool:
        """Remove a node and all its connections from the model."""
        if node_id not in self.nodes:
            return False
            
        # Remove all connections involving this node
        self.connections = [
            conn for conn in self.connections
            if conn.source_node_id != node_id and conn.target_node_id != node_id
        ]
        
        del self.nodes[node_id]
        return True
    
    def connect_nodes(self, source_id: str, source_port: str, 
                     target_id: str, target_port: str) -> Optional[Connection]:
        """Create a connection between two nodes."""
        if source_id not in self.nodes or target_id not in self.nodes:
            return None
            
        source_node = self.nodes[source_id]
        target_node = self.nodes[target_id]
        
        # Create connection
        connection = Connection(
            source_node_id=source_id,
            source_port=source_port,
            target_node_id=target_id,
            target_port=target_port
        )
        
        # Validate compatibility
        if not connection.validate_compatibility(source_node, target_node):
            return None
            
        # Set data type from source port
        source_output = source_node.get_output_port(source_port)
        if source_output:
            connection.data_type = source_output.data_type
            
        self.connections.append(connection)
        return connection
    
    def validate_model(self) -> List[ValidationError]:
        """Validate the entire model and return any errors."""
        errors = []
        
        # Validate all nodes
        for node in self.nodes.values():
            errors.extend(node.validate())
            
        # Validate all connections
        for connection in self.connections:
            if connection.source_node_id not in self.nodes:
                errors.append(ValidationError(f"Connection references missing source node: {connection.source_node_id}"))
            if connection.target_node_id not in self.nodes:
                errors.append(ValidationError(f"Connection references missing target node: {connection.target_node_id}"))
                
        # Check for cycles (basic check)
        if self._has_cycles():
            errors.append(ValidationError("Model contains circular dependencies"))
            
        return errors
    
    def _has_cycles(self) -> bool:
        """Check if the model has circular dependencies using DFS."""
        visited = set()
        rec_stack = set()
        
        def dfs(node_id: str) -> bool:
            if node_id in rec_stack:
                return True
            if node_id in visited:
                return False
                
            visited.add(node_id)
            rec_stack.add(node_id)
            
            # Get all nodes this node connects to
            for connection in self.connections:
                if connection.source_node_id == node_id:
                    if dfs(connection.target_node_id):
                        return True
                        
            rec_stack.remove(node_id)
            return False
        
        for node_id in self.nodes:
            if node_id not in visited:
                if dfs(node_id):
                    return True
        return False
    
    def to_ast(self) -> ast.Module:
        """Convert this visual model to an AST. To be implemented by ASTProcessor."""
        raise NotImplementedError("AST conversion handled by ASTProcessor")
    
    def get_execution_order(self) -> List[str]:
        """Get the topological order for node execution."""
        in_degree = {node_id: 0 for node_id in self.nodes}
        
        # Calculate in-degrees
        for connection in self.connections:
            in_degree[connection.target_node_id] += 1
            
        # Topological sort using Kahn's algorithm
        queue = [node_id for node_id, degree in in_degree.items() if degree == 0]
        result = []
        
        while queue:
            node_id = queue.pop(0)
            result.append(node_id)
            
            # Reduce in-degree for connected nodes
            for connection in self.connections:
                if connection.source_node_id == node_id:
                    in_degree[connection.target_node_id] -= 1
                    if in_degree[connection.target_node_id] == 0:
                        queue.append(connection.target_node_id)
                        
        return result if len(result) == len(self.nodes) else []