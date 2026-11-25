"""Persistent state: one SQLite file, stored encrypted in the repo between runs.

The plain database only ever exists inside the runner. What gets committed is
state/state.db.enc, encrypted with a key derived from your STATE_PASSPHRASE
secret, so findings stay private even in a public repository.
"""
import base64
import hashlib
import json
import os
import sqlite3
import time
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

ROOT = Path(__file__).resolve().parent.parent
STATE_DIR = ROOT / "state"
DB_PATH = ROOT / "work" / "state.db"
ENC_PATH = STATE_DIR / "state.db.enc"
SALT = b"scara-opportunity-engine-v1"

SCHEMA = """
CREATE TABLE IF NOT EXISTS candidates (
  id TEXT PRIMARY KEY,
  plugin TEXT, title TEXT, summary TEXT, url TEXT,
  value_usd REAL, cost_usd REAL, claimability REAL, awareness REAL,
  claimants INTEGER, deadline TEXT, status TEXT, private INTEGER,
  score REAL, first_seen REAL, last_seen REAL, data TEXT
);
CREATE TABLE IF NOT EXISTS runs (
  ts REAL, plugin TEXT, seconds REAL, items INTEGER, hits INTEGER, error TEXT
);
CREATE TABLE IF NOT EXISTS kv (k TEXT PRIMARY KEY, v TEXT);
CREATE TABLE IF NOT EXISTS llm_cache (h TEXT PRIMARY KEY, out TEXT, ts REAL);
CREATE TABLE IF NOT EXISTS llm_usage (day TEXT, provider TEXT, calls INTEGER,
  PRIMARY KEY(day, provider));
"""


def configure(name):
    """Use a separate state file (e.g. 'forge') so engines never clash."""
    global DB_PATH, ENC_PATH
    DB_PATH = ROOT / "work" / f"{name}.db"
    ENC_PATH = STATE_DIR / f"{name}.db.enc"


def _fernet():
    pw = os.environ.get("STATE_PASSPHRASE", "")
    if not pw:
        return None
    key = hashlib.pbkdf2_hmac("sha256", pw.encode(), SALT, 200_000)
    return Fernet(base64.urlsafe_b64encode(key))


def load() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    f = _fernet()
    if ENC_PATH.exists() and f and not DB_PATH.exists():
        try:
            DB_PATH.write_bytes(f.decrypt(ENC_PATH.read_bytes()))
        except InvalidToken:
            raise SystemExit("STATE_PASSPHRASE does not match the saved state. "
                             "Restore the old passphrase, or delete state/state.db.enc to start fresh.")
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    return con


def save(con: sqlite3.Connection):
    con.commit()
    f = _fernet()
    if not f:
        print("[store] STATE_PASSPHRASE not set — state kept locally only (not saved to repo).")
        return
    STATE_DIR.mkdir(exist_ok=True)
    ENC_PATH.write_bytes(f.encrypt(DB_PATH.read_bytes()))


def kv_get(con, k, default=None):
    r = con.execute("SELECT v FROM kv WHERE k=?", (k,)).fetchone()
    return json.loads(r["v"]) if r else default


def kv_set(con, k, v):
    con.execute("INSERT OR REPLACE INTO kv VALUES (?,?)", (k, json.dumps(v)))


def upsert_candidate(con, c: dict) -> bool:
    """Insert or refresh a finding. Returns True if it's new."""
    now = time.time()
    old = con.execute("SELECT first_seen FROM candidates WHERE id=?", (c["id"],)).fetchone()
    con.execute(
        """INSERT OR REPLACE INTO candidates VALUES
        (:id,:plugin,:title,:summary,:url,:value_usd,:cost_usd,:claimability,:awareness,
         :claimants,:deadline,:status,:private,:score,:first_seen,:last_seen,:data)""",
        {**c, "first_seen": old["first_seen"] if old else now, "last_seen": now,
         "data": json.dumps(c.get("data", {}), default=str)[:20000]},
    )
    return old is None
