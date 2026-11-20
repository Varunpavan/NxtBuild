from datetime import datetime, timezone
import bcrypt
import jwt
from config import settings


def hash_password(plain_password: str) -> str:
    salt = bcrypt.gensalt(rounds=10)
    return bcrypt.hashpw(plain_password.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8")
        )
    except Exception:
        return False


def create_access_token(user_id: str) -> str:
    now = datetime.now(timezone.utc)
    expire = now + settings.token_expiration_delta
    payload = {
        "id": user_id,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp())
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")


def decode_access_token(token: str) -> dict:
    return jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
