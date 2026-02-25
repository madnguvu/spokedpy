"""
State Persistence — Crash-resilient checkpoint/restore for runtime state.

Persists the following across server reboots:
  - Locked (pinned) slots
  - Marshal tokens with remaining TTL
  - Promoted snippet metadata (staging_id, code, language, engine, slot address)

The checkpoint file is written atomically (write → rename) to avoid corruption
on crash.  On startup, the restore phase replays promoted snippets back through
the staging pipeline + node registry, re-creates marshal tokens with adjusted
TTL, and re-applies slot locks.

Checkpoint file:  data/runtime_state.json  (configurable via DB/env)

The checkpoint is triggered on every state-mutating operation:
  - Snippet promoted
  - Slot locked / unlocked
  - Slot evicted
  - Marshal token created

To avoid hammering disk on rapid-fire operations, writes are debounced
via a background thread (coalesce window = 1 second).
"""

import os
import json
import time
import threading
import traceback
from typing import Any, Dict, List, Optional

from web_interface.project_db import resolve_setting


# ─────────────────────────────────────────────────────────────────────────
# Checkpoint file path resolution
# ─────────────────────────────────────────────────────────────────────────

def _resolve_checkpoint_path() -> str:
    """Resolve the checkpoint file path: DB setting -> env -> default."""
    _data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
    return resolve_setting(
        'state_checkpoint',
        'SPOKEDPY_STATE_CHECKPOINT',
        os.path.join(_data_dir, 'runtime_state.json'),
    )


# ─────────────────────────────────────────────────────────────────────────
# StatePersistence — debounced, atomic checkpoint writer + restore reader
# ─────────────────────────────────────────────────────────────────────────

class StatePersistence:
    """Manages crash-resilient persistence of volatile runtime state.

    Usage:
        sp = StatePersistence()
        sp.checkpoint(locked_slots, marshal_tokens, promoted_snippets)
        ...
        state = sp.restore()   # returns dict or None
    """

    COALESCE_SECONDS = 1.0   # debounce window

    def __init__(self, path: Optional[str] = None):
        self._path = path or _resolve_checkpoint_path()
        self._lock = threading.Lock()
        self._pending: Optional[dict] = None
        self._timer: Optional[threading.Timer] = None
        # Ensure directory exists
        os.makedirs(os.path.dirname(self._path) or '.', exist_ok=True)

    # ─────────────────────────────────────────────────────────────────
    # CHECKPOINT — serialize current state
    # ─────────────────────────────────────────────────────────────────

    def checkpoint(self,
                   locked_slots: dict,
                   marshal_tokens: dict,
                   promoted_snapshots: List[dict]):
        """Schedule an atomic write of the current runtime state.

        Args:
            locked_slots:       { address -> lock_metadata }
            marshal_tokens:     { token -> token_record }
            promoted_snapshots: [ { staging_id, language, engine_letter,
                                    code, label, address, position,
                                    engine_name, code_hash, origin,
                                    submitter, agent_id, token,
                                    ttl, created_at, promoted_at,
                                    spec_output, spec_error,
                                    spec_execution_time, spec_success } ]
        """
        now = time.time()
        state = {
            'version': 2,
            'saved_at': now,
            'saved_at_iso': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(now)),
            'locked_slots': _serialize_locked_slots(locked_slots),
            'marshal_tokens': _serialize_marshal_tokens(marshal_tokens, now),
            'promoted_snippets': promoted_snapshots,
        }
        with self._lock:
            self._pending = state
            # Debounce: if a timer is already ticking, the new state
            # will be picked up when it fires.
            if self._timer is None or not self._timer.is_alive():
                self._timer = threading.Timer(self.COALESCE_SECONDS, self._flush)
                self._timer.daemon = True
                self._timer.start()

    def checkpoint_now(self,
                       locked_slots: dict,
                       marshal_tokens: dict,
                       promoted_snapshots: List[dict]):
        """Immediate (synchronous) checkpoint — used at shutdown."""
        now = time.time()
        state = {
            'version': 2,
            'saved_at': now,
            'saved_at_iso': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(now)),
            'locked_slots': _serialize_locked_slots(locked_slots),
            'marshal_tokens': _serialize_marshal_tokens(marshal_tokens, now),
            'promoted_snippets': promoted_snapshots,
        }
        self._write_atomic(state)

    def _flush(self):
        """Background thread callback: write the pending state."""
        with self._lock:
            data = self._pending
            self._pending = None
        if data:
            self._write_atomic(data)

    def _write_atomic(self, state: dict):
        """Write state to a temp file, then atomically rename."""
        tmp_path = self._path + '.tmp'
        try:
            with open(tmp_path, 'w', encoding='utf-8') as f:
                json.dump(state, f, indent=2, default=str)
            # Atomic rename (on Windows, need to remove target first)
            if os.path.exists(self._path):
                os.replace(tmp_path, self._path)
            else:
                os.rename(tmp_path, self._path)
        except Exception as exc:
            print(f"  [STATE] Checkpoint write FAILED: {exc}")
            traceback.print_exc()

    # ─────────────────────────────────────────────────────────────────
    # RESTORE — deserialize persisted state
    # ─────────────────────────────────────────────────────────────────

    def restore(self) -> Optional[dict]:
        """Read the checkpoint file and return the state dict.

        Returns None if no checkpoint exists or it's corrupted.
        The returned dict has keys:
            version, saved_at, locked_slots, marshal_tokens, promoted_snippets
        """
        if not os.path.exists(self._path):
            return None
        try:
            with open(self._path, 'r', encoding='utf-8') as f:
                state = json.load(f)
            if not isinstance(state, dict) or 'version' not in state:
                print(f"  [STATE] Checkpoint file is malformed, ignoring.")
                return None
            return state
        except (json.JSONDecodeError, IOError) as exc:
            print(f"  [STATE] Checkpoint read FAILED: {exc}")
            return None

    @property
    def path(self) -> str:
        return self._path


# ─────────────────────────────────────────────────────────────────────────
# Serialization helpers
# ─────────────────────────────────────────────────────────────────────────

def _serialize_locked_slots(locked_slots: dict) -> dict:
    """Convert locked_slots dict to JSON-safe representation."""
    out = {}
    for addr, meta in locked_slots.items():
        out[addr] = {
            'locked_at': meta.get('locked_at', 0),
            'locked_by': meta.get('locked_by', 'unknown'),
            'reason': meta.get('reason', ''),
        }
    return out


def _serialize_marshal_tokens(marshal_tokens: dict, now: float) -> dict:
    """Convert marshal_tokens dict to JSON-safe representation.

    Calculates remaining TTL so the restore phase can re-mint tokens
    with the correct remaining lifetime.
    """
    out = {}
    for token, rec in marshal_tokens.items():
        elapsed = now - rec.get('created_at', now)
        remaining = max(0, rec.get('ttl', 0) - elapsed)
        if remaining <= 0:
            continue   # Don't persist already-expired tokens
        out[token] = {
            'staging_id': rec.get('staging_id', ''),
            'created_at': rec.get('created_at', 0),
            'ttl': rec.get('ttl', 0),
            'remaining_ttl': round(remaining, 1),
            'origin': rec.get('origin', 'api'),
            'submitter': rec.get('submitter', ''),
            'agent_id': rec.get('agent_id', ''),
        }
    return out


def build_promoted_snapshots(staging_pipeline, marshal_tokens: dict,
                             locked_slots: dict) -> List[dict]:
    """Build the list of promoted snippet snapshots for checkpointing.

    Scans the staging pipeline history for PROMOTED snippets and cross-
    references them with marshal tokens for provenance data.

    Also checks the node registry for any slots occupied by non-staging
    nodes (e.g. canvas imports) — those are persisted too.
    """
    snapshots = []
    seen_staging_ids = set()

    if staging_pipeline is None:
        return snapshots

    # ── 1. Promoted snippets from pipeline history ─────────────────────
    for sn in staging_pipeline.get_history(limit=1000):
        if sn.phase.value != 'promoted':
            continue
        if sn.staging_id in seen_staging_ids:
            continue
        seen_staging_ids.add(sn.staging_id)

        # Find the marshal token for this snippet
        token_str = ''
        token_rec = {}
        for tok, rec in marshal_tokens.items():
            if rec.get('staging_id') == sn.staging_id:
                token_str = tok
                token_rec = rec
                break

        addr = sn.reserved_address
        is_locked = addr in locked_slots

        snapshots.append({
            'staging_id': sn.staging_id,
            'language': sn.language,
            'engine_letter': sn.engine_letter,
            'code': sn.code,
            'label': sn.label,
            'address': sn.reserved_address,
            'position': sn.reserved_position,
            'engine_name': sn.reserved_engine,
            'code_hash': sn.code_hash,
            'origin': token_rec.get('origin', 'api'),
            'submitter': token_rec.get('submitter', ''),
            'agent_id': token_rec.get('agent_id', ''),
            'token': token_str,
            'ttl': token_rec.get('ttl', 0),
            'created_at': sn.created_at,
            'promoted_at': sn.promoted_at,
            'spec_output': (sn.spec_output or '')[:2000],
            'spec_error': (sn.spec_error or '')[:2000],
            'spec_execution_time': sn.spec_execution_time,
            'spec_success': sn.spec_success,
            'locked': is_locked,
            'saved_file_path': sn.saved_file_path,
            'ledger_node_id': sn.ledger_node_id,
            'registry_slot_id': sn.registry_slot_id,
        })

    # ── 2. Active promoted snippets still in the staging dict ──────────
    for sn in staging_pipeline.get_active():
        if sn.phase.value != 'promoted':
            continue
        if sn.staging_id in seen_staging_ids:
            continue
        seen_staging_ids.add(sn.staging_id)

        token_str = ''
        token_rec = {}
        for tok, rec in marshal_tokens.items():
            if rec.get('staging_id') == sn.staging_id:
                token_str = tok
                token_rec = rec
                break

        addr = sn.reserved_address
        is_locked = addr in locked_slots

        snapshots.append({
            'staging_id': sn.staging_id,
            'language': sn.language,
            'engine_letter': sn.engine_letter,
            'code': sn.code,
            'label': sn.label,
            'address': sn.reserved_address,
            'position': sn.reserved_position,
            'engine_name': sn.reserved_engine,
            'code_hash': sn.code_hash,
            'origin': token_rec.get('origin', 'api'),
            'submitter': token_rec.get('submitter', ''),
            'agent_id': token_rec.get('agent_id', ''),
            'token': token_str,
            'ttl': token_rec.get('ttl', 0),
            'created_at': sn.created_at,
            'promoted_at': sn.promoted_at,
            'spec_output': (sn.spec_output or '')[:2000],
            'spec_error': (sn.spec_error or '')[:2000],
            'spec_execution_time': sn.spec_execution_time,
            'spec_success': sn.spec_success,
            'locked': is_locked,
            'saved_file_path': sn.saved_file_path,
            'ledger_node_id': sn.ledger_node_id,
            'registry_slot_id': sn.registry_slot_id,
        })

    return snapshots
