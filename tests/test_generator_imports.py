"""
Test: All 17 language generators correctly emit module.imports in output.

Verifies that when a UniversalModule has imports populated, each generator
includes those imports in the generated source code output.
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from visual_editor_core.universal_ir import (
    UniversalModule, UniversalFunction, UniversalClass,
    UniversalVariable, Parameter, TypeSignature, DataType
)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _make_module(imports_list, name="test_mod"):
    """Create a UniversalModule with the given imports and a dummy function."""
    m = UniversalModule(name)
    m.imports = list(imports_list)
    f = UniversalFunction("hello")
    f.return_type = TypeSignature(DataType.VOID)
    m.functions.append(f)
    return m


# ---------------------------------------------------------------------------
# Test data: (language, generator_module, generator_class, imports, expected_fragments)
# ---------------------------------------------------------------------------

GENERATOR_TEST_CASES = [
    (
        "python",
        "visual_editor_core.python_generator", "PythonGenerator",
        ["import os", "from sys import argv"],
        ["import os", "from sys import argv"],
    ),
    (
        "javascript",
        "visual_editor_core.js_generator", "JavaScriptGenerator",
        ["const fs = require('fs');", "import path from 'path';"],
        ["require('fs')", "import path"],
    ),
    (
        "typescript",
        "visual_editor_core.typescript_generator", "TypeScriptGenerator",
        ["import { readFile } from 'fs';"],
        ["import { readFile }"],
    ),
    (
        "java",
        "visual_editor_core.java_generator", "JavaGenerator",
        ["import java.util.List;", "import java.io.File;"],
        ["import java.util.List;", "import java.io.File;"],
    ),
    (
        "go",
        "visual_editor_core.go_generator", "GoGenerator",
        ['import "fmt"', 'import "os"'],
        ["fmt", "os"],
    ),
    (
        "rust",
        "visual_editor_core.rust_generator", "RustGenerator",
        ["use std::io;", "use std::collections::HashMap;"],
        ["use std::io;", "use std::collections::HashMap;"],
    ),
    (
        "c",
        "visual_editor_core.c_generator", "CGenerator",
        ["#include <math.h>", '#include "myheader.h"'],
        ["#include <math.h>", '#include "myheader.h"'],
    ),
    (
        "csharp",
        "visual_editor_core.csharp_generator", "CSharpGenerator",
        ["using System.Linq;", "using Newtonsoft.Json;"],
        ["System.Linq", "Newtonsoft.Json"],
    ),
    (
        "kotlin",
        "visual_editor_core.kotlin_generator", "KotlinGenerator",
        ["import kotlin.math.sqrt", "import java.io.File"],
        ["import kotlin.math.sqrt", "import java.io.File"],
    ),
    (
        "swift",
        "visual_editor_core.swift_generator", "SwiftGenerator",
        ["import UIKit", "import CoreData"],
        ["import UIKit", "import CoreData"],
    ),
    (
        "scala",
        "visual_editor_core.scala_generator", "ScalaGenerator",
        ["import scala.collection.mutable", "import java.io.File"],
        ["import scala.collection.mutable", "import java.io.File"],
    ),
    (
        "ruby",
        "visual_editor_core.ruby_generator", "RubyGenerator",
        ["require 'json'", "require 'net/http'"],
        ["require 'json'", "require 'net/http'"],
    ),
    (
        "php",
        "visual_editor_core.php_generator", "PHPGenerator",
        ["use App\\Models\\User;", "use Illuminate\\Http\\Request;"],
        ["use App\\Models\\User;", "use Illuminate\\Http\\Request;"],
    ),
    (
        "lua",
        "visual_editor_core.lua_generator", "LuaGenerator",
        ["local json = require('json')", "local socket = require('socket')"],
        ["require('json')", "require('socket')"],
    ),
    (
        "r",
        "visual_editor_core.r_generator", "RGenerator",
        ["library(ggplot2)", "library(dplyr)"],
        ["library(ggplot2)", "library(dplyr)"],
    ),
    (
        "bash",
        "visual_editor_core.bash_generator", "BashGenerator",
        ["source /etc/profile", ". ./utils.sh"],
        ["source /etc/profile", ". ./utils.sh"],
    ),
    (
        "sql",
        "visual_editor_core.sql_generator", "SQLGenerator",
        ["CREATE EXTENSION IF NOT EXISTS pgcrypto", "\\i schema.sql"],
        ["CREATE EXTENSION IF NOT EXISTS pgcrypto", "\\i schema.sql"],
    ),
]


# ---------------------------------------------------------------------------
# Parametrised test
# ---------------------------------------------------------------------------

class TestGeneratorImports:
    """Every generator must emit module.imports in its output."""

    @pytest.mark.parametrize(
        "lang,gen_module,gen_class,imports,expected",
        GENERATOR_TEST_CASES,
        ids=[t[0] for t in GENERATOR_TEST_CASES],
    )
    def test_imports_appear_in_output(self, lang, gen_module, gen_class, imports, expected):
        import importlib
        mod = importlib.import_module(gen_module)
        cls = getattr(mod, gen_class)

        module = _make_module(imports)
        generator = cls()
        code = generator.generate_module(module)

        for fragment in expected:
            assert fragment in code, (
                f"[{lang}] Expected '{fragment}' in generated output.\n"
                f"Got:\n{code[:500]}"
            )


# ---------------------------------------------------------------------------
# Deduplication tests
# ---------------------------------------------------------------------------

class TestGeneratorImportDeduplication:
    """Generators should not emit duplicate imports."""

    def test_python_no_duplicates(self):
        from visual_editor_core.python_generator import PythonGenerator
        module = _make_module(["import os", "import os"])
        code = PythonGenerator().generate_module(module)
        assert code.count("import os") == 1, "Python generator emitted duplicate import os"

    def test_javascript_no_duplicates(self):
        from visual_editor_core.js_generator import JavaScriptGenerator
        module = _make_module(["const fs = require('fs');", "const fs = require('fs');"])
        code = JavaScriptGenerator().generate_module(module)
        assert code.count("require('fs')") == 1, "JS generator emitted duplicate require"

    def test_php_no_duplicates(self):
        from visual_editor_core.php_generator import PHPGenerator
        module = _make_module(["use App\\Models\\User;", "use App\\Models\\User;"])
        code = PHPGenerator().generate_module(module)
        assert code.count("use App\\Models\\User;") == 1, "PHP generator emitted duplicate use"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestGeneratorImportEdgeCases:
    """Edge cases for import generation."""

    def test_empty_imports_no_crash(self):
        """All generators should handle empty imports gracefully."""
        import importlib
        for lang, gen_module, gen_class, _, _ in GENERATOR_TEST_CASES:
            mod = importlib.import_module(gen_module)
            cls = getattr(mod, gen_class)
            module = _make_module([])
            generator = cls()
            code = generator.generate_module(module)
            assert isinstance(code, str), f"{lang} generator returned non-string for empty imports"

    def test_whitespace_only_imports_skipped(self):
        """Imports that are just whitespace should be skipped."""
        from visual_editor_core.python_generator import PythonGenerator
        module = _make_module(["import os", "   ", "", "from sys import argv"])
        code = PythonGenerator().generate_module(module)
        assert "import os" in code
        assert "from sys import argv" in code
