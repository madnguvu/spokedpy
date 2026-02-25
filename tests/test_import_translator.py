"""
Tests for the cross-language import translator and the non-Python
export path node filtering (Area A + Area B fixes).
"""

import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from visual_editor_core.import_translator import (
    translate_import, translate_imports, _is_python_import, _is_native_import,
)


# ────────────────────────────────────────────────────────────────────
# Area B — translate_import() per-language tests
# ────────────────────────────────────────────────────────────────────

class TestPythonDetection:
    """_is_python_import correctly classifies statements."""

    @pytest.mark.parametrize("stmt", [
        "import os",
        "import numpy as np",
        "from collections import defaultdict",
        "from os.path import join, exists",
    ])
    def test_detects_python_imports(self, stmt):
        assert _is_python_import(stmt)

    @pytest.mark.parametrize("stmt", [
        "const fs = require('fs');",
        "import { useState } from 'react';",
        "#include <stdio.h>",
        "use std::collections::HashMap;",
        "library(dplyr)",
        "require 'json'",
    ])
    def test_rejects_non_python_imports(self, stmt):
        assert not _is_python_import(stmt)


class TestNativeDetection:
    """_is_native_import correctly classifies statements for target languages."""

    def test_js_native(self):
        assert _is_native_import("const fs = require('fs');", 'javascript')
        assert not _is_native_import("import os", 'javascript')

    def test_ts_native(self):
        assert _is_native_import("import { x } from 'y';", 'typescript')

    def test_java_native(self):
        assert _is_native_import("import java.util.*;", 'java')

    def test_go_native(self):
        assert _is_native_import('import "fmt"', 'go')

    def test_rust_native(self):
        assert _is_native_import("use std::io;", 'rust')

    def test_c_native(self):
        assert _is_native_import("#include <stdio.h>", 'c')

    def test_csharp_native(self):
        assert _is_native_import("using System.Linq;", 'csharp')

    def test_ruby_native(self):
        assert _is_native_import("require 'json'", 'ruby')

    def test_php_native(self):
        assert _is_native_import("use App\\Models\\User;", 'php')

    def test_lua_native(self):
        assert _is_native_import('local x = require("x")', 'lua')

    def test_r_native(self):
        assert _is_native_import("library(dplyr)", 'r')

    def test_bash_native(self):
        assert _is_native_import("source ./utils.sh", 'bash')


class TestTranslateToJavaScript:
    def test_from_import(self):
        result = translate_import("from collections import defaultdict", "javascript")
        assert result == "const { defaultdict } = require('collections');"

    def test_import_as(self):
        result = translate_import("import numpy as np", "javascript")
        assert result == "const np = require('numpy');"

    def test_plain_import(self):
        result = translate_import("import os", "javascript")
        assert result == "const os = require('os');"

    def test_from_import_multiple(self):
        result = translate_import("from os.path import join, exists", "javascript")
        assert result == "const { join, exists } = require('os.path');"

    def test_native_passthrough(self):
        native = "const fs = require('fs');"
        assert translate_import(native, "javascript") == native


class TestTranslateToTypeScript:
    def test_from_import(self):
        result = translate_import("from collections import defaultdict", "typescript")
        assert result == "import { defaultdict } from 'collections';"

    def test_import_as(self):
        result = translate_import("import numpy as np", "typescript")
        assert result == "import * as np from 'numpy';"


class TestTranslateToJava:
    def test_from_import(self):
        result = translate_import("from java.util import ArrayList", "java")
        assert result == "import java.util.ArrayList;"

    def test_plain_import(self):
        result = translate_import("import os", "java")
        assert result == "import os.*;"

    def test_from_import_star(self):
        result = translate_import("from java.util import *", "java")
        assert result == "import java.util.*;"


class TestTranslateToGo:
    def test_python_import_commented(self):
        result = translate_import("import os", "go")
        assert result.startswith("// Python dep:")

    def test_native_passthrough(self):
        assert translate_import('import "fmt"', "go") == 'import "fmt"'


class TestTranslateToRust:
    def test_from_import(self):
        result = translate_import("from std.collections import HashMap", "rust")
        assert result == "use std::collections::HashMap;"

    def test_from_import_multiple(self):
        result = translate_import("from std.io import Read, Write", "rust")
        assert result == "use std::io::{Read, Write};"


class TestTranslateToC:
    def test_python_import_commented(self):
        result = translate_import("import os", "c")
        assert result.startswith("// Python dep:")

    def test_native_passthrough(self):
        assert translate_import("#include <stdio.h>", "c") == "#include <stdio.h>"


class TestTranslateToCSharp:
    def test_from_import(self):
        result = translate_import("from System.Linq import Enumerable", "csharp")
        assert result == "using System.Linq;"

    def test_plain_import(self):
        result = translate_import("import System", "csharp")
        assert result == "using System;"


class TestTranslateToKotlin:
    def test_from_import(self):
        result = translate_import("from java.util import ArrayList", "kotlin")
        assert result == "import java.util.ArrayList"

    def test_from_import_star(self):
        result = translate_import("from java.util import *", "kotlin")
        assert result == "import java.util.*"


class TestTranslateToSwift:
    def test_from_import(self):
        result = translate_import("from Foundation.NSObject import NSObject", "swift")
        assert result == "import Foundation"

    def test_plain_import(self):
        result = translate_import("import UIKit", "swift")
        assert result == "import UIKit"


class TestTranslateToScala:
    def test_from_import(self):
        result = translate_import("from scala.collection import mutable", "scala")
        assert result == "import scala.collection.mutable"

    def test_from_import_star(self):
        result = translate_import("from scala.util import *", "scala")
        assert result == "import scala.util._"


class TestTranslateToRuby:
    def test_from_import(self):
        result = translate_import("from json import loads", "ruby")
        assert result == "require 'json'"

    def test_plain_import(self):
        result = translate_import("import yaml", "ruby")
        assert result == "require 'yaml'"


class TestTranslateToPHP:
    def test_from_import(self):
        result = translate_import("from App.Models import User", "php")
        assert result == "use App\\Models\\User;"

    def test_from_import_star(self):
        result = translate_import("from App.Models import *", "php")
        assert result == "use App\\Models;"


class TestTranslateToLua:
    def test_plain_import(self):
        result = translate_import("import json", "lua")
        assert result == 'local json = require("json")'

    def test_import_as(self):
        result = translate_import("import socket as sock", "lua")
        assert result == 'local sock = require("socket")'


class TestTranslateToR:
    def test_plain_import(self):
        result = translate_import("import pandas", "r")
        assert result == "library(pandas)"

    def test_from_import(self):
        result = translate_import("from ggplot2 import aes", "r")
        assert result == "library(ggplot2)"


class TestTranslateToBash:
    def test_python_import_commented(self):
        result = translate_import("import os", "bash")
        assert result.startswith("# Python dep:")

    def test_native_passthrough(self):
        assert translate_import("source ./utils.sh", "bash") == "source ./utils.sh"


class TestTranslateToSQL:
    def test_python_import_commented(self):
        result = translate_import("import os", "sql")
        assert result.startswith("-- Python dep:")


# ────────────────────────────────────────────────────────────────────
# translate_imports() batch helper
# ────────────────────────────────────────────────────────────────────

class TestTranslateImportsBatch:
    def test_deduplication(self):
        imports = ["import os", "import os"]
        result = translate_imports(imports, "javascript")
        assert len(result) == 1

    def test_multiline_expansion(self):
        """Java: from X import A, B should expand to two import lines."""
        imports = ["from java.util import ArrayList, HashMap"]
        result = translate_imports(imports, "java")
        assert "import java.util.ArrayList;" in result
        assert "import java.util.HashMap;" in result
        assert len(result) == 2

    def test_mixed_native_and_foreign(self):
        imports = [
            "const fs = require('fs');",       # native JS
            "from collections import deque",    # Python
        ]
        result = translate_imports(imports, "javascript")
        assert "const fs = require('fs');" in result
        assert "const { deque } = require('collections');" in result

    def test_empty_list(self):
        assert translate_imports([], "javascript") == []


# ────────────────────────────────────────────────────────────────────
# Integration: generators correctly translate Python imports
# ────────────────────────────────────────────────────────────────────

class TestGeneratorTranslation:
    """Each generator's import method translates Python imports correctly."""

    @staticmethod
    def _make_module(imports):
        from visual_editor_core.universal_ir import UniversalModule
        m = UniversalModule(name="test", source_language="python")
        m.imports.extend(imports)
        return m

    PYTHON_IMPORTS = [
        "from collections import defaultdict",
        "import numpy as np",
    ]

    def test_js_generator(self):
        from visual_editor_core.js_generator import JavaScriptGenerator
        gen = JavaScriptGenerator()
        result = gen._generate_imports(self._make_module(self.PYTHON_IMPORTS))
        joined = "\n".join(result)
        assert "require('collections')" in joined
        assert "require('numpy')" in joined
        assert "from collections" not in joined

    def test_ts_generator(self):
        from visual_editor_core.typescript_generator import TypeScriptGenerator
        gen = TypeScriptGenerator()
        result = gen._generate_imports(self._make_module(self.PYTHON_IMPORTS))
        joined = "\n".join(result)
        assert "from 'collections'" in joined
        assert "from 'numpy'" in joined
        assert "from collections import" not in joined

    def test_java_generator(self):
        from visual_editor_core.java_generator import JavaGenerator
        gen = JavaGenerator()
        result = gen._generate_imports(self._make_module(self.PYTHON_IMPORTS))
        joined = "\n".join(result)
        assert "import collections.defaultdict;" in joined
        assert "import numpy.*;" in joined

    def test_go_generator(self):
        from visual_editor_core.go_generator import GoGenerator
        gen = GoGenerator()
        result = gen._collect_imports(self._make_module(self.PYTHON_IMPORTS))
        joined = "\n".join(result)
        assert "Python dep:" in joined

    def test_rust_generator(self):
        from visual_editor_core.rust_generator import RustGenerator
        gen = RustGenerator()
        output = gen.generate_module(self._make_module(self.PYTHON_IMPORTS))
        assert "use collections::defaultdict;" in output
        assert "from collections" not in output

    def test_kotlin_generator(self):
        from visual_editor_core.kotlin_generator import KotlinGenerator
        gen = KotlinGenerator()
        output = gen.generate_module(self._make_module(self.PYTHON_IMPORTS))
        assert "import collections.defaultdict" in output

    def test_swift_generator(self):
        from visual_editor_core.swift_generator import SwiftGenerator
        gen = SwiftGenerator()
        output = gen.generate_module(self._make_module(self.PYTHON_IMPORTS))
        assert "import collections" in output
        assert "from collections" not in output

    def test_ruby_generator(self):
        from visual_editor_core.ruby_generator import RubyGenerator
        gen = RubyGenerator()
        result = gen._generate_requires(self._make_module(self.PYTHON_IMPORTS))
        joined = "\n".join(result)
        assert "require 'collections'" in joined
        assert "require 'numpy'" in joined

    def test_php_generator(self):
        from visual_editor_core.php_generator import PHPGenerator
        gen = PHPGenerator()
        result = gen._generate_use_statements(self._make_module(self.PYTHON_IMPORTS))
        joined = "\n".join(result)
        assert "use collections\\defaultdict;" in joined

    def test_lua_generator(self):
        from visual_editor_core.lua_generator import LuaGenerator
        gen = LuaGenerator()
        result = gen._generate_requires(self._make_module(self.PYTHON_IMPORTS))
        joined = "\n".join(result)
        assert 'require("collections")' in joined
        assert 'require("numpy")' in joined

    def test_r_generator(self):
        from visual_editor_core.r_generator import RGenerator
        gen = RGenerator()
        result = gen._generate_libraries(self._make_module(self.PYTHON_IMPORTS))
        joined = "\n".join(result)
        assert "library(collections)" in joined
        assert "library(numpy)" in joined

    def test_c_generator(self):
        from visual_editor_core.c_generator import CGenerator
        gen = CGenerator()
        output = gen.generate_module(self._make_module(self.PYTHON_IMPORTS))
        assert "// Python dep:" in output
        # Raw Python import syntax should not appear outside comments
        for line in output.splitlines():
            if line.strip().startswith("from collections"):
                pytest.fail("Raw 'from collections' appeared outside a comment")

    def test_bash_generator(self):
        from visual_editor_core.bash_generator import BashGenerator
        gen = BashGenerator()
        output = gen.generate_module(self._make_module(self.PYTHON_IMPORTS))
        assert "# Python dep:" in output
        for line in output.splitlines():
            if line.strip().startswith("from collections"):
                pytest.fail("Raw 'from collections' appeared outside a comment")

    def test_sql_generator(self):
        from visual_editor_core.sql_generator import SQLGenerator
        gen = SQLGenerator()
        output = gen.generate_module(self._make_module(self.PYTHON_IMPORTS))
        assert "-- Python dep:" in output
        for line in output.splitlines():
            if line.strip().startswith("from collections"):
                pytest.fail("Raw 'from collections' appeared outside a comment")

    def test_csharp_generator(self):
        from visual_editor_core.csharp_generator import CSharpGenerator
        gen = CSharpGenerator()
        result = gen._collect_usings(self._make_module(self.PYTHON_IMPORTS))
        joined = "\n".join(result)
        assert "collections" in joined
        assert "from collections" not in joined
