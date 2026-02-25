"""
Project Database — SQLite-backed project persistence.

Stores complete project state (nodes, connections, engine tab code,
viewport, execution sequence) so users can save and reload work.

Schema:
  projects       — id, name, description, created_at, updated_at, state_json
  engine_tabs    — id, project_id, engine_letter, language, code, label, position
"""

import os
import json
import sqlite3
import time
import uuid
from typing import Dict, List, Optional, Any


def _resolve_db_path() -> str:
    """Resolve the database path from env → default.

    Priority:
        1. SPOKEDPY_DB_PATH environment variable
        2. ``<web_interface>/projects.db``  (legacy default)
    """
    env_path = os.environ.get('SPOKEDPY_DB_PATH', '').strip()
    if env_path:
        os.makedirs(os.path.dirname(env_path) or '.', exist_ok=True)
        return env_path
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), 'projects.db')


DB_PATH = _resolve_db_path()


def _get_db() -> sqlite3.Connection:
    """Return a connection to the projects database, creating tables if needed."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA foreign_keys=ON')

    conn.executescript('''
        CREATE TABLE IF NOT EXISTS projects (
            id            TEXT PRIMARY KEY,
            name          TEXT NOT NULL,
            description   TEXT DEFAULT '',
            created_at    REAL NOT NULL,
            updated_at    REAL NOT NULL,
            state_json    TEXT NOT NULL DEFAULT '{}'
        );

        CREATE TABLE IF NOT EXISTS engine_tabs (
            id            TEXT PRIMARY KEY,
            project_id    TEXT NOT NULL,
            engine_letter TEXT NOT NULL,
            language      TEXT NOT NULL,
            code          TEXT DEFAULT '',
            label         TEXT DEFAULT '',
            position      INTEGER DEFAULT 0,
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_tabs_project ON engine_tabs(project_id);

        CREATE TABLE IF NOT EXISTS settings (
            key           TEXT PRIMARY KEY,
            value         TEXT NOT NULL,
            updated_at    REAL NOT NULL
        );
    ''')
    conn.commit()
    return conn


# ─────────────────────────────────────────────────────────────────────
# Project CRUD
# ─────────────────────────────────────────────────────────────────────

def save_project(name: str,
                 state: Dict[str, Any],
                 engine_tabs: List[Dict[str, Any]],
                 description: str = '',
                 project_id: Optional[str] = None) -> Dict[str, Any]:
    """Save or update a project.

    Args:
        name:         Human-readable project name.
        state:        Full canvas state dict (nodes, connections, viewport, etc.).
        engine_tabs:  List of {engine_letter, language, code, label, position}.
        description:  Optional description.
        project_id:   If provided, overwrites existing project.

    Returns:
        Dict with project metadata.
    """
    conn = _get_db()
    now = time.time()
    is_new = True

    if project_id:
        # Update existing
        row = conn.execute('SELECT id FROM projects WHERE id = ?', (project_id,)).fetchone()
        if row:
            is_new = False
            conn.execute('''
                UPDATE projects
                   SET name = ?, description = ?, updated_at = ?, state_json = ?
                 WHERE id = ?
            ''', (name, description, now, json.dumps(state), project_id))
            # Replace engine tabs
            conn.execute('DELETE FROM engine_tabs WHERE project_id = ?', (project_id,))
        else:
            # ID not found — create new with this ID
            conn.execute('''
                INSERT INTO projects (id, name, description, created_at, updated_at, state_json)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (project_id, name, description, now, now, json.dumps(state)))
    else:
        project_id = str(uuid.uuid4())
        conn.execute('''
            INSERT INTO projects (id, name, description, created_at, updated_at, state_json)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (project_id, name, description, now, now, json.dumps(state)))

    # Insert engine tabs
    for tab in engine_tabs:
        tab_id = str(uuid.uuid4())
        conn.execute('''
            INSERT INTO engine_tabs (id, project_id, engine_letter, language, code, label, position)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            tab_id, project_id,
            tab['engine_letter'], tab['language'],
            tab.get('code', ''), tab.get('label', ''),
            tab.get('position', 0)
        ))

    conn.commit()
    conn.close()

    return {
        'id': project_id,
        'name': name,
        'description': description,
        'created_at': now if is_new else None,
        'updated_at': now,
    }


def list_projects() -> List[Dict[str, Any]]:
    """Return all saved projects (metadata only, no state blob)."""
    conn = _get_db()
    rows = conn.execute('''
        SELECT id, name, description, created_at, updated_at
          FROM projects
         ORDER BY updated_at DESC
    ''').fetchall()
    conn.close()

    return [dict(r) for r in rows]


def load_project(project_id: str) -> Optional[Dict[str, Any]]:
    """Load a full project including canvas state and engine tabs."""
    conn = _get_db()
    row = conn.execute('SELECT * FROM projects WHERE id = ?', (project_id,)).fetchone()
    if not row:
        conn.close()
        return None

    tabs = conn.execute('''
        SELECT engine_letter, language, code, label, position
          FROM engine_tabs
         WHERE project_id = ?
         ORDER BY position
    ''', (project_id,)).fetchall()
    conn.close()

    return {
        'id': row['id'],
        'name': row['name'],
        'description': row['description'],
        'created_at': row['created_at'],
        'updated_at': row['updated_at'],
        'state': json.loads(row['state_json']),
        'engine_tabs': [dict(t) for t in tabs],
    }


def delete_project(project_id: str) -> bool:
    """Delete a project and its engine tabs."""
    conn = _get_db()
    cursor = conn.execute('DELETE FROM projects WHERE id = ?', (project_id,))
    conn.commit()
    deleted = cursor.rowcount > 0
    conn.close()
    return deleted


# ─────────────────────────────────────────────────────────────────────
# Settings KV store  (database overrides for .env defaults)
# ─────────────────────────────────────────────────────────────────────
#
# Known keys (stored lowercase):
#   snippets_dir   – directory for promoted snippet files
#   audit_log      – path to the staging audit JSONL file
#   marshal_ttl    – default marshal-token TTL in seconds
#
# The resolution order everywhere is:
#   1. Database setting  (set via web UI / API)
#   2. Environment variable  (.env / shell)
#   3. Hard-coded default
# ─────────────────────────────────────────────────────────────────────

def get_setting(key: str) -> Optional[str]:
    """Return a single setting value, or None if unset."""
    conn = _get_db()
    row = conn.execute(
        'SELECT value FROM settings WHERE key = ?', (key.lower(),)
    ).fetchone()
    conn.close()
    return row['value'] if row else None


def set_setting(key: str, value: str) -> Dict[str, Any]:
    """Upsert a setting. Returns the saved record."""
    now = time.time()
    conn = _get_db()
    conn.execute('''
        INSERT INTO settings (key, value, updated_at)
        VALUES (?, ?, ?)
        ON CONFLICT(key) DO UPDATE
           SET value = excluded.value,
               updated_at = excluded.updated_at
    ''', (key.lower(), value, now))
    conn.commit()
    conn.close()
    return {'key': key.lower(), 'value': value, 'updated_at': now}


def get_all_settings() -> Dict[str, str]:
    """Return all settings as a flat dict."""
    conn = _get_db()
    rows = conn.execute('SELECT key, value FROM settings').fetchall()
    conn.close()
    return {r['key']: r['value'] for r in rows}


def delete_setting(key: str) -> bool:
    """Remove a setting (reverts to env / default)."""
    conn = _get_db()
    cursor = conn.execute('DELETE FROM settings WHERE key = ?', (key.lower(),))
    conn.commit()
    deleted = cursor.rowcount > 0
    conn.close()
    return deleted


def resolve_setting(key: str, env_var: str, default: str) -> str:
    """Three-tier resolution: DB → env → default.

    This is the canonical function every subsystem should call to
    determine the effective value of a configurable path or parameter.
    """
    # 1. Database (web-UI override)
    db_val = get_setting(key)
    if db_val is not None:
        return db_val
    # 2. Environment variable (.env or shell)
    env_val = os.environ.get(env_var, '').strip()
    if env_val:
        return env_val
    # 3. Hard-coded default
    return default
