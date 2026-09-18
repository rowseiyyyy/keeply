import json
from typing import Any


def safe_parse(raw: Any, fallback):
    try:
        v = json.loads(raw)
        return v if v is not None else fallback
    except (TypeError, ValueError):
        return fallback


def serialize_note(row) -> dict:
    return {
        "id": row["id"],
        "title": row["title"],
        "body": row["body"],
        "color": row["color"],
        "pinned": bool(row["pinned"]),
        "archived": bool(row["archived"]),
        "trashed": bool(row["trashed"]),
        "labels": safe_parse(row["labels"], []),
        "images": safe_parse(row["images"], []),
        "attachments": safe_parse(row["attachments"], []),
        "collapsedSections": safe_parse(row["collapsed_sections"], []),
        "position": row["position"],
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
    }


def serialize_version(row) -> dict:
    return {
        "id": row["id"],
        "title": row["title"],
        "body": row["body"],
        "timestamp": row["timestamp"],
    }


def compute_label_tree(notes: list[dict]) -> list[dict]:
    all_paths: set[str] = set()
    for n in notes:
        for label in n.get("labels") or []:
            parts = [p for p in label.split("/") if p]
            cur = ""
            for p in parts:
                cur = f"{cur}/{p}" if cur else p
                all_paths.add(cur)
    result = []
    for path in sorted(all_paths):
        parts = [p for p in path.split("/") if p]
        count = sum(
            1
            for n in notes
            if any(l == path or l.startswith(path + "/") for l in (n.get("labels") or []))
        )
        result.append({
            "path": path,
            "name": parts[-1],
            "depth": len(parts) - 1,
            "count": count,
        })
    return result
