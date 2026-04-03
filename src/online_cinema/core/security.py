import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from fastapi import HTTPException, status
from passlib.context import CryptContext

from online_cinema.core.config import get_settings

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")
PASSWORD_COMPLEXITY_PATTERN = re.compile(r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z\d]).{8,}$")


@dataclass(slots=True)
class TokenPayload:
    sub: str
    token_type: str
    exp: int
    jti: str | None = None


def utcnow() -> datetime:
    return datetime.now(UTC)


def ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    return pwd_context.verify(password, hashed_password)


def validate_password_complexity(password: str) -> None:
    if not PASSWORD_COMPLEXITY_PATTERN.match(password):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Password must be at least 8 characters long and include uppercase, lowercase, "
                "digit, and special characters."
            ),
        )


def create_token(
    *,
    subject: str,
    token_type: str,
    expires_delta: timedelta,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    settings = get_settings()
    expires_at = utcnow() + expires_delta
    payload: dict[str, Any] = {"sub": subject, "type": token_type, "exp": expires_at}
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.secret_key, algorithm="HS256")


def decode_token(token: str, *, expected_type: str) -> TokenPayload:
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired.",
        ) from exc
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token.",
        ) from exc

    token_type = payload.get("type")
    if token_type != expected_type:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type.")

    sub = payload.get("sub")
    exp = payload.get("exp")
    if sub is None or exp is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Malformed token.")

    return TokenPayload(
        sub=str(sub),
        token_type=str(token_type),
        exp=int(exp),
        jti=str(payload["jti"]) if payload.get("jti") else None,
    )
