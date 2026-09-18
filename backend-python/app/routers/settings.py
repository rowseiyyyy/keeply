from fastapi import APIRouter, Body

from ..db import get_db
from ..deps import UserId
from ..utils import safe_parse

router = APIRouter()


def serialize(row) -> dict:
    return {
        "view": row["view"],
        "sort": row["sort"],
        "density": row["density"],
        "theme": row["theme"],
        "tweak": row["tweak"],
        "splitView": bool(row["split_view"]),
        "workspace": safe_parse(row["workspace"], []),
    }


@router.get("/")
def get_settings(user_id: UserId):
    with get_db() as db:
        row = db.execute(
            "SELECT * FROM user_settings WHERE user_id = ?", (user_id,)
        ).fetchone()
        if not row:
            db.execute("INSERT INTO user_settings (user_id) VALUES (?)", (user_id,))
            row = db.execute(
                "SELECT * FROM user_settings WHERE user_id = ?", (user_id,)
            ).fetchone()
    return {"settings": serialize(row)}


@router.put("/")
def update_settings(user_id: UserId, body: dict = Body(default={})):
    with get_db() as db:
        existing = db.execute(
            "SELECT * FROM user_settings WHERE user_id = ?", (user_id,)
        ).fetchone()
        if not existing:
            db.execute("INSERT INTO user_settings (user_id) VALUES (?)", (user_id,))

        db.execute(
            """UPDATE user_settings SET
              view = ?, sort = ?, density = ?, theme = ?, tweak = ?, split_view = ?, workspace = ?
             WHERE user_id = ?""",
            (
                body.get("view") or (existing["view"] if existing else None) or "grid",
                body.get("sort") or (existing["sort"] if existing else None) or "updated",
                body.get("density") or (existing["density"] if existing else None) or "comfortable",
                body.get("theme") or (existing["theme"] if existing else None) or "aurora",
                body.get("tweak") or (existing["tweak"] if existing else None) or "normal",
                (1 if body["splitView"] else 0) if "splitView" in body
                else ((existing["split_view"] if existing else 0) or 0),
                (
                    __import__("json").dumps(body["workspace"])
                    if "workspace" in body
                    else (existing["workspace"] if existing else None) or "[]"
                ),
                user_id,
            ),
        )
        row = db.execute(
            "SELECT * FROM user_settings WHERE user_id = ?", (user_id,)
        ).fetchone()
    return {"settings": serialize(row)}
