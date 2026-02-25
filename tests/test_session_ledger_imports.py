"""
Test: Session ledger import recording and retrieval.

Verifies that the SessionLedger correctly records file imports,
retrieves them with deduplication, and honours DependencyStrategy.
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from visual_editor_core.session_ledger import (
    SessionLedger, DependencyStrategy, resolve_dependency_strategy
)


class TestLedgerImportRecording:
    """Tests for record_file_imports / get_file_imports."""

    def _fresh_ledger(self):
        return SessionLedger()

    def test_record_and_retrieve_imports(self):
        ledger = self._fresh_ledger()
        session = ledger.begin_import("test.py", "python")
        imports = ["import os", "from sys import argv"]
        ledger.record_file_imports(session, imports, "test.py")
        result = ledger.get_file_imports()
        assert "import os" in result
        assert "from sys import argv" in result

    def test_imports_are_deduplicated(self):
        ledger = self._fresh_ledger()
        session = ledger.begin_import("test.py", "python")
        ledger.record_file_imports(session, ["import os", "import os", "import os"], "test.py")
        result = ledger.get_file_imports()
        assert result.count("import os") == 1

    def test_imports_are_sorted(self):
        ledger = self._fresh_ledger()
        session = ledger.begin_import("test.py", "python")
        ledger.record_file_imports(session, ["import z_module", "import a_module"], "test.py")
        result = ledger.get_file_imports()
        assert result == sorted(result)

    def test_no_imports_returns_empty_list(self):
        ledger = self._fresh_ledger()
        result = ledger.get_file_imports()
        assert result == []

    def test_multiple_sessions_merged(self):
        ledger = self._fresh_ledger()
        s1 = ledger.begin_import("a.py", "python")
        ledger.record_file_imports(s1, ["import os"], "a.py")
        s2 = ledger.begin_import("b.py", "python")
        ledger.record_file_imports(s2, ["import sys"], "b.py")
        result = ledger.get_file_imports()
        assert "import os" in result
        assert "import sys" in result


class TestDependencyStrategy:
    """Tests for DependencyStrategy enum and resolution."""

    def test_resolve_ignore(self):
        assert resolve_dependency_strategy("ignore") == DependencyStrategy.IGNORE

    def test_resolve_preserve(self):
        assert resolve_dependency_strategy("preserve") == DependencyStrategy.PRESERVE

    def test_resolve_consolidate(self):
        assert resolve_dependency_strategy("consolidate") == DependencyStrategy.CONSOLIDATE

    def test_resolve_refactor_export(self):
        result = resolve_dependency_strategy("refactor_export")
        assert result == DependencyStrategy.REFACTOR_EXPORT

    def test_resolve_unknown_defaults_preserve(self):
        result = resolve_dependency_strategy("banana")
        assert result == DependencyStrategy.PRESERVE

    def test_resolve_none_defaults_preserve(self):
        result = resolve_dependency_strategy("")
        assert result == DependencyStrategy.PRESERVE

    def test_enum_values_exist(self):
        assert hasattr(DependencyStrategy, 'IGNORE')
        assert hasattr(DependencyStrategy, 'PRESERVE')
        assert hasattr(DependencyStrategy, 'CONSOLIDATE')
        assert hasattr(DependencyStrategy, 'REFACTOR_EXPORT')


class TestLedgerBeginImport:
    """Tests for begin_import session tracking."""

    def _fresh_ledger(self):
        return SessionLedger()

    def test_begin_import_returns_session_number(self):
        ledger = self._fresh_ledger()
        session = ledger.begin_import(
            source_file="test.py",
            source_language="python",
        )
        assert isinstance(session, int)
        assert session >= 1

    def test_successive_imports_increment(self):
        ledger = self._fresh_ledger()
        s1 = ledger.begin_import("a.py", "python")
        s2 = ledger.begin_import("b.py", "python")
        assert s2 > s1
