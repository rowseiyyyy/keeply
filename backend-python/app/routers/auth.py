import re
import time
import uuid

from fastapi import APIRouter, Body, HTTPException

from ..db import get_db
from ..deps import UserId
from ..security import check_password, hash_password, sign_token

router = APIRouter()

EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def public_user(row) -> dict:
    return {"id": row["id"], "email": row["email"], "createdAt": row["created_at"]}


@router.post("/register", status_code=201)
def register(body: dict = Body(default={})):
    email = body.get("email")
    password = body.get("password")
    if not email or not EMAIL_RE.match(email):
        raise HTTPException(status_code=400, detail="A valid email is required")
    if not password or len(password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    with get_db() as db:
        email = email.lower()
        if db.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone():
            raise HTTPException(status_code=409, detail="An account with that email already exists")

        user_id = str(uuid.uuid4())
        now = int(time.time() * 1000)
        db.execute(
            "INSERT INTO users (id, email, password_hash, created_at) VALUES (?, ?, ?, ?)",
            (user_id, email, hash_password(password), now),
        )
        db.execute("INSERT INTO user_settings (user_id) VALUES (?)", (user_id,))

    return {"token": sign_token(user_id), "user": {"id": user_id, "email": email, "createdAt": now}}


@router.post("/login")
def login(body: dict = Body(default={})):
    email = body.get("email")
    password = body.get("password")
    if not email or not password:
        raise HTTPException(status_code=400, detail="Email and password are required")

    with get_db() as db:
        row = db.execute(
            "SELECT * FROM users WHERE email = ?", (email.lower(),)
        ).fetchone()
    if not row or not check_password(password, row["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    return {"token": sign_token(row["id"]), "user": public_user(row)}


@router.get("/me")
def me(user_id: UserId):
    with get_db() as db:
        row = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="User not found")
    return {"user": public_user(row)}
