"""
Session Ledger - Kafka-inspired append-only event log for visual programming sessions.

This module implements an immutable, transactional registry that tracks every
transformation in a visual programming session: imports, edits, type changes,
connections, and exports. By recording the full lineage of every node, the system
can reconstruct correct, working code at export time.

Architecture (Kafka analogy):
    - Language Registry: Permanent lookup table (like a topic schema)
    - Session Ledger: Append-only transaction log (like a Kafka partition)
    - Node Lineage: Full history per node (like a consumer group offset)

    Session UUID-10000  →  "imported file X, created nodes A,B,C in Python"
    Session UUID-10001  →  "converted node B from Python to JavaScript"
    Session UUID-10002  →  "edited node A source code, added parameter"
    Session UUID-10003  →  "connected node A.output → node C.input"
    ...
    Export reads the ledger, knows exactly what each node is, where it came from,
    what its current state is, and can produce correct code.
"""

import uuid
import json
import time
import copy
from datetime import datetime
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, Set
from enum import Enum, IntEnum


# =============================================================================
# LANGUAGE REGISTRY - Permanent, immutable lookup table
# =============================================================================

class LanguageID(IntEnum):
    """
    Permanent language identifiers. These NEVER change.
    Like a Kafka schema registry - once assigned, always assigned.
    
    Ranges:
        100-119: High-level interpreted languages
        120-139: Compiled / systems languages  
        140-159: JVM / managed runtime languages
        160-179: Specialty / domain-specific languages
        200+:    Reserved for future languages
    """
    PYTHON      = 100
    JAVASCRIPT  = 101
    TYPESCRIPT  = 102
    RUBY        = 103
    PHP         = 104
    LUA         = 105
    R           = 106
    BASH        = 107
    PERL        = 108
    
    GO          = 120
    RUST        = 121
    C           = 122
    CPP         = 123
    
    JAVA        = 140
    KOTLIN      = 141
    SCALA       = 142
    CSHARP      = 143
    SWIFT       = 144
    
    SQL         = 160
    HTML        = 161
    CSS         = 162
    
    UNIVERSAL_IR = 0   # Language-agnostic intermediate representation
    UNKNOWN      = -1


# Bidirectional mapping for fast lookup
LANGUAGE_STRING_TO_ID: Dict[str, LanguageID] = {
    'python':     LanguageID.PYTHON,
    'javascript': LanguageID.JAVASCRIPT,
    'typescript': LanguageID.TYPESCRIPT,
    'ruby':       LanguageID.RUBY,
    'php':        LanguageID.PHP,
    'lua':        LanguageID.LUA,
    'r':          LanguageID.R,
    'bash':       LanguageID.BASH,
    'perl':       LanguageID.PERL,
    'go':         LanguageID.GO,
    'rust':       LanguageID.RUST,
    'c':          LanguageID.C,
    'cpp':        LanguageID.CPP,
    'c++':        LanguageID.CPP,
    'java':       LanguageID.JAVA,
    'kotlin':     LanguageID.KOTLIN,
    'scala':      LanguageID.SCALA,
    'csharp':     LanguageID.CSHARP,
    'c#':         LanguageID.CSHARP,
    'swift':      LanguageID.SWIFT,
    'sql':        LanguageID.SQL,
}

LANGUAGE_ID_TO_STRING: Dict[LanguageID, str] = {v: k for k, v in LANGUAGE_STRING_TO_ID.items() if k == k.lower() and k not in ('c++', 'c#')}


def resolve_language_id(language: str) -> LanguageID:
    """Resolve a language string to its permanent ID."""
    return LANGUAGE_STRING_TO_ID.get(language.lower().strip(), LanguageID.UNKNOWN)


def resolve_language_string(lang_id: LanguageID) -> str:
    """Resolve a language ID back to its canonical string."""
    return LANGUAGE_ID_TO_STRING.get(lang_id, 'unknown')


# =============================================================================
# DEPENDENCY STRATEGY - How imports / dependencies are handled during import
# =============================================================================

class DependencyStrategy(Enum):
    """
    Controls how file-level imports and external dependencies are treated
    when importing a file or repository into the visual editor.
    
    Like a web-scraper depth setting:
        IGNORE          → Depth 0: just the code, no imports
        PRESERVE        → Depth 1: keep import statements as string references
        CONSOLIDATE     → Depth 2: resolve + pull dependency source into project nodes
        REFACTOR_EXPORT → Pipeline: import → resolve → immediate re-export with deps inlined
    """
    IGNORE          = "ignore"           # Strip all imports — user manages manually
    PRESERVE        = "preserve"         # Keep import statements as-is (default)
    CONSOLIDATE     = "consolidate"      # Resolve deps, pull source into project nodes
    REFACTOR_EXPORT = "refactor_export"  # Consolidate + immediate export pass


DEPENDENCY_STRATEGY_MAP: Dict[str, DependencyStrategy] = {
    s.value: s for s in DependencyStrategy
}


def resolve_dependency_strategy(value: str) -> DependencyStrategy:
    """Resolve a strategy string to enum, defaulting to PRESERVE."""
    return DEPENDENCY_STRATEGY_MAP.get(
        (value or '').lower().strip(), DependencyStrategy.PRESERVE
    )


# =============================================================================
# EVENT TYPES - What can happen in a session
# =============================================================================

class LedgerEventType(Enum):
    """
    Every type of mutation that can occur in a session.
    Each event is immutable once written — like a Kafka message.
    """
    # Session lifecycle
    SESSION_CREATED        = "session_created"
    SESSION_CLOSED         = "session_closed"
    
    # Import events
    FILE_IMPORTED          = "file_imported"
    REPOSITORY_IMPORTED    = "repository_imported"
    
    # Node events
    NODE_CREATED           = "node_created"
    NODE_DELETED           = "node_deleted"
    NODE_MOVED             = "node_moved"
    NODE_CODE_EDITED       = "node_code_edited"
    NODE_PARAMS_CHANGED    = "node_params_changed"
    NODE_LANGUAGE_CHANGED  = "node_language_changed"
    NODE_TYPE_CHANGED      = "node_type_changed"
    NODE_IO_CHANGED        = "node_io_changed"
    
    # Connection events
    CONNECTION_CREATED     = "connection_created"
    CONNECTION_DELETED     = "connection_deleted"
    
    # Export events
    EXPORT_STARTED         = "export_started"
    EXPORT_COMPLETED       = "export_completed"
    
    # Execution events
    NODE_EXECUTED          = "node_executed"
    EXECUTION_BATCH        = "execution_batch"
    
    # Conversion events
    LANGUAGE_CONVERSION    = "language_conversion"
    BULK_CONVERSION        = "bulk_conversion"


# =============================================================================
# LEDGER ENTRY - A single immutable event record
# =============================================================================

@dataclass(frozen=True)
class LedgerEntry:
    """
    A single immutable entry in the session ledger.
    Once created, it can never be modified — only new entries can be appended.
    
    This is the "cracker in the sleeve" — perfectly ordered, never rearranged.
    """
    # Identity
    entry_id: str                    # Session UUID + sequence (e.g., "abc-10042")
    session_id: str                  # Parent session UUID
    sequence_number: int             # Monotonically increasing (10000, 10001, ...)
    
    # Timing
    timestamp: float                 # Unix timestamp (precise ordering)
    
    # Event classification
    event_type: LedgerEventType      # What happened
    
    # What was affected
    node_id: Optional[str] = None    # Which node (if applicable)
    connection_id: Optional[str] = None  # Which connection (if applicable)
    
    # Language tracking
    source_language_id: Optional[int] = None   # Original language ID
    target_language_id: Optional[int] = None   # Target language ID (for conversions)
    canvas_language_id: Optional[int] = None   # Language as displayed on canvas
    
    # The payload — what exactly changed
    payload: str = "{}"              # JSON-encoded event data (frozen requires str)
    
    # Provenance
    import_session_number: Optional[int] = None  # Which import batch (1st, 2nd, 3rd...)
    creation_order: Optional[int] = None         # Order within its import batch
    global_order: Optional[int] = None           # Overall order across all imports

    def get_payload(self) -> Dict[str, Any]:
        """Deserialize the payload."""
        return json.loads(self.payload)


# =============================================================================
# NODE SNAPSHOT - Current materialized state of a node
# =============================================================================

@dataclass
class NodeSnapshot:
    """
    Materialized current state of a node, derived from replaying its ledger entries.
    This is the "consumed offset" — what you get when you read the ledger up to now.
    """
    node_id: str
    
    # Identity and classification
    node_type: str                     # function, class, variable, control_flow, etc.
    display_name: str                  # What shows on the canvas
    raw_name: str                      # Actual code identifier (e.g., "calculate_score")
    class_name: Optional[str] = None   # Parent class if this is a method
    
    # Language lineage
    original_language_id: int = LanguageID.UNKNOWN   # Language when first created/imported
    current_language_id: int = LanguageID.UNKNOWN     # Language as currently displayed
    canvas_language_id: int = LanguageID.UNKNOWN      # Language on canvas (may differ)
    
    # Source code — the actual content
    original_source_code: str = ""     # Source code as first imported (never changes)
    current_source_code: str = ""      # Current version after edits
    
    # Structure
    parameters: Dict[str, Any] = field(default_factory=dict)
    inputs: List[Dict[str, Any]] = field(default_factory=list)
    outputs: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Provenance tracking
    import_session_number: int = 0     # Which import created this node
    creation_order_in_import: int = 0  # Order within that import
    global_creation_order: int = 0     # Overall order across all imports
    source_file: str = ""              # Original file path
    
    # Version tracking  
    version: int = 0                   # How many times code has been edited
    code_versions: List[Dict[str, Any]] = field(default_factory=list)  # Version history
    
    # Flags
    is_modified: bool = False          # Has been edited since import
    is_converted: bool = False         # Language has been changed
    is_connected: bool = False         # Has connections to other nodes
    
    def to_export_dict(self) -> Dict[str, Any]:
        """Convert to the format needed by the export engine."""
        return {
            'id': self.node_id,
            'type': self.node_type,
            'name': self.display_name,
            'raw_name': self.raw_name,
            'class_name': self.class_name,
            'source_code': self.current_source_code,
            'original_source_code': self.original_source_code,
            'source_language': resolve_language_string(LanguageID(self.original_language_id)),
            'current_language': resolve_language_string(LanguageID(self.current_language_id)),
            'parameters': self.parameters,
            'inputs': self.inputs,
            'outputs': self.outputs,
            'metadata': self.metadata,
            'import_session': self.import_session_number,
            'creation_order': self.global_creation_order,
            'version': self.version,
            'is_modified': self.is_modified,
            'is_converted': self.is_converted,
            'source_file': self.source_file,
        }


# =============================================================================
# HELPERS
# =============================================================================

def _safe_serialize_vars(variables: Dict[str, Any]) -> Dict[str, str]:
    """Serialize execution variables to JSON-safe strings for ledger storage."""
    safe = {}
    for k, v in variables.items():
        if k.startswith('__'):
            continue
        try:
            json.dumps(v)          # already serializable
            safe[k] = v
        except (TypeError, ValueError):
            safe[k] = repr(v)[:200]
    return safe


# =============================================================================
# SESSION LEDGER - The core append-only event log
# =============================================================================

class SessionLedger:
    """
    Append-only event log for a visual programming session.
    
    Like a Kafka partition:
    - Events are written in order and never modified
    - Each event has a monotonically increasing sequence number
    - The current state is derived by replaying events from the beginning
    - You can "rewind" to any point by reading up to a specific sequence
    
    The "sleeve of crackers" — everything stacked neatly, ordered, accessible.
    """
    
    SEQUENCE_START = 10000  # First sequence number
    
    def __init__(self, session_id: Optional[str] = None):
        self.session_id = session_id or str(uuid.uuid4())
        self._entries: List[LedgerEntry] = []
        self._sequence_counter = self.SEQUENCE_START
        self._node_snapshots: Dict[str, NodeSnapshot] = {}
        self._import_counter = 0
        self._global_node_counter = 0
        self._node_creation_order: Dict[str, int] = {}  # node_id -> order within import
        
        # Indexes for fast lookup
        self._entries_by_node: Dict[str, List[int]] = {}  # node_id -> [entry indexes]
        self._entries_by_type: Dict[LedgerEventType, List[int]] = {}
        self._entries_by_import: Dict[int, List[int]] = {}  # import_session -> [entry indexes]
        
        # Record session creation
        self._append(LedgerEventType.SESSION_CREATED, payload={
            'created_at': datetime.now().isoformat(),
            'session_id': self.session_id
        })
    
    def clear(self):
        """Reset the ledger to a fresh state (as if newly created).
        
        Preserves the same object identity so all external references
        (e.g. runtime._session_ledger, NodeRegistry) stay valid.
        """
        self._entries.clear()
        self._sequence_counter = self.SEQUENCE_START
        self._node_snapshots.clear()
        self._import_counter = 0
        self._global_node_counter = 0
        self._node_creation_order.clear()
        self._entries_by_node.clear()
        self._entries_by_type.clear()
        self._entries_by_import.clear()
        
        # Record fresh session creation
        self.session_id = str(uuid.uuid4())
        self._append(LedgerEventType.SESSION_CREATED, payload={
            'created_at': datetime.now().isoformat(),
            'session_id': self.session_id
        })

    @property
    def entry_count(self) -> int:
        return len(self._entries)
    
    @property
    def current_sequence(self) -> int:
        return self._sequence_counter - 1
    
    # =========================================================================
    # CORE APPEND - The only way to write to the ledger
    # =========================================================================
    
    def _append(self, 
                event_type: LedgerEventType,
                node_id: Optional[str] = None,
                connection_id: Optional[str] = None,
                source_language_id: Optional[int] = None,
                target_language_id: Optional[int] = None,
                canvas_language_id: Optional[int] = None,
                payload: Optional[Dict[str, Any]] = None,
                import_session_number: Optional[int] = None,
                creation_order: Optional[int] = None,
                global_order: Optional[int] = None) -> LedgerEntry:
        """
        Append a new immutable entry to the ledger.
        This is the ONLY way to write — no updates, no deletes.
        """
        seq = self._sequence_counter
        self._sequence_counter += 1
        
        entry = LedgerEntry(
            entry_id=f"{self.session_id}-{seq}",
            session_id=self.session_id,
            sequence_number=seq,
            timestamp=time.time(),
            event_type=event_type,
            node_id=node_id,
            connection_id=connection_id,
            source_language_id=source_language_id,
            target_language_id=target_language_id,
            canvas_language_id=canvas_language_id,
            payload=json.dumps(payload or {}),
            import_session_number=import_session_number,
            creation_order=creation_order,
            global_order=global_order
        )
        
        idx = len(self._entries)
        self._entries.append(entry)
        
        # Update indexes
        if node_id:
            self._entries_by_node.setdefault(node_id, []).append(idx)
        self._entries_by_type.setdefault(event_type, []).append(idx)
        if import_session_number is not None:
            self._entries_by_import.setdefault(import_session_number, []).append(idx)
        
        return entry
    
    # =========================================================================
    # IMPORT EVENTS - Recording what comes in
    # =========================================================================
    
    def begin_import(self, source_file: str, source_language: str, 
                     file_content: str = "",
                     dependency_strategy: str = "preserve") -> int:
        """
        Begin a new import session. Returns the import session number.
        Like opening a new Kafka consumer group for a batch.
        
        Args:
            dependency_strategy: How to handle imports/dependencies.
                'ignore'          - strip all imports
                'preserve'        - keep import statements as-is (default)
                'consolidate'     - resolve + inline dependency source
                'refactor_export' - consolidate + immediate export
        """
        self._import_counter += 1
        import_num = self._import_counter
        
        strategy = resolve_dependency_strategy(dependency_strategy)
        
        lang_id = resolve_language_id(source_language)
        
        self._append(
            LedgerEventType.FILE_IMPORTED,
            source_language_id=lang_id.value,
            payload={
                'source_file': source_file,
                'source_language': source_language,
                'language_id': lang_id.value,
                'import_session_number': import_num,
                'file_size': len(file_content),
                'file_hash': hash(file_content) & 0xFFFFFFFF,
                'dependency_strategy': strategy.value,
            },
            import_session_number=import_num
        )
        
        return import_num
    
    def get_dependency_strategy(self) -> DependencyStrategy:
        """Return the dependency strategy from the most recent import session.
        
        If multiple imports used different strategies, the latest one wins
        (the user can change strategy between imports).
        Falls back to PRESERVE if no imports have been recorded.
        """
        latest_strategy = DependencyStrategy.PRESERVE
        for entry in self._entries:
            if entry.event_type == LedgerEventType.FILE_IMPORTED:
                data = entry.get_payload()
                # Skip sub-events like 'file_imports'
                if data.get('event_subtype'):
                    continue
                strat = data.get('dependency_strategy', '')
                if strat:
                    latest_strategy = resolve_dependency_strategy(strat)
        return latest_strategy
    
    def record_file_imports(self, import_session_number: int,
                            imports: List[str], source_file: str = "") -> None:
        """Record the file-level import statements captured during parsing.
        
        These are the `import X` / `from X import Y` lines at the top of a source file.
        They don't become visual nodes but are needed for faithful code export.
        """
        if not imports:
            return
        self._append(
            LedgerEventType.FILE_IMPORTED,  # Reuse FILE_IMPORTED type
            payload={
                'event_subtype': 'file_imports',
                'imports': list(imports),
                'source_file': source_file,
                'import_session_number': import_session_number,
            },
            import_session_number=import_session_number
        )
    
    def get_file_imports(self) -> List[str]:
        """Retrieve all file-level import statements across all import sessions.
        
        Returns a deduplicated, sorted list of import lines.
        """
        all_imports: Set[str] = set()
        for entry in self._entries:
            if entry.event_type == LedgerEventType.FILE_IMPORTED:
                data = entry.get_payload()
                if data.get('event_subtype') == 'file_imports':
                    for imp in data.get('imports', []):
                        all_imports.add(imp)
        return sorted(all_imports)
    
    def record_node_imported(self, 
                              node_id: str,
                              node_type: str,
                              display_name: str,
                              raw_name: str,
                              source_code: str,
                              source_language: str,
                              source_file: str,
                              import_session_number: int,
                              class_name: Optional[str] = None,
                              parameters: Optional[Dict[str, Any]] = None,
                              inputs: Optional[List[Dict]] = None,
                              outputs: Optional[List[Dict]] = None,
                              metadata: Optional[Dict[str, Any]] = None) -> LedgerEntry:
        """
        Record a single node being created from an import.
        This captures the complete state at the moment of import.
        """
        self._global_node_counter += 1
        
        # Track order within this import
        import_nodes = [nid for nid, snap in self._node_snapshots.items() 
                       if snap.import_session_number == import_session_number]
        creation_order = len(import_nodes) + 1
        
        lang_id = resolve_language_id(source_language)
        
        entry = self._append(
            LedgerEventType.NODE_CREATED,
            node_id=node_id,
            source_language_id=lang_id.value,
            canvas_language_id=lang_id.value,  # Initially same as source
            payload={
                'node_type': node_type,
                'display_name': display_name,
                'raw_name': raw_name,
                'class_name': class_name,
                'source_code': source_code,
                'source_language': source_language,
                'source_file': source_file,
                'parameters': parameters or {},
                'inputs': inputs or [],
                'outputs': outputs or [],
                'metadata': metadata or {},
            },
            import_session_number=import_session_number,
            creation_order=creation_order,
            global_order=self._global_node_counter
        )
        
        # Create initial snapshot
        snapshot = NodeSnapshot(
            node_id=node_id,
            node_type=node_type,
            display_name=display_name,
            raw_name=raw_name,
            class_name=class_name,
            original_language_id=lang_id.value,
            current_language_id=lang_id.value,
            canvas_language_id=lang_id.value,
            original_source_code=source_code,
            current_source_code=source_code,
            parameters=parameters or {},
            inputs=inputs or [],
            outputs=outputs or [],
            metadata=metadata or {},
            import_session_number=import_session_number,
            creation_order_in_import=creation_order,
            global_creation_order=self._global_node_counter,
            source_file=source_file,
            version=0,
            code_versions=[{
                'version': 0,
                'source_code': source_code,
                'language_id': lang_id.value,
                'timestamp': time.time(),
                'reason': 'initial_import'
            }],
        )
        self._node_snapshots[node_id] = snapshot
        
        return entry
    
    # =========================================================================
    # MUTATION EVENTS - Recording changes
    # =========================================================================
    
    def record_code_edit(self, node_id: str, new_source_code: str, 
                         reason: str = "user_edit") -> Optional[LedgerEntry]:
        """Record a code edit on a node. Captures before/after."""
        snapshot = self._node_snapshots.get(node_id)
        if not snapshot:
            return None
        
        old_code = snapshot.current_source_code
        if old_code == new_source_code:
            return None  # No actual change
        
        snapshot.version += 1
        snapshot.current_source_code = new_source_code
        snapshot.is_modified = True
        snapshot.code_versions.append({
            'version': snapshot.version,
            'source_code': new_source_code,
            'language_id': snapshot.current_language_id,
            'timestamp': time.time(),
            'reason': reason
        })
        
        return self._append(
            LedgerEventType.NODE_CODE_EDITED,
            node_id=node_id,
            source_language_id=snapshot.current_language_id,
            payload={
                'version': snapshot.version,
                'old_code_hash': hash(old_code) & 0xFFFFFFFF,
                'new_code_hash': hash(new_source_code) & 0xFFFFFFFF,
                'old_code': old_code,
                'new_code': new_source_code,
                'reason': reason,
            }
        )
    
    def record_language_change(self, node_id: str, new_language: str,
                                new_source_code: str = "") -> Optional[LedgerEntry]:
        """Record a language conversion for a node."""
        snapshot = self._node_snapshots.get(node_id)
        if not snapshot:
            return None
        
        old_lang_id = snapshot.current_language_id
        new_lang_id = resolve_language_id(new_language).value
        
        snapshot.current_language_id = new_lang_id
        snapshot.canvas_language_id = new_lang_id
        snapshot.is_converted = True
        
        if new_source_code:
            snapshot.version += 1
            snapshot.current_source_code = new_source_code
            snapshot.code_versions.append({
                'version': snapshot.version,
                'source_code': new_source_code,
                'language_id': new_lang_id,
                'timestamp': time.time(),
                'reason': f'language_conversion_{resolve_language_string(LanguageID(old_lang_id))}_to_{new_language}'
            })
        
        return self._append(
            LedgerEventType.NODE_LANGUAGE_CHANGED,
            node_id=node_id,
            source_language_id=old_lang_id,
            target_language_id=new_lang_id,
            canvas_language_id=new_lang_id,
            payload={
                'old_language': resolve_language_string(LanguageID(old_lang_id)),
                'new_language': new_language,
                'old_language_id': old_lang_id,
                'new_language_id': new_lang_id,
                'new_source_code': new_source_code,
            }
        )
    
    def record_params_change(self, node_id: str, 
                              new_params: Dict[str, Any]) -> Optional[LedgerEntry]:
        """Record parameter changes on a node."""
        snapshot = self._node_snapshots.get(node_id)
        if not snapshot:
            return None
        
        old_params = copy.deepcopy(snapshot.parameters)
        snapshot.parameters = new_params
        snapshot.is_modified = True
        
        return self._append(
            LedgerEventType.NODE_PARAMS_CHANGED,
            node_id=node_id,
            payload={
                'old_params': old_params,
                'new_params': new_params,
            }
        )
    
    def record_io_change(self, node_id: str,
                          new_inputs: List[Dict], 
                          new_outputs: List[Dict]) -> Optional[LedgerEntry]:
        """Record input/output port changes on a node."""
        snapshot = self._node_snapshots.get(node_id)
        if not snapshot:
            return None
        
        old_inputs = snapshot.inputs
        old_outputs = snapshot.outputs
        snapshot.inputs = new_inputs
        snapshot.outputs = new_outputs
        snapshot.is_modified = True
        
        return self._append(
            LedgerEventType.NODE_IO_CHANGED,
            node_id=node_id,
            payload={
                'old_inputs': old_inputs,
                'new_inputs': new_inputs,
                'old_outputs': old_outputs,
                'new_outputs': new_outputs,
            }
        )
    
    def record_node_deleted(self, node_id: str) -> Optional[LedgerEntry]:
        """Record a node deletion. The snapshot is kept for history."""
        snapshot = self._node_snapshots.get(node_id)
        if not snapshot:
            return None
        
        return self._append(
            LedgerEventType.NODE_DELETED,
            node_id=node_id,
            payload={
                'deleted_node_type': snapshot.node_type,
                'deleted_raw_name': snapshot.raw_name,
                'had_source_code': bool(snapshot.current_source_code),
            }
        )
    
    def record_node_moved(self, node_id: str, 
                           new_position: Tuple[float, float]) -> Optional[LedgerEntry]:
        """Record a node position change (lightweight, no payload)."""
        return self._append(
            LedgerEventType.NODE_MOVED,
            node_id=node_id,
            payload={'position': list(new_position)}
        )
    
    # =========================================================================
    # CONNECTION EVENTS
    # =========================================================================
    
    def record_connection_created(self, connection_id: str,
                                   source_node_id: str, source_port: str,
                                   target_node_id: str, target_port: str) -> LedgerEntry:
        """Record a new connection between nodes."""
        # Mark both nodes as connected
        for nid in (source_node_id, target_node_id):
            snap = self._node_snapshots.get(nid)
            if snap:
                snap.is_connected = True
        
        return self._append(
            LedgerEventType.CONNECTION_CREATED,
            connection_id=connection_id,
            payload={
                'source_node_id': source_node_id,
                'source_port': source_port,
                'target_node_id': target_node_id,
                'target_port': target_port,
            }
        )
    
    def record_connection_deleted(self, connection_id: str) -> LedgerEntry:
        """Record a connection deletion."""
        return self._append(
            LedgerEventType.CONNECTION_DELETED,
            connection_id=connection_id
        )
    
    # =========================================================================
    # EXPORT EVENTS  
    # =========================================================================
    
    def record_export_started(self, target_language: str, 
                               options: Dict[str, Any]) -> LedgerEntry:
        """Record that an export has been initiated."""
        lang_id = resolve_language_id(target_language)
        return self._append(
            LedgerEventType.EXPORT_STARTED,
            target_language_id=lang_id.value,
            payload={
                'target_language': target_language,
                'target_language_id': lang_id.value,
                'export_options': options,
                'node_count': len(self.get_active_node_ids()),
            }
        )
    
    def record_export_completed(self, target_language: str,
                                 success: bool, 
                                 code_hash: Optional[int] = None,
                                 error: Optional[str] = None) -> LedgerEntry:
        """Record that an export has completed."""
        return self._append(
            LedgerEventType.EXPORT_COMPLETED,
            payload={
                'target_language': target_language,
                'success': success,
                'code_hash': code_hash,
                'error': error,
            }
        )
    
    # =========================================================================
    # EXECUTION EVENTS - Recording live execution results
    # =========================================================================
    
    def record_node_executed(self, node_id: str, success: bool,
                              output: str = "", error: str = "",
                              execution_time: float = 0.0,
                              variables: Optional[Dict[str, Any]] = None,
                              code_version: Optional[int] = None) -> Optional[LedgerEntry]:
        """Record the result of executing a node's current source code.
        
        This is an immutable log entry — every execution is preserved,
        so you can see the full run history per node.
        """
        snapshot = self._node_snapshots.get(node_id)
        if not snapshot:
            return None
        
        return self._append(
            LedgerEventType.NODE_EXECUTED,
            node_id=node_id,
            source_language_id=snapshot.current_language_id,
            payload={
                'success': success,
                'output': output[:10000],  # cap to avoid huge payloads
                'error': error[:5000] if error else '',
                'execution_time': execution_time,
                'variables': _safe_serialize_vars(variables or {}),
                'code_version': code_version if code_version is not None else snapshot.version,
                'language': resolve_language_string(LanguageID(snapshot.current_language_id)),
            }
        )
    
    def record_execution_batch(self, node_ids: List[str], success: bool,
                                total_time: float = 0.0,
                                error: str = "") -> LedgerEntry:
        """Record a batch execution of multiple nodes (e.g. run-all)."""
        return self._append(
            LedgerEventType.EXECUTION_BATCH,
            payload={
                'node_ids': node_ids,
                'node_count': len(node_ids),
                'success': success,
                'total_time': total_time,
                'error': error[:5000] if error else '',
            }
        )
    
    def get_node_executions(self, node_id: str) -> List[LedgerEntry]:
        """Get all execution events for a specific node."""
        history = self.get_node_history(node_id)
        return [e for e in history if e.event_type == LedgerEventType.NODE_EXECUTED]
    
    # =========================================================================
    # QUERIES - Reading from the ledger
    # =========================================================================
    
    def get_node_snapshot(self, node_id: str) -> Optional[NodeSnapshot]:
        """Get the current materialized state of a node."""
        return self._node_snapshots.get(node_id)
    
    def get_all_snapshots(self) -> Dict[str, NodeSnapshot]:
        """Get all current node snapshots."""
        return dict(self._node_snapshots)
    
    def get_active_node_ids(self) -> Set[str]:
        """Get IDs of all nodes that haven't been deleted."""
        deleted = set()
        for entry in self._entries:
            if entry.event_type == LedgerEventType.NODE_DELETED and entry.node_id:
                deleted.add(entry.node_id)
        return set(self._node_snapshots.keys()) - deleted
    
    def get_active_snapshots(self) -> Dict[str, NodeSnapshot]:
        """Get snapshots of all active (non-deleted) nodes."""
        active_ids = self.get_active_node_ids()
        return {nid: snap for nid, snap in self._node_snapshots.items() if nid in active_ids}
    
    def get_node_history(self, node_id: str) -> List[LedgerEntry]:
        """Get the full history of a node — every event that touched it."""
        indexes = self._entries_by_node.get(node_id, [])
        return [self._entries[i] for i in indexes]
    
    def get_import_history(self, import_session: int) -> List[LedgerEntry]:
        """Get all events from a specific import session."""
        indexes = self._entries_by_import.get(import_session, [])
        return [self._entries[i] for i in indexes]
    
    def get_events_by_type(self, event_type: LedgerEventType) -> List[LedgerEntry]:
        """Get all events of a specific type."""
        indexes = self._entries_by_type.get(event_type, [])
        return [self._entries[i] for i in indexes]
    
    def get_entries_range(self, start_seq: int, end_seq: int) -> List[LedgerEntry]:
        """Get entries in a sequence range — like Kafka offset-based reads."""
        return [e for e in self._entries 
                if start_seq <= e.sequence_number <= end_seq]
    
    def get_full_ledger(self) -> List[LedgerEntry]:
        """Get the entire ledger — open the whole bag of crackers."""
        return list(self._entries)
    
    # =========================================================================
    # EXPORT SUPPORT - Getting data ready for code generation
    # =========================================================================
    
    def get_nodes_for_export(self, target_language: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get all active nodes prepared for export.
        This is the critical method — it produces the data that makes export work.
        
        Returns nodes ordered by:
        1. Import session number (which import they came from)
        2. Global creation order (preserving original file order)
        
        Each node includes its full lineage: original source, current source,
        language trail, modification history.
        """
        active = self.get_active_snapshots()
        
        # Sort by global creation order to preserve original code structure
        sorted_nodes = sorted(active.values(), 
                             key=lambda s: (s.import_session_number, s.global_creation_order))
        
        export_data = []
        for snapshot in sorted_nodes:
            node_data = snapshot.to_export_dict()
            
            # Add lineage summary
            history = self.get_node_history(snapshot.node_id)
            node_data['edit_count'] = sum(1 for h in history 
                                          if h.event_type == LedgerEventType.NODE_CODE_EDITED)
            node_data['language_changes'] = sum(1 for h in history 
                                                 if h.event_type == LedgerEventType.NODE_LANGUAGE_CHANGED)
            
            export_data.append(node_data)
        
        return export_data
    
    def get_nodes_grouped_by_class(self, target_language: Optional[str] = None) -> Dict[str, List[Dict]]:
        """
        Group nodes by class for proper OOP code generation.
        Returns: {'ClassName': [methods...], None: [standalone_functions...]}
        """
        nodes = self.get_nodes_for_export(target_language)
        grouped: Dict[str, List[Dict]] = {'__standalone__': []}
        
        for node in nodes:
            class_name = node.get('class_name')
            if class_name:
                grouped.setdefault(class_name, []).append(node)
            else:
                grouped['__standalone__'].append(node)
        
        return grouped
    
    def get_import_summary(self) -> List[Dict[str, Any]]:
        """Get a summary of all import sessions."""
        summaries = []
        for i in range(1, self._import_counter + 1):
            entries = self.get_import_history(i)
            if not entries:
                continue
            
            file_entry = next((e for e in entries 
                              if e.event_type == LedgerEventType.FILE_IMPORTED), None)
            node_entries = [e for e in entries 
                           if e.event_type == LedgerEventType.NODE_CREATED]
            
            summaries.append({
                'import_session': i,
                'source_file': file_entry.get_payload().get('source_file', '') if file_entry else '',
                'source_language': file_entry.get_payload().get('source_language', '') if file_entry else '',
                'node_count': len(node_entries),
                'timestamp': file_entry.timestamp if file_entry else 0,
            })
        
        return summaries
    
    # =========================================================================
    # SERIALIZATION - Persist/restore the ledger
    # =========================================================================
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize the entire ledger to a dict (for DB storage or JSON export)."""
        return {
            'session_id': self.session_id,
            'sequence_counter': self._sequence_counter,
            'import_counter': self._import_counter,
            'global_node_counter': self._global_node_counter,
            'entries': [
                {
                    'entry_id': e.entry_id,
                    'session_id': e.session_id,
                    'sequence_number': e.sequence_number,
                    'timestamp': e.timestamp,
                    'event_type': e.event_type.value,
                    'node_id': e.node_id,
                    'connection_id': e.connection_id,
                    'source_language_id': e.source_language_id,
                    'target_language_id': e.target_language_id,
                    'canvas_language_id': e.canvas_language_id,
                    'payload': e.payload,
                    'import_session_number': e.import_session_number,
                    'creation_order': e.creation_order,
                    'global_order': e.global_order,
                }
                for e in self._entries
            ],
            'snapshots': {
                nid: {
                    'node_id': s.node_id,
                    'node_type': s.node_type,
                    'display_name': s.display_name,
                    'raw_name': s.raw_name,
                    'class_name': s.class_name,
                    'original_language_id': s.original_language_id,
                    'current_language_id': s.current_language_id,
                    'canvas_language_id': s.canvas_language_id,
                    'original_source_code': s.original_source_code,
                    'current_source_code': s.current_source_code,
                    'parameters': s.parameters,
                    'inputs': s.inputs,
                    'outputs': s.outputs,
                    'metadata': s.metadata,
                    'import_session_number': s.import_session_number,
                    'creation_order_in_import': s.creation_order_in_import,
                    'global_creation_order': s.global_creation_order,
                    'source_file': s.source_file,
                    'version': s.version,
                    'code_versions': s.code_versions,
                    'is_modified': s.is_modified,
                    'is_converted': s.is_converted,
                    'is_connected': s.is_connected,
                }
                for nid, s in self._node_snapshots.items()
            }
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SessionLedger':
        """Restore a ledger from serialized data."""
        ledger = cls.__new__(cls)
        ledger.session_id = data['session_id']
        ledger._sequence_counter = data['sequence_counter']
        ledger._import_counter = data['import_counter']
        ledger._global_node_counter = data['global_node_counter']
        
        # Restore entries
        ledger._entries = []
        ledger._entries_by_node = {}
        ledger._entries_by_type = {}
        ledger._entries_by_import = {}
        
        for i, ed in enumerate(data['entries']):
            entry = LedgerEntry(
                entry_id=ed['entry_id'],
                session_id=ed['session_id'],
                sequence_number=ed['sequence_number'],
                timestamp=ed['timestamp'],
                event_type=LedgerEventType(ed['event_type']),
                node_id=ed.get('node_id'),
                connection_id=ed.get('connection_id'),
                source_language_id=ed.get('source_language_id'),
                target_language_id=ed.get('target_language_id'),
                canvas_language_id=ed.get('canvas_language_id'),
                payload=ed.get('payload', '{}'),
                import_session_number=ed.get('import_session_number'),
                creation_order=ed.get('creation_order'),
                global_order=ed.get('global_order'),
            )
            ledger._entries.append(entry)
            
            if entry.node_id:
                ledger._entries_by_node.setdefault(entry.node_id, []).append(i)
            ledger._entries_by_type.setdefault(entry.event_type, []).append(i)
            if entry.import_session_number is not None:
                ledger._entries_by_import.setdefault(entry.import_session_number, []).append(i)
        
        # Restore snapshots
        ledger._node_snapshots = {}
        for nid, sd in data.get('snapshots', {}).items():
            ledger._node_snapshots[nid] = NodeSnapshot(
                node_id=sd['node_id'],
                node_type=sd['node_type'],
                display_name=sd['display_name'],
                raw_name=sd['raw_name'],
                class_name=sd.get('class_name'),
                original_language_id=sd['original_language_id'],
                current_language_id=sd['current_language_id'],
                canvas_language_id=sd.get('canvas_language_id', sd['current_language_id']),
                original_source_code=sd['original_source_code'],
                current_source_code=sd['current_source_code'],
                parameters=sd.get('parameters', {}),
                inputs=sd.get('inputs', []),
                outputs=sd.get('outputs', []),
                metadata=sd.get('metadata', {}),
                import_session_number=sd['import_session_number'],
                creation_order_in_import=sd['creation_order_in_import'],
                global_creation_order=sd['global_creation_order'],
                source_file=sd.get('source_file', ''),
                version=sd['version'],
                code_versions=sd.get('code_versions', []),
                is_modified=sd.get('is_modified', False),
                is_converted=sd.get('is_converted', False),
                is_connected=sd.get('is_connected', False),
            )
        
        ledger._node_creation_order = {}
        
        return ledger
    
    # =========================================================================
    # DIAGNOSTICS
    # =========================================================================
    
    def get_session_stats(self) -> Dict[str, Any]:
        """Get statistics about the current session."""
        active_ids = self.get_active_node_ids()
        active_snapshots = {nid: self._node_snapshots[nid] for nid in active_ids 
                           if nid in self._node_snapshots}
        
        # Count languages in use
        languages = set()
        for snap in active_snapshots.values():
            languages.add(snap.current_language_id)
        
        return {
            'session_id': self.session_id,
            'total_events': len(self._entries),
            'current_sequence': self.current_sequence,
            'import_sessions': self._import_counter,
            'total_nodes_created': self._global_node_counter,
            'active_nodes': len(active_ids),
            'deleted_nodes': len(self._node_snapshots) - len(active_ids),
            'modified_nodes': sum(1 for s in active_snapshots.values() if s.is_modified),
            'converted_nodes': sum(1 for s in active_snapshots.values() if s.is_converted),
            'connected_nodes': sum(1 for s in active_snapshots.values() if s.is_connected),
            'languages_in_use': [resolve_language_string(LanguageID(lid)) for lid in languages if lid != LanguageID.UNKNOWN],
            'events_by_type': {
                evt.value: len(idxs) 
                for evt, idxs in self._entries_by_type.items()
            }
        }
    
    def __repr__(self) -> str:
        stats = self.get_session_stats()
        return (f"SessionLedger(session={self.session_id[:8]}..., "
                f"events={stats['total_events']}, "
                f"active_nodes={stats['active_nodes']}, "
                f"imports={stats['import_sessions']})")
