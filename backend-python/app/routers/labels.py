import json
import time

from fastapi import APIRouter, Body, HTTPException

from ..db import get_db
from ..deps import UserId
from ..utils import compute_label_tree, safe_parse, serialize_note

router = APIRouter()


@router.get("")
def list_labels(user_id: UserId):
    with get_db() as db:
        rows = db.execute(
            "SELECT * FROM notes WHERE user_id = ? AND trashed = 0", (user_id,)
        ).fetchall()
    notes = [serialize_note(r) for r in rows]
    return {"labels": compute_label_tree(notes)}


@router.post("/reparent")
def reparent(user_id: UserId, body: dict = Body(default={})):
    source = body.get("from")
    target = body.get("to")
    if not source:
        raise HTTPException(status_code=400, detail="from is required")
    if target and (target == source or target.startswith(source + "/")):
        raise HTTPException(status_code=400, detail="Cannot move a label into its own descendant")

    parts = [p for p in source.split("/") if p]
    last_segment = parts[-1] if parts else source
    new_prefix = f"{target}/{last_segment}" if target else last_segment
    if new_prefix == source:
        return {"ok": True, "newPath": new_prefix}

    now = int(time.time() * 1000)
    with get_db() as db:
        rows = db.execute(
            "SELECT * FROM notes WHERE user_id = ? AND trashed = 0", (user_id,)
        ).fetchall()
        for row in rows:
            labels = safe_parse(row["labels"], [])
            changed = False
            next_labels = []
            for label in labels:
                if label == source:
                    changed = True
                    next_labels.append(new_prefix)
                elif label.startswith(source + "/"):
                    changed = True
                    next_labels.append(new_prefix + label[len(source):])
                else:
                    next_labels.append(label)
            if changed:
                db.execute(
                    "UPDATE notes SET labels = ?, updated_at = ? WHERE id = ?",
                    (json.dumps(next_labels), now, row["id"]),
                )
    return {"ok": True, "newPath": new_prefix}
