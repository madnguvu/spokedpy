"""
Visual Editor Core - The foundational component of the Visual Python Development Platform (VPyD).

This package provides bidirectional conversion between visual programming models and Python source code,
supporting multiple visual programming paradigms while maintaining semantic fidelity.
"""

__version__ = "0.1.0"
__author__ = "VPyD Development Team"

from .models import VisualNode, Connection, VisualModel, InputPort, OutputPort, NodeType
from .ast_processor import ASTProcessor
from .code_generator import CodeGenerator
from .visual_parser import VisualParser
from .node_palette import NodePalette
from .execution_engine import ExecutionEngine, JavaScriptExecutor, RustExecutor
from .canvas import Canvas
from .plugin_system import (
    PluginManager, PluginAPI, VisualComponentPlugin, VisualParadigmPlugin,
    CodeGeneratorPlugin, PluginManifest, PluginType, PluginStatus, SecurityLevel
)

# Universal IR and cross-language support
from .uir_translator import UIRTranslator, get_translator
from .universal_ir import UniversalProject, UniversalModule, UniversalFunction, UniversalClass

# Language parsers
from .python_parser import PythonParser
from .js_parser import JavaScriptParser
from .typescript_parser import TypeScriptParser
from .ruby_parser import RubyParser
from .php_parser import PHPParser
from .lua_parser import LuaParser
from .r_parser import RParser
from .java_parser import JavaParser
from .go_parser import GoParser
from .rust_parser import RustParser
from .csharp_parser import CSharpParser
from .kotlin_parser import KotlinParser
from .swift_parser import SwiftParser
from .scala_parser import ScalaParser
from .c_parser import CParser
from .sql_parser import SQLParser
from .bash_parser import BashParser

# Language generators
from .python_generator import PythonGenerator
from .js_generator import JavaScriptGenerator
from .typescript_generator import TypeScriptGenerator
from .ruby_generator import RubyGenerator
from .php_generator import PHPGenerator
from .lua_generator import LuaGenerator
from .r_generator import RGenerator
from .java_generator import JavaGenerator
from .go_generator import GoGenerator
from .rust_generator import RustGenerator
from .csharp_generator import CSharpGenerator
from .kotlin_generator import KotlinGenerator
from .swift_generator import SwiftGenerator
from .scala_generator import ScalaGenerator
from .c_generator import CGenerator
from .sql_generator import SQLGenerator
from .bash_generator import BashGenerator

__all__ = [
    "VisualNode",
    "Connection", 
    "VisualModel",
    "InputPort",
    "OutputPort",
    "NodeType",
    "ASTProcessor",
    "CodeGenerator",
    "VisualParser",
    "NodePalette",
    "ExecutionEngine",
    "JavaScriptExecutor",
    "RustExecutor",
    "Canvas",
    "PluginManager",
    "PluginAPI",
    "VisualComponentPlugin",
    "VisualParadigmPlugin",
    "CodeGeneratorPlugin",
    "PluginManifest",
    "PluginType",
    "PluginStatus",
    "SecurityLevel",
    # Universal IR
    "UIRTranslator",
    "get_translator",
    "UniversalProject",
    "UniversalModule",
    "UniversalFunction",
    "UniversalClass",
    # Language parsers
    "PythonParser",
    "JavaScriptParser",
    "TypeScriptParser",
    "RubyParser",
    "PHPParser",
    "LuaParser",
    "RParser",
    "JavaParser",
    "GoParser",
    "RustParser",
    "CSharpParser",
    "KotlinParser",
    "SwiftParser",
    "ScalaParser",
    "CParser",
    "SQLParser",
    "BashParser",
    # Language generators
    "PythonGenerator",
    "JavaScriptGenerator",
    "TypeScriptGenerator",
    "RubyGenerator",
    "PHPGenerator",
    "LuaGenerator",
    "RGenerator",
    "JavaGenerator",
    "GoGenerator",
    "RustGenerator",
    "CSharpGenerator",
    "KotlinGenerator",
    "SwiftGenerator",
    "ScalaGenerator",
    "CGenerator",
    "SQLGenerator",
    "BashGenerator",
]