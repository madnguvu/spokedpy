"""
Runtime module — execution, registry, and multi-debugger routes.

Extracted from app.py for separation of concerns.
Contains:
  • Node Registry routes      (22 routes under /api/registry/*)
  • Live Execution routes      (6 routes under /api/execution/ledger/*)
  • Multi-Debugger routes      (7 routes under /api/execution/multi-debug/*)
  • WebSocket event handlers   (2 handlers: create_debug_session, step_debug_session)
  • MultiDebuggerManager class

Call  init_runtime(app, session_ledger, socketio)  from app.py to wire everything up.
"""
from flask import Blueprint, request, jsonify
import json
import os
import uuid

# ── Load .env (best-effort; python-dotenv is optional) ───────────────
try:
    from dotenv import load_dotenv as _load_dotenv
    _load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'))
except ImportError:
    pass  # python-dotenv not installed — rely on shell env or defaults
# ─────────────────────────────────────────────────────────────────────

from visual_editor_core.node_registry import (
    NodeRegistry, EngineID, RegistrySlot, SlotPermissionSet, SlotPermission,
    LANGUAGE_STRING_TO_ENGINE, LETTER_TO_ENGINE
)
from visual_editor_core.execution_engine import (
    PythonExecutor as _PythonExecutor,
    JavaScriptExecutor as _JavaScriptExecutor,
    RustExecutor as _RustExecutor,
    BashExecutor as _BashExecutor,
    CExecutor as _CExecutor,
    CppExecutor as _CppExecutor,
    GoExecutor as _GoExecutor,
    JavaExecutor as _JavaExecutor,
    RubyExecutor as _RubyExecutor,
    RExecutor as _RExecutor,
    CSharpExecutor as _CSharpExecutor,
    KotlinExecutor as _KotlinExecutor,
    SwiftExecutor as _SwiftExecutor,
    TypeScriptExecutor as _TypeScriptExecutor,
    PerlExecutor as _PerlExecutor,
    get_executor_for_language,
    get_supported_languages,
    EXECUTOR_ALIASES,
)
from visual_editor_core.session_ledger import (
    LanguageID, resolve_language_string,
)
from visual_editor_core.snippet_staging import (
    StagingPipeline,
    StagingPhase,
    StagedSnippet,
)
from web_interface.project_db import resolve_setting
from web_interface.state_persistence import (
    StatePersistence, build_promoted_snapshots,
)
from visual_editor_core.mesh_relay import (
    MeshRelay, MeshRole, MeshTopology, PeerInfo,
)
import time as _time
import threading as _threading
import secrets as _secrets

# ---------------------------------------------------------------------------
# Blueprint
# ---------------------------------------------------------------------------
runtime_bp = Blueprint('runtime', __name__)

# ---------------------------------------------------------------------------
# Module-level state — populated by init_runtime()
# ---------------------------------------------------------------------------
_session_ledger = None   # SessionLedger reference
_socketio = None         # SocketIO reference
node_registry = None     # NodeRegistry(session_ledger)
_live_executor = None    # PythonExecutor  (shared REPL namespace — kept for Python)
_executors = {}          # language string → executor instance  (all engines)
multi_debugger = None    # MultiDebuggerManager
staging_pipeline = None  # StagingPipeline — speculative execution & promotion
active_debug_sessions = {}
mesh_relay = None        # MeshRelay — distributed instance interconnect

# ---------------------------------------------------------------------------
# State Persistence — crash-resilient checkpoint/restore
# ---------------------------------------------------------------------------
_state_persistence: StatePersistence = None  # type: ignore — set in init_runtime

# ---------------------------------------------------------------------------
# Marshal Token Registry — opaque, TTL-governed handles for external agents
# ---------------------------------------------------------------------------
# Maps token → { staging_id, created_at, ttl, expired }
# Tokens are the ONLY external-facing identifier.  Callers never see
# staging_ids or slot addresses directly — those are internal plumbing.
_marshal_tokens: dict = {}        # token_str → token_record dict
_marshal_lock = _threading.Lock()
_MARSHAL_TOKEN_BYTES = 6          # 6 bytes → 12 hex chars (e.g. "m-7f3a9ce1b204")
_MARSHAL_DEFAULT_TTL = int(
    resolve_setting('marshal_ttl', 'SPOKEDPY_MARSHAL_TTL', '4000')
)                                 # seconds — token lifetime


def _mint_marshal_token(staging_id: str, ttl: int = _MARSHAL_DEFAULT_TTL,
                        origin: str = 'api', submitter: str = '',
                        agent_id: str = '') -> str:
    """Create a unique, opaque marshal token and bind it to a staging_id.

    Args:
        origin:    'api' | 'live-exec' | 'canvas' — how the snippet arrived
        submitter: human-readable label (user name, agent name, etc.)
        agent_id:  machine-readable agent identifier (if applicable)
    """
    token = f"m-{_secrets.token_hex(_MARSHAL_TOKEN_BYTES)}"
    with _marshal_lock:
        _marshal_tokens[token] = {
            'staging_id': staging_id,
            'created_at': _time.time(),
            'ttl': ttl,
            'origin': origin,
            'submitter': submitter or ('Human (Live Exec)' if origin == 'live-exec' else 'API Agent'),
            'agent_id': agent_id,
        }
    return token


# ---------------------------------------------------------------------------
# Locked Slots — Pinned indefinitely, bypass TTL expiration
# ---------------------------------------------------------------------------
# Maps slot_address (e.g. "a3") → lock metadata dict
_locked_slots: dict = {}
_locked_slots_lock = _threading.Lock()


def _resolve_marshal_token(token: str) -> dict | None:
    """Look up a marshal token.  Returns None if unknown or expired.
    Returned dict has keys: staging_id, created_at, ttl, remaining, expired.
    """
    with _marshal_lock:
        rec = _marshal_tokens.get(token)
        if rec is None:
            return None
        elapsed = _time.time() - rec['created_at']
        remaining = max(0, rec['ttl'] - elapsed)
        expired = remaining <= 0
        return {
            **rec,
            'elapsed': round(elapsed, 1),
            'remaining': round(remaining, 1),
            'expired': expired,
        }


def _purge_expired_tokens():
    """Remove tokens that have been expired for more than 2× their TTL."""
    now = _time.time()
    with _marshal_lock:
        to_delete = [
            t for t, r in _marshal_tokens.items()
            if (now - r['created_at']) > r['ttl'] * 2
        ]
        for t in to_delete:
            del _marshal_tokens[t]


def _get_executor(language: str):
    """Get the live executor for a language.  Returns the shared Python
    executor for 'python'; creates/caches subprocess executors for others.
    """
    lang = language.lower().strip()
    lang = EXECUTOR_ALIASES.get(lang, lang)

    if lang in _executors:
        return _executors[lang]
    return None


def _trigger_checkpoint():
    """Debounced write of the current runtime state to disk.

    Called after every state-mutating operation (promote, lock, unlock,
    evict, token mint).  The actual write is coalesced via StatePersistence.
    """
    if _state_persistence is None or staging_pipeline is None:
        return
    try:
        with _marshal_lock:
            tokens_copy = dict(_marshal_tokens)
        with _locked_slots_lock:
            locks_copy = dict(_locked_slots)
        snapshots = build_promoted_snapshots(staging_pipeline, tokens_copy, locks_copy)
        _state_persistence.checkpoint(locks_copy, tokens_copy, snapshots)
    except Exception as exc:
        print(f"  [STATE] Checkpoint trigger failed: {exc}")


def _restore_state():
    """Restore runtime state from the last checkpoint file.

    Called once during init_runtime() AFTER the staging pipeline,
    node registry, and session ledger are initialized.

    Restores:
      1. Promoted snippets → re-run through staging pipeline (queue → promote)
      2. Marshal tokens → re-mint with remaining TTL
      3. Locked slots → re-apply locks
    """
    global _marshal_tokens

    if _state_persistence is None:
        return

    state = _state_persistence.restore()
    if state is None:
        print("  [STATE] No checkpoint file found — fresh start.")
        return

    saved_at = state.get('saved_at', 0)
    age = _time.time() - saved_at
    age_str = f"{age:.0f}s" if age < 3600 else f"{age/3600:.1f}h"
    print(f"  [STATE] Restoring from checkpoint (age: {age_str})")

    promoted = state.get('promoted_snippets', [])
    tokens = state.get('marshal_tokens', {})
    locks = state.get('locked_slots', {})

    restored_count = 0
    failed_count = 0

    # ── 1. Restore promoted snippets ────────────────────────────────
    for snap in promoted:
        code = snap.get('code', '')
        language = snap.get('language', '')
        engine_letter = snap.get('engine_letter', '')
        label = snap.get('label', '')
        staging_id = snap.get('staging_id', '')

        if not code.strip() or not (engine_letter or language):
            print(f"  [STATE]   Skip invalid snippet: {staging_id}")
            failed_count += 1
            continue

        try:
            # Re-run through the full pipeline (queue → speculate → verdict → promote)
            snippet = staging_pipeline.run_full_pipeline(
                engine_letter, language, code, label, auto_promote=True
            )

            if snippet.phase.value == 'promoted':
                restored_count += 1
                addr = snippet.reserved_address

                # ── 2. Restore marshal token with remaining TTL ─────────
                # Check if a persisted token exists for this staging_id
                old_token = snap.get('token', '')
                if old_token and old_token in tokens:
                    trec = tokens[old_token]
                    remaining = trec.get('remaining_ttl', 0)
                    # Only restore if TTL hasn't fully expired
                    if remaining > 0:
                        with _marshal_lock:
                            _marshal_tokens[old_token] = {
                                'staging_id': snippet.staging_id,
                                'created_at': _time.time(),  # reset clock
                                'ttl': remaining,             # use remaining TTL
                                'origin': trec.get('origin', snap.get('origin', 'api')),
                                'submitter': trec.get('submitter', snap.get('submitter', '')),
                                'agent_id': trec.get('agent_id', snap.get('agent_id', '')),
                            }
                    else:
                        # Token expired but snippet is locked — mint a fresh token
                        if snap.get('locked', False):
                            _mint_marshal_token(
                                snippet.staging_id,
                                ttl=_MARSHAL_DEFAULT_TTL,
                                origin=snap.get('origin', 'api'),
                                submitter=snap.get('submitter', ''),
                                agent_id=snap.get('agent_id', ''),
                            )
                else:
                    # No persisted token — mint a fresh one for locked snippets
                    if snap.get('locked', False):
                        _mint_marshal_token(
                            snippet.staging_id,
                            ttl=_MARSHAL_DEFAULT_TTL,
                            origin=snap.get('origin', 'api'),
                            submitter=snap.get('submitter', ''),
                            agent_id=snap.get('agent_id', ''),
                        )

                # ── 3. Restore lock status ──────────────────────────────
                old_addr = snap.get('address', '')
                if old_addr in locks or snap.get('locked', False):
                    lock_meta = locks.get(old_addr, {})
                    with _locked_slots_lock:
                        _locked_slots[addr] = {
                            'locked_at': lock_meta.get('locked_at', _time.time()),
                            'locked_by': lock_meta.get('locked_by', 'restored'),
                            'reason': lock_meta.get('reason', 'Restored from checkpoint'),
                        }

                print(f"  [STATE]   Restored: {addr.upper()} [{language}] {label}")
            else:
                print(f"  [STATE]   Snippet re-execution changed phase to '{snippet.phase.value}': {staging_id}")
                failed_count += 1

        except Exception as exc:
            print(f"  [STATE]   FAILED to restore snippet {staging_id}: {exc}")
            failed_count += 1

    # ── 4. Restore locks for non-snippet addresses ──────────────────
    # (locks that were applied to canvas nodes, not staging pipeline snippets)
    restored_addrs = set()
    for snap in promoted:
        if snap.get('locked', False):
            restored_addrs.add(snap.get('address', ''))
    for addr, lock_meta in locks.items():
        if addr not in restored_addrs:
            with _locked_slots_lock:
                if addr not in _locked_slots:
                    _locked_slots[addr] = {
                        'locked_at': lock_meta.get('locked_at', _time.time()),
                        'locked_by': lock_meta.get('locked_by', 'restored'),
                        'reason': lock_meta.get('reason', 'Restored from checkpoint'),
                    }
                    print(f"  [STATE]   Restored lock on {addr.upper()} (non-snippet)")

    summary = f"  [STATE] Restore complete: {restored_count} promoted"
    if failed_count:
        summary += f", {failed_count} failed"
    summary += f", {len(_locked_slots)} locked"
    print(summary)


def init_runtime(app, session_ledger, socketio):
    """Wire the runtime blueprint into the Flask app.

    Must be called once, after the app and session_ledger are ready.
    """
    global _session_ledger, _socketio, node_registry, _live_executor, multi_debugger, _executors, staging_pipeline
    global _state_persistence, mesh_relay

    _session_ledger = session_ledger
    _socketio = socketio

    # Execution matrix on top of the ledger
    node_registry = NodeRegistry(session_ledger)

    # Persistent Python executor — holds variables across runs (REPL-style)
    _live_executor = _PythonExecutor()

    # Per-language executor pool — all 15 engines
    _executors = {
        'python':     _live_executor,            # shared REPL namespace
        'javascript': _JavaScriptExecutor(),     # Node.js subprocess
        'typescript': _TypeScriptExecutor(),     # ts-node / tsx subprocess
        'rust':       _RustExecutor(),            # rustc subprocess
        'bash':       _BashExecutor(),            # bash / sh / cmd subprocess
        'c':          _CExecutor(),               # gcc / cc compile + run
        'cpp':        _CppExecutor(),             # g++ / clang++ compile + run
        'go':         _GoExecutor(),              # go run subprocess
        'java':       _JavaExecutor(),            # javac + java
        'ruby':       _RubyExecutor(),            # ruby subprocess
        'r':          _RExecutor(),               # Rscript subprocess
        'csharp':     _CSharpExecutor(),          # dotnet-script / csc / dotnet run
        'kotlin':     _KotlinExecutor(),          # kotlinc -script
        'swift':      _SwiftExecutor(),           # swift subprocess
        'perl':       _PerlExecutor(),            # perl subprocess (Strawberry Perl)
    }

    # Multi-debugger manager (ensure global is initialized)
    multi_debugger = MultiDebuggerManager()

    # ── Resolve data paths: DB setting → env var → legacy default ────
    _legacy_dir = os.path.dirname(__file__)           # web_interface/
    _data_dir   = os.path.join(os.path.dirname(_legacy_dir), 'data')

    snippets_dir = resolve_setting(
        'snippets_dir',
        'SPOKEDPY_SNIPPETS_DIR',
        os.path.join(_data_dir, 'snippets'),
    )
    audit_log_path = resolve_setting(
        'audit_log',
        'SPOKEDPY_AUDIT_LOG',
        os.path.join(_data_dir, 'staging_audit.jsonl'),
    )
    # Ensure the resolved directories exist
    os.makedirs(snippets_dir, exist_ok=True)
    os.makedirs(os.path.dirname(audit_log_path) or '.', exist_ok=True)

    print(f"  Snippets dir:  {snippets_dir}")
    print(f"  Audit log:     {audit_log_path}")

    # Staging pipeline — speculative execution & promotion to production
    staging_pipeline = StagingPipeline(
        executors=_executors,
        node_registry=node_registry,
        session_ledger=session_ledger,
        snippets_dir=snippets_dir,
        audit_log_path=audit_log_path,
    )

    # ── State persistence — restore promoted slots from last checkpoint ──
    _state_persistence = StatePersistence()
    print(f"  State file:    {_state_persistence.path}")
    _restore_state()

    # ── Mesh Relay — distributed instance interconnect ──────────────
    instance_name = os.environ.get('SPOKEDPY_INSTANCE_NAME', '')
    mesh_relay = MeshRelay(node_registry, session_ledger, instance_name)
    print(f"  Mesh relay:    {mesh_relay.instance_id} ({mesh_relay.instance_name})")

    # Register the blueprint (all routes become active)
    app.register_blueprint(runtime_bp)

    # Register WebSocket handlers (they need the socketio reference)
    _register_websocket_handlers(socketio)


# ==================== ENGINE MANIFEST (SINGLE SOURCE OF TRUTH) ====================

@runtime_bp.route('/api/engines', methods=['GET'])
def get_engine_manifest():
    """Return the canonical engine manifest — the SINGLE SOURCE OF TRUTH.

    Every engine's identity, capabilities, availability, and toolchain
    info is derived from the EngineID enum + executor pool at startup.

    Fields per engine:
        letter            — single-char engine ID  (a, b, … o)
        name              — display name            (Python, JavaScript, …)
        language          — canonical language key   (python, javascript, …)
        max_slots         — registry slot capacity   (64 for Python, 16 others)
        extension         — file extension for code  (py, js, …)
        platform_enabled  — runtime binary found on this machine (bool)
        runtime_version   — version string of the runtime (or null)
        runtime_path      — path to the runtime binary (or null)
        capabilities      — dict of feature flags this engine supports
        parser            — which parser/executor class handles this language
        tier              — priority tier: 'primary', 'tier-1', 'tier-2'
    """
    import subprocess as _sp

    try:
        # ── Static metadata tables (defined once, canonical) ─────────────
        _EXT_MAP = {
            'python': 'py', 'javascript': 'js', 'typescript': 'ts',
            'rust': 'rs', 'java': 'java', 'swift': 'swift',
            'cpp': 'cpp', 'r': 'R', 'go': 'go', 'ruby': 'rb',
            'csharp': 'cs', 'kotlin': 'kt', 'c': 'c', 'bash': 'sh',
            'perl': 'pl',
        }

        # Version-check commands — (binary_path, [args])
        _VERSION_CMD = {
            'python':     lambda p: [p, '--version'],
            'javascript': lambda p: [p, '--version'],
            'typescript': lambda p: [p, '--version'],
            'rust':       lambda p: [p, '--version'],       # rustc
            'java':       lambda p: [p, '-version'],        # javac
            'go':         lambda p: [p, 'version'],
            'ruby':       lambda p: [p, '--version'],
            'r':          lambda p: [p, '--version'],
            'csharp':     lambda p: [p, '--list-runtimes'],
            'kotlin':     lambda p: [p, '-version'],
            'swift':      lambda p: [p, '--version'],
            'c':          lambda p: [p, '--version'],       # gcc
            'cpp':        lambda p: [p, '--version'],       # g++
            'bash':       lambda p: [p, '-Command', '$PSVersionTable.PSVersion.ToString()'],
            'perl':       lambda p: [p, '--version'],
        }

        # Capability descriptors — what each engine can do
        _CAPABILITIES = {
            'python':     {'repl': True,  'debug': True,  'canvas_exec': True,  'engine_tab': True, 'export': True, 'import_file': True,  'ast_parse': True },
            'javascript': {'repl': False, 'debug': True,  'canvas_exec': True,  'engine_tab': True, 'export': True, 'import_file': True,  'ast_parse': True },
            'typescript': {'repl': False, 'debug': True,  'canvas_exec': True,  'engine_tab': True, 'export': True, 'import_file': True,  'ast_parse': True },
            'rust':       {'repl': False, 'debug': False, 'canvas_exec': True,  'engine_tab': True, 'export': True, 'import_file': True,  'ast_parse': False},
            'java':       {'repl': False, 'debug': False, 'canvas_exec': True,  'engine_tab': True, 'export': True, 'import_file': True,  'ast_parse': False},
            'go':         {'repl': False, 'debug': False, 'canvas_exec': True,  'engine_tab': True, 'export': True, 'import_file': True,  'ast_parse': False},
            'bash':       {'repl': False, 'debug': False, 'canvas_exec': True,  'engine_tab': True, 'export': True, 'import_file': True,  'ast_parse': False},
            'perl':       {'repl': False, 'debug': False, 'canvas_exec': True,  'engine_tab': True, 'export': True, 'import_file': True,  'ast_parse': False},
            'ruby':       {'repl': False, 'debug': False, 'canvas_exec': True,  'engine_tab': True, 'export': True, 'import_file': True,  'ast_parse': False},
            'r':          {'repl': False, 'debug': False, 'canvas_exec': True,  'engine_tab': True, 'export': True, 'import_file': True,  'ast_parse': False},
            'c':          {'repl': False, 'debug': False, 'canvas_exec': True,  'engine_tab': True, 'export': True, 'import_file': True,  'ast_parse': False},
            'cpp':        {'repl': False, 'debug': False, 'canvas_exec': True,  'engine_tab': True, 'export': True, 'import_file': True,  'ast_parse': False},
            'csharp':     {'repl': False, 'debug': False, 'canvas_exec': True,  'engine_tab': True, 'export': True, 'import_file': True,  'ast_parse': False},
            'kotlin':     {'repl': False, 'debug': False, 'canvas_exec': True,  'engine_tab': True, 'export': True, 'import_file': True,  'ast_parse': False},
            'swift':      {'repl': False, 'debug': False, 'canvas_exec': True,  'engine_tab': True, 'export': True, 'import_file': True,  'ast_parse': False},
        }

        # Tier assignment
        _TIERS = {
            'python': 'primary',
            'javascript': 'tier-1', 'typescript': 'tier-1',
            'rust': 'tier-1', 'java': 'tier-1', 'go': 'tier-1',
        }

        # Parser / executor class names
        from visual_editor_core.execution_engine import EXECUTOR_CLASSES as _EC

        # ── Build the manifest ───────────────────────────────────────────
        engines = []
        for engine in EngineID:
            lang_str = resolve_language_string(engine.lang_id)
            executor = _executors.get(lang_str) if _executors else None

            # ── Availability (platform_enabled) ──────────────────────────
            # Lazy re-probe: if the executor's path was None at startup,
            # the user may have installed/PATH'd the runtime since then.
            available = False
            runtime_path = None
            if executor:
                if lang_str == 'python':
                    import sys as _sys
                    available = True
                    runtime_path = _sys.executable
                else:
                    import shutil as _shutil
                    path_attrs = [a for a in dir(executor) if a.endswith('_path')]
                    for a in path_attrs:
                        val = getattr(executor, a, None)
                        if val:
                            available = True
                            runtime_path = val
                            break
                    # Re-probe if still not found
                    if not available and path_attrs:
                        _BINARY_NAMES = {
                            'rust': ['rustc'], 'java': ['javac', 'java'],
                            'go': ['go'], 'ruby': ['ruby'], 'r': ['Rscript'],
                            'csharp': ['dotnet-script', 'dotnet', 'csc'],
                            'kotlin': ['kotlinc', 'kotlin'], 'swift': ['swift'],
                            'c': ['gcc', 'cc'], 'cpp': ['g++', 'c++', 'clang++'],
                            'bash': ['bash', 'sh', 'pwsh', 'powershell'],
                            'perl': ['perl'],
                            'javascript': ['node'], 'typescript': ['tsx', 'ts-node', 'npx'],
                        }
                        for binary in _BINARY_NAMES.get(lang_str, []):
                            found = _shutil.which(binary)
                            if found:
                                available = True
                                runtime_path = found
                                # Update the executor's cached path so future
                                # execute() calls succeed without restart
                                setattr(executor, path_attrs[0], found)
                                break

            # ── Runtime version (cached on first call) ───────────────────
            runtime_version = None
            if available and runtime_path:
                ver_fn = _VERSION_CMD.get(lang_str)
                if ver_fn:
                    try:
                        proc = _sp.run(
                            ver_fn(runtime_path),
                            capture_output=True, text=True, timeout=5,
                            encoding='utf-8', errors='replace')
                        ver_text = (proc.stdout or proc.stderr or '').strip()

                        # Special handling for dotnet --list-runtimes
                        if lang_str == 'csharp' and ver_text:
                            # Find the latest Microsoft.NETCore.App version
                            import re as _re
                            netcore_versions = _re.findall(
                                r'Microsoft\.NETCore\.App\s+([\d.]+)', ver_text)
                            if netcore_versions:
                                runtime_version = f'.NET {netcore_versions[-1]}'
                            else:
                                # Fallback: grab last line that looks like a runtime
                                for line in reversed(ver_text.split('\n')):
                                    line = line.strip()
                                    if line and 'Microsoft' in line:
                                        runtime_version = line.split('[')[0].strip()[:60]
                                        break
                        else:
                            # Take first meaningful line
                            first_line = ver_text.split('\n')[0].strip()
                            # Reject garbage (error messages, empty, etc.)
                            if first_line and len(first_line) < 120 and not first_line.startswith(('At line', 'The command could')):
                                runtime_version = first_line
                            elif proc.returncode == 0 and ver_text:
                                # fallback: try second line
                                lines = [l.strip() for l in ver_text.split('\n') if l.strip()]
                                for l in lines:
                                    if not l.startswith(('At line', 'The command', '+', '~')):
                                        runtime_version = l[:100]
                                        break
                    except Exception:
                        pass

            # ── Executor class name ──────────────────────────────────────
            executor_cls = _EC.get(lang_str)
            parser_name = executor_cls.__name__ if executor_cls else None

            engines.append({
                'letter':           engine.letter,
                'name':             engine.name.replace('_', ' ').title(),
                'language':         lang_str,
                'max_slots':        engine.max_slots,
                'extension':        _EXT_MAP.get(lang_str, 'txt'),
                'platform_enabled': available,
                'runtime_version':  runtime_version,
                'runtime_path':     runtime_path,
                'capabilities':     _CAPABILITIES.get(lang_str, {}),
                'parser':           parser_name,
                'tier':             _TIERS.get(lang_str, 'tier-2'),
            })

        return jsonify({
            'success': True,
            'engines': engines,
            'total':   len(engines),
            'enabled': sum(1 for e in engines if e['platform_enabled']),
            'disabled': sum(1 for e in engines if not e['platform_enabled']),
        })
    except Exception as e:
        import traceback
        return jsonify({'success': False, 'error': str(e),
                        'traceback': traceback.format_exc()}), 500


# ==================== NODE REGISTRY (EXECUTION MATRIX) ====================


@runtime_bp.route('/api/registry/matrix', methods=['GET'])
def get_registry_matrix():
    """Get the full execution matrix — the grid view of all engines and slots."""
    try:
        if node_registry is None:
            return jsonify({'success': False, 'error': 'Runtime not initialized: node_registry is None'}), 500
        return jsonify({'success': True, **node_registry.get_matrix_summary()})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@runtime_bp.route('/api/registry/commit', methods=['POST'])
def commit_node_to_registry():
    """Commit a ledger node into a registry slot.

    Body: { node_id, engine? (e.g. "PYTHON"), position? (1-8), permissions? }
    If engine/position are omitted, auto-assigned from node's language.
    """
    try:
        if node_registry is None:
            return jsonify({'success': False, 'error': 'Runtime not initialized: node_registry is None'}), 500

        data = request.get_json() or {}
        node_id = data.get('node_id')
        if not node_id:
            return jsonify({'success': False, 'error': 'node_id required'}), 400

        engine_name = data.get('engine')
        position = data.get('position')
        if position is not None:
            position = int(position)

        perms = None
        if 'permissions' in data:
            perms = SlotPermissionSet.from_dict(data['permissions'])

        slot = node_registry.commit_node(node_id, engine_name, position, perms)
        if not slot:
            return jsonify({
                'success': False,
                'error': 'Failed to commit — node not in ledger, engine full, or unsupported language'
            }), 400

        return jsonify({'success': True, 'slot': slot.to_dict()})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@runtime_bp.route('/api/registry/commit-all', methods=['POST'])
def commit_all_to_registry():
    """Commit all active ledger nodes into the registry matrix."""
    try:
        if node_registry is None:
            return jsonify({'success': False, 'error': 'Runtime not initialized: node_registry is None'}), 500

        slots = node_registry.commit_all_from_ledger()
        return jsonify({
            'success': True,
            'committed': len(slots),
            'slots': [s.to_dict() for s in slots],
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@runtime_bp.route('/api/registry/refresh', methods=['POST'])
def refresh_registry():
    """Check all slots against the ledger for version bumps (hot-swap detection)."""
    try:
        if node_registry is None:
            return jsonify({'success': False, 'error': 'Runtime not initialized: node_registry is None'}), 500

        dirty_count = node_registry.refresh_all_from_ledger()
        return jsonify({
            'success': True,
            'dirty_count': dirty_count,
            'message': f'{dirty_count} slot(s) need hot-swapping'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@runtime_bp.route('/api/registry/slot/<slot_id>', methods=['GET'])
def get_registry_slot(slot_id):
    """Get a single slot by its global address (nra01, nra02, ...)."""
    try:
        if node_registry is None:
            return jsonify({'success': False, 'error': 'Runtime not initialized: node_registry is None'}), 500

        slot = node_registry.get_slot(slot_id)
        if not slot:
            return jsonify({'success': False, 'error': 'Slot not found'}), 404
        return jsonify({'success': True, 'slot': slot.to_dict()})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@runtime_bp.route('/api/registry/slot/<slot_id>', methods=['DELETE'])
def clear_registry_slot(slot_id):
    """Clear a slot — remove the committed node. Checks DEL permission."""
    try:
        if node_registry is None:
            return jsonify({'success': False, 'error': 'Runtime not initialized: node_registry is None'}), 500

        slot = node_registry.get_slot(slot_id)
        if not slot:
            return jsonify({'success': False, 'error': 'Slot not found'}), 404

        if not slot.permissions.has(SlotPermission.DEL):
            return jsonify({'success': False, 'error': 'DEL permission denied'}), 403

        ok = node_registry.clear_slot(slot_id)
        return jsonify({'success': ok})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@runtime_bp.route('/api/registry/slot/<slot_id>/push', methods=['POST'])
def push_to_registry_slot(slot_id):
    """Push data into a slot's input buffer (inter-slot communication)."""
    try:
        if node_registry is None:
            return jsonify({'success': False, 'error': 'Runtime not initialized: node_registry is None'}), 500

        data = request.get_json() or {}
        payload = data.get('data')
        source = data.get('source_slot')

        ok = node_registry.push_to_slot(slot_id, payload, source)
        if not ok:
            return jsonify({'success': False, 'error': 'Push failed — slot not found or PUSH denied'}), 400
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@runtime_bp.route('/api/registry/slot/<slot_id>/output', methods=['GET'])
def read_registry_slot_output(slot_id):
    """Read from a slot's output buffer. Checks GET permission."""
    try:
        if node_registry is None:
            return jsonify({'success': False, 'error': 'Runtime not initialized: node_registry is None'}), 500

        last_n = request.args.get('last', 10, type=int)
        output = node_registry.read_slot_output(slot_id, last_n)
        return jsonify({'success': True, 'output': output})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@runtime_bp.route('/api/registry/slot/<slot_id>/execute', methods=['POST'])
def execute_registry_slot(slot_id):
    """Execute a slot's committed code. Checks POST permission.

    This triggers immediate execution — outside the normal engine loop.
    Useful for manual testing / debugging.
    Supports Python, JavaScript, and Rust engines.
    """
    try:
        if node_registry is None or _session_ledger is None:
            return jsonify({'success': False, 'error': 'Runtime not initialized'}), 500

        slot = node_registry.get_slot(slot_id)
        if not slot:
            return jsonify({'success': False, 'error': 'Slot not found'}), 404
        if not slot.node_id:
            return jsonify({'success': False, 'error': 'Slot is empty'}), 400

        snapshot = _session_ledger.get_node_snapshot(slot.node_id)
        if not snapshot:
            return jsonify({'success': False, 'error': 'Node not in ledger'}), 404

        lang = resolve_language_string(LanguageID(snapshot.current_language_id))
        executor = _get_executor(lang)
        if executor is None:
            supported = ', '.join(get_supported_languages())
            return jsonify({
                'success': False,
                'error': f'No live executor for "{lang}". Supported: {supported}'
            }), 400

        code = snapshot.current_source_code
        if not code or not code.strip():
            return jsonify({'success': False, 'error': 'No source code'}), 400

        # Inject input buffer as variable if present (Python only — has namespace)
        inputs = node_registry.drain_input_buffer(slot_id)
        if inputs and hasattr(executor, 'set_variable_value'):
            executor.set_variable_value('_slot_input', [i['data'] for i in inputs])

        result = executor.execute(code)

        node_registry.record_execution(
            slot_id=slot_id,
            success=result.success,
            output=result.output or '',
            error=str(result.error) if result.error else '',
            execution_time=result.execution_time,
        )

        return jsonify({
            'success': True,
            'result': {
                'slot_id': slot_id,
                'address': slot.address,
                'node_name': slot.node_name,
                'language': lang,
                'output': result.output or '',
                'error': str(result.error) if result.error else '',
                'execution_time': round(result.execution_time, 4),
                'version': slot.committed_version,
                'hot_swapped': slot.last_executed_version < slot.committed_version,
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@runtime_bp.route('/api/registry/slot/<slot_id>/permissions', methods=['PUT'])
def update_slot_permissions(slot_id):
    """Update permissions for a specific slot."""
    try:
        if node_registry is None:
            return jsonify({'success': False, 'error': 'Runtime not initialized: node_registry is None'}), 500

        data = request.get_json() or {}
        perms = SlotPermissionSet.from_dict(data)
        ok = node_registry.set_slot_permissions(slot_id, perms)
        if not ok:
            return jsonify({'success': False, 'error': 'Slot not found'}), 404
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@runtime_bp.route('/api/registry/slot/<slot_id>/rollback', methods=['POST'])
def rollback_registry_slot(slot_id):
    """Rollback a slot to a previous code version. Zero-downtime rollback."""
    try:
        if node_registry is None:
            return jsonify({'success': False, 'error': 'Runtime not initialized: node_registry is None'}), 500

        data = request.get_json() or {}
        version = data.get('version')
        if version is None:
            return jsonify({'success': False, 'error': 'version required'}), 400

        ok = node_registry.rollback_slot(slot_id, int(version))
        if not ok:
            return jsonify({'success': False, 'error': 'Rollback failed — invalid version or slot'}), 400
        return jsonify({'success': True, 'message': f'Slot rolled back to v{version} — engine will pick up on next tick'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@runtime_bp.route('/api/registry/slot/<slot_id>/subscribe', methods=['POST'])
def subscribe_slot(slot_id):
    """Subscribe this slot to another slot's output."""
    try:
        if node_registry is None:
            return jsonify({'success': False, 'error': 'Runtime not initialized: node_registry is None'}), 500

        data = request.get_json() or {}
        publisher = data.get('publisher_slot_id')
        if not publisher:
            return jsonify({'success': False, 'error': 'publisher_slot_id required'}), 400

        # Delegate subscription to the underlying registry implementation.
        # Prefer a well-defined public API on NodeRegistry; fall back to a no-op
        # until the underlying implementation exposes subscription support.
        registry = getattr(node_registry, 'registry', node_registry)

        ok = False

        # If the registry exposes a supported subscription API, use it.
        if hasattr(registry, 'set_slot_subscription'):
            # Hypothetical API: set_slot_subscription(subscriber, publisher) -> bool
            ok = registry.set_slot_subscription(subscriber_slot_id=slot_id, publisher_slot_id=publisher)  # type: ignore[attr-defined]
        elif hasattr(registry, 'link_slots'):
            # Alternate hypothetical API: link_slots(subscriber, publisher) -> bool
            ok = registry.link_slots(subscriber_slot_id=slot_id, publisher_slot_id=publisher)  # type: ignore[attr-defined]
        else:
            # Subscription is not implemented on this registry; report clearly.
            return jsonify({
                'success': False,
                'error': 'Subscription not supported by current NodeRegistry implementation'
            }), 500

        if not ok:
            return jsonify({'success': False, 'error': 'Subscription failed — invalid slot(s) or registry rejected the link'}), 400

        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@runtime_bp.route('/api/registry/engine/<engine_name>', methods=['GET'])
def get_engine_row(engine_name):
    """Get a single engine row with all its slots."""
    try:
        if node_registry is None:
            return jsonify({'success': False, 'error': 'Runtime not initialized: node_registry is None'}), 500

        row = node_registry.get_engine_row(engine_name.upper())
        if not row:
            return jsonify({'success': False, 'error': 'Engine not found'}), 404

        return jsonify({'success': True, 'engine': row.to_dict()})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@runtime_bp.route('/api/registry/engine/<engine_name>/permissions', methods=['PUT'])
def update_engine_permissions(engine_name):
    """Set permissions for all slots in an engine row."""
    try:
        if node_registry is None:
            return jsonify({'success': False, 'error': 'Runtime not initialized: node_registry is None'}), 500

        data = request.get_json() or {}
        perms = SlotPermissionSet.from_dict(data)
        count = node_registry.set_engine_permissions(engine_name.upper(), perms)
        return jsonify({'success': True, 'updated': count})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@runtime_bp.route('/api/registry/dirty', methods=['GET'])
def get_dirty_slots():
    """Get all slots that need hot-swapping (newer code in ledger)."""
    try:
        if node_registry is None:
            return jsonify({'success': False, 'error': 'Runtime not initialized: node_registry is None'}), 500

        dirty = node_registry.get_dirty_slots()
        return jsonify({
            'success': True,
            'count': len(dirty),
            'slots': [s.to_dict() for s in dirty],
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@runtime_bp.route('/api/registry/node/<node_id>/slot', methods=['GET'])
def get_slot_for_node(node_id):
    """Find which slot a node is committed to."""
    try:
        if node_registry is None:
            return jsonify({'success': False, 'error': 'Runtime not initialized: node_registry is None'}), 500

        slot = node_registry.get_slot_by_node(node_id)
        if not slot:
            return jsonify({'success': False, 'error': 'Node not committed to any slot'}), 404
        return jsonify({'success': True, 'slot': slot.to_dict()})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@runtime_bp.route('/api/registry/record-execution', methods=['POST'])
def record_registry_execution():
    """Record an execution result for a node in its registry slot."""
    try:
        if node_registry is None:
            return jsonify({'success': False, 'error': 'Runtime not initialized: node_registry is None'}), 500

        data = request.get_json() or {}
        node_id = data.get('node_id')
        success = data.get('success', False)

        if not node_id:
            return jsonify({'success': False, 'error': 'node_id required'}), 400

        slot = node_registry.get_slot_by_node(node_id)
        if not slot:
            return jsonify({'success': False, 'error': 'Node not in registry'}), 404

        ok = node_registry.record_execution(
            slot_id=slot.slot_id,
            success=success,
            output=data.get('output', ''),
            error=data.get('error', ''),
            execution_time=data.get('execution_time', 0.0)
        )
        return jsonify({'success': ok, 'slot_address': slot.address})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ==================== LIVE EXECUTION (LEDGER-SOURCED) ====================


@runtime_bp.route('/api/execution/engines', methods=['GET'])
def get_execution_engines():
    """Return the list of languages that have a live executor wired up."""
    try:
        engines = {}
        for lang, executor in _executors.items():
            engines[lang] = {
                'language': lang,
                'executor_class': type(executor).__name__,
                'supports_namespace': hasattr(executor, 'global_namespace'),
                'available': True,
            }
            # Check if the runtime binary is actually available
            if hasattr(executor, '_node_path'):
                engines[lang]['available'] = executor._node_path is not None
                engines[lang]['runtime'] = executor._node_path or 'not found'
            if hasattr(executor, '_rustc_path'):
                engines[lang]['available'] = executor._rustc_path is not None
                engines[lang]['runtime'] = executor._rustc_path or 'not found'

        return jsonify({
            'success': True,
            'engines': engines,
            'supported_languages': get_supported_languages(),
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@runtime_bp.route('/api/execution/ledger/nodes', methods=['GET'])
def get_executable_nodes():
    """List all active nodes from the ledger that can be executed.

    Returns snapshots with their current source code, language, version,
    and execution history summary.
    """
    try:
        if _session_ledger is None:
            return jsonify({'success': False, 'error': 'Runtime not initialized: _session_ledger is None'}), 500

        snapshots = _session_ledger.get_active_snapshots()
        nodes = []
        for nid, snap in snapshots.items():
            exec_history = _session_ledger.get_node_executions(nid)
            last_exec = exec_history[-1].get_payload() if exec_history else None
            nodes.append({
                'id': nid,
                'display_name': snap.display_name,
                'raw_name': snap.raw_name,
                'node_type': snap.node_type,
                'language': resolve_language_string(LanguageID(snap.current_language_id)),
                'language_id': snap.current_language_id,
                'source_code': snap.current_source_code,
                'version': snap.version,
                'is_modified': snap.is_modified,
                'is_converted': snap.is_converted,
                'class_name': snap.class_name,
                'execution_count': len(exec_history),
                'last_execution': last_exec,
            })
        # Sort by creation order
        nodes.sort(key=lambda n: n['display_name'])
        return jsonify({'success': True, 'nodes': nodes})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@runtime_bp.route('/api/execution/ledger/run/<node_id>', methods=['POST'])
def run_node_from_ledger(node_id):
    """Execute a single node using its current_source_code from the ledger.

    This is the key design: we read from the ledger (the source of truth),
    NOT from whatever the canvas currently shows.
    Supports Python, JavaScript, and Rust.
    """
    try:
        if _session_ledger is None:
            return jsonify({'success': False, 'error': 'Runtime not initialized: _session_ledger is None'}), 500

        snapshot = _session_ledger.get_node_snapshot(node_id)
        if not snapshot:
            return jsonify({'success': False, 'error': 'Node not found in ledger'}), 404

        lang = resolve_language_string(LanguageID(snapshot.current_language_id))
        executor = _get_executor(lang)
        if executor is None:
            supported = ', '.join(get_supported_languages())
            return jsonify({
                'success': False,
                'error': f'No live executor for "{lang}". Supported: {supported}'
            }), 400

        code = snapshot.current_source_code
        if not code or not code.strip():
            return jsonify({'success': False, 'error': 'Node has no source code'}), 400

        # Execute using the language-specific executor
        result = executor.execute(code)

        # Record in the ledger as an immutable execution event
        serializable_vars = {}
        if result.variables:
            for k, v in result.variables.items():
                if k.startswith('__'):
                    continue
                try:
                    json.dumps(v)
                    serializable_vars[k] = v
                except (TypeError, ValueError):
                    serializable_vars[k] = repr(v)[:200]

        _session_ledger.record_node_executed(
            node_id=node_id,
            success=result.success,
            output=result.output or '',
            error=str(result.error) if result.error else '',
            execution_time=result.execution_time,
            variables=serializable_vars,
            code_version=snapshot.version,
        )

        return jsonify({
            'success': True,
            'result': {
                'executed': True,
                'output': result.output or '',
                'error': str(result.error) if result.error else '',
                'execution_time': round(result.execution_time, 4),
                'variables': serializable_vars,
                'code_version': snapshot.version,
                'language': lang,
                'node_name': snapshot.display_name,
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@runtime_bp.route('/api/execution/ledger/run-all', methods=['POST'])
def run_all_from_ledger():
    """Execute all active nodes from the ledger in creation order.

    Uses the ledger's get_nodes_for_export() ordering — the same order
    the code would appear in an exported file.
    Supports Python, JavaScript, and Rust.  Nodes whose language has no
    executor are skipped with a warning in the results.
    """
    try:
        if _session_ledger is None:
            return jsonify({'success': False, 'error': 'Runtime not initialized: _session_ledger is None'}), 500

        data = request.get_json() or {}
        reset_namespace = data.get('reset', False)

        if reset_namespace:
            # Reset all executors that support it
            for executor in _executors.values():
                if hasattr(executor, 'reset_namespace'):
                    executor.reset_namespace()

        export_nodes = _session_ledger.get_nodes_for_export()
        results = []
        executed_ids = []
        total_time = 0.0
        all_success = True

        for node_data in export_nodes:
            lang = node_data.get('current_language', 'unknown')
            executor = _get_executor(lang)
            if executor is None:
                # Skip unsupported languages — include a note in results
                results.append({
                    'node_id': node_data['id'],
                    'node_name': node_data.get('raw_name') or node_data.get('name') or node_data['id'],
                    'success': True,
                    'output': '',
                    'error': '',
                    'execution_time': 0,
                    'variables': {},
                    'skipped': True,
                    'skip_reason': f'No live executor for "{lang}"',
                    'language': lang,
                })
                continue

            code = node_data.get('source_code', '')
            if not code or not code.strip():
                continue

            nid = node_data['id']
            executed_ids.append(nid)
            result = executor.execute(code)
            total_time += result.execution_time

            serializable_vars = {}
            if result.variables:
                for k, v in result.variables.items():
                    if k.startswith('__'):
                        continue
                    try:
                        json.dumps(v)
                        serializable_vars[k] = v
                    except (TypeError, ValueError):
                        serializable_vars[k] = repr(v)[:200]

            _session_ledger.record_node_executed(
                node_id=nid,
                success=result.success,
                output=result.output or '',
                error=str(result.error) if result.error else '',
                execution_time=result.execution_time,
                variables=serializable_vars,
            )

            node_result = {
                'node_id': nid,
                'node_name': node_data.get('raw_name') or node_data.get('name') or nid,
                'success': result.success,
                'output': result.output or '',
                'error': str(result.error) if result.error else '',
                'execution_time': round(result.execution_time, 4),
                'variables': serializable_vars,
                'language': lang,
            }
            results.append(node_result)

            if not result.success:
                all_success = False
                if not data.get('continue_on_error', False):
                    break

        _session_ledger.record_execution_batch(
            node_ids=executed_ids,
            success=all_success,
            total_time=total_time,
        )

        return jsonify({
            'success': True,
            'results': results,
            'summary': {
                'total_nodes': len(results),
                'passed': sum(1 for r in results if r['success']),
                'failed': sum(1 for r in results if not r['success']),
                'total_time': round(total_time, 4),
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@runtime_bp.route('/api/execution/ledger/history/<node_id>', methods=['GET'])
def get_node_execution_history(node_id):
    """Get all past execution events for a node from the ledger."""
    try:
        if _session_ledger is None:
            return jsonify({'success': False, 'error': 'Runtime not initialized: _session_ledger is None'}), 500

        executions = _session_ledger.get_node_executions(node_id)
        history = []
        for entry in executions:
            payload = entry.get_payload()
            history.append({
                'entry_id': entry.entry_id,
                'timestamp': entry.timestamp,
                'success': payload.get('success', False),
                'output': payload.get('output', ''),
                'error': payload.get('error', ''),
                'execution_time': payload.get('execution_time', 0),
                'code_version': payload.get('code_version', 0),
                'language': payload.get('language', 'unknown'),
            })
        return jsonify({'success': True, 'history': history})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@runtime_bp.route('/api/execution/reset-namespace', methods=['POST'])
def reset_execution_namespace():
    """Reset all executor namespaces — clears stale variables from prior runs."""
    try:
        reset_count = 0
        for lang, executor in _executors.items():
            if hasattr(executor, 'reset_namespace'):
                executor.reset_namespace()
                reset_count += 1
        return jsonify({'success': True, 'reset_count': reset_count})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@runtime_bp.route('/api/execution/ledger/variables', methods=['GET'])
def get_live_variables():
    """Get the current state of all variables in the live executor namespace."""
    try:
        if _live_executor is None:
            return jsonify({'success': False, 'error': 'Runtime not initialized: _live_executor is None'}), 500

        variables = {}

        # Prefer explicit namespace attribute if present (e.g. in some executors)
        namespace = getattr(_live_executor, 'namespace', None)
        if isinstance(namespace, dict):
            all_ns = dict(namespace)
        else:
            global_ns = getattr(_live_executor, 'global_namespace', {}) or {}
            local_ns = getattr(_live_executor, 'local_namespace', {}) or {}
            all_ns = {**global_ns, **local_ns}

        for k, v in all_ns.items():
            if k.startswith('__') or callable(v):
                continue
            try:
                json.dumps(v)
                variables[k] = {'value': v, 'type': type(v).__name__}
            except (TypeError, ValueError):
                variables[k] = {'value': repr(v)[:200], 'type': type(v).__name__}
        return jsonify({'success': True, 'variables': variables})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@runtime_bp.route('/api/execution/ledger/reset', methods=['POST'])
def reset_live_executor():
    """Reset all live executor namespaces (clear all variables)."""
    global _live_executor, _executors
    try:
        _live_executor = _PythonExecutor()
        _executors = {
            'python':     _live_executor,
            'javascript': _JavaScriptExecutor(),
            'rust':       _RustExecutor(),
        }
        return jsonify({'success': True, 'message': 'All executor namespaces reset'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ==================== MULTI-DEBUGGER EXECUTION ====================


class MultiDebuggerManager:
    """Manage multiple concurrent debug sessions for on-canvas execution"""

    def __init__(self):
        self.sessions = {}
        self.execution_order = []
        self.shared_namespace = {}

    def create_session(self, session_id, nodes, options=None):
        """Create a new debug session for a set of nodes.

        options.language  — override executor language (default: 'python')
        options.shared_namespace — share variables across sessions (default: True)
        """
        from visual_editor_core.execution_engine import (
            VisualDebugger, PythonExecutor, get_executor_for_language,
        )

        options = options or {}
        lang = options.get('language', 'python')

        # Create language-appropriate executor
        executor = get_executor_for_language(lang)
        if executor is None:
            executor = PythonExecutor()   # fallback

        session = {
            'id': session_id,
            'debugger': VisualDebugger(),
            'executor': executor,
            'language': lang,
            'nodes': nodes,
            'state': 'created',
            'current_node': None,
            'results': {},
            'shared_namespace': options.get('shared_namespace', True)
        }

        self.sessions[session_id] = session
        return session

    def start_session(self, session_id):
        """Start execution of a debug session"""
        if session_id not in self.sessions:
            raise ValueError(f"Session {session_id} not found")

        session = self.sessions[session_id]
        session['state'] = 'running'

        # If using shared namespace, copy it to the executor
        if session['shared_namespace']:
            session['executor'].namespace.update(self.shared_namespace)

        return session

    def step_session(self, session_id, step_type='next'):
        """Execute one step in a debug session"""
        if session_id not in self.sessions:
            raise ValueError(f"Session {session_id} not found")

        session = self.sessions[session_id]
        debugger = session['debugger']
        executor = session['executor']
        nodes = session['nodes']

        if not nodes:
            session['state'] = 'completed'
            return {'status': 'completed', 'results': session['results']}

        # Get next node to execute
        if session['current_node'] is None:
            current_index = 0
        else:
            current_index = next(
                (i for i, n in enumerate(nodes) if n['id'] == session['current_node']),
                -1
            ) + 1

        if current_index >= len(nodes):
            session['state'] = 'completed'
            # Update shared namespace
            if session['shared_namespace']:
                self.shared_namespace.update(executor.namespace)
            return {'status': 'completed', 'results': session['results']}

        node = nodes[current_index]
        session['current_node'] = node['id']

        # Execute the node
        code = node.get('code_snippet', '')
        if code:
            result = executor.execute(code)
            session['results'][node['id']] = result

            # Update shared namespace after execution
            if session['shared_namespace']:
                self.shared_namespace.update(executor.namespace)

            return {
                'status': 'stepped',
                'node_id': node['id'],
                'result': result,
                'variables': dict(executor.namespace)
            }

        return {
            'status': 'stepped',
            'node_id': node['id'],
            'result': None,
            'variables': dict(executor.namespace)
        }

    def get_session_state(self, session_id):
        """Get current state of a debug session"""
        if session_id not in self.sessions:
            return None

        session = self.sessions[session_id]
        return {
            'id': session_id,
            'state': session['state'],
            'current_node': session['current_node'],
            'results': session['results'],
            'variables': dict(session['executor'].namespace)
        }

    def stop_session(self, session_id):
        """Stop and remove a debug session"""
        if session_id in self.sessions:
            session = self.sessions[session_id]
            session['state'] = 'stopped'
            del self.sessions[session_id]
            return True
        return False

    def run_all_parallel(self, timeout=30):
        """Run all sessions in parallel (concurrent execution)"""
        import concurrent.futures

        results = {}

        def run_session(sid):
            session = self.sessions.get(sid)
            if not session:
                return None

            self.start_session(sid)

            while session['state'] == 'running':
                step_result = self.step_session(sid)
                if step_result['status'] == 'completed':
                    break

            return self.get_session_state(sid)

        with concurrent.futures.ThreadPoolExecutor(max_workers=len(self.sessions)) as pool:
            future_to_session = {
                pool.submit(run_session, sid): sid
                for sid in self.sessions.keys()
            }

            for future in concurrent.futures.as_completed(future_to_session, timeout=timeout):
                session_id = future_to_session[future]
                try:
                    results[session_id] = future.result()
                except Exception as e:
                    results[session_id] = {'error': str(e)}

        return results


# ==================== MULTI-DEBUGGER REST ROUTES ====================


@runtime_bp.route('/api/execution/multi-debug/create', methods=['POST'])
def create_debug_session_route():
    """Create a new debug session for a set of nodes"""
    try:
        data = request.json or {}
        session_id = data.get('session_id', str(uuid.uuid4()))
        nodes = data.get('nodes', [])
        options = data.get('options', {})

        if multi_debugger is None:
            return jsonify({
                'success': False,
                'error': 'multi_debugger not initialized'
            }), 500

        session = multi_debugger.create_session(session_id, nodes, options)

        return jsonify({
            'success': True,
            'session_id': session_id,
            'state': session['state'],
            'node_count': len(nodes)
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@runtime_bp.route('/api/execution/multi-debug/start/<session_id>', methods=['POST'])
def start_debug_session(session_id):
    """Start a debug session"""
    try:
        if multi_debugger is None:
            return jsonify({
                'success': False,
                'error': 'multi_debugger not initialized'
            }), 500

        session = multi_debugger.start_session(session_id)

        # Emit start event via WebSocket (if socketio is initialized)
        if _socketio is not None:
            _socketio.emit('debug_session_started', {
                'session_id': session_id,
                'state': session['state']
            })

        return jsonify({
            'success': True,
            'session_id': session_id,
            'state': session['state']
        })

    except ValueError as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 404
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@runtime_bp.route('/api/execution/multi-debug/step/<session_id>', methods=['POST'])
def step_debug_session(session_id):
    """Execute one step in a debug session"""
    try:
        data = request.json or {}
        step_type = data.get('step_type', 'next')

        if multi_debugger is None:
            return jsonify({
                'success': False,
                'error': 'multi_debugger not initialized'
            }), 500
        result = multi_debugger.step_session(session_id, step_type)

        # Emit step event via WebSocket for real-time UI update (if socketio is initialized)
        if _socketio is not None:
            _socketio.emit('debug_step_executed', {
                'session_id': session_id,
                'result': result
            })

        return jsonify({
            'success': True,
            'session_id': session_id,
            'result': result
        })

    except ValueError as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 404
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@runtime_bp.route('/api/execution/multi-debug/state/<session_id>', methods=['GET'])
def get_debug_session_state(session_id):
    """Get current state of a debug session"""
    try:
        if multi_debugger is None:
            return jsonify({
                'success': False,
                'error': 'multi_debugger not initialized'
            }), 500

        state = multi_debugger.get_session_state(session_id)
        if state is None:
            return jsonify({
                'success': False,
                'error': 'Session not found'
            }), 404

        return jsonify({
            'success': True,
            **state
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@runtime_bp.route('/api/execution/multi-debug/stop/<session_id>', methods=['POST'])
def stop_debug_session(session_id):
    """Stop and remove a debug session"""
    try:
        if multi_debugger is None:
            return jsonify({
                'success': False,
                'error': 'multi_debugger not initialized'
            }), 500

        success = multi_debugger.stop_session(session_id)

        if success:
            if _socketio is not None:
                _socketio.emit('debug_session_stopped', {
                    'session_id': session_id
                })
            return jsonify({
                'success': True,
                'session_id': session_id
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Session not found',
                'session_id': session_id
            }), 404

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
@runtime_bp.route('/api/execution/multi-debug/run-all', methods=['POST'])
def run_all_debug_sessions():
    """Run all active debug sessions in parallel"""
    try:
        data = request.json or {}
        timeout = data.get('timeout', 30)

        if multi_debugger is None:
            return jsonify({
                'success': False,
                'error': 'multi_debugger not initialized'
            }), 500

        results = multi_debugger.run_all_parallel(timeout)

        # Emit completion event (if socketio is initialized)
        if _socketio is not None:
            _socketio.emit('all_sessions_completed', {
                'results': results
            })

        return jsonify({
            'success': True,
            'results': results
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@runtime_bp.route('/api/execution/multi-debug/list', methods=['GET'])
def list_debug_sessions():
    """List all active debug sessions"""
    try:
        if multi_debugger is None:
            return jsonify({
                'success': False,
                'error': 'multi_debugger not initialized'
            }), 500

        sessions_list = []
        for session_id in multi_debugger.sessions:
            state = multi_debugger.get_session_state(session_id)
            if state:
                sessions_list.append(state)

        return jsonify({
            'success': True,
            'sessions': sessions_list,
            'count': len(sessions_list)
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ==================== WEBSOCKET EVENTS FOR MULTI-DEBUGGER ====================


def _register_websocket_handlers(sio):
    """Register SocketIO event handlers.  Called once from init_runtime()."""
    global multi_debugger

    # Ensure multi_debugger is initialized when handlers are registered
    if multi_debugger is None:
        multi_debugger = MultiDebuggerManager()

    # Capture a local reference so type checkers and handlers see a non-None manager
    md = multi_debugger

    @sio.on('create_debug_session')
    def handle_create_debug_session(data):
        """WebSocket handler for creating debug session"""
        # NOTE: this function is registered as a Socket.IO event handler and
        # therefore is used indirectly by the framework.
        def ws_emit(event, payload):
            sio.emit(event, payload)

        try:
            session_id = data.get('session_id', str(uuid.uuid4()))
            nodes = data.get('nodes', [])
            options = data.get('options', {})

            session = md.create_session(session_id, nodes, options)

            ws_emit('debug_session_created', {
                'success': True,
                'session_id': session_id,
                'state': session['state']
            })

        except Exception as e:
            ws_emit('debug_session_error', {
                'success': False,
                'error': str(e)
            })

    def handle_step_debug_session(data):
        """WebSocket handler for stepping debug session"""
        # NOTE: this function is registered as a Socket.IO event handler and
        # therefore is used indirectly by the framework.
        def ws_emit(event, payload):
            sio.emit(event, payload)

        try:
            session_id = data.get('session_id')
            step_type = data.get('step_type', 'next')

            if not session_id:
                ws_emit('debug_step_error', {'error': 'session_id required'})
                return

            if md is None:
                ws_emit('debug_step_error', {
                    'success': False,
                    'error': 'multi_debugger not initialized'
                })
                return

            result = md.step_session(session_id, step_type)

            ws_emit('debug_step_executed', {
                'success': True,
                'session_id': session_id,
                **result
            })

        except Exception as e:
            ws_emit('debug_step_error', {
                'success': False,
                'error': str(e)
            })


# ==================== PROJECT PERSISTENCE (SQLITE) ====================

from web_interface.project_db import (
    save_project as _db_save_project,
    list_projects as _db_list_projects,
    load_project as _db_load_project,
    delete_project as _db_delete_project,
)

from web_interface.engine_demos import (
    get_demo_tabs as _get_demo_tabs,
    get_all_demo_tabs as _get_all_demo_tabs,
    get_available_engines as _get_available_engines,
)


@runtime_bp.route('/api/projects', methods=['GET'])
def api_list_projects():
    """List all saved projects (metadata only)."""
    try:
        projects = _db_list_projects()
        return jsonify({'success': True, 'projects': projects})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@runtime_bp.route('/api/projects', methods=['POST'])
def api_save_project():
    """Save a project (canvas state + engine tabs).

    Body: { name, state, engine_tabs, description?, project_id? }
    """
    try:
        data = request.get_json() or {}
        name = data.get('name', 'Untitled')
        state = data.get('state', {})
        engine_tabs = data.get('engine_tabs', [])
        description = data.get('description', '')
        project_id = data.get('project_id', None)

        result = _db_save_project(name, state, engine_tabs, description, project_id)
        return jsonify({'success': True, 'project': result})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@runtime_bp.route('/api/projects/<project_id>', methods=['GET'])
def api_load_project(project_id):
    """Load a full project including canvas state and engine tabs."""
    try:
        project = _db_load_project(project_id)
        if not project:
            return jsonify({'success': False, 'error': 'Project not found'}), 404
        return jsonify({'success': True, 'project': project})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@runtime_bp.route('/api/projects/<project_id>', methods=['DELETE'])
def api_delete_project(project_id):
    """Delete a saved project."""
    try:
        deleted = _db_delete_project(project_id)
        if not deleted:
            return jsonify({'success': False, 'error': 'Project not found'}), 404
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ==================== SIMULTANEOUS MULTI-ENGINE EXECUTION ====================


@runtime_bp.route('/api/execution/engines/run-simultaneous', methods=['POST'])
def run_engines_simultaneous():
    """Execute code snippets across multiple engines simultaneously.

    Body: {
        tabs: [
            { engine_letter: "a", language: "python", code: "print('hello')", label: "main.py" },
            { engine_letter: "b", language: "javascript", code: "console.log('hi')", label: "app.js" },
            { engine_letter: "d", language: "rust", code: "fn main() { println!(\"hi\"); }", label: "main.rs" }
        ],
        reset_before: true  // optional: reset namespaces first
    }

    Returns per-tab execution results (language, output, error, time).
    """
    import concurrent.futures

    try:
        data = request.get_json() or {}
        tabs = data.get('tabs', [])
        reset_before = data.get('reset_before', False)

        if not tabs:
            return jsonify({'success': False, 'error': 'No tabs provided'}), 400

        if reset_before:
            for executor in _executors.values():
                if hasattr(executor, 'reset_namespace'):
                    executor.reset_namespace()

        def execute_tab(tab):
            lang = tab.get('language', '').lower().strip()
            code = tab.get('code', '')
            label = tab.get('label', lang)
            engine_letter = tab.get('engine_letter', '?')

            if not code.strip():
                return {
                    'engine_letter': engine_letter,
                    'language': lang,
                    'label': label,
                    'success': True,
                    'output': '',
                    'error': '',
                    'execution_time': 0,
                    'skipped': True,
                    'skip_reason': 'Empty code',
                }

            executor = _get_executor(lang)
            if executor is None:
                return {
                    'engine_letter': engine_letter,
                    'language': lang,
                    'label': label,
                    'success': False,
                    'output': '',
                    'error': f'No executor for "{lang}"',
                    'execution_time': 0,
                    'skipped': True,
                    'skip_reason': f'No executor for "{lang}"',
                }

            # For non-Python executors (subprocess-based) we can run in parallel.
            # For Python executor the GIL serialises anyway, but that's fine.
            result = executor.execute(code)

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
                'engine_letter': engine_letter,
                'language': lang,
                'label': label,
                'success': result.success,
                'output': result.output or '',
                'error': str(result.error) if result.error else '',
                'execution_time': round(result.execution_time, 4),
                'variables': variables,
            }

        # Execute all tabs concurrently
        results = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(tabs)) as pool:
            future_to_tab = {pool.submit(execute_tab, tab): tab for tab in tabs}
            for future in concurrent.futures.as_completed(future_to_tab, timeout=60):
                try:
                    results.append(future.result())
                except Exception as exc:
                    tab = future_to_tab[future]
                    results.append({
                        'engine_letter': tab.get('engine_letter', '?'),
                        'language': tab.get('language', '?'),
                        'label': tab.get('label', '?'),
                        'success': False,
                        'output': '',
                        'error': str(exc),
                        'execution_time': 0,
                    })

        # Sort results in input order (by engine_letter)
        letter_order = [t.get('engine_letter') for t in tabs]
        results.sort(key=lambda r: letter_order.index(r['engine_letter'])
                      if r['engine_letter'] in letter_order else 99)

        total_time = sum(r.get('execution_time', 0) for r in results)
        passed = sum(1 for r in results if r.get('success') and not r.get('skipped'))
        failed = sum(1 for r in results if not r.get('success'))

        return jsonify({
            'success': True,
            'results': results,
            'summary': {
                'total_tabs': len(results),
                'passed': passed,
                'failed': failed,
                'total_time': round(total_time, 4),
            }
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ==================== PER-SLOT EXECUTION (ISOLATION) ====================

@runtime_bp.route('/api/execution/registry/run-all-slots', methods=['POST'])
def run_all_registry_slots():
    """Execute every committed slot in the registry as an independent unit.

    Unlike ``run-simultaneous`` (which receives concatenated code per engine),
    this endpoint reads each slot's code from the session ledger and executes
    it in its own temp file / executor call.  This prevents "duplicate main"
    and other collision errors when an engine has multiple occupied slots.

    Body (optional):
        {
            "engines":       ["a","e","g","i","m"],  // filter to specific engines
            "reset_before":  false                   // reset namespaces first
        }

    Returns per-slot results with slot address, language, output, error, time.
    """
    import concurrent.futures

    try:
        if node_registry is None or _session_ledger is None:
            return jsonify({'success': False, 'error': 'Runtime not initialized'}), 500

        data = request.get_json(silent=True) or {}
        engine_filter = set(data.get('engines', []))
        reset_before = data.get('reset_before', False)

        if reset_before:
            for executor in _executors.values():
                if hasattr(executor, 'reset_namespace'):
                    executor.reset_namespace()

        # Collect all committed slots with code
        slots_to_run = []
        matrix = node_registry.get_matrix_summary()
        engines_dict = matrix.get('engines', {})
        for engine_name, engine_info in engines_dict.items():
            letter = engine_info.get('letter', '')
            if engine_filter and letter not in engine_filter:
                continue
            lang_name = engine_info.get('language', '')
            slots_dict = engine_info.get('slots', {})
            for pos_str, slot_data in slots_dict.items():
                if slot_data is None:
                    continue
                nid = slot_data.get('node_id')
                if not nid:
                    continue
                snapshot = _session_ledger.get_node_snapshot(nid)
                if not snapshot or not snapshot.current_source_code or not snapshot.current_source_code.strip():
                    continue
                lang = resolve_language_string(LanguageID(snapshot.current_language_id))
                position = int(pos_str) if pos_str.isdigit() else 0
                slots_to_run.append({
                    'slot_id': slot_data.get('slot_id', ''),
                    'address': f'{letter}{position}',
                    'engine_letter': letter,
                    'language': lang,
                    'code': snapshot.current_source_code.strip(),
                    'label': snapshot.display_name or slot_data.get('node_name', ''),
                    'node_id': nid,
                    'position': position,
                })

        if not slots_to_run:
            return jsonify({
                'success': True,
                'results': [],
                'summary': {'total_slots': 0, 'passed': 0, 'failed': 0, 'total_time': 0},
                'message': 'No committed slots with code in the registry',
            })

        def execute_slot(s):
            lang = s['language']
            code = s['code']
            executor = _get_executor(lang)
            if executor is None:
                return {
                    'slot_id': s['slot_id'],
                    'address': s['address'],
                    'engine_letter': s['engine_letter'],
                    'language': lang,
                    'label': s['label'],
                    'success': False,
                    'output': '',
                    'error': f'No executor for "{lang}"',
                    'execution_time': 0,
                    'skipped': True,
                    'skip_reason': f'No executor for "{lang}"',
                }

            result = executor.execute(code)

            # Record into registry
            node_registry.record_execution(
                slot_id=s['slot_id'],
                success=result.success,
                output=result.output or '',
                error=str(result.error) if result.error else '',
                execution_time=result.execution_time,
            )

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
                'slot_id': s['slot_id'],
                'address': s['address'],
                'engine_letter': s['engine_letter'],
                'language': lang,
                'label': s['label'],
                'success': result.success,
                'output': result.output or '',
                'error': str(result.error) if result.error else '',
                'execution_time': round(result.execution_time, 4),
                'variables': variables,
            }

        # Execute all slots concurrently (each slot is independent)
        results = []
        max_w = min(len(slots_to_run), 8)  # cap concurrency
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_w) as pool:
            future_map = {pool.submit(execute_slot, s): s for s in slots_to_run}
            for future in concurrent.futures.as_completed(future_map, timeout=120):
                try:
                    results.append(future.result())
                except Exception as exc:
                    s = future_map[future]
                    results.append({
                        'slot_id': s.get('slot_id', ''),
                        'address': s.get('address', ''),
                        'engine_letter': s.get('engine_letter', '?'),
                        'language': s.get('language', '?'),
                        'label': s.get('label', '?'),
                        'success': False,
                        'output': '',
                        'error': str(exc),
                        'execution_time': 0,
                    })

        # Sort by address for consistent ordering
        results.sort(key=lambda r: r.get('address', 'z99'))

        total_time = sum(r.get('execution_time', 0) for r in results)
        passed = sum(1 for r in results if r.get('success') and not r.get('skipped'))
        failed = sum(1 for r in results if not r.get('success'))

        return jsonify({
            'success': True,
            'results': results,
            'summary': {
                'total_slots': len(results),
                'passed': passed,
                'failed': failed,
                'total_time': round(total_time, 4),
            },
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@runtime_bp.route('/api/execution/registry/hydrate-slots', methods=['GET'])
def hydrate_registry_slots():
    """Build per-slot tabs from all committed registry slots.

    Unlike ``hydrate-from-canvas`` (which concatenates per language),
    this returns ONE tab per committed slot — each with its own code.

    Returns:
        { success, tabs: [ {engine_letter, language, code, label, slot_id, address, slot}, ... ] }
    """
    try:
        if node_registry is None or _session_ledger is None:
            return jsonify({'success': False, 'error': 'Runtime not initialized'}), 500

        matrix = node_registry.get_matrix_summary()
        tabs = []

        engines_dict = matrix.get('engines', {})
        for engine_name, engine_info in engines_dict.items():
            letter = engine_info.get('letter', '')
            slots_dict = engine_info.get('slots', {})
            for pos_str, slot_data in slots_dict.items():
                if slot_data is None:
                    continue
                nid = slot_data.get('node_id')
                if not nid:
                    continue
                snapshot = _session_ledger.get_node_snapshot(nid)
                if not snapshot or not snapshot.current_source_code or not snapshot.current_source_code.strip():
                    continue
                lang = resolve_language_string(LanguageID(snapshot.current_language_id))
                position = int(pos_str) if pos_str.isdigit() else 0
                tabs.append({
                    'engine_letter': letter,
                    'language': lang,
                    'code': snapshot.current_source_code.strip(),
                    'label': snapshot.display_name or slot_data.get('node_name', ''),
                    'slot_id': slot_data.get('slot_id', ''),
                    'address': f'{letter}{position}',
                    'slot': position,
                })

        tabs.sort(key=lambda t: t.get('address', 'z99'))

        return jsonify({
            'success': True,
            'tabs': tabs,
            'slot_count': len(tabs),
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ==================== POLYGLOT ENGINE DEMO ====================

@runtime_bp.route('/api/execution/engines/hydrate-from-canvas', methods=['GET'])
def hydrate_engine_tabs_from_canvas():
    """Build engine tab payloads from active canvas nodes in the ledger.

    Groups nodes by language, concatenates their source code, and returns
    a ready-to-use tabs array that the frontend can feed directly into
    ``runAllEngines()`` or ``loadFromJSON()``.

    This is the bridge between "nodes on canvas" and "engine tabs ready
    to run" — no manual tab creation needed.

    Returns:
        { success, tabs: [ {engine_letter, language, code, label}, ... ] }
    """
    try:
        if _session_ledger is None:
            return jsonify({'success': False, 'error': 'Session ledger not initialized'}), 500

        snapshots = _session_ledger.get_active_snapshots()
        if not snapshots:
            return jsonify({'success': True, 'tabs': [], 'node_count': 0,
                            'message': 'No active nodes in the ledger'})

        # Group nodes by language
        by_lang: dict[str, list] = {}
        for nid, snap in snapshots.items():
            code = snap.current_source_code
            if not code or not code.strip():
                continue
            lang = resolve_language_string(LanguageID(snap.current_language_id)).lower()
            by_lang.setdefault(lang, []).append({
                'display_name': snap.display_name,
                'node_type': snap.node_type,
                'code': code.strip(),
            })

        if not by_lang:
            return jsonify({'success': True, 'tabs': [], 'node_count': 0,
                            'message': 'Nodes found but none have source code'})

        # Reverse map: language → engine letter
        lang_to_letter = {v: k for k, v in LETTER_TO_LANG_DEFAULT.items()}

        tabs = []
        total_nodes = 0
        for lang, nodes in by_lang.items():
            letter = lang_to_letter.get(lang)
            if not letter:
                continue

            comment = '#' if lang in ('python', 'ruby', 'r', 'perl', 'bash') else '//'
            chunks = []
            for n in nodes:
                chunks.append(f"{comment} ── {n['display_name']} ({n['node_type']}) ──\n{n['code']}")
            combined = '\n\n'.join(chunks)

            display = ENGINE_NAMES_DEFAULT.get(letter, lang.title())
            tabs.append({
                'engine_letter': letter,
                'language': lang,
                'code': combined,
                'label': f"{display} ({len(nodes)} node{'s' if len(nodes) > 1 else ''})",
            })
            total_nodes += len(nodes)

        return jsonify({'success': True, 'tabs': tabs, 'node_count': total_nodes,
                        'language_count': len(tabs)})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# Fallback defaults for engine name/letter mapping
LETTER_TO_LANG_DEFAULT = {
    'a': 'python', 'b': 'javascript', 'c': 'typescript', 'd': 'rust',
    'e': 'java', 'f': 'swift', 'g': 'cpp', 'h': 'r',
    'i': 'go', 'j': 'ruby', 'k': 'csharp', 'l': 'kotlin',
    'm': 'c', 'n': 'bash', 'o': 'perl',
}
ENGINE_NAMES_DEFAULT = {
    'a': 'Python', 'b': 'JavaScript', 'c': 'TypeScript', 'd': 'Rust',
    'e': 'Java', 'f': 'Swift', 'g': 'C++', 'h': 'R',
    'i': 'Go', 'j': 'Ruby', 'k': 'C#', 'l': 'Kotlin',
    'm': 'C', 'n': 'Bash', 'o': 'Perl',
}


@runtime_bp.route('/api/demos/engine-tabs', methods=['GET'])
def api_demo_engine_tabs():
    """Return demo code tabs for all engines with detected toolchains.

    Query params:
        all=1   — include all 14 engines, with 'available' flag
    """
    try:
        show_all = request.args.get('all', '0') == '1'
        if show_all:
            tabs = _get_all_demo_tabs()
        else:
            tabs = _get_demo_tabs()
        return jsonify({'success': True, 'tabs': tabs, 'count': len(tabs)})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@runtime_bp.route('/api/engines/available', methods=['GET'])
def api_engines_available():
    """Return which of the 14 engines have their toolchain on PATH."""
    try:
        engines = _get_available_engines()
        ready = [e for e in engines if e['available']]
        return jsonify({
            'success': True,
            'engines': engines,
            'ready_count': len(ready),
            'total': len(engines),
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ==================== STAGING PIPELINE ====================

@runtime_bp.route('/api/staging/queue', methods=['POST'])
def staging_queue():
    """Queue a snippet into the staging pipeline.

    Body: { engine_letter, language, code, label? }
    Returns the staged snippet with reserved slot address.
    """
    try:
        if staging_pipeline is None:
            return jsonify({'success': False, 'error': 'Staging pipeline not initialized'}), 500
        data = request.get_json() or {}
        engine_letter = data.get('engine_letter', '')
        language = data.get('language', '')
        code = data.get('code', '')
        label = data.get('label', '')

        if not code.strip():
            return jsonify({'success': False, 'error': 'No code provided'}), 400
        if not engine_letter and not language:
            return jsonify({'success': False, 'error': 'engine_letter or language required'}), 400

        snippet = staging_pipeline.queue_snippet(engine_letter, language, code, label)
        return jsonify({'success': True, 'snippet': snippet.to_dict()})
    except ValueError as ve:
        return jsonify({'success': False, 'error': str(ve)}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@runtime_bp.route('/api/staging/speculate/<staging_id>', methods=['POST'])
def staging_speculate(staging_id):
    """Run speculative (dry-run) execution of a queued snippet.

    The snippet is executed in an ISOLATED sandbox. The production
    namespace is NOT touched.
    """
    try:
        if staging_pipeline is None:
            return jsonify({'success': False, 'error': 'Staging pipeline not initialized'}), 500
        snippet = staging_pipeline.speculate(staging_id)
        return jsonify({'success': True, 'snippet': snippet.to_dict()})
    except ValueError as ve:
        return jsonify({'success': False, 'error': str(ve)}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@runtime_bp.route('/api/staging/verdict/<staging_id>', methods=['POST'])
def staging_verdict(staging_id):
    """Issue a verdict on a speculated snippet.

    Body: { action: 'auto'|'approve'|'reject'|'hold', reason? }
    """
    try:
        if staging_pipeline is None:
            return jsonify({'success': False, 'error': 'Staging pipeline not initialized'}), 500
        data = request.get_json() or {}
        action = data.get('action', 'auto')
        reason = data.get('reason', '')
        snippet = staging_pipeline.verdict(staging_id, action, reason)
        return jsonify({'success': True, 'snippet': snippet.to_dict()})
    except ValueError as ve:
        return jsonify({'success': False, 'error': str(ve)}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@runtime_bp.route('/api/staging/promote/<staging_id>', methods=['POST'])
def staging_promote(staging_id):
    """Promote a PASSED snippet to production.

    Writes code to disk, creates ledger node, commits to registry slot.
    """
    try:
        if staging_pipeline is None:
            return jsonify({'success': False, 'error': 'Staging pipeline not initialized'}), 500
        snippet = staging_pipeline.promote(staging_id)
        return jsonify({'success': True, 'snippet': snippet.to_dict()})
    except ValueError as ve:
        return jsonify({'success': False, 'error': str(ve)}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@runtime_bp.route('/api/staging/run-full', methods=['POST'])
def staging_run_full():
    """Run the FULL staging pipeline in one call.

    Body: { engine_letter, language, code, label?, auto_promote? }

    queue → speculate → verdict → promote (if pass & auto_promote=true)
    """
    try:
        if staging_pipeline is None:
            return jsonify({'success': False, 'error': 'Staging pipeline not initialized'}), 500
        data = request.get_json() or {}
        engine_letter = data.get('engine_letter', '')
        language = data.get('language', '')
        code = data.get('code', '')
        label = data.get('label', '')
        auto_promote = data.get('auto_promote', True)

        if not code.strip():
            return jsonify({'success': False, 'error': 'No code provided'}), 400

        snippet = staging_pipeline.run_full_pipeline(
            engine_letter, language, code, label, auto_promote
        )
        return jsonify({'success': True, 'snippet': snippet.to_dict()})
    except ValueError as ve:
        return jsonify({'success': False, 'error': str(ve)}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@runtime_bp.route('/api/staging/rollback/<staging_id>', methods=['POST'])
def staging_rollback(staging_id):
    """Rollback a promoted snippet from production.

    Body: { reason? }
    """
    try:
        if staging_pipeline is None:
            return jsonify({'success': False, 'error': 'Staging pipeline not initialized'}), 500
        data = request.get_json() or {}
        reason = data.get('reason', '')
        snippet = staging_pipeline.rollback(staging_id, reason)
        return jsonify({'success': True, 'snippet': snippet.to_dict()})
    except ValueError as ve:
        return jsonify({'success': False, 'error': str(ve)}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@runtime_bp.route('/api/staging/snippets', methods=['GET'])
def staging_list():
    """List active staged snippets + optional history.

    Query: ?include_history=1&limit=100
    """
    try:
        if staging_pipeline is None:
            return jsonify({'success': False, 'error': 'Staging pipeline not initialized'}), 500
        include_history = request.args.get('include_history', '0') == '1'
        limit = int(request.args.get('limit', '100'))

        active = [s.to_dict() for s in staging_pipeline.get_active()]
        result = {'success': True, 'active': active}

        if include_history:
            result['history'] = [s.to_dict() for s in staging_pipeline.get_history(limit)]

        result['summary'] = staging_pipeline.get_pipeline_summary()
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@runtime_bp.route('/api/staging/snippet/<staging_id>', methods=['GET'])
def staging_get_snippet(staging_id):
    """Get a single snippet by staging_id (with full audit trail)."""
    try:
        if staging_pipeline is None:
            return jsonify({'success': False, 'error': 'Staging pipeline not initialized'}), 500
        snippet = staging_pipeline.get_snippet(staging_id)
        if snippet is None:
            return jsonify({'success': False, 'error': 'Not found'}), 404

        audit = staging_pipeline.get_audit_trail(staging_id)
        return jsonify({
            'success': True,
            'snippet': snippet.to_dict(),
            'audit_trail': audit,
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@runtime_bp.route('/api/staging/audit', methods=['GET'])
def staging_audit():
    """Get the full audit trail (most recent first).

    Query: ?staging_id=xxx&limit=500
    """
    try:
        if staging_pipeline is None:
            return jsonify({'success': False, 'error': 'Staging pipeline not initialized'}), 500
        sid = request.args.get('staging_id')
        limit = int(request.args.get('limit', '500'))
        entries = staging_pipeline.get_audit_trail(sid, limit)
        return jsonify({'success': True, 'entries': entries, 'count': len(entries)})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@runtime_bp.route('/api/staging/summary', methods=['GET'])
def staging_summary():
    """Get pipeline summary: active counts, history stats, reserved slots."""
    try:
        if staging_pipeline is None:
            return jsonify({'success': False, 'error': 'Staging pipeline not initialized'}), 500
        return jsonify({'success': True, **staging_pipeline.get_pipeline_summary()})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ==================== SETTINGS API ====================
# Three-tier configuration: DB (web UI) → .env → hard-coded default.
# The web interface can override any setting; deleting it reverts to
# the env / default value.

from web_interface.project_db import (
    get_setting as _db_get_setting,
    set_setting as _db_set_setting,
    get_all_settings as _db_get_all_settings,
    delete_setting as _db_delete_setting,
)

# Keys that can be managed through the API, with their env-var name
# and hard-coded fallback.
_KNOWN_SETTINGS = {
    'snippets_dir': {
        'env': 'SPOKEDPY_SNIPPETS_DIR',
        'default': os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'snippets'),
        'label': 'Snippet output directory',
        'restart_required': True,
    },
    'audit_log': {
        'env': 'SPOKEDPY_AUDIT_LOG',
        'default': os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'staging_audit.jsonl'),
        'label': 'Staging audit log path',
        'restart_required': True,
    },
    'marshal_ttl': {
        'env': 'SPOKEDPY_MARSHAL_TTL',
        'default': '4000',
        'label': 'Marshal token TTL (seconds)',
        'restart_required': False,
    },
}


@runtime_bp.route('/api/settings', methods=['GET'])
def settings_list():
    """Return all known settings with their effective values and sources."""
    db_settings = _db_get_all_settings()
    result = {}
    for key, meta in _KNOWN_SETTINGS.items():
        db_val = db_settings.get(key)
        env_val = os.environ.get(meta['env'], '').strip() or None
        effective = db_val or env_val or meta['default']
        source = 'database' if db_val else ('environment' if env_val else 'default')
        result[key] = {
            'value': effective,
            'source': source,
            'db_override': db_val,
            'env_value': env_val,
            'default': meta['default'],
            'label': meta['label'],
            'restart_required': meta['restart_required'],
        }
    return jsonify({'success': True, 'settings': result})


@runtime_bp.route('/api/settings/<key>', methods=['GET'])
def settings_get(key: str):
    """Return one setting with full resolution info."""
    key = key.lower()
    meta = _KNOWN_SETTINGS.get(key)
    if not meta:
        return jsonify({'success': False, 'error': f'Unknown setting: {key}'}), 404
    db_val = _db_get_setting(key)
    env_val = os.environ.get(meta['env'], '').strip() or None
    effective = db_val or env_val or meta['default']
    source = 'database' if db_val else ('environment' if env_val else 'default')
    return jsonify({
        'success': True,
        'key': key,
        'value': effective,
        'source': source,
        'db_override': db_val,
        'env_value': env_val,
        'default': meta['default'],
        'label': meta['label'],
        'restart_required': meta['restart_required'],
    })


@runtime_bp.route('/api/settings/<key>', methods=['PUT'])
def settings_set(key: str):
    """Set a database override for a setting.

    Body: ``{ "value": "..." }``
    """
    key = key.lower()
    meta = _KNOWN_SETTINGS.get(key)
    if not meta:
        return jsonify({'success': False, 'error': f'Unknown setting: {key}'}), 404
    data = request.get_json(force=True, silent=True) or {}
    value = data.get('value')
    if value is None:
        return jsonify({'success': False, 'error': 'Missing "value" field'}), 400
    rec = _db_set_setting(key, str(value))
    return jsonify({
        'success': True,
        'setting': rec,
        'restart_required': meta['restart_required'],
        'note': 'Server restart required for this change to take effect.' if meta['restart_required'] else 'Applied immediately.',
    })


@runtime_bp.route('/api/settings/<key>', methods=['DELETE'])
def settings_delete(key: str):
    """Remove a database override (reverts to env / default)."""
    key = key.lower()
    meta = _KNOWN_SETTINGS.get(key)
    if not meta:
        return jsonify({'success': False, 'error': f'Unknown setting: {key}'}), 404
    deleted = _db_delete_setting(key)
    if not deleted:
        return jsonify({'success': False, 'error': 'Setting was not overridden'}), 404
    return jsonify({
        'success': True,
        'reverted_to': os.environ.get(meta['env'], '').strip() or meta['default'],
        'source': 'environment' if os.environ.get(meta['env'], '').strip() else 'default',
    })


# ==================== MARSHAL TOKEN API ====================
# Opaque, TTL-governed gateway for external agents and systems.
# Callers submit code once, receive a unique token, and use that
# token for all subsequent interactions.  The token is the only
# identifier they ever need.  Internal staging_ids, slot addresses,
# and registry details are returned *through* the token endpoint
# as the snippet progresses through the pipeline.

@runtime_bp.route('/api/marshal', methods=['POST'])
def marshal_submit():
    """Submit code to the marshal.  Returns a unique token immediately.

    Body: { engine_letter, language, code, label?, auto_promote?, ttl? }

    The token is the caller's sole handle.  Use it at:
      GET /api/marshal/<token>          — full status + output + instructions
      GET /api/marshal/<token>/status   — compact phase-only check

    Response:
    {
        "success": true,
        "token": "m-7f3a9ce1b204",
        "phase": "promoted",
        "ttl": 4000,
        "expires_in": 4000,
        "endpoints": {
            "status":  "/api/marshal/m-7f3a9ce1b204/status",
            "details": "/api/marshal/m-7f3a9ce1b204",
            "resubmit": "/api/marshal"
        },
        "instructions": "Your code has been staged and processed. ..."
    }
    """
    try:
        if staging_pipeline is None:
            return jsonify({'success': False, 'error': 'Staging pipeline not initialized'}), 500

        data = request.get_json() or {}
        engine_letter = data.get('engine_letter', '')
        language = data.get('language', '')
        code = data.get('code', '')
        label = data.get('label', '')
        auto_promote = data.get('auto_promote', True)
        ttl = int(data.get('ttl', _MARSHAL_DEFAULT_TTL))
        # Provenance — who/what submitted this
        origin = data.get('origin', 'api')          # 'api' | 'live-exec' | 'canvas'
        submitter = data.get('submitter', '')
        agent_id = data.get('agent_id', '')

        if not code.strip():
            return jsonify({'success': False, 'error': 'No code provided'}), 400
        if not engine_letter and not language:
            return jsonify({'success': False, 'error': 'engine_letter or language required'}), 400

        # Purge stale tokens periodically
        _purge_expired_tokens()

        # Run the full pipeline synchronously
        snippet = staging_pipeline.run_full_pipeline(
            engine_letter, language, code, label, auto_promote
        )

        # Mint an opaque token bound to this snippet
        token = _mint_marshal_token(snippet.staging_id, ttl=ttl,
                                    origin=origin, submitter=submitter,
                                    agent_id=agent_id)

        # ── Broadcast snippet lifecycle event via SocketIO ──────────────
        if _socketio:
            _socketio.emit('snippet_lifecycle', {
                'event': 'submitted',
                'phase': snippet.phase.value,
                'token': token,
                'engine_letter': engine_letter or snippet.engine_letter,
                'language': language or snippet.language,
                'address': snippet.reserved_address,
                'label': label or snippet.label,
                'origin': origin,
                'submitter': submitter or ('Human' if origin == 'live-exec' else 'API Agent'),
                'ttl': ttl,
                'code_preview': code[:120].replace('\n', ' ') if code else '',
            })

        # Build the response
        phase = snippet.phase.value
        resp = {
            'success': True,
            'token': token,
            'phase': phase,
            'ttl': ttl,
            'expires_in': ttl,
            'endpoints': {
                'status':  f'/api/marshal/{token}/status',
                'details': f'/api/marshal/{token}',
                'resubmit': '/api/marshal',
            },
        }

        if phase == 'promoted':
            resp['instructions'] = (
                f"Your code is live. "
                f"Use GET /api/marshal/{token} for full details including output and slot info. "
                f"Use GET /api/marshal/{token}/status for a quick phase check. "
                f"This token expires in {ttl} seconds — after expiry, resubmit your code to /api/marshal to get a new token."
            )
            resp['output'] = (snippet.spec_output or '').strip()
            resp['execution_time'] = round(snippet.spec_execution_time, 4)
        elif phase in ('rejected', 'failed'):
            resp['instructions'] = (
                f"Your code was {phase}. Check the error below, fix your code, "
                f"and POST to /api/marshal again. The reserved slot has been released."
            )
            resp['error'] = snippet.spec_error or ''
        else:
            resp['instructions'] = (
                f"Your code is being processed (phase: {phase}). "
                f"Poll GET /api/marshal/{token}/status to monitor progress. "
                f"This token expires in {ttl} seconds."
            )

        # ── Checkpoint state after successful submission ────────────────
        if phase == 'promoted':
            _trigger_checkpoint()

        return jsonify(resp)
    except ValueError as ve:
        return jsonify({'success': False, 'error': str(ve)}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@runtime_bp.route('/api/marshal/<token>', methods=['GET'])
def marshal_details(token):
    """Full status report for a marshal token.

    Returns snippet details, output, slot info, audit trail,
    and TTL remaining.  404 if token is unknown or expired.
    """
    try:
        if staging_pipeline is None:
            return jsonify({'success': False, 'error': 'Staging pipeline not initialized'}), 500

        trec = _resolve_marshal_token(token)
        if trec is None:
            return jsonify({
                'success': False,
                'error': 'Unknown token. It may have expired or never existed.',
                'action': 'Resubmit your code to POST /api/marshal to get a new token.',
            }), 404

        if trec['expired']:
            return jsonify({
                'success': False,
                'error': 'Token expired.',
                'expired': True,
                'action': 'Resubmit your code to POST /api/marshal to get a new token.',
                'ttl_was': trec['ttl'],
                'elapsed': trec['elapsed'],
            }), 410  # 410 Gone

        snippet = staging_pipeline.get_snippet(trec['staging_id'])
        if snippet is None:
            return jsonify({
                'success': False,
                'error': 'Snippet not found (server may have restarted).',
                'action': 'Resubmit your code to POST /api/marshal.',
            }), 404

        sd = snippet.to_dict()
        phase = sd['phase']

        resp = {
            'success': True,
            'token': token,
            'phase': phase,
            'ttl': trec['ttl'],
            'expires_in': trec['remaining'],
            'label': sd.get('label', ''),
            'language': sd.get('language', ''),
            'engine_letter': sd.get('engine_letter', ''),
            'created_at': sd.get('created_at', 0),
            'endpoints': {
                'status':  f'/api/marshal/{token}/status',
                'details': f'/api/marshal/{token}',
                'resubmit': '/api/marshal',
            },
        }

        # Execution results
        if sd.get('spec_output') is not None:
            resp['output'] = (sd['spec_output'] or '').strip()
        if sd.get('spec_error'):
            resp['error'] = sd['spec_error']
        if sd.get('spec_execution_time'):
            resp['execution_time'] = round(sd['spec_execution_time'], 4)
        resp['spec_success'] = sd.get('spec_success', False)

        # Slot info (only exposed once promoted, and ONLY through this token)
        if phase == 'promoted':
            resp['slot'] = {
                'slot_id': sd.get('registry_slot_id', ''),
                'address': sd.get('reserved_address', ''),
                'execute': f"/api/registry/slot/{sd.get('registry_slot_id', '')}/execute",
                'output': f"/api/registry/slot/{sd.get('registry_slot_id', '')}/output?last_n=10",
                'push': f"/api/registry/slot/{sd.get('registry_slot_id', '')}/push",
                'details': f"/api/registry/slot/{sd.get('registry_slot_id', '')}"
            }

        # Audit trail
        try:
            audit = staging_pipeline.get_audit_trail(trec['staging_id'])
            resp['audit_trail'] = audit
        except Exception:
            resp['audit_trail'] = []

        return jsonify(resp)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@runtime_bp.route('/api/marshal/<token>/status', methods=['GET'])
def marshal_status(token):
    """Compact phase-only check for a marshal token.

    Returns just the phase, TTL remaining, and whether the token is
    still valid.  Designed for fast polling by agents.
    """
    try:
        trec = _resolve_marshal_token(token)
        if trec is None:
            return jsonify({
                'valid': False,
                'error': 'Unknown token.',
                'action': 'resubmit',
            }), 404

        if trec['expired']:
            return jsonify({
                'valid': False,
                'expired': True,
                'action': 'resubmit',
                'ttl_was': trec['ttl'],
            }), 410

        snippet = staging_pipeline.get_snippet(trec['staging_id']) if staging_pipeline else None
        phase = snippet.phase.value if snippet else 'unknown'

        return jsonify({
            'valid': True,
            'token': token,
            'phase': phase,
            'expires_in': trec['remaining'],
            'promoted': phase == 'promoted',
        })
    except Exception as e:
        return jsonify({'valid': False, 'error': str(e)}), 500


# ==================== CONTINUOUS RUNTIME CONTROL ====================

# Module-level runtime state (the actual loop lives in the browser;
# this endpoint just records state for server-side awareness and
# emits SocketIO events so other connected clients can see status).
_runtime_state = {
    'state': 'stopped',   # running | paused | stopped
    'interval': 5,
    'started_at': None,
    'cycles': 0,
}


@runtime_bp.route('/api/runtime/control', methods=['POST'])
def runtime_control():
    """Accept runtime control commands from the Runtime Panel.

    Body: { action: "start"|"pause"|"resume"|"stop", interval?: int }
    Broadcasts status via SocketIO so all connected dashboards stay in sync.
    """
    from datetime import datetime as _dt

    try:
        data = request.get_json() or {}
        action = data.get('action', '').lower()

        if action == 'start':
            _runtime_state['state'] = 'running'
            _runtime_state['started_at'] = _dt.utcnow().isoformat()
            _runtime_state['cycles'] = 0
            _runtime_state['interval'] = data.get('interval', _runtime_state['interval'])
        elif action == 'resume':
            _runtime_state['state'] = 'running'
        elif action == 'pause':
            _runtime_state['state'] = 'paused'
        elif action == 'stop':
            _runtime_state['state'] = 'stopped'
            _runtime_state['started_at'] = None
        else:
            return jsonify({'success': False, 'error': f'Unknown action: {action}'}), 400

        if data.get('interval'):
            _runtime_state['interval'] = int(data['interval'])

        # Broadcast to all connected clients
        if _socketio:
            _socketio.emit('runtime_status', {
                'state': _runtime_state['state'],
                'interval': _runtime_state['interval'],
                'started_at': _runtime_state['started_at'],
            })

        return jsonify({'success': True, **_runtime_state})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@runtime_bp.route('/api/runtime/status', methods=['GET'])
def runtime_status():
    """Get the current runtime state."""
    return jsonify({'success': True, **_runtime_state})


@runtime_bp.route('/api/runtime/server-info', methods=['GET'])
def runtime_server_info():
    """Return server information for the dashboard.

    Includes available engines, executor pool state, and server uptime.
    """
    import time as _time

    try:
        # Engine pool info
        engine_info = []
        for lang, executor in _executors.items():
            engine_info.append({
                'language': lang,
                'type': type(executor).__name__,
                'has_namespace': hasattr(executor, 'namespace'),
            })

        # Available engines on this machine
        available = _get_available_engines()

        return jsonify({
            'success': True,
            'runtime_state': _runtime_state,
            'engines': engine_info,
            'engine_count': len(engine_info),
            'available_engines': available,
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ==================== ENRICHED MATRIX + SLOT INTERACTIONS ====================

@runtime_bp.route('/api/registry/matrix/enriched', methods=['GET'])
def get_enriched_matrix():
    """Return the full matrix with provenance, TTL, lock status, and
    staging pipeline state for each occupied slot.

    This is the data source for the interactive mission-control matrix.
    Each slot includes:
      - origin: 'live-exec' | 'api' | 'canvas'
      - submitter / agent_id
      - token, TTL remaining
      - locked (pinned indefinitely)
      - staging phase history
      - performance stats (exec count, avg time, last output)
    """
    try:
        if node_registry is None:
            return jsonify({'success': False, 'error': 'Registry not initialized'}), 500

        matrix = node_registry.get_matrix_summary()

        # Build a reverse lookup: staging_id → token record + token string
        token_by_staging = {}
        with _marshal_lock:
            for tok, rec in _marshal_tokens.items():
                elapsed = _time.time() - rec['created_at']
                remaining = max(0, rec['ttl'] - elapsed)
                token_by_staging[rec['staging_id']] = {
                    'token': tok,
                    'ttl': rec['ttl'],
                    'remaining': round(remaining, 1),
                    'expired': remaining <= 0,
                    'origin': rec.get('origin', 'api'),
                    'submitter': rec.get('submitter', 'Unknown'),
                    'agent_id': rec.get('agent_id', ''),
                    'created_at': rec['created_at'],
                }

        # Build staging snippet lookup
        snippet_by_staging = {}
        if staging_pipeline:
            for sn in staging_pipeline.get_active():
                snippet_by_staging[sn.staging_id] = sn
            for sn in staging_pipeline.get_history(limit=500):
                snippet_by_staging[sn.staging_id] = sn

        # Enrich each occupied slot
        engines = matrix.get('engines', {})
        for engine_name, row in engines.items():
            letter = row.get('letter', '')
            slots = row.get('slots', {})
            for pos_str, slot_data in slots.items():
                if not slot_data or not slot_data.get('node_id'):
                    continue
                addr = f"{letter}{pos_str}"
                nid = slot_data.get('node_id', '')

                # Check if this slot was created via staging pipeline
                staging_id = None
                if nid.startswith('snippet-'):
                    staging_id = nid.replace('snippet-', '')

                # Provenance from marshal token
                provenance = token_by_staging.get(staging_id, {})

                # Staging snippet data
                sn_data = {}
                sn = snippet_by_staging.get(staging_id)
                if sn:
                    sn_data = {
                        'phase': sn.phase.value,
                        'spec_success': sn.spec_success,
                        'spec_execution_time': round(sn.spec_execution_time, 4),
                        'spec_output_preview': (sn.spec_output or '')[:200],
                        'code_preview': (sn.code or '')[:300],
                        'code_hash': sn.code_hash[:12] if sn.code_hash else '',
                        'promoted_at': sn.promoted_at,
                        'label': sn.label,
                    }

                # Lock status
                is_locked = False
                lock_info = {}
                with _locked_slots_lock:
                    if addr in _locked_slots:
                        is_locked = True
                        lock_info = _locked_slots[addr]

                # Execution stats — pull directly from the RegistrySlot object
                exec_stats = {
                    'exec_count': slot_data.get('exec_count', 0),
                }
                # Try to get richer stats from the actual slot
                try:
                    pos_int = int(pos_str)
                    actual_slot = node_registry.get_slot_by_address(letter, pos_int)
                    if actual_slot:
                        exec_stats['exec_count'] = actual_slot.execution_count
                        exec_stats['last_exec_time'] = round(actual_slot.last_execution_time, 4)
                        exec_stats['last_success'] = actual_slot.last_error == ''
                        exec_stats['last_output_preview'] = (actual_slot.last_output or '')[:200]
                except (ValueError, AttributeError):
                    pass

                # Determine visual origin
                if provenance:
                    vis_origin = provenance.get('origin', 'api')
                elif nid.startswith('snippet-'):
                    vis_origin = 'api'
                else:
                    vis_origin = 'live-exec'

                slot_data['provenance'] = {
                    'origin': vis_origin,
                    'submitter': provenance.get('submitter', 'Live Execution' if vis_origin == 'live-exec' else 'Unknown'),
                    'agent_id': provenance.get('agent_id', ''),
                    'token': provenance.get('token', ''),
                    'ttl': provenance.get('ttl', 0),
                    'ttl_remaining': provenance.get('remaining', 0),
                    'expired': provenance.get('expired', False),
                    'created_at': provenance.get('created_at', 0),
                }
                slot_data['staging'] = sn_data
                slot_data['locked'] = is_locked
                slot_data['lock_info'] = lock_info
                slot_data['exec_stats'] = exec_stats

        # Include active staging pipeline entries (snippets in flight)
        in_flight = []
        if staging_pipeline:
            for sn in staging_pipeline.get_active():
                in_flight.append({
                    'staging_id': sn.staging_id,
                    'phase': sn.phase.value,
                    'engine_letter': sn.engine_letter,
                    'language': sn.language,
                    'label': sn.label,
                    'reserved_address': sn.reserved_address,
                    'code_preview': (sn.code or '')[:120].replace('\n', ' '),
                    'created_at': sn.created_at,
                })

        return jsonify({
            'success': True,
            **matrix,
            'in_flight': in_flight,
            'locked_count': len(_locked_slots),
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@runtime_bp.route('/api/registry/slot/<address>/lock', methods=['POST'])
def lock_slot(address):
    """Lock (pin) a slot indefinitely — bypasses token TTL expiration.

    Body: { reason? }
    Double-click on a matrix cell calls this.
    """
    try:
        addr = address.lower().strip()
        with _locked_slots_lock:
            body = request.get_json(silent=True) or {}
            _locked_slots[addr] = {
                'locked_at': _time.time(),
                'locked_by': 'dashboard',
                'reason': body.get('reason', 'Pinned from dashboard'),
            }

        # Broadcast lock event
        if _socketio:
            _socketio.emit('snippet_lifecycle', {
                'event': 'locked',
                'address': addr,
            })

        _trigger_checkpoint()
        return jsonify({'success': True, 'address': addr, 'locked': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@runtime_bp.route('/api/registry/slot/<address>/unlock', methods=['POST'])
def unlock_slot(address):
    """Unlock a previously pinned slot — restores normal TTL expiration."""
    try:
        addr = address.lower().strip()
        with _locked_slots_lock:
            removed = _locked_slots.pop(addr, None)
        if _socketio:
            _socketio.emit('snippet_lifecycle', {
                'event': 'unlocked',
                'address': addr,
            })
        _trigger_checkpoint()
        return jsonify({'success': True, 'address': addr, 'was_locked': removed is not None})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@runtime_bp.route('/api/registry/slot/<address>/evict', methods=['DELETE'])
def evict_slot(address):
    """Evict (delete) a snippet from a slot — removes from registry + ledger.

    Long-press on a matrix cell calls this after confirmation.
    """
    try:
        if node_registry is None:
            return jsonify({'success': False, 'error': 'Registry not initialized'}), 500

        addr = address.lower().strip()
        # Support both 'p1' and 'p-1' address formats
        if '-' in addr:
            parts = addr.split('-', 1)
            letter = parts[0]
            pos_str = parts[1]
        elif len(addr) >= 2:
            letter = addr[0]
            pos_str = addr[1:]
        else:
            return jsonify({'success': False, 'error': 'Invalid address'}), 400

        # Find the slot in the registry
        matrix = node_registry.get_matrix_summary()
        engines = matrix.get('engines', {})

        target_engine = None
        target_slot = None
        for ename, row in engines.items():
            if row.get('letter') == letter:
                target_engine = ename
                target_slot = row.get('slots', {}).get(pos_str)
                break

        if not target_slot or not target_slot.get('node_id'):
            return jsonify({'success': False, 'error': f'No snippet in slot {addr.upper()}'}), 404

        node_id = target_slot['node_id']
        slot_id = target_slot.get('slot_id', '')

        # Clear the registry slot
        if slot_id:
            node_registry.clear_slot(slot_id)

        # Delete the node from the session ledger so it can't be
        # re-committed by commit_all_from_ledger or re-hydrated by
        # autoHydrateFromCanvas.  The ledger keeps the history
        # (immutable audit trail) but marks the node as deleted.
        ledger_deleted = False
        if _session_ledger:
            entry = _session_ledger.record_node_deleted(node_id)
            ledger_deleted = entry is not None

        # Expire / remove the marshal token tied to this snippet
        # so it doesn't appear as in-flight or contribute to TTL sweeps
        staging_id = None
        if node_id.startswith('snippet-'):
            staging_id = node_id.replace('snippet-', '')
        evicted_token = None
        if staging_id:
            with _marshal_lock:
                for tok, rec in list(_marshal_tokens.items()):
                    if rec.get('staging_id') == staging_id:
                        evicted_token = tok
                        del _marshal_tokens[tok]
                        break

        # Remove lock if any
        with _locked_slots_lock:
            _locked_slots.pop(addr, None)

        # Broadcast eviction
        if _socketio:
            _socketio.emit('snippet_lifecycle', {
                'event': 'evicted',
                'address': addr,
                'node_id': node_id,
            })

        _trigger_checkpoint()
        return jsonify({
            'success': True,
            'address': addr.upper(),
            'evicted_node': node_id,
            'slot_id': slot_id,
            'ledger_deleted': ledger_deleted,
            'token_revoked': evicted_token,
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@runtime_bp.route('/api/registry/slot/<address>/info', methods=['GET'])
def slot_info(address):
    """Full forensic details for a single slot — token, provenance, code,
    performance stats.  Called by the single-click overlay.
    """
    try:
        if node_registry is None:
            return jsonify({'success': False, 'error': 'Registry not initialized'}), 500

        addr = address.lower().strip()
        # Support both 'p1' and 'p-1' address formats
        if '-' in addr:
            parts = addr.split('-', 1)
            letter = parts[0]
            pos_str = parts[1]
        elif len(addr) >= 2:
            letter = addr[0]
            pos_str = addr[1:]
        else:
            return jsonify({'success': False, 'error': 'Invalid address'}), 400

        matrix = node_registry.get_matrix_summary()
        engines = matrix.get('engines', {})

        slot_data = None
        engine_name = ''
        for ename, row in engines.items():
            if row.get('letter') == letter:
                engine_name = ename
                slot_data = row.get('slots', {}).get(pos_str)
                break

        if not slot_data or not slot_data.get('node_id'):
            return jsonify({'success': True, 'address': addr.upper(),
                            'occupied': False, 'message': 'Slot is empty'})

        nid = slot_data.get('node_id', '')
        staging_id = nid.replace('snippet-', '') if nid.startswith('snippet-') else None

        # Provenance from token
        provenance = {}
        if staging_id:
            with _marshal_lock:
                for tok, rec in _marshal_tokens.items():
                    if rec['staging_id'] == staging_id:
                        elapsed = _time.time() - rec['created_at']
                        remaining = max(0, rec['ttl'] - elapsed)
                        provenance = {
                            'token': tok,
                            'ttl': rec['ttl'],
                            'ttl_remaining': round(remaining, 1),
                            'expired': remaining <= 0,
                            'origin': rec.get('origin', 'api'),
                            'submitter': rec.get('submitter', 'Unknown'),
                            'agent_id': rec.get('agent_id', ''),
                            'created_at': rec['created_at'],
                        }
                        break

        # Full staging snippet
        snippet_details = {}
        if staging_id and staging_pipeline:
            sn = staging_pipeline.get_snippet(staging_id)
            if sn:
                snippet_details = sn.to_dict()

        # Lock info
        is_locked = False
        lock_info = {}
        with _locked_slots_lock:
            if addr in _locked_slots:
                is_locked = True
                lock_info = _locked_slots[addr]

        # Ledger snapshot for non-staging nodes
        ledger_info = {}
        if _session_ledger and not staging_id:
            snap = _session_ledger.get_active_snapshots().get(nid)
            if snap:
                ledger_info = {
                    'display_name': snap.display_name,
                    'node_type': snap.node_type,
                    'language': resolve_language_string(LanguageID(snap.current_language_id)),
                    'source_code': snap.current_source_code or '',
                    'version': snap.version,
                }

        # Execution stats from actual RegistrySlot
        exec_stats = {'exec_count': slot_data.get('exec_count', 0)}
        try:
            pos_int = int(pos_str)
            actual_slot = node_registry.get_slot_by_address(letter, pos_int)
            if actual_slot:
                exec_stats['exec_count'] = actual_slot.execution_count
                exec_stats['last_exec_time'] = round(actual_slot.last_execution_time, 4)
                exec_stats['last_success'] = actual_slot.last_error == ''
                exec_stats['last_output_preview'] = (actual_slot.last_output or '')[:400]
                exec_stats['last_error'] = (actual_slot.last_error or '')[:400]
                exec_stats['last_executed_at'] = actual_slot.last_executed_at
        except (ValueError, AttributeError):
            pass

        return jsonify({
            'success': True,
            'address': addr.upper(),
            'occupied': True,
            'engine': engine_name,
            'node_id': nid,
            'slot_id': slot_data.get('slot_id', ''),
            'version': slot_data.get('version', 0),
            'provenance': provenance,
            'staging': snippet_details,
            'ledger': ledger_info,
            'locked': is_locked,
            'lock_info': lock_info,
            'origin': provenance.get('origin', 'live-exec'),
            'exec_stats': exec_stats,
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ==================== STATE PERSISTENCE API ====================

@runtime_bp.route('/api/state/checkpoint', methods=['POST'])
def force_checkpoint():
    """Force an immediate state checkpoint (synchronous write).

    Called by the frontend before a planned restart, or manually by
    the user to ensure state is persisted.
    """
    try:
        if _state_persistence is None or staging_pipeline is None:
            return jsonify({'success': False, 'error': 'State persistence not initialized'}), 500

        with _marshal_lock:
            tokens_copy = dict(_marshal_tokens)
        with _locked_slots_lock:
            locks_copy = dict(_locked_slots)

        snapshots = build_promoted_snapshots(staging_pipeline, tokens_copy, locks_copy)
        _state_persistence.checkpoint_now(locks_copy, tokens_copy, snapshots)

        return jsonify({
            'success': True,
            'message': 'Checkpoint written',
            'path': _state_persistence.path,
            'promoted_count': len(snapshots),
            'locked_count': len(locks_copy),
            'token_count': len(tokens_copy),
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@runtime_bp.route('/api/state/checkpoint', methods=['GET'])
def get_checkpoint_info():
    """Return metadata about the current checkpoint file.

    Does NOT return full state — just summary info for diagnostics.
    """
    try:
        if _state_persistence is None:
            return jsonify({'success': False, 'error': 'State persistence not initialized'}), 500

        state = _state_persistence.restore()
        if state is None:
            return jsonify({
                'success': True,
                'exists': False,
                'path': _state_persistence.path,
            })

        return jsonify({
            'success': True,
            'exists': True,
            'path': _state_persistence.path,
            'version': state.get('version', 0),
            'saved_at': state.get('saved_at', 0),
            'saved_at_iso': state.get('saved_at_iso', ''),
            'promoted_count': len(state.get('promoted_snippets', [])),
            'locked_count': len(state.get('locked_slots', {})),
            'token_count': len(state.get('marshal_tokens', {})),
            'snippets_summary': [
                {
                    'staging_id': s.get('staging_id', ''),
                    'address': s.get('address', ''),
                    'language': s.get('language', ''),
                    'label': s.get('label', ''),
                    'locked': s.get('locked', False),
                }
                for s in state.get('promoted_snippets', [])
            ],
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# =============================================================================
# MESH RELAY — Distributed Instance Interconnect
# =============================================================================

@runtime_bp.route('/api/mesh/status', methods=['GET'])
def mesh_status():
    """Get the current mesh relay status and topology."""
    try:
        if mesh_relay is None:
            return jsonify({'success': False, 'error': 'Mesh relay not initialized'}), 500

        topology = mesh_relay.get_topology()
        return jsonify({'success': True, **topology})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@runtime_bp.route('/api/mesh/peers', methods=['GET'])
def mesh_list_peers():
    """List all registered peers."""
    try:
        if mesh_relay is None:
            return jsonify({'success': False, 'error': 'Mesh relay not initialized'}), 500

        return jsonify({
            'success': True,
            'instance_id': mesh_relay.instance_id,
            'instance_name': mesh_relay.instance_name,
            'peers': mesh_relay.list_peers(),
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@runtime_bp.route('/api/mesh/peers', methods=['POST'])
def mesh_add_peer():
    """
    Register a remote VPyD instance as a peer.

    Body: { "peer_id": "node-2", "url": "http://192.168.1.102:5002", "role": "peer" }
    """
    try:
        if mesh_relay is None:
            return jsonify({'success': False, 'error': 'Mesh relay not initialized'}), 500

        data = request.get_json() or {}
        peer_id = data.get('peer_id', '').strip()
        url = data.get('url', '').strip()
        role_str = data.get('role', 'peer')

        if not peer_id or not url:
            return jsonify({'success': False, 'error': 'peer_id and url are required'}), 400

        try:
            role = MeshRole(role_str)
        except ValueError:
            role = MeshRole.PEER

        ok = mesh_relay.add_peer(peer_id, url, role)
        if not ok:
            return jsonify({'success': False, 'error': 'Failed to add peer — max peers reached or duplicate ID'}), 400

        return jsonify({
            'success': True,
            'peer_id': peer_id,
            'peers': mesh_relay.list_peers(),
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@runtime_bp.route('/api/mesh/peers/<peer_id>', methods=['DELETE'])
def mesh_remove_peer(peer_id):
    """Remove a peer from the mesh."""
    try:
        if mesh_relay is None:
            return jsonify({'success': False, 'error': 'Mesh relay not initialized'}), 500

        ok = mesh_relay.remove_peer(peer_id)
        if not ok:
            return jsonify({'success': False, 'error': f'Peer {peer_id} not found'}), 404

        return jsonify({'success': True, 'removed': peer_id})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@runtime_bp.route('/api/mesh/activate', methods=['POST'])
def mesh_activate():
    """Activate the mesh relay — starts heartbeat and relay threads."""
    try:
        if mesh_relay is None:
            return jsonify({'success': False, 'error': 'Mesh relay not initialized'}), 500

        result = mesh_relay.activate()
        return jsonify({'success': True, **result})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@runtime_bp.route('/api/mesh/deactivate', methods=['POST'])
def mesh_deactivate():
    """Deactivate the mesh relay — stops threads and clears relay lanes."""
    try:
        if mesh_relay is None:
            return jsonify({'success': False, 'error': 'Mesh relay not initialized'}), 500

        ok = mesh_relay.deactivate()
        return jsonify({'success': ok})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@runtime_bp.route('/api/mesh/subscribe', methods=['POST'])
def mesh_subscribe():
    """
    Subscribe a local slot's output to be forwarded to a peer.

    Body: { "local_addr": "a5", "peer_id": "node-2" }
    """
    try:
        if mesh_relay is None:
            return jsonify({'success': False, 'error': 'Mesh relay not initialized'}), 500

        data = request.get_json() or {}
        local_addr = data.get('local_addr', '').strip()
        peer_id = data.get('peer_id', '').strip()

        if not local_addr or not peer_id:
            return jsonify({'success': False, 'error': 'local_addr and peer_id are required'}), 400

        ok = mesh_relay.subscribe_slot_to_peer(local_addr, peer_id)
        if not ok:
            return jsonify({'success': False, 'error': 'Subscription failed — peer not found'}), 400

        return jsonify({'success': True, 'local_addr': local_addr, 'peer_id': peer_id})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@runtime_bp.route('/api/mesh/heartbeat', methods=['GET'])
def mesh_heartbeat():
    """
    Heartbeat endpoint — called by remote peers to check liveness.
    Returns this instance's basic status.
    """
    try:
        if mesh_relay is None:
            return jsonify({'success': False, 'error': 'Mesh relay not initialized'}), 500

        local_matrix = node_registry.get_matrix_summary() if node_registry else {}
        return jsonify({
            'success': True,
            'instance_id': mesh_relay.instance_id,
            'instance_name': mesh_relay.instance_name,
            'slot_count': local_matrix.get('total_committed', 0),
            'mesh_active': mesh_relay.is_active,
            'timestamp': _time.time(),
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@runtime_bp.route('/api/mesh/relay/push', methods=['POST'])
def mesh_relay_push():
    """
    Inbound relay — called by a remote peer to push data into
    one of this instance's inbound relay lanes.

    Body: {
        "source_instance": "abc123",
        "source_addr": "a5",
        "target_addr": "a49",
        "data": [...]
    }
    """
    try:
        if mesh_relay is None:
            return jsonify({'success': False, 'error': 'Mesh relay not initialized'}), 500

        data = request.get_json() or {}
        source_instance = data.get('source_instance', '')
        source_addr = data.get('source_addr', '')
        target_addr = data.get('target_addr', '')
        payload = data.get('data')

        ok = mesh_relay.handle_inbound_push(
            source_instance, source_addr, target_addr, payload)
        return jsonify({'success': ok})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@runtime_bp.route('/api/mesh/topology', methods=['GET'])
def mesh_topology():
    """
    Full distributed topology view — local matrix + all peers' matrices.
    This powers the mesh visualization in the runtime panel.
    """
    try:
        if mesh_relay is None:
            return jsonify({'success': False, 'error': 'Mesh relay not initialized'}), 500

        topo = mesh_relay.get_topology()

        # Optionally fetch remote matrices for the full view
        include_remote = request.args.get('include_remote', 'false').lower() == 'true'
        if include_remote:
            remote_matrices = {}
            for peer in topo.get('peers', []):
                pid = peer['peer_id']
                if peer.get('is_alive'):
                    remote = mesh_relay.get_remote_slots(pid)
                    if remote:
                        remote_matrices[pid] = remote
            topo['remote_matrices'] = remote_matrices

        return jsonify({'success': True, **topo})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500