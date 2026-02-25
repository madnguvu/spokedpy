"""
Test: All 16 language parsers correctly capture imports into module.imports.

Verifies the parser → module.imports pipeline for every supported language.
Each parser should populate self.current_module.imports with the import/require/use
statements found in the source code.
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _parse(parser_cls, source: str, filename: str = "test_file"):
    """Instantiate a parser, parse source, return the module."""
    parser = parser_cls()
    module = parser.parse_code(source, filename)
    return module


# ---------------------------------------------------------------------------
# 1. JavaScript
# ---------------------------------------------------------------------------

class TestJavaScriptParserImports:
    """JavaScript parser should capture require() and import statements."""

    def _get_parser(self):
        from visual_editor_core.js_parser import JavaScriptParser
        return JavaScriptParser

    def test_require_statement(self):
        source = "const fs = require('fs');\nfunction hello() {}"
        module = _parse(self._get_parser(), source)
        assert any("require" in imp for imp in module.imports), \
            f"Expected require() in imports, got: {module.imports}"

    def test_import_statement(self):
        source = "import path from 'path';\nfunction hello() {}"
        module = _parse(self._get_parser(), source)
        assert any("import" in imp for imp in module.imports), \
            f"Expected import in imports, got: {module.imports}"

    def test_no_imports(self):
        source = "function hello() { return 42; }"
        module = _parse(self._get_parser(), source)
        # Should still parse without error; imports may be empty
        assert isinstance(module.imports, list)


# ---------------------------------------------------------------------------
# 2. TypeScript
# ---------------------------------------------------------------------------

class TestTypeScriptParserImports:
    """TypeScript parser should capture import statements."""

    def _get_parser(self):
        from visual_editor_core.typescript_parser import TypeScriptParser
        return TypeScriptParser

    def test_import_statement(self):
        source = "import { readFile } from 'fs';\nfunction hello(): void {}"
        module = _parse(self._get_parser(), source)
        assert any("import" in imp for imp in module.imports), \
            f"Expected import in imports, got: {module.imports}"

    def test_type_import(self):
        source = "import type { Foo } from './types';\nfunction bar() {}"
        module = _parse(self._get_parser(), source)
        assert isinstance(module.imports, list)


# ---------------------------------------------------------------------------
# 3. Java
# ---------------------------------------------------------------------------

class TestJavaParserImports:
    """Java parser should capture import and package statements."""

    def _get_parser(self):
        from visual_editor_core.java_parser import JavaParser
        return JavaParser

    def test_import_statement(self):
        source = "import java.util.List;\npublic class Hello { public void greet() {} }"
        module = _parse(self._get_parser(), source)
        assert any("java.util.List" in imp for imp in module.imports), \
            f"Expected java.util.List in imports, got: {module.imports}"

    def test_package_statement(self):
        source = "package com.example;\nimport java.io.File;\npublic class Hello {}"
        module = _parse(self._get_parser(), source)
        # Package should be recorded (as metadata or import)
        assert len(module.imports) >= 1


# ---------------------------------------------------------------------------
# 4. Kotlin
# ---------------------------------------------------------------------------

class TestKotlinParserImports:
    """Kotlin parser should capture import statements."""

    def _get_parser(self):
        from visual_editor_core.kotlin_parser import KotlinParser
        return KotlinParser

    def test_import_statement(self):
        source = "import kotlin.math.sqrt\nfun hello() {}"
        module = _parse(self._get_parser(), source)
        assert any("kotlin.math.sqrt" in imp for imp in module.imports), \
            f"Expected kotlin.math.sqrt in imports, got: {module.imports}"


# ---------------------------------------------------------------------------
# 5. Scala
# ---------------------------------------------------------------------------

class TestScalaParserImports:
    """Scala parser should capture import statements."""

    def _get_parser(self):
        from visual_editor_core.scala_parser import ScalaParser
        return ScalaParser

    def test_import_statement(self):
        source = "import scala.collection.mutable\ndef hello(): Unit = {}"
        module = _parse(self._get_parser(), source)
        assert any("scala.collection.mutable" in imp for imp in module.imports), \
            f"Expected scala.collection.mutable in imports, got: {module.imports}"


# ---------------------------------------------------------------------------
# 6. Go
# ---------------------------------------------------------------------------

class TestGoParserImports:
    """Go parser should capture import statements."""

    def _get_parser(self):
        from visual_editor_core.go_parser import GoParser
        return GoParser

    def test_single_import(self):
        source = 'import "fmt"\nfunc hello() {}'
        module = _parse(self._get_parser(), source)
        assert any("fmt" in imp for imp in module.imports), \
            f"Expected fmt in imports, got: {module.imports}"

    def test_grouped_import(self):
        source = 'import (\n\t"fmt"\n\t"os"\n)\nfunc hello() {}'
        module = _parse(self._get_parser(), source)
        assert len(module.imports) >= 2, \
            f"Expected at least 2 imports, got: {module.imports}"


# ---------------------------------------------------------------------------
# 7. Rust
# ---------------------------------------------------------------------------

class TestRustParserImports:
    """Rust parser should capture use statements."""

    def _get_parser(self):
        from visual_editor_core.rust_parser import RustParser
        return RustParser

    def test_use_statement(self):
        source = "use std::io;\nfn hello() {}"
        module = _parse(self._get_parser(), source)
        assert any("std::io" in imp for imp in module.imports), \
            f"Expected std::io in imports, got: {module.imports}"

    def test_extern_crate(self):
        source = "extern crate serde;\nuse serde::Deserialize;\nfn hello() {}"
        module = _parse(self._get_parser(), source)
        assert any("serde" in imp for imp in module.imports), \
            f"Expected serde in imports, got: {module.imports}"


# ---------------------------------------------------------------------------
# 8. C
# ---------------------------------------------------------------------------

class TestCParserImports:
    """C parser should capture #include directives."""

    def _get_parser(self):
        from visual_editor_core.c_parser import CParser
        return CParser

    def test_system_include(self):
        source = "#include <stdio.h>\nint main() { return 0; }"
        module = _parse(self._get_parser(), source)
        assert any("stdio.h" in imp for imp in module.imports), \
            f"Expected stdio.h in imports, got: {module.imports}"

    def test_local_include(self):
        source = '#include "myheader.h"\nint main() { return 0; }'
        module = _parse(self._get_parser(), source)
        assert any("myheader.h" in imp for imp in module.imports), \
            f"Expected myheader.h in imports, got: {module.imports}"


# ---------------------------------------------------------------------------
# 9. C#
# ---------------------------------------------------------------------------

class TestCSharpParserImports:
    """C# parser should capture using directives."""

    def _get_parser(self):
        from visual_editor_core.csharp_parser import CSharpParser
        return CSharpParser

    def test_using_statement(self):
        source = "using System.Linq;\nclass Hello { void Greet() {} }"
        module = _parse(self._get_parser(), source)
        assert any("System.Linq" in imp for imp in module.imports), \
            f"Expected System.Linq in imports, got: {module.imports}"


# ---------------------------------------------------------------------------
# 10. Swift
# ---------------------------------------------------------------------------

class TestSwiftParserImports:
    """Swift parser should capture import statements."""

    def _get_parser(self):
        from visual_editor_core.swift_parser import SwiftParser
        return SwiftParser

    def test_import_statement(self):
        source = "import UIKit\nfunc hello() {}"
        module = _parse(self._get_parser(), source)
        assert any("UIKit" in imp for imp in module.imports), \
            f"Expected UIKit in imports, got: {module.imports}"


# ---------------------------------------------------------------------------
# 11. Ruby
# ---------------------------------------------------------------------------

class TestRubyParserImports:
    """Ruby parser should capture require statements."""

    def _get_parser(self):
        from visual_editor_core.ruby_parser import RubyParser
        return RubyParser

    def test_require_statement(self):
        source = "require 'json'\ndef hello\n  puts 'hi'\nend"
        module = _parse(self._get_parser(), source)
        assert any("json" in imp for imp in module.imports), \
            f"Expected json in imports, got: {module.imports}"


# ---------------------------------------------------------------------------
# 12. PHP
# ---------------------------------------------------------------------------

class TestPHPParserImports:
    """PHP parser should capture use/require/include statements."""

    def _get_parser(self):
        from visual_editor_core.php_parser import PHPParser
        return PHPParser

    def test_use_statement(self):
        source = "<?php\nuse App\\Models\\User;\nfunction hello() {}"
        module = _parse(self._get_parser(), source)
        assert any("User" in imp or "App" in imp for imp in module.imports), \
            f"Expected use statement in imports, got: {module.imports}"


# ---------------------------------------------------------------------------
# 13. Lua
# ---------------------------------------------------------------------------

class TestLuaParserImports:
    """Lua parser should capture require statements."""

    def _get_parser(self):
        from visual_editor_core.lua_parser import LuaParser
        return LuaParser

    def test_require_statement(self):
        source = "local json = require('json')\nfunction hello()\nend"
        module = _parse(self._get_parser(), source)
        assert any("require" in imp for imp in module.imports), \
            f"Expected require in imports, got: {module.imports}"


# ---------------------------------------------------------------------------
# 14. R
# ---------------------------------------------------------------------------

class TestRParserImports:
    """R parser should capture library() and source() calls."""

    def _get_parser(self):
        from visual_editor_core.r_parser import RParser
        return RParser

    def test_library_call(self):
        source = "library(ggplot2)\nhello <- function() { print('hi') }"
        module = _parse(self._get_parser(), source)
        assert any("ggplot2" in imp for imp in module.imports), \
            f"Expected ggplot2 in imports, got: {module.imports}"


# ---------------------------------------------------------------------------
# 15. Bash
# ---------------------------------------------------------------------------

class TestBashParserImports:
    """Bash parser should capture source/. statements."""

    def _get_parser(self):
        from visual_editor_core.bash_parser import BashParser
        return BashParser

    def test_source_statement(self):
        source = "#!/bin/bash\nsource /etc/profile\nhello() { echo 'hi'; }"
        module = _parse(self._get_parser(), source)
        assert any("source" in imp or "/etc/profile" in imp for imp in module.imports), \
            f"Expected source statement in imports, got: {module.imports}"


# ---------------------------------------------------------------------------
# 16. SQL
# ---------------------------------------------------------------------------

class TestSQLParserImports:
    """SQL parser should capture schema-level includes/extensions."""

    def _get_parser(self):
        from visual_editor_core.sql_parser import SQLParser
        return SQLParser

    def test_create_extension(self):
        source = "CREATE EXTENSION IF NOT EXISTS pgcrypto;\nCREATE TABLE test (id SERIAL PRIMARY KEY);"
        module = _parse(self._get_parser(), source)
        # SQL imports are optional; just verify no crash and list type
        assert isinstance(module.imports, list)


# ---------------------------------------------------------------------------
# Aggregate smoke test
# ---------------------------------------------------------------------------

class TestAllParsersSmoke:
    """Quick smoke test that every parser can parse minimal source without error."""

    PARSERS_AND_SOURCES = [
        ("JavaScriptParser", "visual_editor_core.js_parser",       "const x = 1;"),
        ("TypeScriptParser", "visual_editor_core.typescript_parser","const x: number = 1;"),
        ("JavaParser",       "visual_editor_core.java_parser",      "public class T {}"),
        ("KotlinParser",     "visual_editor_core.kotlin_parser",    "fun main() {}"),
        ("ScalaParser",      "visual_editor_core.scala_parser",     "object T {}"),
        ("GoParser",         "visual_editor_core.go_parser",        "package main\nfunc main() {}"),
        ("RustParser",       "visual_editor_core.rust_parser",      "fn main() {}"),
        ("CParser",          "visual_editor_core.c_parser",         "int main() { return 0; }"),
        ("CSharpParser",     "visual_editor_core.csharp_parser",    "class T {}"),
        ("SwiftParser",      "visual_editor_core.swift_parser",     "func hello() {}"),
        ("RubyParser",       "visual_editor_core.ruby_parser",      "def hello\nend"),
        ("PHPParser",        "visual_editor_core.php_parser",       "<?php\nfunction hello() {}"),
        ("LuaParser",        "visual_editor_core.lua_parser",       "function hello()\nend"),
        ("RParser",          "visual_editor_core.r_parser",         "hello <- function() {}"),
        ("BashParser",       "visual_editor_core.bash_parser",      "#!/bin/bash\nhello() { :; }"),
        ("SQLParser",        "visual_editor_core.sql_parser",       "SELECT 1;"),
    ]

    @pytest.mark.parametrize("cls_name,mod_path,source", PARSERS_AND_SOURCES,
                             ids=[p[0] for p in PARSERS_AND_SOURCES])
    def test_parser_smoke(self, cls_name, mod_path, source):
        import importlib
        mod = importlib.import_module(mod_path)
        cls = getattr(mod, cls_name)
        parser = cls()
        module = parser.parse_code(source, "smoke_test")
        assert module is not None, f"{cls_name}.parse_code() returned None"
        assert isinstance(module.imports, list), \
            f"{cls_name} module.imports is not a list: {type(module.imports)}"
