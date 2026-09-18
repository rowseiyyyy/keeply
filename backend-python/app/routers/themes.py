import time
import uuid

from fastapi import APIRouter, Body, HTTPException

from ..db import get_db
from ..deps import UserId

router = APIRouter()


def serialize(row) -> dict:
    return {"id": row["id"], "name": row["name"], "bg": row["bg"], "a": row["a"], "b": row["b"], "c": row["c"]}


@router.get("/")
def list_themes(user_id: UserId):
    with get_db() as db:
        rows = db.execute(
            "SELECT * FROM custom_themes WHERE user_id = ? ORDER BY created_at ASC",
            (user_id,),
        ).fetchall()
    return {"themes": [serialize(r) for r in rows]}


@router.post("/", status_code=201)
def create_theme(user_id: UserId, body: dict = Body(default={})):
    name = body.get("name")
    bg, a, b, c = body.get("bg"), body.get("a"), body.get("b"), body.get("c")
    if not bg or not a or not b or not c:
        raise HTTPException(status_code=400, detail="bg, a, b and c colors are required")
    theme_id = f"custom-{uuid.uuid4()}"
    with get_db() as db:
        db.execute(
            "INSERT INTO custom_themes (id, user_id, name, bg, a, b, c, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (theme_id, user_id, name or "Custom theme", bg, a, b, c, int(time.time() * 1000)),
        )
    return {"theme": {"id": theme_id, "name": name or "Custom theme", "bg": bg, "a": a, "b": b, "c": c}}


@router.delete("/{theme_id}", status_code=204)
def delete_theme(theme_id: str, user_id: UserId):
    with get_db() as db:
        cur = db.execute(
            "DELETE FROM custom_themes WHERE id = ? AND user_id = ?", (theme_id, user_id)
        )
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Theme not found")
