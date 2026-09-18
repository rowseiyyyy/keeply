import os
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret-change-me")
JWT_EXPIRES_IN = os.getenv("JWT_EXPIRES_IN", "30d")


def _expires_delta() -> timedelta:
    value = JWT_EXPIRES_IN.strip()
    unit = value[-1]
    try:
        amount = int(value[:-1])
    except ValueError:
        amount, unit = 30, "d"
    multipliers = {"s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800}
    return timedelta(seconds=amount * multipliers.get(unit, 86400))


def sign_token(user_id: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {"sub": user_id, "iat": now, "exp": now + _expires_delta()}
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def verify_token(token: str) -> str:
    payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    return payload["sub"]


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=10)).decode("utf-8")


def check_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False
