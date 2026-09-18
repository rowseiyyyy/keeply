import json
import time
import uuid
from typing import Optional

from fastapi import APIRouter, Body, HTTPException, Query

from ..db import get_db
from ..deps import UserId, get_owned_note
from ..utils import serialize_note, serialize_version

router = APIRouter()

MAX_VERSIONS = 20

JSON_FIELDS = ("labels", "images", "attachments", "collapsedSections")
BOOL_FIELDS = ("pinned", "archived", "trashed")


def _json(value):
    return json.dumps(value)


@router.get("/")
def list_notes(
    user_id: UserId,
    trashed: Optional[str] = Query(default=None),
    archived: Optional[str] = Query(default=None),
    label: Optional[str] = Query(default=None),
    search: Optional[str] = Query(default=None),
):
    with get_db() as db:
        rows = db.execute(
            "SELECT * FROM notes WHERE user_id = ? ORDER BY position ASC, updated_at DESC",
            (user_id,),
        ).fetchall()
    notes = [serialize_note(r) for r in rows]

    if trashed is not None:
        want = trashed in ("true", "1")
        notes = [n for n in notes if n["trashed"] == want]
    if archived is not None:
        want = archived in ("true", "1")
        notes = [n for n in notes if n["archived"] == want]
    if label:
        notes = [n for n in notes if any(l == label or l.startswith(label + "/") for l in n["labels"])]
    if search:
        s = str(search).lower()
        notes = [
            n
            for n in notes
            if s in n["title"].lower()
            or s in n["body"].lower()
            or any(s in l.lower() for l in n["labels"])
            or any(s in (a.get("name") or "").lower() for a in n["attachments"])
        ]
    return {"notes": notes}


@router.get("/{note_id}")
def get_note(note_id: str, user_id: UserId):
    with get_db() as db:
        row = get_owned_note(db, note_id, user_id)
    if not row:
        raise HTTPException(status_code=404, detail="Note not found")
    return {"note": serialize_note(row)}


@router.post("/", status_code=201)
def create_note(user_id: UserId, body: dict = Body(default={})):
    note_id = str(uuid.uuid4())
    now = int(time.time() * 1000)
    with get_db() as db:
        max_pos = db.execute(
            "SELECT COALESCE(MIN(position), 0) - 1 AS p FROM notes WHERE user_id = ?",
            (user_id,),
        ).fetchone()["p"]
        db.execute(
            """INSERT INTO notes
              (id, user_id, title, body, color, pinned, archived, trashed, labels, images,
               attachments, collapsed_sections, position, created_at, updated_at)
             VALUES (?, ?, ?, ?, ?, ?, 0, 0, ?, ?, ?, ?, ?, ?, ?)""",
            (
                note_id,
                user_id,
                body.get("title") or "",
                body.get("body") or "",
                body.get("color") or "default",
                1 if body.get("pinned") else 0,
                _json(body.get("labels", [])),
                _json(body.get("images", [])),
                _json(body.get("attachments", [])),
                _json(body.get("collapsedSections", [])),
                max_pos,
                now,
                now,
            ),
        )
        row = get_owned_note(db, note_id, user_id)
    return {"note": serialize_note(row)}

@router.put("/{note_id}")
def update_note(note_id: str, user_id: UserId, body: dict = Body(default={})):
    now = int(time.time() * 1000)
    with get_db() as db:
        existing = get_owned_note(db, note_id, user_id)
        if not existing:
            raise HTTPException(status_code=404, detail="Note not found")

        new_title = body["title"] if "title" in body else existing["title"]
        new_body = body["body"] if "body" in body else existing["body"]

        if new_title != existing["title"] or new_body != existing["body"]:
            db.execute(
                "INSERT INTO note_versions (id, note_id, title, body, timestamp) VALUES (?, ?, ?, ?, ?)",
                (str(uuid.uuid4()), existing["id"], existing["title"], existing["body"], existing["updated_at"]),
            )
            excess = db.execute(
                "SELECT id FROM note_versions WHERE note_id = ? ORDER BY timestamp DESC LIMIT -1 OFFSET ?",
                (existing["id"], MAX_VERSIONS),
            ).fetchall()
            if excess:
                db.execute(
                    f"DELETE FROM note_versions WHERE id IN ({','.join('?' for _ in excess)})",
                    [r["id"] for r in excess],
                )

        db.execute(
            """UPDATE notes SET
              title = ?, body = ?, color = ?, pinned = ?, archived = ?, trashed = ?,
              labels = ?, images = ?, attachments = ?, collapsed_sections = ?, updated_at = ?
             WHERE id = ? AND user_id = ?""",
            (
                new_title,
                new_body,
                body["color"] if "color" in body else existing["color"],
                (1 if body["pinned"] else 0) if "pinned" in body else existing["pinned"],
                (1 if body["archived"] else 0) if "archived" in body else existing["archived"],
                (1 if body["trashed"] else 0) if "trashed" in body else existing["trashed"],
                _json(body["labels"]) if "labels" in body else existing["labels"],
                _json(body["images"]) if "images" in body else existing["images"],
                _json(body["attachments"]) if "attachments" in body else existing["attachments"],
                _json(body["collapsedSections"]) if "collapsedSections" in body else existing["collapsed_sections"],
                now,
                existing["id"],
                user_id,
            ),
        )
        row = get_owned_note(db, existing["id"], user_id)
    return {"note": serialize_note(row)}


@router.patch("/{note_id}")
def patch_note(note_id: str, user_id: UserId, body: dict = Body(default={})):
    field_map = {
        "title": "title",
        "body": "body",
        "color": "color",
        "pinned": "pinned",
        "archived": "archived",
        "trashed": "trashed",
        "labels": "labels",
        "images": "images",
        "attachments": "attachments",
        "collapsedSections": "collapsed_sections",
    }
    with get_db() as db:
        existing = get_owned_note(db, note_id, user_id)
        if not existing:
            raise HTTPException(status_code=404, detail="Note not found")

        sets, values = [], []
        for key, column in field_map.items():
            if key not in body:
                continue
            sets.append(f"{column} = ?")
            if key in BOOL_FIELDS:
                values.append(1 if body[key] else 0)
            elif key in JSON_FIELDS:
                values.append(_json(body[key]))
            else:
                values.append(body[key])
        if not sets:
            return {"note": serialize_note(existing)}

        sets.append("updated_at = ?")
        values.append(int(time.time() * 1000))
        values.extend([existing["id"], user_id])
        db.execute(
            f"UPDATE notes SET {', '.join(sets)} WHERE id = ? AND user_id = ?", values
        )
        row = get_owned_note(db, existing["id"], user_id)
    return {"note": serialize_note(row)}


@router.delete("/{note_id}", status_code=204)
def delete_note(note_id: str, user_id: UserId):
    with get_db() as db:
        existing = get_owned_note(db, note_id, user_id)
        if not existing:
            raise HTTPException(status_code=404, detail="Note not found")
        db.execute("DELETE FROM notes WHERE id = ? AND user_id = ?", (existing["id"], user_id))


@router.post("/reorder")
def reorder(user_id: UserId, body: dict = Body(default={})):
    ordered_ids = body.get("orderedIds")
    if not isinstance(ordered_ids, list):
        raise HTTPException(status_code=400, detail="orderedIds must be an array of note ids")
    with get_db() as db:
        for index, note_id in enumerate(ordered_ids):
            db.execute(
                "UPDATE notes SET position = ? WHERE id = ? AND user_id = ?",
                (index, note_id, user_id),
            )
    return {"ok": True}


@router.get("/{note_id}/versions")
def list_versions(note_id: str, user_id: UserId):
    with get_db() as db:
        existing = get_owned_note(db, note_id, user_id)
        if not existing:
            raise HTTPException(status_code=404, detail="Note not found")
        rows = db.execute(
            "SELECT * FROM note_versions WHERE note_id = ? ORDER BY timestamp DESC",
            (existing["id"],),
        ).fetchall()
    return {"versions": [serialize_version(r) for r in rows]}


@router.post("/{note_id}/versions/{version_id}/restore")
def restore_version(note_id: str, version_id: str, user_id: UserId):
    now = int(time.time() * 1000)
    with get_db() as db:
        existing = get_owned_note(db, note_id, user_id)
        if not existing:
            raise HTTPException(status_code=404, detail="Note not found")
        version = db.execute(
            "SELECT * FROM note_versions WHERE id = ? AND note_id = ?",
            (version_id, existing["id"]),
        ).fetchone()
        if not version:
            raise HTTPException(status_code=404, detail="Version not found")

        db.execute(
            "INSERT INTO note_versions (id, note_id, title, body, timestamp) VALUES (?, ?, ?, ?, ?)",
            (str(uuid.uuid4()), existing["id"], existing["title"], existing["body"], existing["updated_at"]),
        )
        db.execute(
            "UPDATE notes SET title = ?, body = ?, updated_at = ? WHERE id = ? AND user_id = ?",
            (version["title"], version["body"], now, existing["id"], user_id),
        )
        row = get_owned_note(db, existing["id"], user_id)
    return {"note": serialize_note(row)}

