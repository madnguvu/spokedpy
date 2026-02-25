"""
Node Registry — Multi-Language Execution Matrix with Per-Slot API Permissions.

This module implements the execution matrix described in the architecture diagram:

                 position →  1     2     3     4  …  16  …  64
    engine_assignment ↓
      Python    (a)         1002  1010  1011  1012  …   …  (64 slots)
      Javascript(b)                          1001        (16 slots)
      TypeScript(c)               1004             1005  (16 slots)
      Rust      (d)         1003                         (16 slots)
      Java      (e)                                      (16 slots)
      Swift     (f)                                      (16 slots)
      C++       (g)               1008             1006  (16 slots)
      R         (h)                     1007             (16 slots)
      Go        (i)                                      (16 slots)
      Ruby      (j)                                      (16 slots)
      C#        (k)                                      (16 slots)
      Kotlin    (l)                                      (16 slots)
      C         (m)                                      (16 slots)
      Bash      (n)                                      (16 slots)

    Total: 14 engines, 288 addressable slots (64 + 13×16)

    Removed engines (languages still exist in the IR system):
      Lua, Scala, PHP — nodes in these languages can still be parsed,
      stored in the ledger, and exported. They just don't have a
      dedicated engine row. Use C or Bash as a host engine if needed.

Each cell is an addressable slot: (engine_row, position_col) → committed node.
The registry sits ON TOP of the Session Ledger — the ledger is the immutable
history; the registry is the live execution state.

Key concepts:
    - EngineRow:   A language runtime (Python, JS, Rust, etc.) that processes
                   its committed slots in a loop ("bit-bashing")
    - Slot:        An addressable cell (row, col) holding one committed node
    - Slot Version: The ledger version of the code in this slot — the engine
                    checks this on each loop tick and hot-swaps if newer
    - Permissions:  Per-slot API permissions controlling inter-slot communication
                    (GET, PUSH, POST, DEL)
    - Hot-Swap:     When a node's code is updated in the ledger, the registry
                    version tag is bumped. On the next engine loop tick, the
                    engine loads the new code — zero downtime.

The registry provides a REST-style API for each slot:
    localhost:5002/api/nra01/     → Node Registry Address, slot 01
    Permissions: { get: true, push: true, post: true, del: false }

This achieves CI with 100% uptime: commit to ledger → engine picks it up next
loop → old version finished, new version starts. No restart, no deploy pipeline.
"""

import time
import uuid
import json
import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple
from enum import Enum, IntEnum
from .session_ledger import (
    SessionLedger, NodeSnapshot, LanguageID,
    resolve_language_id, resolve_language_string,
    LANGUAGE_ID_TO_STRING
)


# =============================================================================
# ENGINE ROWS — One per language runtime
# =============================================================================

class EngineID(Enum):
    """
    Engine identifiers — each maps to a language runtime.
    The letter suffix matches the diagram (a, b, c, ...).

    Slot capacities:
        Python (a)                  → 64 slots  (primary engine)
        JavaScript, TypeScript, Rust, Java → 16 slots  (tier-1)
        All others                  → 16 slots  (tier-2)

    Removed engines (languages still exist in the IR, just no dedicated engine):
        Lua, Scala, PHP — use the C or Bash engine as a host if needed.
    """
    PYTHON      = ('a', LanguageID.PYTHON,      64)
    JAVASCRIPT  = ('b', LanguageID.JAVASCRIPT,   16)
    TYPESCRIPT  = ('c', LanguageID.TYPESCRIPT,    16)
    RUST        = ('d', LanguageID.RUST,          16)
    JAVA        = ('e', LanguageID.JAVA,          16)
    SWIFT       = ('f', LanguageID.SWIFT,         16)
    CPP         = ('g', LanguageID.CPP,           16)
    R           = ('h', LanguageID.R,             16)
    GO          = ('i', LanguageID.GO,            16)
    RUBY        = ('j', LanguageID.RUBY,          16)
    CSHARP      = ('k', LanguageID.CSHARP,        16)
    KOTLIN      = ('l', LanguageID.KOTLIN,         16)
    C           = ('m', LanguageID.C,              16)
    BASH        = ('n', LanguageID.BASH,           16)
    PERL        = ('o', LanguageID.PERL,           16)

    def __init__(self, letter: str, lang_id: LanguageID, max_slots: int = 16):
        self.letter = letter
        self.lang_id = lang_id
        self.max_slots = max_slots


# Map LanguageID → EngineID for fast lookup
LANGUAGE_TO_ENGINE: Dict[LanguageID, EngineID] = {
    e.lang_id: e for e in EngineID
}

# Map letter → EngineID
LETTER_TO_ENGINE: Dict[str, EngineID] = {
    e.letter: e for e in EngineID
}

# Map language string → EngineID
LANGUAGE_STRING_TO_ENGINE: Dict[str, EngineID] = {}
for _engine in EngineID:
    _lang_str = resolve_language_string(_engine.lang_id)
    if _lang_str != 'unknown':
        LANGUAGE_STRING_TO_ENGINE[_lang_str] = _engine


# =============================================================================
# SLOT PERMISSIONS — Controls inter-slot communication
# =============================================================================

class SlotPermission(Enum):
    """
    Permissions that can be granted to a slot or a group of slots.
    These control the REST-style API for register-to-register communication.
    """
    GET  = 'get'    # Read slot output / state
    PUSH = 'push'   # Push data into a slot's input buffer
    POST = 'post'   # Submit new code / trigger execution
    DEL  = 'del'    # Clear / reset a slot


@dataclass
class SlotPermissionSet:
    """
    Permission set for a slot or slot group.
    Controls which operations external callers can perform.
    """
    get: bool = True       # Default: readable
    push: bool = False     # Default: no external push
    post: bool = False     # Default: no external trigger
    delete: bool = False   # Default: no external delete

    def to_dict(self) -> Dict[str, bool]:
        return {
            'get': self.get,
            'push': self.push,
            'post': self.post,
            'del': self.delete,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, bool]) -> 'SlotPermissionSet':
        return cls(
            get=d.get('get', True),
            push=d.get('push', False),
            post=d.get('post', False),
            delete=d.get('del', False),
        )

    def has(self, perm: SlotPermission) -> bool:
        return {
            SlotPermission.GET: self.get,
            SlotPermission.PUSH: self.push,
            SlotPermission.POST: self.post,
            SlotPermission.DEL: self.delete,
        }.get(perm, False)


# =============================================================================
# SLOT — A single cell in the execution matrix
# =============================================================================

@dataclass
class RegistrySlot:
    """
    A single addressable cell in the execution matrix.

    Address format: nra{NN} where NN is the global slot number.
    Matrix position: (engine_row, position_col)

    The slot holds a reference to a committed node (by node_id) and tracks
    which version of the node's code was last loaded by the engine.
    """
    # Addressing
    slot_id: str                         # e.g., "nra01"
    engine_id: str                       # EngineID name: "PYTHON", "RUST", etc.
    position: int                        # Column in the matrix (1-indexed)

    # What's committed here
    node_id: Optional[str] = None        # Ledger node ID currently in this slot
    node_name: str = ''                  # Display name (for readability)
    committed_version: int = 0           # Ledger version when committed
    last_executed_version: int = -1      # Version the engine last ran (-1 = never)

    # Execution state
    last_output: str = ''                # Output from last execution
    last_error: str = ''                 # Error from last execution (empty = success)
    last_execution_time: float = 0.0     # Seconds
    execution_count: int = 0             # Total times this slot has been executed
    last_executed_at: float = 0.0        # Unix timestamp

    # Input/output buffers for inter-slot communication
    input_buffer: List[Dict[str, Any]] = field(default_factory=list)
    output_buffer: List[Dict[str, Any]] = field(default_factory=list)

    # Permissions
    permissions: SlotPermissionSet = field(default_factory=SlotPermissionSet)

    # Flags
    is_active: bool = True               # Can the engine execute this slot?
    is_dirty: bool = False               # Has new code been committed but not yet executed?
    is_paused: bool = False              # Temporarily skip this slot in the loop

    def needs_hot_swap(self) -> bool:
        """Check if the engine should reload code for this slot."""
        return (
            self.node_id is not None
            and self.committed_version > self.last_executed_version
            and self.is_active
            and not self.is_paused
        )

    @property
    def address(self) -> str:
        """Full address: engine_letter + position, e.g. 'a1' for Python pos 1."""
        try:
            engine = EngineID[self.engine_id]
            return f"{engine.letter}{self.position}"
        except (KeyError, AttributeError):
            return f"?{self.position}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            'slot_id': self.slot_id,
            'address': self.address,
            'engine_id': self.engine_id,
            'position': self.position,
            'node_id': self.node_id,
            'node_name': self.node_name,
            'committed_version': self.committed_version,
            'last_executed_version': self.last_executed_version,
            'needs_hot_swap': self.needs_hot_swap(),
            'last_output': self.last_output[:500],
            'last_error': self.last_error[:500],
            'last_execution_time': round(self.last_execution_time, 4),
            'execution_count': self.execution_count,
            'last_executed_at': self.last_executed_at,
            'input_buffer_size': len(self.input_buffer),
            'output_buffer_size': len(self.output_buffer),
            'permissions': self.permissions.to_dict(),
            'is_active': self.is_active,
            'is_dirty': self.is_dirty,
            'is_paused': self.is_paused,
        }


# =============================================================================
# ENGINE ROW — All slots for a single language runtime
# =============================================================================

@dataclass
class EngineRow:
    """
    A single row in the matrix — all slots assigned to one language engine.
    The engine processes these slots in a loop (bit-bashing).
    """
    engine_id: EngineID
    max_slots: int = 16                  # Per-engine capacity (Python=64, others=16)
    slots: Dict[int, RegistrySlot] = field(default_factory=dict)  # position → Slot
    is_running: bool = False             # Is the engine loop active?
    loop_tick_count: int = 0             # How many loop iterations have run
    loop_interval_ms: int = 100          # Milliseconds between ticks

    @property
    def language_name(self) -> str:
        return resolve_language_string(self.engine_id.lang_id)

    @property
    def letter(self) -> str:
        return self.engine_id.letter

    def occupied_positions(self) -> List[int]:
        """Get positions that have committed nodes."""
        return sorted(p for p, s in self.slots.items() if s.node_id is not None)

    def next_free_position(self) -> Optional[int]:
        """Find the next available position, or None if full."""
        for pos in range(1, self.max_slots + 1):
            if pos not in self.slots or self.slots[pos].node_id is None:
                return pos
        return None

    def slots_needing_hot_swap(self) -> List[RegistrySlot]:
        """Get all slots that have newer code than what was last executed."""
        return [s for s in self.slots.values() if s.needs_hot_swap()]

    def to_dict(self) -> Dict[str, Any]:
        return {
            'engine_id': self.engine_id.name,
            'letter': self.letter,
            'language': self.language_name,
            'max_slots': self.max_slots,
            'occupied': len(self.occupied_positions()),
            'positions': self.occupied_positions(),
            'is_running': self.is_running,
            'loop_tick_count': self.loop_tick_count,
            'loop_interval_ms': self.loop_interval_ms,
            'slots': {
                str(pos): slot.to_dict()
                for pos, slot in sorted(self.slots.items())
            },
        }


# =============================================================================
# NODE REGISTRY — The full execution matrix
# =============================================================================

class NodeRegistry:
    """
    Multi-language execution matrix with per-slot API permissions.

    The registry maps committed nodes from the Session Ledger into addressable
    slots organized by language engine. Each slot can be:
      - Committed:  A node's code has been placed here
      - Hot-swapped: The node's code was updated in the ledger, and the engine
                     picked up the new version on its next loop tick
      - Paused:     Temporarily skipped by the engine
      - Cleared:    The slot is empty (available for a new node)

    Addressing:
      - Global: "nra01" through "nraNNN" (node registry address)
      - Matrix: (engine_letter, position) e.g. ("a", 1) = Python slot 1
      - Node-based: by node_id (ledger reference)

    The registry provides three permission groups (from the diagram):
      - nra*, nrc*     → GET, PUSH   (read and push to any slot)
      - nra01-05       → DEL         (can clear specific slots)
      - nra*           → POST        (can trigger execution on any slot)
    """

    def __init__(self, ledger: SessionLedger, max_slots_per_engine: int = 0):
        """
        Create the execution matrix.

        Args:
            ledger: The session ledger (source of truth for node code).
            max_slots_per_engine: If > 0, overrides every engine's default
                slot capacity (useful for testing). If 0, each engine uses
                its own EngineID.max_slots (Python=64, others=16).
        """
        self._ledger = ledger
        self._slot_counter = 0
        self._lock = threading.RLock()

        # The matrix: engine_name → EngineRow
        # Each engine gets its own slot capacity from EngineID.max_slots
        # unless max_slots_per_engine is explicitly provided as an override.
        self._engines: Dict[str, EngineRow] = {}
        for engine in EngineID:
            capacity = max_slots_per_engine if max_slots_per_engine > 0 else engine.max_slots
            self._engines[engine.name] = EngineRow(
                engine_id=engine,
                max_slots=capacity,
            )

        # Store the override value for serialization
        self._max_slots_override = max_slots_per_engine

        # Index: node_id → slot_id (quick lookup)
        self._node_to_slot: Dict[str, str] = {}
        # Index: slot_id → (engine_name, position)
        self._slot_index: Dict[str, Tuple[str, int]] = {}

        # Permission groups (from diagram)
        self._permission_groups: Dict[str, SlotPermissionSet] = {
            'default': SlotPermissionSet(get=True, push=True, post=False, delete=False),
            'admin': SlotPermissionSet(get=True, push=True, post=True, delete=True),
            'execute': SlotPermissionSet(get=True, push=False, post=True, delete=False),
            'readonly': SlotPermissionSet(get=True, push=False, post=False, delete=False),
        }

        # Communication channels: slot_id → list of subscriber slot_ids
        self._channels: Dict[str, List[str]] = {}

    # =========================================================================
    # SLOT MANAGEMENT
    # =========================================================================

    def _next_slot_id(self) -> str:
        """Generate the next global slot address: nra01, nra02, ..."""
        self._slot_counter += 1
        return f"nra{self._slot_counter:02d}"

    def commit_node(self, node_id: str,
                    engine_name: Optional[str] = None,
                    position: Optional[int] = None,
                    permissions: Optional[SlotPermissionSet] = None) -> Optional[RegistrySlot]:
        """
        Commit a node from the ledger into a registry slot.

        If engine_name is not specified, it's inferred from the node's
        current_language_id in the ledger. If position is not specified,
        the next free position in that engine row is used.

        This is the "deploy" operation — the node's code is now live.
        """
        with self._lock:
            snapshot = self._ledger.get_node_snapshot(node_id)
            if not snapshot:
                return None

            # Determine engine
            if engine_name is None:
                lang_id = LanguageID(snapshot.current_language_id)
                engine = LANGUAGE_TO_ENGINE.get(lang_id)
                if engine is None:
                    return None
                engine_name = engine.name

            row = self._engines.get(engine_name)
            if row is None:
                return None

            # If node is already committed somewhere, update in-place
            existing_slot_id = self._node_to_slot.get(node_id)
            if existing_slot_id and existing_slot_id in self._slot_index:
                eng, pos = self._slot_index[existing_slot_id]
                existing_slot = self._engines[eng].slots.get(pos)
                if existing_slot:
                    existing_slot.committed_version = snapshot.version
                    existing_slot.node_name = snapshot.display_name
                    existing_slot.is_dirty = True
                    return existing_slot

            # Find position
            if position is None:
                position = row.next_free_position()
                if position is None:
                    return None  # Row is full

            # Create slot
            slot_id = self._next_slot_id()
            slot = RegistrySlot(
                slot_id=slot_id,
                engine_id=engine_name,
                position=position,
                node_id=node_id,
                node_name=snapshot.display_name,
                committed_version=snapshot.version,
                permissions=permissions or SlotPermissionSet(
                    get=True, push=True, post=False, delete=False
                ),
                is_dirty=True,
            )

            row.slots[position] = slot
            self._node_to_slot[node_id] = slot_id
            self._slot_index[slot_id] = (engine_name, position)

            return slot

    def commit_all_from_ledger(self) -> List[RegistrySlot]:
        """
        Commit all active ledger nodes into the registry matrix.
        Nodes are placed into their language engine row in creation order.
        Returns list of all committed slots.
        """
        committed = []
        active_snapshots = self._ledger.get_active_snapshots()

        # Sort by creation order
        sorted_nodes = sorted(
            active_snapshots.values(),
            key=lambda s: (s.import_session_number, s.global_creation_order)
        )

        for snapshot in sorted_nodes:
            slot = self.commit_node(snapshot.node_id)
            if slot:
                committed.append(slot)

        return committed

    def update_slot_from_ledger(self, slot_id: str) -> bool:
        """
        Refresh a slot's committed version from the ledger.
        Called when a node's code has been edited — the engine will see
        the version bump on its next tick and hot-swap.
        """
        with self._lock:
            if slot_id not in self._slot_index:
                return False

            engine_name, position = self._slot_index[slot_id]
            slot = self._engines[engine_name].slots.get(position)
            if not slot or not slot.node_id:
                return False

            snapshot = self._ledger.get_node_snapshot(slot.node_id)
            if not snapshot:
                return False

            if snapshot.version > slot.committed_version:
                slot.committed_version = snapshot.version
                slot.node_name = snapshot.display_name
                slot.is_dirty = True
                return True

            return False

    def refresh_all_from_ledger(self) -> int:
        """
        Check all occupied slots against the ledger for version bumps.
        Returns the number of slots that need hot-swapping.
        """
        dirty_count = 0
        with self._lock:
            for slot_id in list(self._slot_index.keys()):
                if self.update_slot_from_ledger(slot_id):
                    dirty_count += 1
        return dirty_count

    def clear_slot(self, slot_id: str) -> bool:
        """
        Clear a slot — remove the committed node. The slot becomes available.
        The node's code is NOT deleted from the ledger (it's immutable).
        """
        with self._lock:
            if slot_id not in self._slot_index:
                return False

            engine_name, position = self._slot_index[slot_id]
            slot = self._engines[engine_name].slots.get(position)
            if not slot:
                return False

            # Remove from indexes
            if slot.node_id and slot.node_id in self._node_to_slot:
                del self._node_to_slot[slot.node_id]

            # Clear the slot contents (keep the slot object, just empty it)
            slot.node_id = None
            slot.node_name = ''
            slot.committed_version = 0
            slot.last_executed_version = -1
            slot.is_dirty = False
            slot.is_active = True
            slot.input_buffer.clear()
            slot.output_buffer.clear()

            del self._slot_index[slot_id]

            return True

    def move_slot(self, slot_id: str, target_engine: str,
                  target_position: Optional[int] = None) -> Optional[RegistrySlot]:
        """
        Move a committed node to a different engine/position.
        This is used when a node's language changes (e.g., Python → Rust).
        """
        with self._lock:
            if slot_id not in self._slot_index:
                return None

            engine_name, position = self._slot_index[slot_id]
            old_slot = self._engines[engine_name].slots.get(position)
            if not old_slot or not old_slot.node_id:
                return None

            target_row = self._engines.get(target_engine)
            if not target_row:
                return None

            if target_position is None:
                target_position = target_row.next_free_position()
                if target_position is None:
                    return None

            # Create new slot in target
            node_id = old_slot.node_id
            new_slot_id = self._next_slot_id()
            new_slot = RegistrySlot(
                slot_id=new_slot_id,
                engine_id=target_engine,
                position=target_position,
                node_id=node_id,
                node_name=old_slot.node_name,
                committed_version=old_slot.committed_version,
                permissions=old_slot.permissions,
                is_dirty=True,
            )

            # Place in new row
            target_row.slots[target_position] = new_slot
            self._node_to_slot[node_id] = new_slot_id
            self._slot_index[new_slot_id] = (target_engine, target_position)

            # Clear old slot
            del self._slot_index[slot_id]
            old_slot.node_id = None
            old_slot.node_name = ''
            old_slot.is_dirty = False

            return new_slot

    # =========================================================================
    # EXECUTION RECORDING — Engine loop reports results here
    # =========================================================================

    def record_execution(self, slot_id: str, success: bool,
                         output: str = '', error: str = '',
                         execution_time: float = 0.0) -> bool:
        """
        Record that an engine has executed a slot.
        Updates the slot state and marks it as no longer dirty.
        Also records the execution in the ledger for immutable history.
        """
        with self._lock:
            if slot_id not in self._slot_index:
                return False

            engine_name, position = self._slot_index[slot_id]
            slot = self._engines[engine_name].slots.get(position)
            if not slot:
                return False

            slot.last_executed_version = slot.committed_version
            slot.last_output = output[:10000]
            slot.last_error = error[:5000]
            slot.last_execution_time = execution_time
            slot.execution_count += 1
            slot.last_executed_at = time.time()
            slot.is_dirty = False

            # Publish output to output buffer
            if output:
                slot.output_buffer.append({
                    'timestamp': time.time(),
                    'data': output[:10000],
                    'version': slot.committed_version,
                })
                # Cap buffer size
                if len(slot.output_buffer) > 50:
                    slot.output_buffer = slot.output_buffer[-50:]

            # Push to subscribers
            self._broadcast_output(slot_id, output)

            # Record in ledger
            if slot.node_id:
                self._ledger.record_node_executed(
                    node_id=slot.node_id,
                    success=success,
                    output=output,
                    error=error,
                    execution_time=execution_time,
                    code_version=slot.committed_version,
                )

            return True

    # =========================================================================
    # INTER-SLOT COMMUNICATION — The register-to-register bus
    # =========================================================================

    def push_to_slot(self, target_slot_id: str, data: Any,
                     source_slot_id: Optional[str] = None) -> bool:
        """
        Push data into a slot's input buffer.
        Checks PUSH permission before allowing.
        """
        with self._lock:
            if target_slot_id not in self._slot_index:
                return False

            engine_name, position = self._slot_index[target_slot_id]
            slot = self._engines[engine_name].slots.get(position)
            if not slot:
                return False

            if not slot.permissions.has(SlotPermission.PUSH):
                return False

            slot.input_buffer.append({
                'timestamp': time.time(),
                'source': source_slot_id,
                'data': data,
            })

            # Cap buffer size
            if len(slot.input_buffer) > 100:
                slot.input_buffer = slot.input_buffer[-100:]

            return True

    def read_slot_output(self, slot_id: str, last_n: int = 10) -> List[Dict[str, Any]]:
        """
        Read from a slot's output buffer.
        Checks GET permission before allowing.
        """
        with self._lock:
            if slot_id not in self._slot_index:
                return []

            engine_name, position = self._slot_index[slot_id]
            slot = self._engines[engine_name].slots.get(position)
            if not slot:
                return []

            if not slot.permissions.has(SlotPermission.GET):
                return []

            return slot.output_buffer[-last_n:]

    def subscribe(self, subscriber_slot_id: str, publisher_slot_id: str) -> bool:
        """
        Subscribe one slot to another's output.
        When the publisher produces output, it's automatically pushed
        to the subscriber's input buffer.
        """
        with self._lock:
            self._channels.setdefault(publisher_slot_id, [])
            if subscriber_slot_id not in self._channels[publisher_slot_id]:
                self._channels[publisher_slot_id].append(subscriber_slot_id)
            return True

    def unsubscribe(self, subscriber_slot_id: str, publisher_slot_id: str) -> bool:
        """Remove a subscription."""
        with self._lock:
            subs = self._channels.get(publisher_slot_id, [])
            if subscriber_slot_id in subs:
                subs.remove(subscriber_slot_id)
                return True
            return False

    def _broadcast_output(self, publisher_slot_id: str, output: str):
        """Push output to all subscribers of a slot."""
        subscribers = self._channels.get(publisher_slot_id, [])
        for sub_id in subscribers:
            self.push_to_slot(sub_id, output, source_slot_id=publisher_slot_id)

    def drain_input_buffer(self, slot_id: str) -> List[Dict[str, Any]]:
        """
        Drain all items from a slot's input buffer (engine reads these
        before executing). Returns the items and clears the buffer.
        """
        with self._lock:
            if slot_id not in self._slot_index:
                return []

            engine_name, position = self._slot_index[slot_id]
            slot = self._engines[engine_name].slots.get(position)
            if not slot:
                return []

            items = list(slot.input_buffer)
            slot.input_buffer.clear()
            return items

    # =========================================================================
    # PERMISSIONS
    # =========================================================================

    def set_slot_permissions(self, slot_id: str,
                             permissions: SlotPermissionSet) -> bool:
        """Set permissions for a specific slot."""
        with self._lock:
            if slot_id not in self._slot_index:
                return False

            engine_name, position = self._slot_index[slot_id]
            slot = self._engines[engine_name].slots.get(position)
            if not slot:
                return False

            slot.permissions = permissions
            return True

    def set_engine_permissions(self, engine_name: str,
                               permissions: SlotPermissionSet) -> int:
        """Set permissions for all slots in an engine row."""
        row = self._engines.get(engine_name)
        if not row:
            return 0

        count = 0
        for slot in row.slots.values():
            slot.permissions = SlotPermissionSet(
                get=permissions.get,
                push=permissions.push,
                post=permissions.post,
                delete=permissions.delete,
            )
            count += 1
        return count

    def get_permission_group(self, group_name: str) -> Optional[SlotPermissionSet]:
        """Get a named permission group."""
        return self._permission_groups.get(group_name)

    def apply_permission_group(self, slot_id: str, group_name: str) -> bool:
        """Apply a named permission group to a slot."""
        perms = self._permission_groups.get(group_name)
        if not perms:
            return False
        return self.set_slot_permissions(slot_id, perms)

    # =========================================================================
    # QUERIES
    # =========================================================================

    def get_slot(self, slot_id: str) -> Optional[RegistrySlot]:
        """Get a slot by its global address (nra01, nra02, ...)."""
        with self._lock:
            if slot_id not in self._slot_index:
                return None
            engine_name, position = self._slot_index[slot_id]
            return self._engines[engine_name].slots.get(position)

    def get_slot_by_address(self, engine_letter: str, position: int) -> Optional[RegistrySlot]:
        """Get a slot by matrix address (e.g., 'a', 1 for Python pos 1)."""
        engine = LETTER_TO_ENGINE.get(engine_letter)
        if not engine:
            return None
        row = self._engines.get(engine.name)
        if not row:
            return None
        return row.slots.get(position)

    def get_slot_by_node(self, node_id: str) -> Optional[RegistrySlot]:
        """Get the slot a node is committed to (if any)."""
        slot_id = self._node_to_slot.get(node_id)
        if not slot_id:
            return None
        return self.get_slot(slot_id)

    def get_engine_row(self, engine_name: str) -> Optional[EngineRow]:
        """Get an engine row by name."""
        return self._engines.get(engine_name)

    def get_all_engines(self) -> Dict[str, EngineRow]:
        """Get all engine rows."""
        return dict(self._engines)

    def get_occupied_slots(self) -> List[RegistrySlot]:
        """Get all slots that have committed nodes."""
        result = []
        for row in self._engines.values():
            for slot in row.slots.values():
                if slot.node_id is not None:
                    result.append(slot)
        return result

    def get_dirty_slots(self) -> List[RegistrySlot]:
        """Get all slots that need hot-swapping."""
        result = []
        for row in self._engines.values():
            result.extend(row.slots_needing_hot_swap())
        return result

    def get_matrix_summary(self) -> Dict[str, Any]:
        """
        Get a summary of the entire matrix — suitable for the UI.
        Returns the grid layout matching the diagram.
        """
        matrix = {}
        total_committed = 0
        total_dirty = 0

        for engine_name, row in self._engines.items():
            row_data = {
                'engine': engine_name,
                'letter': row.letter,
                'language': row.language_name,
                'max_slots': row.max_slots,
                'is_running': row.is_running,
                'tick_count': row.loop_tick_count,
                'slots': {},
            }

            for pos in range(1, row.max_slots + 1):
                slot = row.slots.get(pos)
                if slot and slot.node_id:
                    row_data['slots'][str(pos)] = {
                        'slot_id': slot.slot_id,
                        'node_id': slot.node_id,
                        'node_name': slot.node_name,
                        'version': slot.committed_version,
                        'needs_swap': slot.needs_hot_swap(),
                        'exec_count': slot.execution_count,
                        'is_paused': slot.is_paused,
                    }
                    total_committed += 1
                    if slot.needs_hot_swap():
                        total_dirty += 1
                else:
                    row_data['slots'][str(pos)] = None

            matrix[engine_name] = row_data

        return {
            'max_slots_per_engine': self._max_slots_override,
            'total_engines': len(self._engines),
            'total_committed': total_committed,
            'total_dirty': total_dirty,
            'total_capacity': sum(r.max_slots for r in self._engines.values()),
            'engines': matrix,
        }

    # =========================================================================
    # ROLLBACK — Point a slot to a previous ledger version
    # =========================================================================

    def rollback_slot(self, slot_id: str, target_version: int) -> bool:
        """
        Rollback a slot to a previous code version from the ledger.

        The engine's next loop tick will pick up this version.
        The broken version stays in the ledger for forensics.
        This is CI rollback without downtime.
        """
        with self._lock:
            if slot_id not in self._slot_index:
                return False

            engine_name, position = self._slot_index[slot_id]
            slot = self._engines[engine_name].slots.get(position)
            if not slot or not slot.node_id:
                return False

            # Verify the target version exists in the ledger
            snapshot = self._ledger.get_node_snapshot(slot.node_id)
            if not snapshot:
                return False

            # Check that the version is valid
            valid_versions = [cv['version'] for cv in snapshot.code_versions]
            if target_version not in valid_versions:
                return False

            # Get the code for that version
            target_cv = next(
                cv for cv in snapshot.code_versions
                if cv['version'] == target_version
            )

            # Record a code edit in the ledger (so the rollback is tracked)
            self._ledger.record_code_edit(
                node_id=slot.node_id,
                new_source_code=target_cv['source_code'],
                reason=f'rollback_to_v{target_version}',
            )

            # Update the slot — the engine will pick this up
            new_snapshot = self._ledger.get_node_snapshot(slot.node_id)
            if new_snapshot:
                slot.committed_version = new_snapshot.version
                slot.is_dirty = True

            return True

    # =========================================================================
    # SERIALIZATION
    # =========================================================================

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the full registry state."""
        return {
            'slot_counter': self._slot_counter,
            'max_slots_override': self._max_slots_override,
            'node_to_slot': dict(self._node_to_slot),
            'slot_index': {
                sid: {'engine': eng, 'position': pos}
                for sid, (eng, pos) in self._slot_index.items()
            },
            'engines': {
                name: row.to_dict()
                for name, row in self._engines.items()
            },
            'channels': dict(self._channels),
            'permission_groups': {
                name: perms.to_dict()
                for name, perms in self._permission_groups.items()
            },
        }
