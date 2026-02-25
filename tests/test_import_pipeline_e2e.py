"""
Test: End-to-end import pipeline (parser → ledger → generator).

Verifies the full round-trip: parse source code → capture imports into
module.imports → record in ledger → feed into generator → verify output.
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from visual_editor_core.session_ledger import SessionLedger
from visual_editor_core.universal_ir import (
    UniversalModule, UniversalFunction, TypeSignature, DataType
)


def _make_module_with_imports(imports, name="test_mod"):
    """Create a UniversalModule with given imports and a dummy function."""
    m = UniversalModule(name)
    m.imports = list(imports)
    f = UniversalFunction("hello")
    f.return_type = TypeSignature(DataType.VOID)
    m.functions.append(f)
    return m


def _ledger_round_trip(source_file, source_language, imports):
    """Record imports into a fresh ledger session and retrieve them."""
    ledger = SessionLedger()
    session = ledger.begin_import(source_file, source_language)
    ledger.record_file_imports(session, imports, source_file)
    return ledger.get_file_imports()


class TestPythonPipeline:
    """Python: parse → ledger → generate round-trip."""

    def test_python_imports_round_trip(self):
        from visual_editor_core.python_parser import PythonParser
        from visual_editor_core.python_generator import PythonGenerator

        source = (
            "import os\n"
            "from collections import OrderedDict\n"
            "\n"
            "def greet(name):\n"
            "    print(f'Hello {name}')\n"
        )

        # 1. Parse
        parser = PythonParser()
        module = parser.parse_code(source, "greet.py")
        assert "import os" in module.imports
        assert any("OrderedDict" in imp for imp in module.imports)

        # 2. Record in ledger
        retrieved = _ledger_round_trip("greet.py", "python", module.imports)
        assert "import os" in retrieved

        # 3. Generate — feed ledger imports into a fresh module
        gen_module = _make_module_with_imports(retrieved, "greet")
        code = PythonGenerator().generate_module(gen_module)
        assert "import os" in code
        assert "OrderedDict" in code


class TestJavaScriptPipeline:
    """JavaScript: parse → ledger → generate round-trip."""

    def test_js_imports_round_trip(self):
        from visual_editor_core.js_parser import JavaScriptParser
        from visual_editor_core.js_generator import JavaScriptGenerator

        source = (
            "const fs = require('fs');\n"
            "import path from 'path';\n"
            "\n"
            "function readConfig() {\n"
            "    return fs.readFileSync('config.json');\n"
            "}\n"
        )

        # 1. Parse
        parser = JavaScriptParser()
        module = parser.parse_code(source, "config.js")
        assert any("require" in imp or "fs" in imp for imp in module.imports)

        # 2. Record in ledger
        retrieved = _ledger_round_trip("config.js", "javascript", module.imports)
        assert len(retrieved) >= 1

        # 3. Generate
        gen_module = _make_module_with_imports(retrieved, "config")
        code = JavaScriptGenerator().generate_module(gen_module)
        # At least one of the imports should appear
        assert any(imp in code for imp in retrieved), \
            f"None of {retrieved} found in generated code:\n{code[:300]}"


class TestRustPipeline:
    """Rust: parse → ledger → generate round-trip."""

    def test_rust_imports_round_trip(self):
        from visual_editor_core.rust_parser import RustParser
        from visual_editor_core.rust_generator import RustGenerator

        source = (
            "use std::io;\n"
            "use std::collections::HashMap;\n"
            "\n"
            "fn main() {\n"
            "    println!(\"hello\");\n"
            "}\n"
        )

        # 1. Parse
        parser = RustParser()
        module = parser.parse_code(source, "main.rs")
        assert any("std::io" in imp for imp in module.imports)

        # 2. Ledger
        retrieved = _ledger_round_trip("main.rs", "rust", module.imports)
        assert any("std::io" in imp for imp in retrieved)

        # 3. Generate
        gen_module = _make_module_with_imports(retrieved, "main")
        code = RustGenerator().generate_module(gen_module)
        assert "use std::io;" in code
        assert "use std::collections::HashMap;" in code


class TestGoLangPipeline:
    """Go: parse → ledger → generate round-trip."""

    def test_go_imports_round_trip(self):
        from visual_editor_core.go_parser import GoParser
        from visual_editor_core.go_generator import GoGenerator

        source = (
            'package main\n'
            '\n'
            'import (\n'
            '\t"fmt"\n'
            '\t"os"\n'
            ')\n'
            '\n'
            'func main() {\n'
            '\tfmt.Println("hello")\n'
            '}\n'
        )

        # 1. Parse
        parser = GoParser()
        module = parser.parse_code(source, "main.go")
        assert any("fmt" in imp for imp in module.imports)

        # 2. Ledger
        retrieved = _ledger_round_trip("main.go", "go", module.imports)
        assert len(retrieved) >= 2

        # 3. Generate
        gen_module = _make_module_with_imports(retrieved, "main")
        code = GoGenerator().generate_module(gen_module)
        assert "fmt" in code
        assert "os" in code


class TestPHPPipeline:
    """PHP: parse → ledger → generate round-trip."""

    def test_php_imports_round_trip(self):
        from visual_editor_core.php_parser import PHPParser
        from visual_editor_core.php_generator import PHPGenerator

        source = (
            "<?php\n"
            "use App\\Models\\User;\n"
            "\n"
            "function getUser() {\n"
            "    return new User();\n"
            "}\n"
        )

        # 1. Parse
        parser = PHPParser()
        module = parser.parse_code(source, "user.php")
        assert any("User" in imp or "App" in imp for imp in module.imports)

        # 2. Ledger
        retrieved = _ledger_round_trip("user.php", "php", module.imports)
        assert len(retrieved) >= 1

        # 3. Generate
        gen_module = _make_module_with_imports(retrieved, "user")
        code = PHPGenerator().generate_module(gen_module)
        assert any(imp in code for imp in retrieved), \
            f"None of {retrieved} found in generated code:\n{code[:300]}"
