import sqlite3
from typing import Annotated

from fastapi import Depends, HTTPException, Request

from .db import get_db
from .security import verify_token

DbDep = Annotated[sqlite3.Connection, Depends(get_db)]


def _user_id(request: Request, db: DbDep) -> str:
    header = request.headers.get("authorization") or ""
    if not header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    try:
        return verify_token(header[len("Bearer "):])
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


UserId = Annotated[str, Depends(_user_id)]


def get_owned_note(db: sqlite3.Connection, note_id: str, user_id: str):
    return db.execute(
        "SELECT * FROM notes WHERE id = ? AND user_id = ?", (note_id, user_id)
    ).fetchone()

