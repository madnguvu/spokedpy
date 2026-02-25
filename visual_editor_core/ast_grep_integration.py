"""
AST-Grep Integration for Visual Editor Core.

This module provides integration with ast-grep for:
1. Pattern-based code searching across visual nodes
2. Bulk refactoring operations on matching nodes
3. Visual tagging of nodes that match patterns
"""

import subprocess
import json
import tempfile
import os
import re
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field

# Try to import ast-grep-py Python bindings
try:
    from ast_grep_py import SgRoot
    AST_GREP_PY_AVAILABLE = True
except ImportError:
    AST_GREP_PY_AVAILABLE = False
    SgRoot = None


@dataclass
class AstGrepMatch:
    """Represents a match found by ast-grep."""
    node_id: str
    node_name: str
    node_type: str
    match_text: str
    start_line: int
    end_line: int
    start_col: int
    end_col: int
    source_code: str
    captured_vars: Dict[str, str] = field(default_factory=dict)


@dataclass
class RefactorResult:
    """Result of a refactoring operation."""
    node_id: str
    original_code: str
    refactored_code: str
    success: bool
    error: Optional[str] = None


class AstGrepIntegration:
    """
    Integration with ast-grep for pattern matching and refactoring.
    
    ast-grep uses a pattern syntax similar to the target language:
    - $VAR matches any single AST node and captures it
    - $$$ matches zero or more AST nodes
    - Literal code matches exactly
    
    Examples:
    - `print($MSG)` matches any print call
    - `def $NAME($$$ARGS): $$$BODY` matches any function definition
    - `for $VAR in $ITER: $$$BODY` matches any for loop
    """
    
    def __init__(self):
        self.ast_grep_available = self._check_ast_grep_available()
        self.ast_grep_py_available = AST_GREP_PY_AVAILABLE
        self.matched_nodes: Dict[str, AstGrepMatch] = {}
        self.tag_color = "#fbbf24"  # Amber/yellow for visual tags
        print(f"[AST-GREP] Python library available: {self.ast_grep_py_available}, CLI available: {self.ast_grep_available}")
        
    def _check_ast_grep_available(self) -> bool:
        """Check if ast-grep CLI (sg) is available in the system."""
        try:
            result = subprocess.run(
                ["sg", "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False
    
    def search_pattern(self, pattern: str, nodes: Dict[str, Any], 
                       language: str = "python") -> List[AstGrepMatch]:
        """
        Search for a pattern across all nodes' source code.
        
        Args:
            pattern: ast-grep pattern to search for
            nodes: Dictionary of node_id -> node data with 'source_code' or 'code' field
            language: Programming language (default: python)
            
        Returns:
            List of AstGrepMatch objects for matching nodes
        """
        matches = []
        self.matched_nodes.clear()
        
        # Debug: count nodes with source code
        nodes_with_code = 0
        nodes_checked = 0
        
        for node_id, node_data in nodes.items():
            nodes_checked += 1
            # Get source code from node
            source_code = self._get_node_source(node_data)
            if not source_code:
                # Debug first few nodes without source
                if nodes_checked <= 3:
                    print(f"[AST-GREP DEBUG] Node {node_id} has no source_code. Keys: {list(node_data.keys())}")
                    if 'parameters' in node_data:
                        print(f"[AST-GREP DEBUG]   parameters keys: {list(node_data['parameters'].keys())}")
                continue
            
            nodes_with_code += 1
            
            # Debug: show first node's source preview
            if nodes_with_code == 1:
                print(f"[AST-GREP DEBUG] First node with code: {node_id}")
                print(f"[AST-GREP DEBUG] Source preview: {source_code[:150]}...")
            
            # Search this node's source code
            node_matches = self._search_in_code(pattern, source_code, language)
            
            # Debug: show matches for first few nodes
            if nodes_with_code <= 3 and node_matches:
                print(f"[AST-GREP DEBUG] Node {node_id} has {len(node_matches)} matches")
            
            for match in node_matches:
                ast_match = AstGrepMatch(
                    node_id=node_id,
                    node_name=node_data.get('name', node_data.get('id', node_id)),
                    node_type=node_data.get('type', 'unknown'),
                    match_text=match.get('text', ''),
                    start_line=match.get('start', {}).get('line', 0),
                    end_line=match.get('end', {}).get('line', 0),
                    start_col=match.get('start', {}).get('column', 0),
                    end_col=match.get('end', {}).get('column', 0),
                    source_code=source_code,
                    captured_vars=match.get('metaVariables', {})
                )
                matches.append(ast_match)
                self.matched_nodes[node_id] = ast_match
        
        print(f"[AST-GREP DEBUG] Checked {nodes_checked} nodes, {nodes_with_code} had source code, found {len(matches)} total matches")
        return matches
    
    def _get_node_source(self, node_data: Dict[str, Any]) -> Optional[str]:
        """Extract source code from a node's data."""
        # Try different possible field names for source code
        for field in ['source_code', 'code', 'body', 'content']:
            if field in node_data:
                return node_data[field]
        
        # Check in parameters
        params = node_data.get('parameters', {})
        for field in ['source_code', 'code', 'body', 'content', 'expression']:
            if field in params:
                return params[field]
        
        # Check in metadata
        metadata = node_data.get('metadata', {})
        if 'source_code' in metadata:
            return metadata['source_code']
        
        return None
    
    def _search_in_code(self, pattern: str, code: str, 
                        language: str = "python") -> List[Dict[str, Any]]:
        """
        Search for a pattern in a code string using ast-grep.
        
        Prefers Python library, falls back to CLI, then regex.
        """
        print(f"[DEBUG _search_in_code] ast_grep_py_available={self.ast_grep_py_available}, cli_available={self.ast_grep_available}")
        print(f"[DEBUG _search_in_code] pattern='{pattern}', code_len={len(code)}")
        
        # Prefer Python library (ast-grep-py)
        if self.ast_grep_py_available:
            result = self._search_with_ast_grep_py(pattern, code, language)
            print(f"[DEBUG _search_in_code] ast-grep-py returned {len(result)} matches")
            return result
        elif self.ast_grep_available:
            result = self._search_with_ast_grep(pattern, code, language)
            print(f"[DEBUG _search_in_code] ast-grep CLI returned {len(result)} matches")
            return result
        else:
            result = self._search_with_regex_fallback(pattern, code)
            print(f"[DEBUG _search_in_code] regex fallback returned {len(result)} matches")
            return result
    
    def _search_with_ast_grep_py(self, pattern: str, code: str,
                                  language: str) -> List[Dict[str, Any]]:
        """Use ast-grep-py Python library to search for pattern."""
        matches = []
        
        try:
            # If SgRoot is not available at runtime for any reason, fall back to regex
            if SgRoot is None:
                print("[DEBUG ast-grep-py] SgRoot bindings not available, falling back to regex")
                return self._search_with_regex_fallback(pattern, code)
            
            # Create SgRoot from source code
            sg = SgRoot(code, language)
            root = sg.root()
            
            # Determine search strategy based on pattern content:
            # - If pattern contains $ placeholders, it's an ast-grep pattern
            # - Otherwise, use regex for text matching
            has_ast_grep_placeholders = '$' in pattern and any(c.isupper() for c in pattern.split('$')[1:][0][:1] if pattern.split('$')[1:])
            
            print(f"[DEBUG ast-grep-py] Pattern: '{pattern}', has_placeholders: {has_ast_grep_placeholders}")
            
            try:
                if has_ast_grep_placeholders:
                    # Use ast-grep pattern syntax (e.g., "def $NAME($$$ARGS): $$$BODY")
                    print(f"[DEBUG ast-grep-py] Using pattern-based search")
                    nodes = root.find_all(pattern=pattern)
                else:
                    # Use regex for simple text search
                    print(f"[DEBUG ast-grep-py] Using regex-based search")
                    nodes = root.find_all(regex=pattern)
            except Exception as search_err:
                # If pattern search fails, fall back to regex
                print(f"[DEBUG ast-grep-py] Pattern search failed: {search_err}, trying regex")
                nodes = root.find_all(regex=pattern)
            
            for node in nodes:
                match_range = node.range()
                match_text = node.text()
                matches.append({
                    'text': match_text,
                    'start': {
                        'line': match_range.start.line,
                        'column': match_range.start.column
                    },
                    'end': {
                        'line': match_range.end.line,
                        'column': match_range.end.column
                    },
                    'metaVariables': {}
                })
                preview = match_text[:50].replace('\n', '\\n')
                print(f"[DEBUG ast-grep-py] Found match: '{preview}...'")
                
        except Exception as e:
            print(f"[DEBUG ast-grep-py] Error: {e}")
            # Fall back to regex on error
            return self._search_with_regex_fallback(pattern, code)
        
        return matches
    
    def _search_with_ast_grep(self, pattern: str, code: str, 
                               language: str) -> List[Dict[str, Any]]:
        """Use ast-grep CLI to search for pattern."""
        matches = []
        
        # Create temporary file with code
        with tempfile.NamedTemporaryFile(mode='w', suffix=f'.{self._get_extension(language)}',
                                          delete=False, encoding='utf-8') as f:
            f.write(code)
            temp_path = f.name
        
        try:
            # Run ast-grep
            result = subprocess.run(
                ["sg", "--pattern", pattern, "--json", temp_path],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0 and result.stdout.strip():
                try:
                    matches = json.loads(result.stdout)
                except json.JSONDecodeError:
                    # Try parsing line by line (NDJSON format)
                    for line in result.stdout.strip().split('\n'):
                        if line.strip():
                            try:
                                matches.append(json.loads(line))
                            except json.JSONDecodeError:
                                pass
        except subprocess.TimeoutExpired:
            pass
        finally:
            os.unlink(temp_path)
        
        return matches
    
    def _search_with_regex_fallback(self, pattern: str, code: str) -> List[Dict[str, Any]]:
        """
        Fallback regex-based search when ast-grep is not available.
        
        Supports two modes:
        1. AST-grep style patterns with $VAR and $$$ placeholders
        2. Literal text search (when pattern contains no $ placeholders)
        """
        matches = []
        
        # Check if this is an ast-grep style pattern or literal text
        has_placeholders = '$' in pattern and re.search(r'\$[A-Z_]', pattern)
        print(f"[DEBUG regex_fallback] pattern='{pattern}', has_placeholders={has_placeholders}")
        
        if has_placeholders:
            # Convert ast-grep pattern to regex
            try:
                regex_pattern = self._pattern_to_regex(pattern)
                print(f"[DEBUG regex_fallback] converted to regex: '{regex_pattern}'")
            except Exception as e:
                print(f"Pattern conversion error: {e}")
                return []
        else:
            # Literal text search - escape everything for exact match
            regex_pattern = re.escape(pattern)
            # Allow flexible whitespace
            regex_pattern = re.sub(r'\\ ', r'\\s*', regex_pattern)
            print(f"[DEBUG regex_fallback] literal search regex: '{regex_pattern}'")
        
        try:
            print(f"[DEBUG regex_fallback] Searching in code (first 100 chars): '{code[:100]}'")
            for match in re.finditer(regex_pattern, code, re.MULTILINE | re.DOTALL):
                # Calculate line/column from match position
                start_pos = match.start()
                end_pos = match.end()
                
                lines_before_start = code[:start_pos].count('\n')
                lines_before_end = code[:end_pos].count('\n')
                
                last_newline_before_start = code.rfind('\n', 0, start_pos)
                last_newline_before_end = code.rfind('\n', 0, end_pos)
                
                start_col = start_pos - last_newline_before_start - 1 if last_newline_before_start >= 0 else start_pos
                end_col = end_pos - last_newline_before_end - 1 if last_newline_before_end >= 0 else end_pos
                
                # Get captured groups as dict, handling potential errors
                try:
                    captured = match.groupdict()
                except Exception:
                    captured = {}
                
                matches.append({
                    'text': match.group(0),
                    'start': {'line': lines_before_start + 1, 'column': max(0, start_col)},
                    'end': {'line': lines_before_end + 1, 'column': max(0, end_col)},
                    'metaVariables': captured
                })
        except re.error as e:
            # If regex is invalid, return no matches with debug info
            print(f"Regex search error: {e}, pattern was: {regex_pattern}")
            return []
        
        return matches
    
    def _pattern_to_regex(self, pattern: str) -> str:
        """Convert an ast-grep-like pattern to regex."""
        # Use unique markers that won't appear in code
        MULTI_MARKER = "___MULTIVAR___"
        VAR_PREFIX = "___VAR_"
        VAR_SUFFIX = "___"
        
        result = pattern
        
        # First, handle $$$ patterns (multi-match with optional name like $$$ARGS)
        # Replace $$$NAME with marker, capturing the name
        multi_var_names = re.findall(r'\$\$\$([A-Z_][A-Z0-9_]*)?', result)
        for i, var_name in enumerate(multi_var_names):
            if var_name:
                result = result.replace(f'$$${var_name}', f'{MULTI_MARKER}{i}_{var_name}___')
            else:
                result = result.replace('$$$', f'{MULTI_MARKER}{i}___', 1)
        
        # Replace $VAR patterns with markers, capturing the variable name
        var_names = re.findall(r'\$([A-Z_][A-Z0-9_]*)', result)
        for var_name in var_names:
            result = result.replace(f'${var_name}', f'{VAR_PREFIX}{var_name}{VAR_SUFFIX}')
        
        # Escape regex special chars
        for char in r'\.^$*+?{}[]|()':
            result = result.replace(char, '\\' + char)
        
        # Restore multi-var placeholders as regex patterns (match any content)
        for i, var_name in enumerate(multi_var_names):
            if var_name:
                marker = f'{MULTI_MARKER}{i}_{var_name}___'
                result = result.replace(marker.replace('(', '\\(').replace(')', '\\)'), r'.*?')
            else:
                marker = f'{MULTI_MARKER}{i}___'
                result = result.replace(marker.replace('(', '\\(').replace(')', '\\)'), r'.*?')
        
        # Restore single var placeholders as regex patterns
        for var_name in var_names:
            marker = f'{VAR_PREFIX}{var_name}{VAR_SUFFIX}'
            # Use a simpler capture pattern that's more flexible
            result = result.replace(marker, r'(?P<' + var_name + r'>[^\s\(\)\[\]\{\}:,]+)')
        
        # Handle whitespace flexibility
        result = re.sub(r'\s+', r'\\s*', result)
        
        return result
    
    def _get_extension(self, language: str) -> str:
        """Get file extension for a language."""
        extensions = {
            'python': 'py',
            'javascript': 'js',
            'typescript': 'ts',
            'rust': 'rs',
            'go': 'go',
            'c': 'c',
            'cpp': 'cpp',
            'java': 'java',
        }
        return extensions.get(language.lower(), 'txt')
    
    def refactor_pattern(self, search_pattern: str, replace_pattern: str,
                         nodes: Dict[str, Any], language: str = "python",
                         node_ids: Optional[List[str]] = None) -> List[RefactorResult]:
        """
        Apply a refactoring transformation to matching nodes.
        
        Args:
            search_pattern: Pattern to search for (ast-grep syntax)
            replace_pattern: Replacement pattern (can use $VAR references)
            nodes: Dictionary of node_id -> node data
            language: Programming language
            node_ids: Optional list of specific node IDs to refactor (None = all)
            
        Returns:
            List of RefactorResult objects
        """
        results = []
        
        # Filter nodes if specific IDs provided
        target_nodes = nodes
        if node_ids:
            target_nodes = {nid: nodes[nid] for nid in node_ids if nid in nodes}
        
        for node_id, node_data in target_nodes.items():
            source_code = self._get_node_source(node_data)
            if not source_code:
                continue
            
            try:
                refactored = self._apply_refactor(
                    search_pattern, replace_pattern, source_code, language
                )
                
                if refactored != source_code:
                    results.append(RefactorResult(
                        node_id=node_id,
                        original_code=source_code,
                        refactored_code=refactored,
                        success=True
                    ))
            except Exception as e:
                results.append(RefactorResult(
                    node_id=node_id,
                    original_code=source_code,
                    refactored_code=source_code,
                    success=False,
                    error=str(e)
                ))
        
        return results
    
    def _apply_refactor(self, search_pattern: str, replace_pattern: str,
                        code: str, language: str) -> str:
        """Apply refactoring transformation to code."""
        if self.ast_grep_available:
            return self._refactor_with_ast_grep(search_pattern, replace_pattern, code, language)
        else:
            return self._refactor_with_regex_fallback(search_pattern, replace_pattern, code)
    
    def _refactor_with_ast_grep(self, search_pattern: str, replace_pattern: str,
                                 code: str, language: str) -> str:
        """Use ast-grep to apply refactoring."""
        # Create temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix=f'.{self._get_extension(language)}',
                                          delete=False, encoding='utf-8') as f:
            f.write(code)
            temp_path = f.name
        
        try:
            # Run ast-grep with rewrite
            result = subprocess.run(
                ["sg", "--pattern", search_pattern, "--rewrite", replace_pattern, temp_path],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            # Read the modified file
            with open(temp_path, 'r', encoding='utf-8') as f:
                return f.read()
        except subprocess.TimeoutExpired:
            return code
        finally:
            os.unlink(temp_path)
    
    def _refactor_with_regex_fallback(self, search_pattern: str, 
                                       replace_pattern: str, code: str) -> str:
        """Fallback regex-based refactoring."""
        regex_pattern = self._pattern_to_regex(search_pattern)
        
        # Convert replace pattern - $VAR -> \g<VAR>
        regex_replace = re.sub(r'\$([A-Z_][A-Z0-9_]*)', r'\\g<\1>', replace_pattern)
        
        try:
            return re.sub(regex_pattern, regex_replace, code)
        except re.error:
            return code
    
    def get_matched_node_ids(self) -> List[str]:
        """Get list of currently matched node IDs for visual tagging."""
        return list(self.matched_nodes.keys())
    
    def get_tag_style(self) -> Dict[str, Any]:
        """Get the visual style for tagged/matched nodes."""
        return {
            'stroke': self.tag_color,
            'strokeWidth': 3,
            'strokeDasharray': '5,3',
            'filter': f'drop-shadow(0 0 8px {self.tag_color})',
            'animation': 'pulse 1.5s ease-in-out infinite'
        }
    
    def clear_matches(self):
        """Clear all current matches."""
        self.matched_nodes.clear()
    
    def get_common_patterns(self) -> List[Dict[str, str]]:
        """Get list of common useful patterns for Python."""
        return [
            {
                'name': 'Print Statements',
                'pattern': 'print($MSG)',
                'description': 'Find all print() calls'
            },
            {
                'name': 'Function Definitions',
                'pattern': 'def $NAME($$$ARGS): $$$BODY',
                'description': 'Find all function definitions'
            },
            {
                'name': 'Class Definitions',
                'pattern': 'class $NAME: $$$BODY',
                'description': 'Find all class definitions'
            },
            {
                'name': 'For Loops',
                'pattern': 'for $VAR in $ITER: $$$BODY',
                'description': 'Find all for loops'
            },
            {
                'name': 'List Comprehensions',
                'pattern': '[$EXPR for $VAR in $ITER]',
                'description': 'Find list comprehensions'
            },
            {
                'name': 'Try/Except Blocks',
                'pattern': 'try: $$$BODY except $$$HANDLER',
                'description': 'Find try/except blocks'
            },
            {
                'name': 'Import Statements',
                'pattern': 'import $MODULE',
                'description': 'Find import statements'
            },
            {
                'name': 'From Imports',
                'pattern': 'from $MODULE import $$$NAMES',
                'description': 'Find from...import statements'
            },
            {
                'name': 'Async Functions',
                'pattern': 'async def $NAME($$$ARGS): $$$BODY',
                'description': 'Find async function definitions'
            },
            {
                'name': 'Await Expressions',
                'pattern': 'await $EXPR',
                'description': 'Find await expressions'
            },
            {
                'name': 'With Statements',
                'pattern': 'with $CONTEXT as $VAR: $$$BODY',
                'description': 'Find context manager usage'
            },
            {
                'name': 'Lambda Functions',
                'pattern': 'lambda $$$ARGS: $EXPR',
                'description': 'Find lambda expressions'
            },
            {
                'name': 'Dict Literals',
                'pattern': '{$$$ITEMS}',
                'description': 'Find dictionary literals'
            },
            {
                'name': 'Assert Statements',
                'pattern': 'assert $CONDITION',
                'description': 'Find assert statements'
            },
            {
                'name': 'Raise Statements',
                'pattern': 'raise $EXCEPTION',
                'description': 'Find raise statements'
            }
        ]
    
    def get_common_refactorings(self) -> List[Dict[str, str]]:
        """Get list of common refactoring patterns for Python."""
        return [
            {
                'name': 'Print to Logging',
                'search': 'print($MSG)',
                'replace': 'logging.info($MSG)',
                'description': 'Convert print() calls to logging.info()'
            },
            {
                'name': 'String Format to F-String',
                'search': '"{}".format($VAL)',
                'replace': 'f"{$VAL}"',
                'description': 'Convert .format() to f-strings'
            },
            {
                'name': 'Add Type Hint to Function',
                'search': 'def $NAME($$$ARGS):',
                'replace': 'def $NAME($$$ARGS) -> None:',
                'description': 'Add return type hint to functions'
            },
            {
                'name': 'List to Generator',
                'search': '[$EXPR for $VAR in $ITER]',
                'replace': '($EXPR for $VAR in $ITER)',
                'description': 'Convert list comprehension to generator'
            },
            {
                'name': 'Open with Context Manager',
                'search': '$FILE = open($PATH)',
                'replace': 'with open($PATH) as $FILE:',
                'description': 'Wrap file open in context manager'
            },
            {
                'name': 'Assert to Raise',
                'search': 'assert $COND, $MSG',
                'replace': 'if not $COND: raise AssertionError($MSG)',
                'description': 'Convert assert to explicit raise'
            }
        ]


# Singleton instance
_ast_grep = None

def get_ast_grep_integration() -> AstGrepIntegration:
    """Get the global ast-grep integration instance."""
    global _ast_grep
    if _ast_grep is None:
        _ast_grep = AstGrepIntegration()
    return _ast_grep
