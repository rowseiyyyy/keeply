import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parents[1]
# Reuse the existing Node backend's data files so this is a drop-in replacement.
DATA_DIR = Path(os.getenv("DATA_DIR", BASE_DIR.parent / "backend" / "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "keeply.db"

UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", BASE_DIR.parent / "backend" / "uploads"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
  id TEXT PRIMARY KEY,
  email TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL,
  created_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS notes (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  title TEXT NOT NULL DEFAULT '',
  body TEXT NOT NULL DEFAULT '',
  color TEXT NOT NULL DEFAULT 'default',
  pinned INTEGER NOT NULL DEFAULT 0,
  archived INTEGER NOT NULL DEFAULT 0,
  trashed INTEGER NOT NULL DEFAULT 0,
  labels TEXT NOT NULL DEFAULT '[]',
  images TEXT NOT NULL DEFAULT '[]',
  attachments TEXT NOT NULL DEFAULT '[]',
  collapsed_sections TEXT NOT NULL DEFAULT '[]',
  position INTEGER NOT NULL DEFAULT 0,
  created_at INTEGER NOT NULL,
  updated_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_notes_user ON notes(user_id);

CREATE TABLE IF NOT EXISTS note_versions (
  id TEXT PRIMARY KEY,
  note_id TEXT NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
  title TEXT NOT NULL DEFAULT '',
  body TEXT NOT NULL DEFAULT '',
  timestamp INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_versions_note ON note_versions(note_id);

CREATE TABLE IF NOT EXISTS custom_themes (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  bg TEXT NOT NULL,
  a TEXT NOT NULL,
  b TEXT NOT NULL,
  c TEXT NOT NULL,
  created_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_themes_user ON custom_themes(user_id);

CREATE TABLE IF NOT EXISTS user_settings (
  user_id TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
  view TEXT NOT NULL DEFAULT 'grid',
  sort TEXT NOT NULL DEFAULT 'updated',
  density TEXT NOT NULL DEFAULT 'comfortable',
  theme TEXT NOT NULL DEFAULT 'aurora',
  tweak TEXT NOT NULL DEFAULT 'normal',
  split_view INTEGER NOT NULL DEFAULT 0,
  workspace TEXT NOT NULL DEFAULT '[]'
);
"""


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def get_db():
    """Per-request connection (endpoints are sync defs, run in FastAPI's threadpool)."""
    conn = connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_db_dep():
    """FastAPI dependency wrapper around get_db (contextmanager can't be a dependency)."""
    with get_db() as conn:
        yield conn


def init_db() -> None:
    conn = connect()
    try:
        with conn:
            conn.executescript(SCHEMA)
    finally:
        conn.close()
