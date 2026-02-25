"""
Universal Intermediate Representation (UIR) for cross-language visual programming.

This module defines a language-agnostic representation of programming concepts
that can be translated between different programming languages.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Union, Literal
from enum import Enum
import uuid


class DataType(Enum):
    """Universal data types that map across languages."""
    VOID = "void"
    BOOLEAN = "boolean"
    INTEGER = "integer"
    FLOAT = "float"
    STRING = "string"
    ARRAY = "array"
    OBJECT = "object"
    FUNCTION = "function"
    ANY = "any"
    UNKNOWN = "unknown"


class PurityLevel(Enum):
    """Function purity levels for optimization and translation."""
    PURE = "pure"  # No side effects, deterministic
    READ_ONLY = "read_only"  # Reads external state but doesn't modify
    SIDE_EFFECTS = "side_effects"  # Modifies external state
    IO_BOUND = "io_bound"  # Performs I/O operations
    ASYNC = "async"  # Asynchronous operations


@dataclass
class TypeSignature:
    """Universal type signature."""
    base_type: DataType
    generic_params: List['TypeSignature'] = field(default_factory=list)
    nullable: bool = False
    
    def __str__(self) -> str:
        if self.generic_params:
            params = ', '.join(str(p) for p in self.generic_params)
            return f"{self.base_type.value}<{params}>"
        return self.base_type.value


@dataclass
class Parameter:
    """Universal function parameter."""
    name: str
    type_sig: TypeSignature
    default_value: Optional[Any] = None
    required: bool = True
    
    def __post_init__(self):
        if self.default_value is not None:
            self.required = False


@dataclass
class Contract:
    """Input/output contract for functions."""
    description: str
    type_sig: TypeSignature
    constraints: List[str] = field(default_factory=list)
    examples: List[Any] = field(default_factory=list)


@dataclass
class SemanticDescription:
    """Language-agnostic description of what a function does."""
    purpose: str
    input_contracts: List[Contract]
    output_contract: Contract
    side_effects: List[str] = field(default_factory=list)
    complexity: str = "O(1)"  # Big O notation
    purity: PurityLevel = PurityLevel.PURE


@dataclass
class UniversalFunction:
    """Universal representation of a function."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    parameters: List[Parameter] = field(default_factory=list)
    return_type: TypeSignature = field(default_factory=lambda: TypeSignature(DataType.VOID))
    semantics: Optional[SemanticDescription] = None
    
    # Language-specific metadata
    source_language: str = ""
    source_code: str = ""
    implementation_hints: Dict[str, Any] = field(default_factory=dict)
    
    # Dependencies
    dependencies: List[str] = field(default_factory=list)  # Other function IDs
    external_libraries: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        if not self.name:
            self.name = f"function_{self.id[:8]}"


@dataclass
class UniversalClass:
    """Universal representation of a class/object."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    methods: List[UniversalFunction] = field(default_factory=list)
    properties: List[Parameter] = field(default_factory=list)
    base_classes: List[str] = field(default_factory=list)
    
    # Language-specific metadata
    source_language: str = ""
    source_code: str = ""
    implementation_hints: Dict[str, Any] = field(default_factory=dict)


@dataclass
class UniversalVariable:
    """Universal representation of a variable/constant."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    type_sig: TypeSignature = field(default_factory=lambda: TypeSignature(DataType.ANY))
    value: Optional[Any] = None
    is_constant: bool = False
    is_global: bool = False
    
    # Language-specific metadata
    source_language: str = ""
    implementation_hints: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DataFlow:
    """Represents data flow between universal elements."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source_id: str = ""
    source_output: str = ""
    target_id: str = ""
    target_input: str = ""
    data_type: TypeSignature = field(default_factory=lambda: TypeSignature(DataType.ANY))


@dataclass
class UniversalModule:
    """Universal representation of a module/file."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    functions: List[UniversalFunction] = field(default_factory=list)
    classes: List[UniversalClass] = field(default_factory=list)
    variables: List[UniversalVariable] = field(default_factory=list)
    imports: List[str] = field(default_factory=list)
    exports: List[str] = field(default_factory=list)
    
    # Language-specific metadata
    source_language: str = ""
    source_file: str = ""


@dataclass
class UniversalProject:
    """Universal representation of an entire project."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    modules: List[UniversalModule] = field(default_factory=list)
    data_flows: List[DataFlow] = field(default_factory=list)
    
    # Cross-language mappings
    language_mappings: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    bridge_requirements: List[str] = field(default_factory=list)
    
    def get_all_functions(self) -> List[UniversalFunction]:
        """Get all functions from all modules."""
        functions = []
        for module in self.modules:
            functions.extend(module.functions)
            for cls in module.classes:
                functions.extend(cls.methods)
        return functions
    
    def get_function_by_id(self, func_id: str) -> Optional[UniversalFunction]:
        """Find a function by its ID."""
        for func in self.get_all_functions():
            if func.id == func_id:
                return func
        return None
    
    def get_dependencies_graph(self) -> Dict[str, List[str]]:
        """Build a dependency graph of all functions."""
        graph = {}
        for func in self.get_all_functions():
            graph[func.id] = func.dependencies.copy()
        return graph


class LanguageMapping:
    """Maps universal concepts to language-specific implementations."""
    
    def __init__(self, source_lang: str, target_lang: str):
        self.source_lang = source_lang
        self.target_lang = target_lang
        self.type_mappings = self._init_type_mappings()
        self.concept_mappings = self._init_concept_mappings()
    
    def _init_type_mappings(self) -> Dict[DataType, str]:
        """Initialize type mappings for the target language."""
        if self.target_lang == "python":
            return {
                DataType.VOID: "None",
                DataType.BOOLEAN: "bool",
                DataType.INTEGER: "int",
                DataType.FLOAT: "float",
                DataType.STRING: "str",
                DataType.ARRAY: "List",
                DataType.OBJECT: "Dict",
                DataType.FUNCTION: "Callable",
                DataType.ANY: "Any",
                DataType.UNKNOWN: "Any"
            }
        elif self.target_lang == "javascript":
            return {
                DataType.VOID: "void",
                DataType.BOOLEAN: "boolean",
                DataType.INTEGER: "number",
                DataType.FLOAT: "number",
                DataType.STRING: "string",
                DataType.ARRAY: "Array",
                DataType.OBJECT: "object",
                DataType.FUNCTION: "Function",
                DataType.ANY: "any",
                DataType.UNKNOWN: "unknown"
            }
        else:
            return {}
    
    def _init_concept_mappings(self) -> Dict[str, str]:
        """Initialize concept mappings for the target language."""
        if self.target_lang == "python":
            return {
                "async_function": "async def",
                "promise": "asyncio.Future",
                "array_map": "list comprehension",
                "object_destructuring": "unpacking",
                "null_check": "is None",
                "string_interpolation": "f-string"
            }
        elif self.target_lang == "javascript":
            return {
                "async_function": "async function",
                "promise": "Promise",
                "array_map": "Array.map",
                "object_destructuring": "destructuring",
                "null_check": "== null",
                "string_interpolation": "template literal"
            }
        else:
            return {}
    
    def map_type(self, universal_type: TypeSignature) -> str:
        """Map a universal type to target language type."""
        return self.type_mappings.get(universal_type.base_type, "any")
    
    def map_concept(self, concept: str) -> str:
        """Map a universal concept to target language implementation."""
        return self.concept_mappings.get(concept, concept)