"""
Settings Hub — Centralized configuration, logging, test runner,
and change-history backend for the SpokedPy web interface.

Provides:
  Database tables:  app_logs, test_runs, change_history
  Routes:
    GET /api/hub/settings          — all settings (expanded _KNOWN_SETTINGS)
    GET /api/hub/logs              — query app_logs
    POST /api/hub/logs             — write a log entry
    POST /api/hub/tests/run        — execute test suite, store results
    GET /api/hub/tests             — list past test runs
    GET /api/hub/tests/<run_id>    — single test run detail
    GET /api/hub/history           — change-history feed
    POST /api/hub/settings/bulk    — batch-update settings
"""

import json
import os
import re
import sqlite3
import subprocess
import sys
import time
import traceback
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from flask import Blueprint, jsonify, request

from web_interface.project_db import (
    _get_db,
    get_all_settings,
    get_setting,
    set_setting,
    delete_setting,
    resolve_setting,
)

hub_bp = Blueprint('settings_hub', __name__)

# ─────────────────────────────────────────────────────────────────────
# Schema bootstrap — runs on first import
# ─────────────────────────────────────────────────────────────────────

def _ensure_hub_tables():
    """Create the tables used exclusively by the settings hub."""
    conn = _get_db()
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS app_logs (
            id          TEXT PRIMARY KEY,
            timestamp   REAL NOT NULL,
            level       TEXT NOT NULL DEFAULT 'info',
            source      TEXT NOT NULL DEFAULT 'system',
            message     TEXT NOT NULL,
            detail      TEXT DEFAULT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_logs_ts   ON app_logs(timestamp DESC);
        CREATE INDEX IF NOT EXISTS idx_logs_lvl  ON app_logs(level);
        CREATE INDEX IF NOT EXISTS idx_logs_src  ON app_logs(source);

        CREATE TABLE IF NOT EXISTS test_runs (
            id          TEXT PRIMARY KEY,
            started_at  REAL NOT NULL,
            finished_at REAL,
            status      TEXT NOT NULL DEFAULT 'running',
            total       INTEGER DEFAULT 0,
            passed      INTEGER DEFAULT 0,
            failed      INTEGER DEFAULT 0,
            errors      INTEGER DEFAULT 0,
            skipped     INTEGER DEFAULT 0,
            duration    REAL DEFAULT 0,
            output      TEXT DEFAULT '',
            detail_json TEXT DEFAULT '[]'
        );
        CREATE INDEX IF NOT EXISTS idx_tests_ts ON test_runs(started_at DESC);

        CREATE TABLE IF NOT EXISTS change_history (
            id          TEXT PRIMARY KEY,
            timestamp   REAL NOT NULL,
            category    TEXT NOT NULL,
            action      TEXT NOT NULL,
            key         TEXT DEFAULT NULL,
            old_value   TEXT DEFAULT NULL,
            new_value   TEXT DEFAULT NULL,
            actor       TEXT DEFAULT 'user'
        );
        CREATE INDEX IF NOT EXISTS idx_hist_ts  ON change_history(timestamp DESC);
        CREATE INDEX IF NOT EXISTS idx_hist_cat ON change_history(category);
    ''')
    conn.commit()
    conn.close()


_ensure_hub_tables()


# ─────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────

def _log(level: str, source: str, message: str, detail: str = None):
    """Write a log entry to app_logs."""
    conn = _get_db()
    conn.execute(
        'INSERT INTO app_logs (id, timestamp, level, source, message, detail) VALUES (?,?,?,?,?,?)',
        (str(uuid.uuid4()), time.time(), level, source, message, detail),
    )
    conn.commit()
    conn.close()


def _record_change(category: str, action: str, key: str = None,
                   old_value: str = None, new_value: str = None,
                   actor: str = 'user'):
    """Append to change_history."""
    conn = _get_db()
    conn.execute(
        'INSERT INTO change_history (id, timestamp, category, action, key, old_value, new_value, actor) '
        'VALUES (?,?,?,?,?,?,?,?)',
        (str(uuid.uuid4()), time.time(), category, action, key, old_value, new_value, actor),
    )
    conn.commit()
    conn.close()


# ─────────────────────────────────────────────────────────────────────
# EXPANDED SETTINGS MANIFEST — everything that is configurable
# ─────────────────────────────────────────────────────────────────────

SETTINGS_MANIFEST: Dict[str, Dict[str, Any]] = {
    # ── Paths ────────────────────────────────────────────────────────
    'snippets_dir': {
        'env': 'SPOKEDPY_SNIPPETS_DIR',
        'default': os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'snippets'),
        'label': 'Snippet output directory',
        'group': 'paths',
        'type': 'path',
        'restart': True,
    },
    'audit_log': {
        'env': 'SPOKEDPY_AUDIT_LOG',
        'default': os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'staging_audit.jsonl'),
        'label': 'Staging audit log path',
        'group': 'paths',
        'type': 'path',
        'restart': True,
    },
    'db_path': {
        'env': 'SPOKEDPY_DB_PATH',
        'default': os.path.join(os.path.dirname(os.path.abspath(__file__)), 'projects.db'),
        'label': 'SQLite database path',
        'group': 'paths',
        'type': 'path',
        'restart': True,
    },
    # ── Server ───────────────────────────────────────────────────────
    'host': {
        'env': 'SPOKEDPY_HOST',
        'default': '0.0.0.0',
        'label': 'Server bind address',
        'group': 'server',
        'type': 'string',
        'restart': True,
    },
    'port': {
        'env': 'SPOKEDPY_PORT',
        'default': '5002',
        'label': 'Server port',
        'group': 'server',
        'type': 'number',
        'restart': True,
    },
    'reloader': {
        'env': 'SPOKEDPY_RELOADER',
        'default': '0',
        'label': 'Enable Werkzeug reloader (0/1)',
        'group': 'server',
        'type': 'boolean',
        'restart': True,
    },
    # ── Marshal ──────────────────────────────────────────────────────
    'marshal_ttl': {
        'env': 'SPOKEDPY_MARSHAL_TTL',
        'default': '4000',
        'label': 'Marshal token TTL (seconds)',
        'group': 'marshal',
        'type': 'number',
        'restart': False,
    },
    # ── AI Agent ─────────────────────────────────────────────────────
    'ai_endpoint': {
        'env': 'SPOKEDPY_AI_ENDPOINT',
        'default': 'https://api.openai.com/v1',
        'label': 'AI API endpoint',
        'group': 'ai',
        'type': 'url',
        'restart': False,
    },
    'ai_api_key': {
        'env': 'SPOKEDPY_AI_API_KEY',
        'default': '',
        'label': 'AI API key',
        'group': 'ai',
        'type': 'secret',
        'restart': False,
    },
    'ai_model': {
        'env': 'SPOKEDPY_AI_MODEL',
        'default': 'gpt-4o',
        'label': 'AI model',
        'group': 'ai',
        'type': 'string',
        'restart': False,
    },
    'ai_temperature': {
        'env': 'SPOKEDPY_AI_TEMPERATURE',
        'default': '0.7',
        'label': 'AI temperature',
        'group': 'ai',
        'type': 'number',
        'restart': False,
    },
    'ai_system_prompt': {
        'env': 'SPOKEDPY_AI_SYSTEM_PROMPT',
        'default': '',
        'label': 'AI system prompt override',
        'group': 'ai',
        'type': 'textarea',
        'restart': False,
    },
    # ── Canvas / Visual ──────────────────────────────────────────────
    'parallax_factor': {
        'env': 'SPOKEDPY_PARALLAX_FACTOR',
        'default': '6',
        'label': 'Parallax zoom offset factor',
        'group': 'canvas',
        'type': 'number',
        'restart': False,
    },
    'grid_size': {
        'env': 'SPOKEDPY_GRID_SIZE',
        'default': '20',
        'label': 'Canvas grid spacing (px)',
        'group': 'canvas',
        'type': 'number',
        'restart': False,
    },
    'zoom_min': {
        'env': 'SPOKEDPY_ZOOM_MIN',
        'default': '0.1',
        'label': 'Minimum zoom level',
        'group': 'canvas',
        'type': 'number',
        'restart': False,
    },
    'zoom_max': {
        'env': 'SPOKEDPY_ZOOM_MAX',
        'default': '5.0',
        'label': 'Maximum zoom level',
        'group': 'canvas',
        'type': 'number',
        'restart': False,
    },
    'snap_to_grid': {
        'env': 'SPOKEDPY_SNAP_TO_GRID',
        'default': '1',
        'label': 'Snap nodes to grid (0/1)',
        'group': 'canvas',
        'type': 'boolean',
        'restart': False,
    },
}

SETTING_GROUPS = [
    {'key': 'paths',   'label': 'Paths & Storage',   'icon': 'folder'},
    {'key': 'server',  'label': 'Server',             'icon': 'server'},
    {'key': 'marshal', 'label': 'Marshal Tokens',     'icon': 'key'},
    {'key': 'ai',      'label': 'AI Agent',           'icon': 'bot'},
    {'key': 'canvas',  'label': 'Canvas & Visuals',   'icon': 'layout'},
]


def _resolve_all() -> Dict[str, Dict[str, Any]]:
    """Return every setting with effective value + provenance."""
    db = get_all_settings()
    out = {}
    for key, meta in SETTINGS_MANIFEST.items():
        db_val = db.get(key)
        env_val = os.environ.get(meta['env'], '').strip() or None
        effective = db_val or env_val or meta['default']
        source = 'database' if db_val else ('environment' if env_val else 'default')
        out[key] = {
            'value': effective,
            'source': source,
            'db_override': db_val,
            'env_value': env_val,
            'default': meta['default'],
            'label': meta['label'],
            'group': meta['group'],
            'type': meta['type'],
            'restart': meta['restart'],
        }
    return out


# ─────────────────────────────────────────────────────────────────────
# ROUTES — Settings
# ─────────────────────────────────────────────────────────────────────

@hub_bp.route('/api/hub/settings', methods=['GET'])
def hub_settings_list():
    """Return every known setting with value, source, and metadata."""
    return jsonify({
        'success': True,
        'settings': _resolve_all(),
        'groups': SETTING_GROUPS,
    })


@hub_bp.route('/api/hub/settings/bulk', methods=['POST'])
def hub_settings_bulk():
    """Batch-update multiple settings at once.

    Body: ``{ "updates": { "key": "value", ... } }``
    """
    data = request.get_json(force=True, silent=True) or {}
    updates = data.get('updates', {})
    if not updates:
        return jsonify({'success': False, 'error': 'No updates provided'}), 400

    results = {}
    needs_restart = False
    for key, value in updates.items():
        key = key.lower()
        meta = SETTINGS_MANIFEST.get(key)
        if not meta:
            results[key] = {'error': f'Unknown setting: {key}'}
            continue
        old_val = resolve_setting(key, meta['env'], meta['default'])
        set_setting(key, str(value))
        _record_change('settings', 'update', key, old_val, str(value))
        results[key] = {'ok': True, 'restart': meta['restart']}
        if meta['restart']:
            needs_restart = True

    _log('info', 'settings', f'Bulk settings update: {len(updates)} keys', json.dumps(list(updates.keys())))
    return jsonify({
        'success': True,
        'results': results,
        'restart_required': needs_restart,
    })


@hub_bp.route('/api/hub/settings/<key>', methods=['DELETE'])
def hub_settings_revert(key: str):
    """Remove a DB override so the setting reverts to env/default."""
    key = key.lower()
    meta = SETTINGS_MANIFEST.get(key)
    if not meta:
        return jsonify({'success': False, 'error': f'Unknown setting: {key}'}), 404
    old_val = get_setting(key)
    deleted = delete_setting(key)
    if deleted:
        new_val = os.environ.get(meta['env'], '').strip() or meta['default']
        _record_change('settings', 'revert', key, old_val, new_val)
        _log('info', 'settings', f'Reverted setting "{key}" to {new_val}')
    return jsonify({'success': True, 'deleted': deleted})


# ─────────────────────────────────────────────────────────────────────
# ROUTES — Logging
# ─────────────────────────────────────────────────────────────────────

@hub_bp.route('/api/hub/logs', methods=['GET'])
def hub_logs_list():
    """Query app logs.

    Query params:
        level   — filter by level (info, warn, error, debug)
        source  — filter by source subsystem
        limit   — max rows (default 200)
        offset  — pagination offset
        since   — epoch timestamp lower bound
    """
    level = request.args.get('level')
    source = request.args.get('source')
    limit = int(request.args.get('limit', 200))
    offset = int(request.args.get('offset', 0))
    since = request.args.get('since', type=float)

    conn = _get_db()
    clauses = []
    params: list = []
    if level:
        clauses.append('level = ?')
        params.append(level)
    if source:
        clauses.append('source = ?')
        params.append(source)
    if since:
        clauses.append('timestamp >= ?')
        params.append(since)

    where = ('WHERE ' + ' AND '.join(clauses)) if clauses else ''
    rows = conn.execute(
        f'SELECT * FROM app_logs {where} ORDER BY timestamp DESC LIMIT ? OFFSET ?',
        params + [limit, offset],
    ).fetchall()

    total = conn.execute(
        f'SELECT COUNT(*) AS c FROM app_logs {where}', params,
    ).fetchone()['c']
    conn.close()

    return jsonify({
        'success': True,
        'logs': [dict(r) for r in rows],
        'total': total,
        'limit': limit,
        'offset': offset,
    })


@hub_bp.route('/api/hub/logs', methods=['POST'])
def hub_logs_write():
    """Write a log entry from the frontend.

    Body: ``{ "level": "info", "source": "ui", "message": "...", "detail": "..." }``
    """
    data = request.get_json(force=True, silent=True) or {}
    msg = data.get('message', '').strip()
    if not msg:
        return jsonify({'success': False, 'error': 'Empty message'}), 400
    _log(
        data.get('level', 'info'),
        data.get('source', 'ui'),
        msg,
        data.get('detail'),
    )
    return jsonify({'success': True})


@hub_bp.route('/api/hub/logs', methods=['DELETE'])
def hub_logs_clear():
    """Clear all logs (or logs older than `before` epoch)."""
    before = request.args.get('before', type=float)
    conn = _get_db()
    if before:
        conn.execute('DELETE FROM app_logs WHERE timestamp < ?', (before,))
    else:
        conn.execute('DELETE FROM app_logs')
    conn.commit()
    conn.close()
    _log('info', 'system', 'Logs cleared')
    return jsonify({'success': True})


# ─────────────────────────────────────────────────────────────────────
# ROUTES — Test Runner
# ─────────────────────────────────────────────────────────────────────

_TESTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'tests')


def _discover_test_files() -> List[str]:
    """Return list of test_*.py files under tests/."""
    if not os.path.isdir(_TESTS_DIR):
        return []
    return sorted(
        f for f in os.listdir(_TESTS_DIR)
        if f.startswith('test_') and f.endswith('.py')
    )


@hub_bp.route('/api/hub/tests/discover', methods=['GET'])
def hub_tests_discover():
    """List available test files."""
    files = _discover_test_files()
    return jsonify({'success': True, 'test_files': files, 'tests_dir': _TESTS_DIR})


@hub_bp.route('/api/hub/tests/run', methods=['POST'])
def hub_tests_run():
    """Execute pytest and store results.

    Body (optional): ``{ "files": ["test_foo.py"], "verbose": true }``
    """
    data = request.get_json(force=True, silent=True) or {}
    files = data.get('files', [])
    verbose = data.get('verbose', False)

    run_id = str(uuid.uuid4())
    started = time.time()

    # Build pytest command — per-test timeout prevents individual hangs
    cmd = [sys.executable, '-m', 'pytest', '--tb=short', '-q',
           '--timeout=30']
    if verbose:
        cmd.append('-v')

    if files:
        cmd.extend(os.path.join(_TESTS_DIR, f) for f in files if f.startswith('test_'))
    else:
        cmd.append(_TESTS_DIR)

    # Record run start
    conn = _get_db()
    conn.execute(
        'INSERT INTO test_runs (id, started_at, status) VALUES (?,?,?)',
        (run_id, started, 'running'),
    )
    conn.commit()
    conn.close()

    _log('info', 'tests', f'Test run {run_id[:8]} started', json.dumps(cmd))

    # Execute synchronously — 600s overall limit (633 tests × ~0.3s avg + margin)
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600,
            cwd=os.path.dirname(os.path.dirname(__file__)),
        )
        output = result.stdout + '\n' + result.stderr
        returncode = result.returncode
    except subprocess.TimeoutExpired:
        output = 'Test run timed out after 600s'
        returncode = -1
    except Exception as exc:
        output = f'Failed to execute tests: {exc}\n{traceback.format_exc()}'
        returncode = -2

    finished = time.time()
    duration = finished - started

    # Parse pytest summary line:  "X passed, Y failed, Z errors, W skipped"
    passed = failed = errors = skipped = total = 0
    summary_match = re.search(
        r'(\d+)\s+passed', output
    )
    if summary_match:
        passed = int(summary_match.group(1))
    fail_match = re.search(r'(\d+)\s+failed', output)
    if fail_match:
        failed = int(fail_match.group(1))
    err_match = re.search(r'(\d+)\s+error', output)
    if err_match:
        errors = int(err_match.group(1))
    skip_match = re.search(r'(\d+)\s+skipped', output)
    if skip_match:
        skipped = int(skip_match.group(1))
    total = passed + failed + errors + skipped

    status = 'passed' if returncode == 0 else 'failed'
    if returncode == -1:
        status = 'timeout'
    if returncode == -2:
        status = 'error'

    # Update run record
    conn = _get_db()
    conn.execute('''
        UPDATE test_runs
           SET finished_at = ?, status = ?, total = ?, passed = ?,
               failed = ?, errors = ?, skipped = ?, duration = ?, output = ?
         WHERE id = ?
    ''', (finished, status, total, passed, failed, errors, skipped, duration, output, run_id))
    conn.commit()
    conn.close()

    _record_change('tests', 'run', run_id, None, status)
    _log('info', 'tests',
         f'Test run {run_id[:8]} finished: {status} '
         f'({passed} passed, {failed} failed, {errors} errors in {duration:.1f}s)')

    return jsonify({
        'success': True,
        'run': {
            'id': run_id,
            'status': status,
            'total': total,
            'passed': passed,
            'failed': failed,
            'errors': errors,
            'skipped': skipped,
            'duration': round(duration, 2),
            'output': output,
        },
    })


@hub_bp.route('/api/hub/tests', methods=['GET'])
def hub_tests_list():
    """List past test runs."""
    limit = int(request.args.get('limit', 20))
    conn = _get_db()
    rows = conn.execute(
        'SELECT id, started_at, finished_at, status, total, passed, failed, errors, skipped, duration '
        'FROM test_runs ORDER BY started_at DESC LIMIT ?',
        (limit,),
    ).fetchall()
    conn.close()
    return jsonify({'success': True, 'runs': [dict(r) for r in rows]})


@hub_bp.route('/api/hub/tests/<run_id>', methods=['GET'])
def hub_tests_detail(run_id: str):
    """Get full detail of a single test run, including output."""
    conn = _get_db()
    row = conn.execute('SELECT * FROM test_runs WHERE id = ?', (run_id,)).fetchone()
    conn.close()
    if not row:
        return jsonify({'success': False, 'error': 'Run not found'}), 404
    return jsonify({'success': True, 'run': dict(row)})


# ─────────────────────────────────────────────────────────────────────
# ROUTES — Change History
# ─────────────────────────────────────────────────────────────────────

@hub_bp.route('/api/hub/history', methods=['GET'])
def hub_history_list():
    """Query the change-history feed.

    Query params:
        category  — settings | tests | logs
        limit     — default 100
        offset    — pagination
    """
    category = request.args.get('category')
    limit = int(request.args.get('limit', 100))
    offset = int(request.args.get('offset', 0))

    conn = _get_db()
    if category:
        rows = conn.execute(
            'SELECT * FROM change_history WHERE category = ? ORDER BY timestamp DESC LIMIT ? OFFSET ?',
            (category, limit, offset),
        ).fetchall()
    else:
        rows = conn.execute(
            'SELECT * FROM change_history ORDER BY timestamp DESC LIMIT ? OFFSET ?',
            (limit, offset),
        ).fetchall()
    conn.close()
    return jsonify({'success': True, 'history': [dict(r) for r in rows]})


# ─────────────────────────────────────────────────────────────────────
# ROUTES — Server info (for the modal header)
# ─────────────────────────────────────────────────────────────────────

@hub_bp.route('/api/hub/info', methods=['GET'])
def hub_server_info():
    """Return server metadata for the settings modal."""
    import platform
    return jsonify({
        'success': True,
        'info': {
            'python_version': sys.version,
            'platform': platform.platform(),
            'pid': os.getpid(),
            'cwd': os.getcwd(),
            'db_path': resolve_setting('db_path', 'SPOKEDPY_DB_PATH',
                                       os.path.join(os.path.dirname(os.path.abspath(__file__)), 'projects.db')),
            'tests_dir': _TESTS_DIR,
            'test_count': len(_discover_test_files()),
        },
    })


# ─────────────────────────────────────────────────────────────────────
# Blueprint registration helper
# ─────────────────────────────────────────────────────────────────────

def register_settings_hub(app):
    """Register the settings-hub blueprint."""
    app.register_blueprint(hub_bp)
    _log('info', 'system', 'SpokedPy server started')
    print(f"  Settings Hub:  /api/hub/settings")
    print(f"  App Logs:      /api/hub/logs")
    print(f"  Test Runner:   /api/hub/tests/run")
    print(f"  History:       /api/hub/history")
