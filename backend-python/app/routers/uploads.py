import os
import uuid
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

from ..db import UPLOAD_DIR
from ..deps import UserId

router = APIRouter()

MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_BYTES", 15 * 1024 * 1024))


@router.post("/", status_code=201)
def upload_file(user_id: UserId, file: UploadFile = File(...)):
    ext = Path(file.filename or "").suffix
    filename = f"{uuid.uuid4()}{ext}"
    dest = UPLOAD_DIR / filename

    size = 0
    with dest.open("wb") as out:
        while chunk := file.file.read(1024 * 1024):
            size += len(chunk)
            if size > MAX_UPLOAD_BYTES:
                out.close()
                dest.unlink(missing_ok=True)
                raise HTTPException(status_code=413, detail="File too large")
            out.write(chunk)

    return {
        "id": dest.stem,
        "name": file.filename,
        "size": size,
        "type": file.content_type,
        "url": f"/uploads/{filename}",
    }
