"""
Universal IR Translator Service.

This module provides translation services between different programming languages
using the Universal Intermediate Representation as a bridge.
"""

from typing import Dict, List, Optional, Any, Tuple
from .universal_ir import UniversalProject, UniversalModule, UniversalFunction
from .python_parser import PythonParser
from .js_parser import JavaScriptParser
from .python_generator import PythonGenerator
from .js_generator import JavaScriptGenerator

# Import new language parsers and generators
from .typescript_parser import TypeScriptParser
from .typescript_generator import TypeScriptGenerator
from .ruby_parser import RubyParser
from .ruby_generator import RubyGenerator
from .php_parser import PHPParser
from .php_generator import PHPGenerator
from .lua_parser import LuaParser
from .lua_generator import LuaGenerator
from .r_parser import RParser
from .r_generator import RGenerator

# Import additional language support (Java, Go, Rust, C#, Kotlin, Swift, Scala, C, SQL, Bash)
from .java_parser import JavaParser
from .java_generator import JavaGenerator
from .go_parser import GoParser
from .go_generator import GoGenerator
from .rust_parser import RustParser
from .rust_generator import RustGenerator
from .csharp_parser import CSharpParser
from .csharp_generator import CSharpGenerator
from .kotlin_parser import KotlinParser
from .kotlin_generator import KotlinGenerator
from .swift_parser import SwiftParser
from .swift_generator import SwiftGenerator
from .scala_parser import ScalaParser
from .scala_generator import ScalaGenerator
from .c_parser import CParser
from .c_generator import CGenerator
from .sql_parser import SQLParser
from .sql_generator import SQLGenerator
from .bash_parser import BashParser
from .bash_generator import BashGenerator


class UIRTranslator:
    """Main translator service for cross-language code translation."""
    
    def __init__(self):
        # Initialize parsers
        self.python_parser = PythonParser()
        self.js_parser = JavaScriptParser()
        self.typescript_parser = TypeScriptParser()
        self.ruby_parser = RubyParser()
        self.php_parser = PHPParser()
        self.lua_parser = LuaParser()
        self.r_parser = RParser()
        self.java_parser = JavaParser()
        self.go_parser = GoParser()
        self.rust_parser = RustParser()
        self.csharp_parser = CSharpParser()
        self.kotlin_parser = KotlinParser()
        self.swift_parser = SwiftParser()
        self.scala_parser = ScalaParser()
        self.c_parser = CParser()
        self.sql_parser = SQLParser()
        self.bash_parser = BashParser()
        
        # Initialize generators
        self.python_generator = PythonGenerator()
        self.js_generator = JavaScriptGenerator()
        self.typescript_generator = TypeScriptGenerator()
        self.ruby_generator = RubyGenerator()
        self.php_generator = PHPGenerator()
        self.lua_generator = LuaGenerator()
        self.r_generator = RGenerator()
        self.java_generator = JavaGenerator()
        self.go_generator = GoGenerator()
        self.rust_generator = RustGenerator()
        self.csharp_generator = CSharpGenerator()
        self.kotlin_generator = KotlinGenerator()
        self.swift_generator = SwiftGenerator()
        self.scala_generator = ScalaGenerator()
        self.c_generator = CGenerator()
        self.sql_generator = SQLGenerator()
        self.bash_generator = BashGenerator()
        
        # Supported languages
        self.supported_languages = {
            'python': {
                'parser': self.python_parser,
                'generator': self.python_generator,
                'extensions': ['.py']
            },
            'javascript': {
                'parser': self.js_parser,
                'generator': self.js_generator,
                'extensions': ['.js', '.mjs']
            },
            'typescript': {
                'parser': self.typescript_parser,
                'generator': self.typescript_generator,
                'extensions': ['.ts', '.tsx']
            },
            'ruby': {
                'parser': self.ruby_parser,
                'generator': self.ruby_generator,
                'extensions': ['.rb']
            },
            'php': {
                'parser': self.php_parser,
                'generator': self.php_generator,
                'extensions': ['.php']
            },
            'lua': {
                'parser': self.lua_parser,
                'generator': self.lua_generator,
                'extensions': ['.lua']
            },
            'r': {
                'parser': self.r_parser,
                'generator': self.r_generator,
                'extensions': ['.R', '.r']
            },
            'java': {
                'parser': self.java_parser,
                'generator': self.java_generator,
                'extensions': ['.java']
            },
            'go': {
                'parser': self.go_parser,
                'generator': self.go_generator,
                'extensions': ['.go']
            },
            'rust': {
                'parser': self.rust_parser,
                'generator': self.rust_generator,
                'extensions': ['.rs']
            },
            'csharp': {
                'parser': self.csharp_parser,
                'generator': self.csharp_generator,
                'extensions': ['.cs']
            },
            'kotlin': {
                'parser': self.kotlin_parser,
                'generator': self.kotlin_generator,
                'extensions': ['.kt', '.kts']
            },
            'swift': {
                'parser': self.swift_parser,
                'generator': self.swift_generator,
                'extensions': ['.swift']
            },
            'scala': {
                'parser': self.scala_parser,
                'generator': self.scala_generator,
                'extensions': ['.scala', '.sc']
            },
            'c': {
                'parser': self.c_parser,
                'generator': self.c_generator,
                'extensions': ['.c', '.h']
            },
            'sql': {
                'parser': self.sql_parser,
                'generator': self.sql_generator,
                'extensions': ['.sql']
            },
            'bash': {
                'parser': self.bash_parser,
                'generator': self.bash_generator,
                'extensions': ['.sh', '.bash']
            }
        }
    
    def parse_code_to_uir(self, code: str, source_language: str, filename: Optional[str] = None) -> UniversalModule:
        """Parse source code into Universal IR."""
        if source_language not in self.supported_languages:
            raise ValueError(f"Unsupported source language: {source_language}")
        
        parser = self.supported_languages[source_language]['parser']
        
        if filename is None:
            extensions = self.supported_languages[source_language]['extensions']
            filename = f"code{extensions[0]}"
        
        return parser.parse_code(code, filename)
    
    def generate_code_from_uir(self, module: UniversalModule, target_language: str) -> str:
        """Generate target language code from Universal IR."""
        if target_language not in self.supported_languages:
            raise ValueError(f"Unsupported target language: {target_language}")
        
        generator = self.supported_languages[target_language]['generator']
        return generator.generate_module(module)
    
    def translate_code(self, code: str, source_language: str, target_language: str, 
                      filename: Optional[str] = None) -> Tuple[str, UniversalModule]:
        """Translate code from source language to target language."""
        # Parse source code to UIR
        uir_module = self.parse_code_to_uir(code, source_language, filename)
        
        # Generate target code from UIR
        target_code = self.generate_code_from_uir(uir_module, target_language)
        
        return target_code, uir_module
    
    def create_cross_language_project(self, code_files: List[Dict[str, Any]]) -> UniversalProject:
        """Create a Universal Project from multiple language files."""
        project = UniversalProject(name="Cross-Language Project")
        
        for file_info in code_files:
            code = file_info.get('content', '')
            language = file_info.get('language', 'unknown')
            filename = file_info.get('filename', 'unknown')
            
            if language in self.supported_languages:
                try:
                    module = self.parse_code_to_uir(code, language, filename)
                    project.modules.append(module)
                except Exception as e:
                    print(f"Failed to parse {filename}: {e}")
        
        return project
    
    def export_project_to_language(self, project: UniversalProject, target_language: str) -> Dict[str, str]:
        """Export entire project to target language."""
        if target_language not in self.supported_languages:
            raise ValueError(f"Unsupported target language: {target_language}")
        
        generator = self.supported_languages[target_language]['generator']
        return generator.generate_project(project)
    
    def get_function_signatures(self, module: UniversalModule) -> List[Dict[str, Any]]:
        """Extract function signatures for visual representation."""
        signatures = []
        
        for func in module.functions:
            signature = {
                'id': func.id,
                'name': func.name,
                'source_language': func.source_language,
                'parameters': [
                    {
                        'name': param.name,
                        'type': str(param.type_sig),
                        'required': param.required,
                        'default_value': param.default_value
                    }
                    for param in func.parameters
                ],
                'return_type': str(func.return_type),
                'description': func.semantics.purpose if func.semantics else None,
                'is_async': func.implementation_hints.get('is_async', False),
                'complexity': func.implementation_hints.get('complexity', 1)
            }
            signatures.append(signature)
        
        # Include class methods
        for cls in module.classes:
            for method in cls.methods:
                signature = {
                    'id': method.id,
                    'name': f"{cls.name}.{method.name}",
                    'source_language': method.source_language,
                    'class_name': cls.name,
                    'parameters': [
                        {
                            'name': param.name,
                            'type': str(param.type_sig),
                            'required': param.required,
                            'default_value': param.default_value
                        }
                        for param in method.parameters
                    ],
                    'return_type': str(method.return_type),
                    'description': method.semantics.purpose if method.semantics else None,
                    'is_async': method.implementation_hints.get('is_async', False),
                    'is_method': True,
                    'complexity': method.implementation_hints.get('complexity', 1)
                }
                signatures.append(signature)
        
        return signatures
    
    def create_visual_nodes_from_functions(self, module: UniversalModule) -> List[Dict[str, Any]]:
        """Create visual node definitions from Universal IR functions."""
        nodes = []
        
        for func in module.functions:
            # Create input ports from parameters
            inputs = []
            for param in func.parameters:
                inputs.append({
                    'name': param.name,
                    'type': self._map_uir_type_to_visual(param.type_sig),
                    'required': param.required,
                    'default_value': param.default_value
                })
            
            # Create output port from return type
            outputs = []
            if func.return_type.base_type.value != 'void':
                outputs.append({
                    'name': 'result',
                    'type': self._map_uir_type_to_visual(func.return_type)
                })
            
            # Determine function type and visual properties
            func_type, visual_props = self._analyze_function_type(func)
            
            node = {
                'id': f"uir_func_{func.id}",
                'name': self._generate_display_name(func, func_type),
                'type': 'function',
                'category': f"UIR ({func.source_language.title()})",
                'description': func.semantics.purpose if func.semantics else f"{func_type} from {func.source_language}",
                'inputs': inputs,
                'outputs': outputs,
                'icon': visual_props['icon'],
                'metadata': {
                    'uir_function_id': func.id,
                    'raw_name': func.name,
                    'source_language': func.source_language,
                    'function_type': func_type,
                    'is_async': func.implementation_hints.get('is_async', False),
                    'source_code': func.source_code,
                    'dependencies': func.dependencies,
                    'external_calls': func.implementation_hints.get('external_calls', []),
                    'visual_props': visual_props
                }
            }
            nodes.append(node)

            control_flow_nodes = func.implementation_hints.get('control_flow', [])
            for index, control in enumerate(control_flow_nodes):
                control_kind = control.get('kind', 'control_flow')
                control_name = f"[{func.source_language.upper()[:2]}] {control_kind.replace('_', ' ')}"
                control_ports = self._get_control_flow_ports(control_kind)
                display_as = self._derive_control_display(control_kind, control.get('source_code', ''))
                nodes.append({
                    'id': f"uir_cf_{func.id}_{index}",
                    'name': display_as or control_name,
                    'type': control_kind,
                    'category': f"Control Flow ({func.source_language.title()})",
                    'description': f"{control_kind.replace('_', ' ').title()} in {func.name}",
                    'inputs': control_ports['inputs'],
                    'outputs': control_ports['outputs'],
                    'icon': 'git-branch',
                    'metadata': {
                        'uir_control_id': f"{func.id}:{index}",
                        'parent_function_id': func.id,
                        'display_as': display_as,
                        'source_language': func.source_language,
                        'function_type': 'Control Flow',
                        'source_code': control.get('source_code', ''),
                        'order': control.get('lineno', index),
                        'visual_props': {
                            'color': '#0ea5e9',
                            'border': 'dashed'
                        }
                    }
                })
        
        # Add class methods as nodes
        for cls in module.classes:
            for method in cls.methods:
                inputs = []
                for param in method.parameters:
                    inputs.append({
                        'name': param.name,
                        'type': self._map_uir_type_to_visual(param.type_sig),
                        'required': param.required,
                        'default_value': param.default_value
                    })
                
                outputs = []
                if method.return_type.base_type.value != 'void':
                    outputs.append({
                        'name': 'result',
                        'type': self._map_uir_type_to_visual(method.return_type)
                    })
                
                # Determine method type and visual properties
                method_type, visual_props = self._analyze_function_type(method, is_method=True)
                
                node = {
                    'id': f"uir_method_{method.id}",
                    'name': self._generate_display_name(method, method_type, cls.name),
                    'type': 'function',
                    'category': f"UIR ({method.source_language.title()})",
                    'description': method.semantics.purpose if method.semantics else f"{method_type} from {method.source_language}",
                    'inputs': inputs,
                    'outputs': outputs,
                    'icon': visual_props['icon'],
                    'metadata': {
                        'uir_function_id': method.id,
                        'raw_name': f"{cls.name}.{method.name}",
                        'source_language': method.source_language,
                        'class_name': cls.name,
                        'function_type': method_type,
                        'is_method': True,
                        'is_async': method.implementation_hints.get('is_async', False),
                        'source_code': method.source_code,
                        'dependencies': method.dependencies,
                        'external_calls': method.implementation_hints.get('external_calls', []),
                        'visual_props': visual_props
                    }
                }
                nodes.append(node)

                control_flow_nodes = method.implementation_hints.get('control_flow', [])
                for index, control in enumerate(control_flow_nodes):
                    control_kind = control.get('kind', 'control_flow')
                    control_name = f"[{method.source_language.upper()[:2]}] {control_kind.replace('_', ' ')}"
                    control_ports = self._get_control_flow_ports(control_kind)
                    display_as = self._derive_control_display(control_kind, control.get('source_code', ''))
                    nodes.append({
                        'id': f"uir_cf_{method.id}_{index}",
                        'name': display_as or control_name,
                        'type': control_kind,
                        'category': f"Control Flow ({method.source_language.title()})",
                        'description': f"{control_kind.replace('_', ' ').title()} in {cls.name}.{method.name}",
                        'inputs': control_ports['inputs'],
                        'outputs': control_ports['outputs'],
                        'icon': 'git-branch',
                        'metadata': {
                            'uir_control_id': f"{method.id}:{index}",
                            'parent_function_id': method.id,
                            'display_as': display_as,
                            'source_language': method.source_language,
                            'function_type': 'Control Flow',
                            'source_code': control.get('source_code', ''),
                            'order': control.get('lineno', index),
                            'visual_props': {
                                'color': '#0ea5e9',
                                'border': 'dashed'
                            }
                        }
                    })
        
        return nodes

    def _get_control_flow_ports(self, control_kind: str) -> Dict[str, list]:
        if control_kind == 'if_condition':
            return {
                'inputs': [{'name': 'condition', 'type': 'bool', 'required': True}],
                'outputs': [{'name': 'true', 'type': 'object'}, {'name': 'false', 'type': 'object'}]
            }
        if control_kind == 'for_loop':
            return {
                'inputs': [{'name': 'iterable', 'type': 'object', 'required': True}],
                'outputs': [{'name': 'body', 'type': 'object'}]
            }
        if control_kind == 'while_loop':
            return {
                'inputs': [{'name': 'condition', 'type': 'bool', 'required': True}],
                'outputs': [{'name': 'body', 'type': 'object'}]
            }
        if control_kind == 'try_except':
            return {
                'inputs': [{'name': 'input', 'type': 'object', 'required': False}],
                'outputs': [{'name': 'success', 'type': 'object'}, {'name': 'error', 'type': 'object'}]
            }
        if control_kind == 'with':
            return {
                'inputs': [{'name': 'resource', 'type': 'object', 'required': False}],
                'outputs': [{'name': 'body', 'type': 'object'}]
            }
        return {
            'inputs': [{'name': 'input', 'type': 'object', 'required': False}],
            'outputs': [{'name': 'output', 'type': 'object'}]
        }

    def _derive_control_display(self, control_kind: str, source_code: str) -> str:
        if not source_code:
            return ""
        first_line = source_code.strip().splitlines()[0].strip()
        if control_kind == 'if_condition' and first_line.startswith('if '):
            condition = first_line[3:].rstrip(':').strip()
            return f"if {condition}"
        if control_kind == 'while_loop' and first_line.startswith('while '):
            condition = first_line[6:].rstrip(':').strip()
            return f"while {condition}"
        if control_kind == 'for_loop' and first_line.startswith('for '):
            header = first_line[4:].rstrip(':').strip()
            return f"for {header.split(' in ')[0].strip()}" if ' in ' in header else f"for {header}"
        if control_kind == 'with' and first_line.startswith('with '):
            return f"with {first_line[5:].rstrip(':').strip()}"
        if control_kind == 'try_except' and first_line.startswith('try'):
            return "try"
        return ""
    
    def _map_uir_type_to_visual(self, type_sig) -> str:
        """Map UIR type signature to visual editor type."""
        type_mapping = {
            'void': 'void',
            'boolean': 'bool',
            'integer': 'number',
            'float': 'number',
            'string': 'string',
            'array': 'array',
            'object': 'object',
            'function': 'function',
            'any': 'any',
            'unknown': 'any'
        }
        
        return type_mapping.get(type_sig.base_type.value, 'any')
    
    def _analyze_function_type(self, func: UniversalFunction, is_method: bool = False) -> tuple:
        """Analyze function to determine its type and visual properties."""
        func_name = func.name.lower()
        source_code = func.source_code.lower() if func.source_code else ""
        
        # Determine function type based on naming patterns and code analysis
        if is_method:
            if func_name == 'constructor' or func_name == '__init__':
                func_type = "Constructor"
                visual_props = {'icon': 'settings', 'color': '#9C27B0', 'border': 'solid'}
            elif func_name.startswith('get') or func_name.startswith('_get'):
                func_type = "Getter"
                visual_props = {'icon': 'eye', 'color': '#4CAF50', 'border': 'dashed'}
            elif func_name.startswith('set') or func_name.startswith('_set'):
                func_type = "Setter"
                visual_props = {'icon': 'edit', 'color': '#FF9800', 'border': 'dashed'}
            elif func_name.startswith('_'):
                func_type = "Private Method"
                visual_props = {'icon': 'lock', 'color': '#607D8B', 'border': 'dotted'}
            else:
                func_type = "Public Method"
                visual_props = {'icon': 'zap', 'color': '#2196F3', 'border': 'solid'}
        else:
            # Analyze standalone functions
            if func_name.startswith('_'):
                func_type = "Private Function"
                visual_props = {'icon': 'lock', 'color': '#607D8B', 'border': 'dotted'}
            elif any(keyword in func_name for keyword in ['create', 'make', 'build', 'generate']):
                func_type = "Factory Function"
                visual_props = {'icon': 'plus-circle', 'color': '#4CAF50', 'border': 'solid'}
            elif any(keyword in func_name for keyword in ['remove', 'delete', 'destroy', 'clear']):
                func_type = "Destructor Function"
                visual_props = {'icon': 'trash-2', 'color': '#F44336', 'border': 'solid'}
            elif any(keyword in func_name for keyword in ['validate', 'check', 'verify', 'test']):
                func_type = "Validator Function"
                visual_props = {'icon': 'check-circle', 'color': '#FF9800', 'border': 'solid'}
            elif any(keyword in func_name for keyword in ['parse', 'process', 'transform', 'convert']):
                func_type = "Processor Function"
                visual_props = {'icon': 'cpu', 'color': '#9C27B0', 'border': 'solid'}
            elif any(keyword in func_name for keyword in ['handle', 'on', 'callback']):
                func_type = "Event Handler"
                visual_props = {'icon': 'zap', 'color': '#FF5722', 'border': 'solid'}
            elif func.implementation_hints.get('is_async', False):
                func_type = "Async Function"
                visual_props = {'icon': 'clock', 'color': '#3F51B5', 'border': 'double'}
            else:
                func_type = "Function"
                visual_props = {'icon': 'function', 'color': '#2196F3', 'border': 'solid'}
        
        # Add language-specific styling
        language_accents = {
            'javascript': '#F7DF1E',  # Yellow
            'python': '#3776AB',       # Blue
            'typescript': '#3178C6',   # TypeScript Blue
            'ruby': '#CC342D',         # Ruby Red
            'php': '#777BB4',          # PHP Purple
            'lua': '#000080',          # Lua Navy Blue
            'r': '#276DC3',            # R Blue
            'java': '#B07219',         # Java Orange
            'go': '#00ADD8',           # Go Cyan
            'rust': '#DEA584',         # Rust Orange
            'csharp': '#178600',       # C# Green
            'kotlin': '#A97BFF',       # Kotlin Purple
            'swift': '#F05138',        # Swift Orange
            'scala': '#DC322F',        # Scala Red
            'c': '#555555',            # C Gray
            'sql': '#E38C00',          # SQL Orange
            'bash': '#89E051'          # Bash Green
        }
        if func.source_language in language_accents:
            visual_props['language_accent'] = language_accents[func.source_language]
        
        return func_type, visual_props
    
    def _generate_display_name(self, func: UniversalFunction, func_type: str, class_name: Optional[str] = None) -> str:
        """Generate a descriptive display name for the function."""
        base_name = func.name
        
        # Add class prefix for methods
        if class_name:
            base_name = f"{class_name}.{base_name}"
        
        # Add type indicator for special functions
        if func_type in ["Private Function", "Private Method"]:
            # Keep the underscore prefix visible
            pass
        elif func_type == "Constructor":
            base_name = f"new {class_name}" if class_name else f"new {base_name}"
        elif func_type == "Async Function":
            base_name = f"async {base_name}"
        
        # Add language indicator
        lang_indicator = {
            'javascript': 'JS',
            'python': 'PY',
            'typescript': 'TS',
            'ruby': 'RB',
            'php': 'PHP',
            'lua': 'LUA',
            'r': 'R',
            'java': 'JAVA',
            'go': 'GO',
            'rust': 'RS',
            'csharp': 'C#',
            'kotlin': 'KT',
            'swift': 'SWIFT',
            'scala': 'SCALA',
            'c': 'C',
            'sql': 'SQL',
            'bash': 'BASH'
        }.get(func.source_language, func.source_language.upper()[:2])
        
        return f"[{lang_indicator}] {base_name}"
    
    def get_supported_languages(self) -> List[str]:
        """Get list of supported languages."""
        return list(self.supported_languages.keys())
    
    def detect_language_from_filename(self, filename: str) -> Optional[str]:
        """Detect programming language from filename."""
        filename_lower = filename.lower()
        
        for lang, info in self.supported_languages.items():
            for ext in info['extensions']:
                if filename_lower.endswith(ext):
                    return lang
        
        return None
    
    def validate_translation(self, original_code: str, translated_code: str, 
                           source_lang: str, target_lang: str) -> Dict[str, Any]:
        """Validate a translation by round-trip testing."""
        try:
            # Parse original code
            original_uir = self.parse_code_to_uir(original_code, source_lang)
            
            # Parse translated code back to UIR
            translated_uir = self.parse_code_to_uir(translated_code, target_lang)
            
            # Compare function signatures
            original_funcs = {f.name: f for f in original_uir.functions}
            translated_funcs = {f.name: f for f in translated_uir.functions}
            
            validation_results = {
                'valid': True,
                'issues': [],
                'function_count_match': len(original_funcs) == len(translated_funcs),
                'missing_functions': [],
                'extra_functions': [],
                'signature_mismatches': []
            }
            
            # Check for missing functions
            for func_name in original_funcs:
                if func_name not in translated_funcs:
                    validation_results['missing_functions'].append(func_name)
                    validation_results['valid'] = False
            
            # Check for extra functions
            for func_name in translated_funcs:
                if func_name not in original_funcs:
                    validation_results['extra_functions'].append(func_name)
            
            # Check signature compatibility
            for func_name in original_funcs:
                if func_name in translated_funcs:
                    orig_func = original_funcs[func_name]
                    trans_func = translated_funcs[func_name]
                    
                    if len(orig_func.parameters) != len(trans_func.parameters):
                        validation_results['signature_mismatches'].append({
                            'function': func_name,
                            'issue': 'parameter_count_mismatch',
                            'original': len(orig_func.parameters),
                            'translated': len(trans_func.parameters)
                        })
                        validation_results['valid'] = False
            
            return validation_results
            
        except Exception as e:
            return {
                'valid': False,
                'error': str(e),
                'issues': [f"Validation failed: {str(e)}"]
            }


# Global translator instance
translator = UIRTranslator()


def get_translator() -> UIRTranslator:
    """Get the global UIR translator instance."""
    return translator
