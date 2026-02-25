"""
Test suite for the Node Registry — Multi-Language Execution Matrix.

Tests cover:
  - Registry initialization (14 engine rows)
  - Committing nodes from the ledger into slots
  - Auto-assignment of engine/position from node language
  - Hot-swap detection when ledger code is edited
  - Inter-slot communication (push, subscribe, drain)
  - Slot permissions (GET, PUSH, POST, DEL)
  - Rollback to previous code versions
  - Matrix summary / query APIs
  - Slot clearing, moving between engines
"""

import pytest
import time
from visual_editor_core.node_registry import (
    NodeRegistry, EngineID, EngineRow, RegistrySlot,
    SlotPermissionSet, SlotPermission,
    LANGUAGE_TO_ENGINE, LETTER_TO_ENGINE, LANGUAGE_STRING_TO_ENGINE,
)
from visual_editor_core.session_ledger import SessionLedger, LanguageID


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def ledger():
    """Fresh ledger with no nodes."""
    return SessionLedger()


@pytest.fixture
def populated_ledger():
    """Ledger with 5 nodes across 3 languages."""
    ledger = SessionLedger()
    imp = ledger.begin_import('test.py', 'python')

    ledger.record_node_imported('py1', 'function', 'hello', 'hello',
        'def hello():\n    print("hi")', 'python', 'test.py', imp)
    ledger.record_node_imported('py2', 'class', 'Point', 'Point',
        'class Point:\n    pass', 'python', 'test.py', imp)
    ledger.record_node_imported('js1', 'function', 'greet', 'greet',
        'function greet() { console.log("yo"); }', 'javascript', 'test.js', imp)
    ledger.record_node_imported('rs1', 'function', 'calc', 'calc',
        'fn calc() -> i32 { 42 }', 'rust', 'lib.rs', imp)
    ledger.record_node_imported('ts1', 'function', 'render', 'render',
        'function render(): void {}', 'typescript', 'app.ts', imp)

    return ledger


@pytest.fixture
def registry(populated_ledger):
    """Registry with 5 nodes committed."""
    reg = NodeRegistry(populated_ledger)
    reg.commit_all_from_ledger()
    return reg


@pytest.fixture
def empty_registry(ledger):
    """Empty registry with no committed nodes."""
    return NodeRegistry(ledger)


# =============================================================================
# INITIALIZATION
# =============================================================================

class TestRegistryInit:
    """Test registry creation and engine enumeration."""

    def test_creates_14_engines(self, empty_registry):
        engines = empty_registry.get_all_engines()
        assert len(engines) == 14

    def test_engine_ids_match_languages(self):
        assert EngineID.PYTHON.lang_id == LanguageID.PYTHON
        assert EngineID.RUST.lang_id == LanguageID.RUST
        assert EngineID.JAVASCRIPT.lang_id == LanguageID.JAVASCRIPT
        assert EngineID.CPP.lang_id == LanguageID.CPP

    def test_engine_letters(self):
        assert EngineID.PYTHON.letter == 'a'
        assert EngineID.JAVASCRIPT.letter == 'b'
        assert EngineID.TYPESCRIPT.letter == 'c'
        assert EngineID.RUST.letter == 'd'
        assert EngineID.JAVA.letter == 'e'
        assert EngineID.SWIFT.letter == 'f'
        assert EngineID.CPP.letter == 'g'
        assert EngineID.R.letter == 'h'

    def test_engine_slot_capacities(self):
        assert EngineID.PYTHON.max_slots == 64
        assert EngineID.JAVASCRIPT.max_slots == 16
        assert EngineID.TYPESCRIPT.max_slots == 16
        assert EngineID.RUST.max_slots == 16

    def test_letter_to_engine_mapping(self):
        assert LETTER_TO_ENGINE['a'] == EngineID.PYTHON
        assert LETTER_TO_ENGINE['d'] == EngineID.RUST

    def test_language_to_engine_mapping(self):
        assert LANGUAGE_TO_ENGINE[LanguageID.PYTHON] == EngineID.PYTHON
        assert LANGUAGE_TO_ENGINE[LanguageID.RUST] == EngineID.RUST

    def test_empty_matrix_summary(self, empty_registry):
        summary = empty_registry.get_matrix_summary()
        assert summary['total_committed'] == 0
        assert summary['total_dirty'] == 0
        assert summary['total_engines'] == 14
        assert summary['total_capacity'] == 64 + 13 * 16  # Python=64, 13 others=16


# =============================================================================
# COMMITTING NODES
# =============================================================================

class TestCommitNodes:
    """Test committing ledger nodes into registry slots."""

    def test_commit_single_node(self, empty_registry, populated_ledger):
        empty_registry._ledger = populated_ledger
        slot = empty_registry.commit_node('py1')
        assert slot is not None
        assert slot.node_id == 'py1'
        assert slot.engine_id == 'PYTHON'
        assert slot.position == 1
        assert slot.node_name == 'hello'
        assert slot.committed_version == 0
        assert slot.is_dirty is True

    def test_commit_all(self, registry):
        summary = registry.get_matrix_summary()
        assert summary['total_committed'] == 5

    def test_auto_assigns_engine_from_language(self, registry):
        py_slot = registry.get_slot_by_node('py1')
        rs_slot = registry.get_slot_by_node('rs1')
        js_slot = registry.get_slot_by_node('js1')
        ts_slot = registry.get_slot_by_node('ts1')

        assert py_slot.engine_id == 'PYTHON'
        assert rs_slot.engine_id == 'RUST'
        assert js_slot.engine_id == 'JAVASCRIPT'
        assert ts_slot.engine_id == 'TYPESCRIPT'

    def test_auto_increments_position(self, registry):
        py1 = registry.get_slot_by_node('py1')
        py2 = registry.get_slot_by_node('py2')
        assert py1.position == 1
        assert py2.position == 2

    def test_commit_to_specific_position(self, populated_ledger):
        reg = NodeRegistry(populated_ledger)
        slot = reg.commit_node('py1', position=5)
        assert slot.position == 5

    def test_commit_to_specific_engine(self, populated_ledger):
        reg = NodeRegistry(populated_ledger)
        slot = reg.commit_node('py1', engine_name='JAVA')
        assert slot.engine_id == 'JAVA'

    def test_commit_nonexistent_node_returns_none(self, empty_registry):
        slot = empty_registry.commit_node('nonexistent')
        assert slot is None

    def test_commit_same_node_twice_updates_in_place(self, populated_ledger):
        reg = NodeRegistry(populated_ledger)
        slot1 = reg.commit_node('py1')
        slot2 = reg.commit_node('py1')
        assert slot1.slot_id == slot2.slot_id
        assert reg.get_matrix_summary()['total_committed'] == 1

    def test_slot_ids_are_unique(self, registry):
        occupied = registry.get_occupied_slots()
        slot_ids = [s.slot_id for s in occupied]
        assert len(slot_ids) == len(set(slot_ids))

    def test_slot_address_format(self, registry):
        py1 = registry.get_slot_by_node('py1')
        assert py1.address == 'a1'  # Python, position 1

        rs1 = registry.get_slot_by_node('rs1')
        assert rs1.address == 'd1'  # Rust, position 1


# =============================================================================
# HOT-SWAP DETECTION
# =============================================================================

class TestHotSwap:
    """Test hot-swap detection when ledger code is updated."""

    def test_new_slots_are_dirty(self, registry):
        """All freshly committed slots need their first execution."""
        dirty = registry.get_dirty_slots()
        assert len(dirty) == 5

    def test_execution_clears_dirty(self, registry):
        py1 = registry.get_slot_by_node('py1')
        registry.record_execution(py1.slot_id, True, output='hi')
        assert not py1.needs_hot_swap()
        assert py1.last_executed_version == py1.committed_version

    def test_code_edit_makes_dirty_again(self, registry, populated_ledger):
        py1 = registry.get_slot_by_node('py1')
        registry.record_execution(py1.slot_id, True, output='hi')
        assert not py1.needs_hot_swap()

        # Edit the code in the ledger
        populated_ledger.record_code_edit('py1', 'def hello():\n    print("hello world!")')
        registry.refresh_all_from_ledger()

        assert py1.needs_hot_swap()
        assert py1.committed_version > py1.last_executed_version

    def test_refresh_returns_dirty_count(self, registry, populated_ledger):
        # Execute all slots first
        for slot in registry.get_occupied_slots():
            registry.record_execution(slot.slot_id, True)

        # Edit two nodes
        populated_ledger.record_code_edit('py1', 'def hello(): pass')
        populated_ledger.record_code_edit('js1', 'function greet() {}')

        dirty_count = registry.refresh_all_from_ledger()
        assert dirty_count == 2

    def test_needs_hot_swap_false_when_paused(self, registry):
        py1 = registry.get_slot_by_node('py1')
        py1.is_paused = True
        assert not py1.needs_hot_swap()

    def test_needs_hot_swap_false_when_inactive(self, registry):
        py1 = registry.get_slot_by_node('py1')
        py1.is_active = False
        assert not py1.needs_hot_swap()


# =============================================================================
# EXECUTION RECORDING
# =============================================================================

class TestExecution:
    """Test recording execution results in slots."""

    def test_record_execution_updates_slot(self, registry):
        py1 = registry.get_slot_by_node('py1')
        registry.record_execution(py1.slot_id, True, output='hello', execution_time=0.05)

        assert py1.last_output == 'hello'
        assert py1.last_error == ''
        assert py1.execution_count == 1
        assert py1.last_execution_time == 0.05
        assert py1.last_executed_at > 0

    def test_record_execution_increments_count(self, registry):
        py1 = registry.get_slot_by_node('py1')
        registry.record_execution(py1.slot_id, True, output='run1')
        registry.record_execution(py1.slot_id, True, output='run2')
        registry.record_execution(py1.slot_id, True, output='run3')
        assert py1.execution_count == 3

    def test_record_execution_appends_to_output_buffer(self, registry):
        py1 = registry.get_slot_by_node('py1')
        registry.record_execution(py1.slot_id, True, output='out1')
        registry.record_execution(py1.slot_id, True, output='out2')
        assert len(py1.output_buffer) == 2

    def test_record_error(self, registry):
        py1 = registry.get_slot_by_node('py1')
        registry.record_execution(py1.slot_id, False, error='NameError: x')
        assert py1.last_error == 'NameError: x'

    def test_execution_records_in_ledger(self, registry, populated_ledger):
        py1 = registry.get_slot_by_node('py1')
        registry.record_execution(py1.slot_id, True, output='hello')

        executions = populated_ledger.get_node_executions('py1')
        assert len(executions) == 1
        payload = executions[0].get_payload()
        assert payload['success'] is True
        assert payload['output'] == 'hello'


# =============================================================================
# INTER-SLOT COMMUNICATION
# =============================================================================

class TestInterSlotComm:
    """Test the register-to-register communication bus."""

    def test_push_to_slot(self, registry):
        js1 = registry.get_slot_by_node('js1')
        # Grant PUSH permission
        registry.set_slot_permissions(js1.slot_id,
            SlotPermissionSet(get=True, push=True))

        ok = registry.push_to_slot(js1.slot_id, {'msg': 'hello from python'})
        assert ok is True

        items = registry.drain_input_buffer(js1.slot_id)
        assert len(items) == 1
        assert items[0]['data'] == {'msg': 'hello from python'}

    def test_push_denied_without_permission(self, registry):
        js1 = registry.get_slot_by_node('js1')
        # Default: push=False
        registry.set_slot_permissions(js1.slot_id,
            SlotPermissionSet(get=True, push=False))

        ok = registry.push_to_slot(js1.slot_id, 'data')
        assert ok is False

    def test_subscribe_receives_output(self, registry):
        py1 = registry.get_slot_by_node('py1')
        js1 = registry.get_slot_by_node('js1')

        # Grant push to js1 and subscribe
        registry.set_slot_permissions(js1.slot_id,
            SlotPermissionSet(get=True, push=True))
        registry.subscribe(js1.slot_id, py1.slot_id)

        # py1 executes and produces output
        registry.record_execution(py1.slot_id, True, output='result: 42')

        # js1 should have received it
        items = registry.drain_input_buffer(js1.slot_id)
        assert len(items) == 1
        assert items[0]['data'] == 'result: 42'
        assert items[0]['source'] == py1.slot_id

    def test_unsubscribe(self, registry):
        py1 = registry.get_slot_by_node('py1')
        js1 = registry.get_slot_by_node('js1')

        registry.set_slot_permissions(js1.slot_id,
            SlotPermissionSet(get=True, push=True))
        registry.subscribe(js1.slot_id, py1.slot_id)
        registry.unsubscribe(js1.slot_id, py1.slot_id)

        registry.record_execution(py1.slot_id, True, output='no one hears')
        items = registry.drain_input_buffer(js1.slot_id)
        assert len(items) == 0

    def test_drain_clears_buffer(self, registry):
        js1 = registry.get_slot_by_node('js1')
        registry.set_slot_permissions(js1.slot_id,
            SlotPermissionSet(get=True, push=True))

        registry.push_to_slot(js1.slot_id, 'msg1')
        registry.push_to_slot(js1.slot_id, 'msg2')

        items = registry.drain_input_buffer(js1.slot_id)
        assert len(items) == 2

        # Buffer should be empty now
        items2 = registry.drain_input_buffer(js1.slot_id)
        assert len(items2) == 0

    def test_read_slot_output(self, registry):
        py1 = registry.get_slot_by_node('py1')
        registry.record_execution(py1.slot_id, True, output='out1')
        registry.record_execution(py1.slot_id, True, output='out2')

        output = registry.read_slot_output(py1.slot_id, last_n=5)
        assert len(output) == 2

    def test_read_denied_without_permission(self, registry):
        py1 = registry.get_slot_by_node('py1')
        registry.set_slot_permissions(py1.slot_id,
            SlotPermissionSet(get=False))

        output = registry.read_slot_output(py1.slot_id)
        assert len(output) == 0


# =============================================================================
# PERMISSIONS
# =============================================================================

class TestPermissions:
    """Test slot and engine-level permissions."""

    def test_default_permissions(self, registry):
        py1 = registry.get_slot_by_node('py1')
        perms = py1.permissions
        assert perms.get is True
        assert perms.push is True
        assert perms.post is False
        assert perms.delete is False

    def test_set_slot_permissions(self, registry):
        py1 = registry.get_slot_by_node('py1')
        registry.set_slot_permissions(py1.slot_id,
            SlotPermissionSet(get=True, push=True, post=True, delete=True))
        assert py1.permissions.post is True
        assert py1.permissions.delete is True

    def test_set_engine_permissions(self, registry):
        count = registry.set_engine_permissions('PYTHON',
            SlotPermissionSet(get=True, push=False, post=True, delete=False))
        assert count == 2  # py1 and py2

        py1 = registry.get_slot_by_node('py1')
        assert py1.permissions.post is True
        assert py1.permissions.push is False

    def test_permission_groups(self, registry):
        admin = registry.get_permission_group('admin')
        assert admin is not None
        assert admin.get is True
        assert admin.push is True
        assert admin.post is True
        assert admin.delete is True

    def test_apply_permission_group(self, registry):
        py1 = registry.get_slot_by_node('py1')
        ok = registry.apply_permission_group(py1.slot_id, 'readonly')
        assert ok is True
        assert py1.permissions.get is True
        assert py1.permissions.push is False
        assert py1.permissions.post is False

    def test_permissions_to_dict(self):
        perms = SlotPermissionSet(get=True, push=False, post=True, delete=False)
        d = perms.to_dict()
        assert d == {'get': True, 'push': False, 'post': True, 'del': False}

    def test_permissions_from_dict(self):
        perms = SlotPermissionSet.from_dict({'get': True, 'push': True, 'post': False, 'del': True})
        assert perms.get is True
        assert perms.push is True
        assert perms.post is False
        assert perms.delete is True

    def test_has_permission(self):
        perms = SlotPermissionSet(get=True, push=False, post=True, delete=False)
        assert perms.has(SlotPermission.GET) is True
        assert perms.has(SlotPermission.PUSH) is False
        assert perms.has(SlotPermission.POST) is True
        assert perms.has(SlotPermission.DEL) is False


# =============================================================================
# SLOT OPERATIONS
# =============================================================================

class TestSlotOperations:
    """Test clearing, moving, and querying slots."""

    def test_clear_slot(self, registry):
        py1 = registry.get_slot_by_node('py1')
        slot_id = py1.slot_id
        # Grant DEL permission
        py1.permissions.delete = True

        ok = registry.clear_slot(slot_id)
        assert ok is True
        assert registry.get_slot(slot_id) is None
        assert registry.get_slot_by_node('py1') is None

        summary = registry.get_matrix_summary()
        assert summary['total_committed'] == 4

    def test_move_slot_to_different_engine(self, registry):
        py1 = registry.get_slot_by_node('py1')
        old_slot_id = py1.slot_id

        new_slot = registry.move_slot(old_slot_id, 'JAVA')
        assert new_slot is not None
        assert new_slot.engine_id == 'JAVA'
        assert new_slot.node_id == 'py1'
        assert new_slot.is_dirty is True

        # Old slot should be cleared
        assert registry.get_slot(old_slot_id) is None

    def test_get_slot_by_address(self, registry):
        slot = registry.get_slot_by_address('a', 1)  # Python pos 1
        assert slot is not None
        assert slot.node_id == 'py1'

    def test_get_slot_by_address_nonexistent(self, registry):
        slot = registry.get_slot_by_address('a', 7)
        assert slot is None

    def test_get_engine_row(self, registry):
        row = registry.get_engine_row('PYTHON')
        assert row is not None
        assert row.engine_id == EngineID.PYTHON
        assert len(row.occupied_positions()) == 2

    def test_occupied_slots(self, registry):
        occupied = registry.get_occupied_slots()
        assert len(occupied) == 5

    def test_slot_to_dict(self, registry):
        py1 = registry.get_slot_by_node('py1')
        d = py1.to_dict()
        assert 'slot_id' in d
        assert 'address' in d
        assert 'permissions' in d
        assert 'needs_hot_swap' in d
        assert d['node_id'] == 'py1'


# =============================================================================
# ROLLBACK
# =============================================================================

class TestRollback:
    """Test zero-downtime rollback to previous code versions."""

    def test_rollback_to_previous_version(self, registry, populated_ledger):
        # Edit the node first
        populated_ledger.record_code_edit('py1', 'def hello(): print("v1")')
        registry.refresh_all_from_ledger()

        py1 = registry.get_slot_by_node('py1')
        assert py1.committed_version == 1

        # Rollback to v0
        ok = registry.rollback_slot(py1.slot_id, 0)
        assert ok is True

        # The rollback creates a NEW version (v2) with v0's code
        py1 = registry.get_slot_by_node('py1')
        assert py1.committed_version == 2
        assert py1.is_dirty is True

        # Verify the code was actually restored
        snapshot = populated_ledger.get_node_snapshot('py1')
        assert 'print("hi")' in snapshot.current_source_code

    def test_rollback_invalid_version_fails(self, registry):
        py1 = registry.get_slot_by_node('py1')
        ok = registry.rollback_slot(py1.slot_id, 999)
        assert ok is False

    def test_rollback_nonexistent_slot_fails(self, registry):
        ok = registry.rollback_slot('nra_fake', 0)
        assert ok is False


# =============================================================================
# MATRIX SUMMARY
# =============================================================================

class TestMatrixSummary:
    """Test the full matrix summary output."""

    def test_summary_structure(self, registry):
        summary = registry.get_matrix_summary()
        assert 'engines' in summary
        assert 'total_committed' in summary
        assert 'total_dirty' in summary
        assert 'total_engines' in summary
        assert 'max_slots_per_engine' in summary

    def test_summary_engine_details(self, registry):
        summary = registry.get_matrix_summary()
        python_engine = summary['engines']['PYTHON']
        assert python_engine['letter'] == 'a'
        assert python_engine['language'] == 'python'
        assert python_engine['max_slots'] == 64
        assert len(python_engine['slots']) == 64  # All 64 positions shown

        # Position 1 should have py1
        assert python_engine['slots']['1'] is not None
        assert python_engine['slots']['1']['node_name'] == 'hello'

        # Position 3 should be empty
        assert python_engine['slots']['3'] is None

    def test_engine_row_to_dict(self, registry):
        row = registry.get_engine_row('PYTHON')
        d = row.to_dict()
        assert d['engine_id'] == 'PYTHON'
        assert d['letter'] == 'a'
        assert d['occupied'] == 2

    def test_registry_to_dict(self, registry):
        d = registry.to_dict()
        assert 'slot_counter' in d
        assert 'node_to_slot' in d
        assert 'engines' in d
        assert 'channels' in d
        assert 'permission_groups' in d
        assert len(d['node_to_slot']) == 5


# =============================================================================
# ENGINE ROW
# =============================================================================

class TestEngineRow:
    """Test engine row operations."""

    def test_next_free_position(self, registry):
        row = registry.get_engine_row('PYTHON')
        assert row.next_free_position() == 3  # 1 and 2 are taken

    def test_row_full_returns_none(self, populated_ledger):
        reg = NodeRegistry(populated_ledger, max_slots_per_engine=2)
        reg.commit_all_from_ledger()
        row = reg.get_engine_row('PYTHON')
        assert row.next_free_position() is None

    def test_slots_needing_hot_swap(self, registry):
        row = registry.get_engine_row('PYTHON')
        dirty = row.slots_needing_hot_swap()
        assert len(dirty) == 2  # py1 and py2

    def test_language_name(self, registry):
        row = registry.get_engine_row('PYTHON')
        assert row.language_name == 'python'

        row = registry.get_engine_row('RUST')
        assert row.language_name == 'rust'
