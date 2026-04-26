from datetime import datetime, timedelta, timezone

import jwt
from jwt import ExpiredSignatureError, InvalidTokenError


def create_access_token(
    user_id: int,
    secret: str,
    algorithm: str,
    expires_delta: timedelta,
) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "exp": now + expires_delta,
        "iat": now,
    }
    return jwt.encode(payload, secret, algorithm=algorithm)


def decode_access_token(
    token: str,
    secret: str,
    algorithm: str,
) -> dict | None:
    try:
        return jwt.decode(token, secret, algorithms=[algorithm])
    except (ExpiredSignatureError, InvalidTokenError):
        return None
