"""
Test: All generator and parser files compile without syntax errors.

This is a basic sanity check that prevents broken files from being deployed.
"""

import py_compile
import os
import pytest
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ---------------------------------------------------------------------------
# Every generator
# ---------------------------------------------------------------------------

GENERATOR_FILES = [
    "visual_editor_core/python_generator.py",
    "visual_editor_core/js_generator.py",
    "visual_editor_core/typescript_generator.py",
    "visual_editor_core/java_generator.py",
    "visual_editor_core/go_generator.py",
    "visual_editor_core/rust_generator.py",
    "visual_editor_core/c_generator.py",
    "visual_editor_core/csharp_generator.py",
    "visual_editor_core/kotlin_generator.py",
    "visual_editor_core/swift_generator.py",
    "visual_editor_core/scala_generator.py",
    "visual_editor_core/ruby_generator.py",
    "visual_editor_core/php_generator.py",
    "visual_editor_core/lua_generator.py",
    "visual_editor_core/r_generator.py",
    "visual_editor_core/bash_generator.py",
    "visual_editor_core/sql_generator.py",
]

PARSER_FILES = [
    "visual_editor_core/python_parser.py",
    "visual_editor_core/js_parser.py",
    "visual_editor_core/typescript_parser.py",
    "visual_editor_core/java_parser.py",
    "visual_editor_core/go_parser.py",
    "visual_editor_core/rust_parser.py",
    "visual_editor_core/c_parser.py",
    "visual_editor_core/csharp_parser.py",
    "visual_editor_core/kotlin_parser.py",
    "visual_editor_core/swift_parser.py",
    "visual_editor_core/scala_parser.py",
    "visual_editor_core/ruby_parser.py",
    "visual_editor_core/php_parser.py",
    "visual_editor_core/lua_parser.py",
    "visual_editor_core/r_parser.py",
    "visual_editor_core/bash_parser.py",
    "visual_editor_core/sql_parser.py",
]

CORE_FILES = [
    "web_interface/app.py",
    "visual_editor_core/session_ledger.py",
    "visual_editor_core/universal_ir.py",
    "visual_editor_core/uir_translator.py",
]


ALL_FILES = GENERATOR_FILES + PARSER_FILES + CORE_FILES


class TestCompileCheck:
    """Every source file must compile without syntax errors."""

    @pytest.mark.parametrize("rel_path", ALL_FILES, ids=[os.path.basename(f) for f in ALL_FILES])
    def test_file_compiles(self, rel_path):
        full_path = os.path.join(ROOT, rel_path)
        assert os.path.exists(full_path), f"File not found: {full_path}"
        try:
            py_compile.compile(full_path, doraise=True)
        except py_compile.PyCompileError as e:
            pytest.fail(f"Compile error in {rel_path}: {e}")
