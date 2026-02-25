"""
Snippet Staging Pipeline — Speculative Execution & Promotion to Production.

This module implements a 4-phase lifecycle for code snippets injected via
the engine tab system:

    ┌─────────────────────────────────────────────────────────────┐
    │  Phase 1: QUEUE                                             │
    │    Snippet arrives → assigned a staging_id → slot RESERVED  │
    │    on the target engine row (position held, not yet live).  │
    │                                                              │
    │  Phase 2: SPECULATIVE EXECUTION (dry-run)                   │
    │    Executor runs the code in an ISOLATED sandbox.           │
    │    Output, errors, timing, and variables are captured.      │
    │    The production namespace is NOT touched.                 │
    │                                                              │
    │  Phase 3: VERDICT (pass / fail / manual)                    │
    │    If pass  → auto-promote to Phase 4                       │
    │    If fail  → reject, release reserved slot, log reason     │
    │    If manual → hold for human approval                      │
    │                                                              │
    │  Phase 4: PROMOTE TO PRODUCTION                             │
    │    • Code written to `snippets/<lang>/<staging_id>.ext`     │
    │    • Synthetic node created in the SessionLedger            │
    │    • Node committed to the NodeRegistry (reserved slot)     │
    │    • Full audit trail: staging log, speculative output,     │
    │      promotion timestamp, executor version, hash, etc.      │
    └─────────────────────────────────────────────────────────────┘

Every event is logged to an append-only audit ledger (JSON-lines).
Path is configurable via:  DB setting → SPOKEDPY_AUDIT_LOG env → data/staging_audit.jsonl

The staging folder structure (configurable via DB setting → SPOKEDPY_SNIPPETS_DIR env → data/snippets/):
    data/snippets/
        python/    → .py files
        javascript/ → .js files
        typescript/ → .ts files
        java/      → .java files
        go/        → .go files
        csharp/    → .cs files
        bash/      → .sh files
        rust/      → .rs files
        ...
"""

import os
import json
import time
import uuid
import hashlib
import shutil
import threading
import traceback
from enum import Enum
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Tuple
from pathlib import Path


# ── File extensions per language ────────────────────────────────────────────
LANG_EXTENSIONS = {
    'python':     '.py',
    'javascript': '.js',
    'typescript': '.ts',
    'rust':       '.rs',
    'java':       '.java',
    'swift':      '.swift',
    'cpp':        '.cpp',
    'c':          '.c',
    'r':          '.r',
    'go':         '.go',
    'ruby':       '.rb',
    'csharp':     '.cs',
    'kotlin':     '.kt',
    'bash':       '.sh',
    'perl':       '.pl',
}

# Engine letter → language string
LETTER_TO_LANG = {
    'a': 'python', 'b': 'javascript', 'c': 'typescript', 'd': 'rust',
    'e': 'java',   'f': 'swift',      'g': 'cpp',        'h': 'r',
    'i': 'go',     'j': 'ruby',       'k': 'csharp',     'l': 'kotlin',
    'm': 'c',      'n': 'bash',       'o': 'perl',
}

LANG_TO_LETTER = {v: k for k, v in LETTER_TO_LANG.items()}


# ═══════════════════════════════════════════════════════════════════════════
# STAGING LIFECYCLE
# ═══════════════════════════════════════════════════════════════════════════

class StagingPhase(str, Enum):
    """Lifecycle phase of a staged snippet."""
    QUEUED       = 'queued'          # Received, slot reserved
    SPECULATING  = 'speculating'     # Dry-run executing
    PASSED       = 'passed'          # Speculative run succeeded
    FAILED       = 'failed'          # Speculative run failed
    PROMOTING    = 'promoting'       # Writing to disk / ledger / registry
    PROMOTED     = 'promoted'        # Live in production
    REJECTED     = 'rejected'        # Manually or auto-rejected
    ROLLED_BACK  = 'rolled_back'     # Was promoted, then rolled back


class AuditEventType(str, Enum):
    """Types of events recorded in the audit trail."""
    SNIPPET_QUEUED         = 'snippet_queued'
    SLOT_RESERVED          = 'slot_reserved'
    SPEC_EXEC_STARTED      = 'spec_exec_started'
    SPEC_EXEC_COMPLETED    = 'spec_exec_completed'
    SPEC_EXEC_FAILED       = 'spec_exec_failed'
    VERDICT_PASS           = 'verdict_pass'
    VERDICT_FAIL           = 'verdict_fail'
    VERDICT_MANUAL_HOLD    = 'verdict_manual_hold'
    PROMOTION_STARTED      = 'promotion_started'
    FILE_WRITTEN           = 'file_written'
    LEDGER_NODE_CREATED    = 'ledger_node_created'
    REGISTRY_SLOT_COMMITTED = 'registry_slot_committed'
    PROMOTION_COMPLETED    = 'promotion_completed'
    REJECTION              = 'rejection'
    ROLLBACK               = 'rollback'
    SLOT_RELEASED          = 'slot_released'
    ERROR                  = 'error'


# ═══════════════════════════════════════════════════════════════════════════
# STAGED SNIPPET — One entry in the pipeline
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class StagedSnippet:
    """A snippet progressing through the staging pipeline."""

    # ── Identity ──────────────────────────────────────────────────────────
    staging_id: str                          # Unique staging ID (uuid)
    language: str                            # e.g. 'python'
    engine_letter: str                       # e.g. 'a'
    label: str                               # Human-readable name
    code: str                                # The snippet source code
    code_hash: str                           # SHA-256 of the code

    # ── Lifecycle ─────────────────────────────────────────────────────────
    phase: StagingPhase = StagingPhase.QUEUED
    created_at: float = 0.0                  # Unix timestamp
    updated_at: float = 0.0

    # ── Slot reservation ──────────────────────────────────────────────────
    reserved_engine: str = ''                # EngineID name (e.g. 'PYTHON')
    reserved_position: int = 0               # Slot position in engine row
    reserved_address: str = ''               # e.g. 'a3'

    # ── Speculative execution results ─────────────────────────────────────
    spec_output: str = ''
    spec_error: str = ''
    spec_execution_time: float = 0.0
    spec_success: bool = False
    spec_variables: Dict[str, Any] = field(default_factory=dict)
    spec_started_at: float = 0.0
    spec_completed_at: float = 0.0

    # ── Promotion details ─────────────────────────────────────────────────
    saved_file_path: str = ''                # Path where snippet was saved
    ledger_node_id: str = ''                 # Node ID in the SessionLedger
    registry_slot_id: str = ''               # Slot ID in the NodeRegistry (nra##)
    promoted_at: float = 0.0

    # ── Rejection / rollback ──────────────────────────────────────────────
    rejection_reason: str = ''
    rejection_at: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d['phase'] = self.phase.value
        # Truncate large fields for API responses
        if len(d.get('spec_output', '')) > 5000:
            d['spec_output'] = d['spec_output'][:5000] + '\n…(truncated)'
        if len(d.get('code', '')) > 10000:
            d['code'] = d['code'][:10000] + '\n…(truncated)'
        return d


# ═══════════════════════════════════════════════════════════════════════════
# AUDIT LOGGER — append-only forensic event trail
# ═══════════════════════════════════════════════════════════════════════════

class AuditLogger:
    """Append-only JSON-lines audit log for the staging pipeline.

    Every event — queue, reserve, spec-exec, verdict, promote, reject —
    gets an immutable line in the log. These are never modified or deleted.
    """

    def __init__(self, log_path: str):
        self._path = log_path
        self._lock = threading.Lock()
        # Ensure directory exists
        os.makedirs(os.path.dirname(log_path) or '.', exist_ok=True)

    def log(self, event_type: AuditEventType, staging_id: str,
            data: Optional[Dict[str, Any]] = None):
        """Append a single audit event."""
        entry = {
            'timestamp': time.time(),
            'iso_time': time.strftime('%Y-%m-%dT%H:%M:%S', time.gmtime()),
            'event': event_type.value,
            'staging_id': staging_id,
            'data': data or {},
        }
        with self._lock:
            with open(self._path, 'a', encoding='utf-8') as f:
                f.write(json.dumps(entry, default=str) + '\n')

    def read_all(self, limit: int = 500) -> List[Dict]:
        """Read the last N audit entries (newest first)."""
        if not os.path.exists(self._path):
            return []
        with self._lock:
            with open(self._path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
        entries = []
        for line in reversed(lines[-limit:]):
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
        return entries

    def read_for_staging_id(self, staging_id: str) -> List[Dict]:
        """Get the full audit trail for one staging ID."""
        all_entries = self.read_all(limit=10000)
        return [e for e in all_entries if e.get('staging_id') == staging_id]


# ═══════════════════════════════════════════════════════════════════════════
# STAGING PIPELINE — The main engine
# ═══════════════════════════════════════════════════════════════════════════

class StagingPipeline:
    """
    Manages the full snippet lifecycle:
        queue → speculate → verdict → promote (or reject)

    Thread-safe. All state mutations go through `_lock`.

    Dependencies:
        - executors: Dict[str, executor]    — language → executor instance
        - node_registry: NodeRegistry       — for slot reservation & commit
        - session_ledger: SessionLedger     — for creating synthetic nodes
        - snippets_dir: str                 — where promoted snippets are saved
        - audit_log_path: str               — path to the JSONL audit file
    """

    def __init__(self, executors: Dict, node_registry, session_ledger,
                 snippets_dir: str = 'web_interface/snippets',
                 audit_log_path: str = 'web_interface/staging_audit.jsonl'):
        self._executors = executors
        self._registry = node_registry
        self._ledger = session_ledger
        self._snippets_dir = snippets_dir
        self._audit = AuditLogger(audit_log_path)
        self._lock = threading.RLock()

        # Active staging entries: staging_id → StagedSnippet
        self._staged: Dict[str, StagedSnippet] = {}

        # History of completed (promoted / rejected / rolled-back) snippets
        self._history: List[StagedSnippet] = []

        # Reserved positions: engine_name → set of positions held
        self._reserved_positions: Dict[str, set] = {}

        # Ensure snippet directories exist
        for lang in LANG_EXTENSIONS:
            os.makedirs(os.path.join(self._snippets_dir, lang), exist_ok=True)

    # ─────────────────────────────────────────────────────────────────────
    # PHASE 1: QUEUE — receive snippet, reserve a slot
    # ─────────────────────────────────────────────────────────────────────

    def queue_snippet(self, engine_letter: str, language: str, code: str,
                      label: str = '') -> StagedSnippet:
        """
        Accept a snippet into the staging pipeline.

        1. Generates a staging_id
        2. Computes a SHA-256 hash of the code
        3. Reserves the next free slot on the target engine row
        4. Returns the StagedSnippet in QUEUED phase

        Raises ValueError if the engine row is full.
        """
        now = time.time()
        staging_id = f"stg-{uuid.uuid4().hex[:12]}"
        code_hash = hashlib.sha256(code.encode('utf-8')).hexdigest()
        lang = language.lower().strip()

        # Resolve engine
        from .node_registry import LETTER_TO_ENGINE, LANGUAGE_STRING_TO_ENGINE
        engine = LETTER_TO_ENGINE.get(engine_letter)
        if engine is None:
            engine = LANGUAGE_STRING_TO_ENGINE.get(lang)
        if engine is None:
            raise ValueError(f"Unknown engine for letter='{engine_letter}' language='{lang}'")

        engine_name = engine.name

        # Reserve a slot position (don't actually commit yet)
        reserved_pos = self._reserve_position(engine_name)
        address = f"{engine_letter}{reserved_pos}"

        snippet = StagedSnippet(
            staging_id=staging_id,
            language=lang,
            engine_letter=engine_letter,
            label=label or f"snippet-{staging_id[:8]}",
            code=code,
            code_hash=code_hash,
            phase=StagingPhase.QUEUED,
            created_at=now,
            updated_at=now,
            reserved_engine=engine_name,
            reserved_position=reserved_pos,
            reserved_address=address,
        )

        with self._lock:
            self._staged[staging_id] = snippet

        self._audit.log(AuditEventType.SNIPPET_QUEUED, staging_id, {
            'language': lang,
            'engine_letter': engine_letter,
            'label': snippet.label,
            'code_hash': code_hash,
            'code_length': len(code),
        })
        self._audit.log(AuditEventType.SLOT_RESERVED, staging_id, {
            'engine': engine_name,
            'position': reserved_pos,
            'address': address,
        })

        return snippet

    def _reserve_position(self, engine_name: str) -> int:
        """
        Find and reserve the next free slot position on an engine row.
        The reservation is held in memory — the registry slot is NOT
        created until promotion.
        """
        with self._lock:
            row = self._registry.get_engine_row(engine_name)
            if row is None:
                raise ValueError(f"Engine row '{engine_name}' not found")

            reserved = self._reserved_positions.get(engine_name, set())

            for pos in range(1, row.max_slots + 1):
                # Skip positions that are already committed OR reserved
                existing_slot = row.slots.get(pos)
                if existing_slot and existing_slot.node_id is not None:
                    continue
                if pos in reserved:
                    continue
                # Found a free position — reserve it
                self._reserved_positions.setdefault(engine_name, set()).add(pos)
                return pos

            raise ValueError(
                f"Engine '{engine_name}' has no free slots "
                f"(max={row.max_slots}, occupied={len(row.occupied_positions())}, "
                f"reserved={len(reserved)})"
            )

    def _release_position(self, engine_name: str, position: int):
        """Release a reserved position back to the pool."""
        with self._lock:
            reserved = self._reserved_positions.get(engine_name, set())
            reserved.discard(position)

    # ─────────────────────────────────────────────────────────────────────
    # PHASE 2: SPECULATIVE EXECUTION — isolated dry-run
    # ─────────────────────────────────────────────────────────────────────

    def speculate(self, staging_id: str) -> StagedSnippet:
        """
        Run the snippet in an ISOLATED executor (not the production one).

        For Python: creates a fresh PythonExecutor with an empty namespace.
        For subprocess languages: they're already isolated by design.

        Returns the snippet with spec_* fields populated.
        """
        with self._lock:
            snippet = self._staged.get(staging_id)
            if snippet is None:
                raise ValueError(f"No staged snippet with id '{staging_id}'")
            if snippet.phase not in (StagingPhase.QUEUED, StagingPhase.FAILED):
                raise ValueError(
                    f"Snippet {staging_id} is in phase '{snippet.phase.value}', "
                    f"cannot speculate (must be QUEUED or FAILED)"
                )
            snippet.phase = StagingPhase.SPECULATING
            snippet.updated_at = time.time()
            snippet.spec_started_at = time.time()

        self._audit.log(AuditEventType.SPEC_EXEC_STARTED, staging_id, {
            'language': snippet.language,
            'code_hash': snippet.code_hash,
            'reserved_address': snippet.reserved_address,
        })

        try:
            result = self._run_isolated(snippet.language, snippet.code)

            with self._lock:
                snippet.spec_output = result.get('output', '')
                snippet.spec_error = result.get('error', '')
                snippet.spec_execution_time = result.get('execution_time', 0.0)
                snippet.spec_success = result.get('success', False)
                snippet.spec_variables = result.get('variables', {})
                snippet.spec_completed_at = time.time()
                snippet.updated_at = time.time()

                if snippet.spec_success:
                    snippet.phase = StagingPhase.PASSED
                    self._audit.log(AuditEventType.SPEC_EXEC_COMPLETED, staging_id, {
                        'success': True,
                        'execution_time': snippet.spec_execution_time,
                        'output_length': len(snippet.spec_output),
                        'variables_count': len(snippet.spec_variables),
                    })
                else:
                    snippet.phase = StagingPhase.FAILED
                    self._audit.log(AuditEventType.SPEC_EXEC_FAILED, staging_id, {
                        'success': False,
                        'error': snippet.spec_error[:2000],
                        'execution_time': snippet.spec_execution_time,
                    })

        except Exception as exc:
            with self._lock:
                snippet.spec_error = str(exc)
                snippet.spec_completed_at = time.time()
                snippet.spec_success = False
                snippet.phase = StagingPhase.FAILED
                snippet.updated_at = time.time()

            self._audit.log(AuditEventType.SPEC_EXEC_FAILED, staging_id, {
                'success': False,
                'error': str(exc),
                'traceback': traceback.format_exc()[:3000],
            })

        return snippet

    def _run_isolated(self, language: str, code: str) -> Dict[str, Any]:
        """
        Execute code in an ISOLATED environment.

        For Python: creates a FRESH PythonExecutor (empty namespace) so
        that the speculative run cannot see or pollute the production
        namespace.

        For all subprocess-based languages (JS, Go, Rust, etc.): the
        executor already runs in an isolated child process, so we can
        use the shared instance safely.
        """
        lang = language.lower().strip()

        if lang == 'python':
            # Create a disposable executor with a clean namespace
            from .execution_engine import PythonExecutor
            sandbox = PythonExecutor()
            result = sandbox.execute(code)
            variables = {}
            if result.variables:
                for k, v in result.variables.items():
                    if k.startswith('__'):
                        continue
                    try:
                        json.dumps(v)
                        variables[k] = v
                    except (TypeError, ValueError):
                        variables[k] = repr(v)[:200]
            return {
                'success': result.success,
                'output': result.output or '',
                'error': str(result.error) if result.error else '',
                'execution_time': result.execution_time,
                'variables': variables,
            }
        else:
            # Subprocess-based: already isolated
            executor = self._executors.get(lang)
            if executor is None:
                return {
                    'success': False,
                    'output': '',
                    'error': f'No executor for language "{lang}"',
                    'execution_time': 0,
                    'variables': {},
                }
            result = executor.execute(code)
            return {
                'success': result.success,
                'output': result.output or '',
                'error': str(result.error) if result.error else '',
                'execution_time': result.execution_time,
                'variables': {},
            }

    # ─────────────────────────────────────────────────────────────────────
    # PHASE 3: VERDICT — pass / fail / manual hold
    # ─────────────────────────────────────────────────────────────────────

    def verdict(self, staging_id: str, action: str = 'auto',
                reason: str = '') -> StagedSnippet:
        """
        Issue a verdict on a speculated snippet.

        action:
            'auto'    — use the speculative result (pass → promote, fail → reject)
            'approve' — force-approve (human override, even if spec failed)
            'reject'  — force-reject (human override, even if spec passed)
            'hold'    — mark for manual review (no auto-action)

        Returns the updated snippet.
        """
        with self._lock:
            snippet = self._staged.get(staging_id)
            if snippet is None:
                raise ValueError(f"No staged snippet '{staging_id}'")

            if action == 'auto':
                if snippet.phase == StagingPhase.PASSED:
                    self._audit.log(AuditEventType.VERDICT_PASS, staging_id, {
                        'mode': 'auto',
                        'spec_success': True,
                    })
                    # Will promote in the next step
                    return snippet
                elif snippet.phase == StagingPhase.FAILED:
                    snippet.rejection_reason = reason or snippet.spec_error[:500]
                    snippet.rejection_at = time.time()
                    snippet.phase = StagingPhase.REJECTED
                    snippet.updated_at = time.time()
                    self._release_position(snippet.reserved_engine, snippet.reserved_position)
                    self._audit.log(AuditEventType.VERDICT_FAIL, staging_id, {
                        'mode': 'auto',
                        'reason': snippet.rejection_reason,
                    })
                    self._archive_snippet(snippet)
                    return snippet
                else:
                    raise ValueError(
                        f"Cannot auto-verdict snippet in phase '{snippet.phase.value}' "
                        f"(must be PASSED or FAILED)"
                    )

            elif action == 'approve':
                snippet.phase = StagingPhase.PASSED
                snippet.updated_at = time.time()
                self._audit.log(AuditEventType.VERDICT_PASS, staging_id, {
                    'mode': 'manual_approve',
                    'reason': reason,
                })
                return snippet

            elif action == 'reject':
                snippet.rejection_reason = reason or 'Manually rejected'
                snippet.rejection_at = time.time()
                snippet.phase = StagingPhase.REJECTED
                snippet.updated_at = time.time()
                self._release_position(snippet.reserved_engine, snippet.reserved_position)
                self._audit.log(AuditEventType.REJECTION, staging_id, {
                    'mode': 'manual_reject',
                    'reason': reason,
                })
                self._archive_snippet(snippet)
                return snippet

            elif action == 'hold':
                self._audit.log(AuditEventType.VERDICT_MANUAL_HOLD, staging_id, {
                    'reason': reason or 'Awaiting manual review',
                })
                return snippet

            else:
                raise ValueError(f"Unknown verdict action: '{action}'")

    # ─────────────────────────────────────────────────────────────────────
    # PHASE 4: PROMOTE — write to disk, ledger, registry
    # ─────────────────────────────────────────────────────────────────────

    def promote(self, staging_id: str) -> StagedSnippet:
        """
        Promote a PASSED snippet to production.

        Steps:
            1. Write the code to `snippets/<lang>/<staging_id>.<ext>`
            2. Create a synthetic node in the SessionLedger
            3. Commit the node to the reserved slot in the NodeRegistry
            4. Log every step to the audit trail

        Returns the snippet in PROMOTED phase.
        Raises ValueError if the snippet is not in PASSED phase.
        """
        with self._lock:
            snippet = self._staged.get(staging_id)
            if snippet is None:
                raise ValueError(f"No staged snippet '{staging_id}'")
            if snippet.phase != StagingPhase.PASSED:
                raise ValueError(
                    f"Cannot promote snippet in phase '{snippet.phase.value}' "
                    f"(must be PASSED)"
                )
            snippet.phase = StagingPhase.PROMOTING
            snippet.updated_at = time.time()

        self._audit.log(AuditEventType.PROMOTION_STARTED, staging_id, {
            'reserved_address': snippet.reserved_address,
            'code_hash': snippet.code_hash,
        })

        try:
            # ── Step 1: Write code to disk ────────────────────────────────
            ext = LANG_EXTENSIONS.get(snippet.language, '.txt')
            # Traceable filename: <slot_address>_<staging_id>_<timestamp>.<ext>
            ts = time.strftime('%Y%m%dT%H%M%S', time.gmtime(time.time()))
            addr = snippet.reserved_address or 'x0'
            filename = f"{addr}_{snippet.staging_id}_{ts}{ext}"
            lang_dir = os.path.join(self._snippets_dir, snippet.language)
            os.makedirs(lang_dir, exist_ok=True)
            file_path = os.path.join(lang_dir, filename)

            # Write with header comment
            header = self._make_file_header(snippet)
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(header + snippet.code)

            snippet.saved_file_path = file_path
            self._audit.log(AuditEventType.FILE_WRITTEN, staging_id, {
                'path': file_path,
                'size': len(header) + len(snippet.code),
                'code_hash': snippet.code_hash,
            })

            # ── Step 2: Create a synthetic node in the SessionLedger ──────
            node_id = self._create_ledger_node(snippet)
            snippet.ledger_node_id = node_id
            self._audit.log(AuditEventType.LEDGER_NODE_CREATED, staging_id, {
                'node_id': node_id,
                'language': snippet.language,
                'label': snippet.label,
            })

            # ── Step 3: Commit node to the reserved registry slot ─────────
            from .node_registry import SlotPermissionSet
            slot = self._registry.commit_node(
                node_id=node_id,
                engine_name=snippet.reserved_engine,
                position=snippet.reserved_position,
                permissions=SlotPermissionSet(get=True, push=True, post=False, delete=False),
            )

            if slot:
                snippet.registry_slot_id = slot.slot_id
                # Record the speculative execution output into the slot
                self._registry.record_execution(
                    slot_id=slot.slot_id,
                    success=snippet.spec_success,
                    output=snippet.spec_output,
                    error=snippet.spec_error,
                    execution_time=snippet.spec_execution_time,
                )
                self._audit.log(AuditEventType.REGISTRY_SLOT_COMMITTED, staging_id, {
                    'slot_id': slot.slot_id,
                    'address': slot.address,
                    'engine': snippet.reserved_engine,
                    'position': snippet.reserved_position,
                })
            else:
                # Slot commit failed — fall back
                self._audit.log(AuditEventType.ERROR, staging_id, {
                    'step': 'registry_commit',
                    'error': 'commit_node returned None',
                })

            # ── Step 4: Mark promoted ─────────────────────────────────────
            with self._lock:
                snippet.phase = StagingPhase.PROMOTED
                snippet.promoted_at = time.time()
                snippet.updated_at = time.time()
                # Release the reservation (the real slot is now committed)
                self._release_position(snippet.reserved_engine, snippet.reserved_position)

            self._audit.log(AuditEventType.PROMOTION_COMPLETED, staging_id, {
                'file_path': snippet.saved_file_path,
                'node_id': snippet.ledger_node_id,
                'slot_id': snippet.registry_slot_id,
                'address': snippet.reserved_address,
                'promoted_at': snippet.promoted_at,
                'total_staging_time': snippet.promoted_at - snippet.created_at,
            })

            self._archive_snippet(snippet)
            return snippet

        except Exception as exc:
            with self._lock:
                snippet.phase = StagingPhase.FAILED
                snippet.spec_error = f"Promotion failed: {exc}"
                snippet.updated_at = time.time()
            self._audit.log(AuditEventType.ERROR, staging_id, {
                'step': 'promote',
                'error': str(exc),
                'traceback': traceback.format_exc()[:3000],
            })
            raise

    def _make_file_header(self, snippet: StagedSnippet) -> str:
        """Generate a metadata header comment for saved snippet files."""
        lang = snippet.language
        # Pick comment style
        if lang in ('python', 'ruby', 'r', 'bash'):
            prefix = '#'
        elif lang in ('javascript', 'typescript', 'java', 'go',
                       'csharp', 'kotlin', 'swift', 'rust', 'c', 'cpp'):
            prefix = '//'
        else:
            prefix = '#'

        lines = [
            f"{prefix} ═══════════════════════════════════════════════════════",
            f"{prefix}  VPyD Staged Snippet — PROMOTED TO PRODUCTION",
            f"{prefix}  staging_id:  {snippet.staging_id}",
            f"{prefix}  language:    {snippet.language}",
            f"{prefix}  engine:      {snippet.reserved_engine} ({snippet.engine_letter})",
            f"{prefix}  slot:        {snippet.reserved_address} (position {snippet.reserved_position})",
            f"{prefix}  label:       {snippet.label}",
            f"{prefix}  code_hash:   {snippet.code_hash[:16]}…",
            f"{prefix}  created:     {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(snippet.created_at))}",
            f"{prefix}  promoted:    {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(time.time()))}",
            f"{prefix}  spec_time:   {snippet.spec_execution_time:.4f}s",
            f"{prefix}  spec_result: {'PASS' if snippet.spec_success else 'FAIL'}",
            f"{prefix} ═══════════════════════════════════════════════════════",
            f"",
        ]
        return '\n'.join(lines) + '\n'

    def _create_ledger_node(self, snippet: StagedSnippet) -> str:
        """
        Create a synthetic node in the SessionLedger representing this
        promoted snippet.  This makes the snippet a first-class citizen
        with full version history and immutable audit trail.
        """
        from .session_ledger import resolve_language_id
        node_id = f"snippet-{snippet.staging_id}"

        # Begin a synthetic import session for this snippet
        import_session = self._ledger.begin_import(
            source_file=snippet.saved_file_path or f"snippet:{snippet.staging_id}",
            source_language=snippet.language,
            file_content=snippet.code,
            dependency_strategy='preserve',
        )

        # Record the node creation
        self._ledger.record_node_imported(
            node_id=node_id,
            node_type='snippet',
            display_name=snippet.label,
            raw_name=snippet.staging_id,
            source_code=snippet.code,
            source_language=snippet.language,
            source_file=snippet.saved_file_path or f"snippet:{snippet.staging_id}",
            import_session_number=import_session,
            metadata={
                'staging_id': snippet.staging_id,
                'code_hash': snippet.code_hash,
                'engine_letter': snippet.engine_letter,
                'reserved_address': snippet.reserved_address,
                'spec_success': snippet.spec_success,
                'spec_execution_time': snippet.spec_execution_time,
                'promoted_via': 'staging_pipeline',
            },
        )

        # Record the speculative execution as the first execution event
        self._ledger.record_node_executed(
            node_id=node_id,
            success=snippet.spec_success,
            output=snippet.spec_output,
            error=snippet.spec_error,
            execution_time=snippet.spec_execution_time,
            variables=snippet.spec_variables,
        )

        return node_id

    # ─────────────────────────────────────────────────────────────────────
    # ROLLBACK — Unpromote a snippet from production
    # ─────────────────────────────────────────────────────────────────────

    def rollback(self, staging_id: str, reason: str = '') -> StagedSnippet:
        """
        Rollback a promoted snippet from production.

        1. Clears the registry slot
        2. Marks the snippet as ROLLED_BACK
        3. Does NOT delete the saved file (forensics)
        4. Logs everything
        """
        with self._lock:
            # Check active staged first, then history
            snippet = self._staged.get(staging_id)
            if snippet is None:
                for h in self._history:
                    if h.staging_id == staging_id:
                        snippet = h
                        break
            if snippet is None:
                raise ValueError(f"No snippet with staging_id '{staging_id}'")
            if snippet.phase != StagingPhase.PROMOTED:
                raise ValueError(
                    f"Cannot rollback snippet in phase '{snippet.phase.value}' "
                    f"(must be PROMOTED)"
                )

        # Clear the registry slot
        if snippet.registry_slot_id:
            self._registry.clear_slot(snippet.registry_slot_id)
            self._audit.log(AuditEventType.SLOT_RELEASED, staging_id, {
                'slot_id': snippet.registry_slot_id,
                'address': snippet.reserved_address,
            })

        with self._lock:
            snippet.phase = StagingPhase.ROLLED_BACK
            snippet.rejection_reason = reason or 'Rolled back from production'
            snippet.rejection_at = time.time()
            snippet.updated_at = time.time()

        self._audit.log(AuditEventType.ROLLBACK, staging_id, {
            'reason': reason,
            'slot_id': snippet.registry_slot_id,
            'address': snippet.reserved_address,
            'node_id': snippet.ledger_node_id,
            'was_promoted_at': snippet.promoted_at,
            'time_in_production': time.time() - snippet.promoted_at,
        })

        return snippet

    # ─────────────────────────────────────────────────────────────────────
    # FULL PIPELINE — queue → speculate → verdict → promote (one call)
    # ─────────────────────────────────────────────────────────────────────

    def run_full_pipeline(self, engine_letter: str, language: str,
                          code: str, label: str = '',
                          auto_promote: bool = True) -> StagedSnippet:
        """
        Run the complete staging pipeline in one call:

            queue → speculate → verdict → promote (if pass)

        If auto_promote is False, stops after verdict (returns PASSED
        or FAILED — caller must call promote() separately).

        Returns the final StagedSnippet.
        """
        # Phase 1: Queue
        snippet = self.queue_snippet(engine_letter, language, code, label)

        # Phase 2: Speculate
        snippet = self.speculate(snippet.staging_id)

        # Phase 3: Verdict
        snippet = self.verdict(snippet.staging_id, action='auto')

        # Phase 4: Promote (if passed and auto_promote)
        if snippet.phase == StagingPhase.PASSED and auto_promote:
            snippet = self.promote(snippet.staging_id)

        return snippet

    # ─────────────────────────────────────────────────────────────────────
    # QUERIES
    # ─────────────────────────────────────────────────────────────────────

    def get_snippet(self, staging_id: str) -> Optional[StagedSnippet]:
        """Get a snippet by staging_id (checks active + history)."""
        snippet = self._staged.get(staging_id)
        if snippet:
            return snippet
        for h in self._history:
            if h.staging_id == staging_id:
                return h
        return None

    def get_active(self) -> List[StagedSnippet]:
        """Get all snippets currently in the pipeline."""
        return list(self._staged.values())

    def get_history(self, limit: int = 100) -> List[StagedSnippet]:
        """Get completed/rejected snippets (most recent first)."""
        return list(reversed(self._history[-limit:]))

    def get_audit_trail(self, staging_id: Optional[str] = None,
                        limit: int = 500) -> List[Dict]:
        """Get audit log entries, optionally filtered by staging_id."""
        if staging_id:
            return self._audit.read_for_staging_id(staging_id)
        return self._audit.read_all(limit=limit)

    def get_reserved_positions(self) -> Dict[str, List[int]]:
        """Get currently reserved (but not yet committed) positions."""
        with self._lock:
            return {
                eng: sorted(positions)
                for eng, positions in self._reserved_positions.items()
                if positions
            }

    def get_pipeline_summary(self) -> Dict[str, Any]:
        """Get a summary of the pipeline state."""
        with self._lock:
            active = list(self._staged.values())
        by_phase = {}
        for s in active:
            by_phase.setdefault(s.phase.value, 0)
            by_phase[s.phase.value] += 1

        promoted_count = sum(1 for h in self._history if h.phase == StagingPhase.PROMOTED)
        rejected_count = sum(1 for h in self._history if h.phase == StagingPhase.REJECTED)
        rolled_back = sum(1 for h in self._history if h.phase == StagingPhase.ROLLED_BACK)

        return {
            'active_count': len(active),
            'by_phase': by_phase,
            'history_count': len(self._history),
            'promoted_total': promoted_count,
            'rejected_total': rejected_count,
            'rolled_back_total': rolled_back,
            'reserved_positions': self.get_reserved_positions(),
        }

    # ─────────────────────────────────────────────────────────────────────
    # INTERNAL HELPERS
    # ─────────────────────────────────────────────────────────────────────

    def _archive_snippet(self, snippet: StagedSnippet):
        """Move a snippet from active to history."""
        with self._lock:
            self._staged.pop(snippet.staging_id, None)
            self._history.append(snippet)
            # Cap history at 1000
            if len(self._history) > 1000:
                self._history = self._history[-1000:]
