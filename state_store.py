import sqlite3
import json
import hashlib
from datetime import datetime, timezone

DB_PATH = "state.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS proposals (
    proposal_key TEXT PRIMARY KEY,
    change_type TEXT NOT NULL,
    account_id TEXT,
    payload TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL,
    decided_at TEXT
);
"""


def make_key(proposal):
    """
    Turns a proposal into a unique, deterministic fingerprint. Same
    proposal (same account, same type, same target values) always produces
    the same key - that's what lets us detect 'we've seen this exact thing
    before'.
    """
    raw = json.dumps(proposal, sort_keys=True)
    return hashlib.sha256(raw.encode()).hexdigest()[:20]


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute(SCHEMA)
    return conn


def already_exists(conn, key):
    row = conn.execute("SELECT 1 FROM proposals WHERE proposal_key = ?", (key,)).fetchone()
    return row is not None


def add_proposal(conn, proposal):
    key = make_key(proposal)
    conn.execute(
        "INSERT OR IGNORE INTO proposals (proposal_key, change_type, account_id, payload, status, created_at) VALUES (?, ?, ?, ?, 'pending', ?)",
        (
            key,
            proposal["type"],
            proposal.get("account_id") or proposal.get("old_account_id"),
            json.dumps(proposal),
            datetime.now(timezone.utc).isoformat(),
        ),
    )
    conn.commit()
    return key


def list_pending(conn):
    rows = conn.execute("SELECT * FROM proposals WHERE status = 'pending' ORDER BY created_at").fetchall()
    return [dict(r) for r in rows]


def mark_decided(conn, key, status):
    conn.execute(
        "UPDATE proposals SET status = ?, decided_at = ? WHERE proposal_key = ?",
        (status, datetime.now(timezone.utc).isoformat(), key),
    )
    conn.commit()