"""
Cross-language import translator for VPyD.

When code is imported from one language (e.g. Python) and exported to another
(e.g. JavaScript), the raw import statements in ``module.imports`` are still
in the *source* language syntax.  Each target-language generator calls
``translate_import(stmt, target)`` to convert (or comment-out) those lines
before emitting them.
"""

import re
from typing import Optional

# ── Regex patterns for common Python import forms ──────────────────────
_PY_FROM_IMPORT = re.compile(
    r'^from\s+([\w.]+)\s+import\s+(.+)$'
)
_PY_IMPORT = re.compile(
    r'^import\s+([\w.]+)(?:\s+as\s+(\w+))?$'
)

# Languages whose imports have a *different* syntax from Python
_COMMENT_STYLE = {
    'javascript': '//',
    'typescript': '//',
    'java': '//',
    'go': '//',
    'rust': '//',
    'c': '//',
    'csharp': '//',
    'kotlin': '//',
    'swift': '//',
    'scala': '//',
    'lua': '--',
    'r': '#',
    'ruby': '#',
    'php': '//',
    'bash': '#',
    'sql': '--',
}


def _is_python_import(stmt: str) -> bool:
    """Return True if *stmt* looks like a raw Python import statement."""
    s = stmt.strip()
    return bool(_PY_FROM_IMPORT.match(s) or _PY_IMPORT.match(s))


def _is_native_import(stmt: str, target: str) -> bool:
    """Return True if *stmt* is already in the target language's syntax."""
    s = stmt.strip()
    tl = target.lower()

    # If it's a Python import, it's NEVER native for a non-Python target
    if _is_python_import(s):
        if tl not in ('python', 'py'):
            return False

    if tl in ('javascript', 'js'):
        return s.startswith(('const ', 'let ', 'var ', 'require(', 'require ')) or \
               (s.startswith('import ') and ('from ' in s or '{' in s or "'" in s or '"' in s))
    if tl in ('typescript', 'ts'):
        return (s.startswith('export ') or 'require(' in s) or \
               (s.startswith('import ') and ('from ' in s or '{' in s or "'" in s or '"' in s))
    if tl == 'java':
        return s.startswith('import ') and ('.' in s) and not _PY_IMPORT.match(s)
    if tl == 'go':
        return s.startswith('import ') and ('"' in s or '(' in s)
    if tl == 'rust':
        return s.startswith(('use ', 'extern '))
    if tl == 'c':
        return s.startswith('#include')
    if tl in ('csharp', 'cs'):
        return s.startswith('using ')
    if tl == 'kotlin':
        return s.startswith('import ') and '.' in s and not _PY_IMPORT.match(s)
    if tl == 'swift':
        # Swift: `import Foundation` — but Python `import os` also looks like this.
        # We already filtered Python imports above, so if we reach here it's native.
        return s.startswith('import ')
    if tl == 'scala':
        return s.startswith('import ') and '.' in s and not _PY_IMPORT.match(s)
    if tl == 'ruby':
        return s.startswith(('require ', "require '", 'require "', 'require_relative '))
    if tl == 'php':
        return s.startswith(('use ', 'require ', 'include '))
    if tl == 'lua':
        return ('require(' in s) or ('require "' in s) or ("require '" in s)
    if tl == 'r':
        return s.startswith(('library(', 'require(', 'source('))
    if tl == 'bash':
        return s.startswith(('source ', '. '))
    if tl == 'sql':
        return s.upper().startswith(('CREATE ', 'ALTER ', 'SET ', '--'))
    return False


def _comment_out(stmt: str, target: str) -> str:
    """Wrap a foreign import as a comment in the target language."""
    prefix = _COMMENT_STYLE.get(target.lower(), '//')
    return f"{prefix} Python dep: {stmt.strip()}"


# ── Per-language translators ───────────────────────────────────────────

def _to_javascript(stmt: str) -> str:
    m = _PY_FROM_IMPORT.match(stmt.strip())
    if m:
        module, names = m.group(1), m.group(2)
        parts = [n.strip() for n in names.split(',')]
        # "from X import *" → const X = require('X');
        if parts == ['*']:
            return f"const {module.split('.')[-1]} = require('{module}');"
        return f"const {{ {', '.join(parts)} }} = require('{module}');"
    m = _PY_IMPORT.match(stmt.strip())
    if m:
        module, alias = m.group(1), m.group(2)
        name = alias or module.split('.')[-1]
        return f"const {name} = require('{module}');"
    return _comment_out(stmt, 'javascript')


def _to_typescript(stmt: str) -> str:
    m = _PY_FROM_IMPORT.match(stmt.strip())
    if m:
        module, names = m.group(1), m.group(2)
        parts = [n.strip() for n in names.split(',')]
        if parts == ['*']:
            return f"import * as {module.split('.')[-1]} from '{module}';"
        return f"import {{ {', '.join(parts)} }} from '{module}';"
    m = _PY_IMPORT.match(stmt.strip())
    if m:
        module, alias = m.group(1), m.group(2)
        name = alias or module.split('.')[-1]
        return f"import * as {name} from '{module}';"
    return _comment_out(stmt, 'typescript')


def _to_java(stmt: str) -> str:
    m = _PY_FROM_IMPORT.match(stmt.strip())
    if m:
        module, names = m.group(1), m.group(2)
        parts = [n.strip() for n in names.split(',')]
        lines = []
        for p in parts:
            if p == '*':
                lines.append(f"import {module}.*;")
            else:
                lines.append(f"import {module}.{p};")
        return '\n'.join(lines)
    m = _PY_IMPORT.match(stmt.strip())
    if m:
        module = m.group(1)
        return f"import {module}.*;"
    return _comment_out(stmt, 'java')


def _to_go(stmt: str) -> str:
    # Go has no direct mapping for Python modules; comment it
    return _comment_out(stmt, 'go')


def _to_rust(stmt: str) -> str:
    m = _PY_FROM_IMPORT.match(stmt.strip())
    if m:
        module, names = m.group(1), m.group(2)
        parts = [n.strip() for n in names.split(',')]
        mod_path = module.replace('.', '::')
        if parts == ['*']:
            return f"use {mod_path}::*;"
        if len(parts) == 1:
            return f"use {mod_path}::{parts[0]};"
        return f"use {mod_path}::{{{', '.join(parts)}}};"
    m = _PY_IMPORT.match(stmt.strip())
    if m:
        module = m.group(1)
        return f"use {module.replace('.', '::')};"
    return _comment_out(stmt, 'rust')


def _to_c(stmt: str) -> str:
    # C has no module system; comment it
    return _comment_out(stmt, 'c')


def _to_csharp(stmt: str) -> str:
    m = _PY_FROM_IMPORT.match(stmt.strip())
    if m:
        module = m.group(1)
        return f"using {module.replace('.', '.')};"
    m = _PY_IMPORT.match(stmt.strip())
    if m:
        module = m.group(1)
        return f"using {module};"
    return _comment_out(stmt, 'csharp')


def _to_kotlin(stmt: str) -> str:
    m = _PY_FROM_IMPORT.match(stmt.strip())
    if m:
        module, names = m.group(1), m.group(2)
        parts = [n.strip() for n in names.split(',')]
        lines = []
        for p in parts:
            if p == '*':
                lines.append(f"import {module}.*")
            else:
                lines.append(f"import {module}.{p}")
        return '\n'.join(lines)
    m = _PY_IMPORT.match(stmt.strip())
    if m:
        module = m.group(1)
        return f"import {module}.*"
    return _comment_out(stmt, 'kotlin')


def _to_swift(stmt: str) -> str:
    m = _PY_FROM_IMPORT.match(stmt.strip())
    if m:
        module = m.group(1)
        top = module.split('.')[0]
        return f"import {top}"
    m = _PY_IMPORT.match(stmt.strip())
    if m:
        module = m.group(1)
        top = module.split('.')[0]
        return f"import {top}"
    return _comment_out(stmt, 'swift')


def _to_scala(stmt: str) -> str:
    m = _PY_FROM_IMPORT.match(stmt.strip())
    if m:
        module, names = m.group(1), m.group(2)
        parts = [n.strip() for n in names.split(',')]
        mod_path = module.replace('.', '.')
        if parts == ['*']:
            return f"import {mod_path}._"
        if len(parts) == 1:
            return f"import {mod_path}.{parts[0]}"
        return f"import {mod_path}.{{{', '.join(parts)}}}"
    m = _PY_IMPORT.match(stmt.strip())
    if m:
        module = m.group(1)
        return f"import {module}._"
    return _comment_out(stmt, 'scala')


def _to_ruby(stmt: str) -> str:
    m = _PY_FROM_IMPORT.match(stmt.strip())
    if m:
        module = m.group(1)
        return f"require '{module}'"
    m = _PY_IMPORT.match(stmt.strip())
    if m:
        module = m.group(1)
        return f"require '{module}'"
    return _comment_out(stmt, 'ruby')


def _to_php(stmt: str) -> str:
    m = _PY_FROM_IMPORT.match(stmt.strip())
    if m:
        module, names = m.group(1), m.group(2)
        ns = module.replace('.', '\\')
        parts = [n.strip() for n in names.split(',')]
        lines = []
        for p in parts:
            if p == '*':
                lines.append(f"use {ns};")
            else:
                lines.append(f"use {ns}\\{p};")
        return '\n'.join(lines)
    m = _PY_IMPORT.match(stmt.strip())
    if m:
        module = m.group(1)
        return f"use {module.replace('.', chr(92))};"
    return _comment_out(stmt, 'php')


def _to_lua(stmt: str) -> str:
    m = _PY_FROM_IMPORT.match(stmt.strip())
    if m:
        module = m.group(1)
        alias = module.split('.')[-1]
        return f'local {alias} = require("{module}")'
    m = _PY_IMPORT.match(stmt.strip())
    if m:
        module, alias = m.group(1), m.group(2)
        name = alias or module.split('.')[-1]
        return f'local {name} = require("{module}")'
    return _comment_out(stmt, 'lua')


def _to_r(stmt: str) -> str:
    m = _PY_FROM_IMPORT.match(stmt.strip())
    if m:
        module = m.group(1)
        return f"library({module.split('.')[0]})"
    m = _PY_IMPORT.match(stmt.strip())
    if m:
        module = m.group(1)
        return f"library({module.split('.')[0]})"
    return _comment_out(stmt, 'r')


def _to_bash(stmt: str) -> str:
    return _comment_out(stmt, 'bash')


def _to_sql(stmt: str) -> str:
    return _comment_out(stmt, 'sql')


# ── Dispatch table ─────────────────────────────────────────────────────
_TRANSLATORS = {
    'javascript': _to_javascript,
    'js':         _to_javascript,
    'typescript': _to_typescript,
    'ts':         _to_typescript,
    'java':       _to_java,
    'go':         _to_go,
    'rust':       _to_rust,
    'c':          _to_c,
    'csharp':     _to_csharp,
    'cs':         _to_csharp,
    'kotlin':     _to_kotlin,
    'swift':      _to_swift,
    'scala':      _to_scala,
    'ruby':       _to_ruby,
    'php':        _to_php,
    'lua':        _to_lua,
    'r':          _to_r,
    'bash':       _to_bash,
    'sql':        _to_sql,
}


def translate_import(stmt: str, target_language: str) -> str:
    """
    Translate a single import statement to *target_language* syntax.

    * If *stmt* is already in the target language's native syntax → return
      it unchanged.
    * If *stmt* is a Python import → convert to the target-language
      equivalent (or comment it out when no direct mapping exists).
    * Otherwise → return unchanged (assume it's already correct).
    """
    s = stmt.strip()
    if not s:
        return s

    tl = target_language.lower()

    # Already in the target language's native import syntax
    if _is_native_import(s, tl):
        return s

    # Python import → translate to target
    if _is_python_import(s):
        translator = _TRANSLATORS.get(tl)
        if translator:
            return translator(s)
        # Unknown target — comment it out generically
        return f"// Python dep: {s}"

    # Not Python, not native — pass through unchanged
    return s


def translate_imports(imports: list, target_language: str) -> list:
    """Translate a list of import statements, deduplicating the results."""
    seen = set()
    result = []
    for imp in imports:
        translated = translate_import(imp, target_language)
        # A translator may return multi-line (e.g. Java multiple imports)
        for line in translated.split('\n'):
            line = line.rstrip()
            if line and line not in seen:
                seen.add(line)
                result.append(line)
    return result
