from datetime import timedelta
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from online_cinema.core.config import get_settings
from online_cinema.core.security import (
    create_token,
    decode_token,
    ensure_utc,
    hash_password,
    utcnow,
    validate_password_complexity,
    verify_password,
)
from online_cinema.db.models import (
    ActivationToken,
    PasswordResetToken,
    RefreshToken,
    User,
    UserGroup,
    UserGroupEnum,
    UserProfile,
)
from online_cinema.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    MessageResponse,
    RegistrationRequest,
    TokenPairResponse,
)
from online_cinema.services.email import email_service


async def _get_user_group(session: AsyncSession, group_name: UserGroupEnum) -> UserGroup:
    group = await session.scalar(select(UserGroup).where(UserGroup.name == group_name))
    if group is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Group missing.",
        )
    return group


async def _get_user_by_email(session: AsyncSession, email: str) -> User | None:
    stmt = (
        select(User)
        .options(
            selectinload(User.group),
            selectinload(User.profile),
            selectinload(User.activation_token),
            selectinload(User.password_reset_token),
            selectinload(User.refresh_tokens),
        )
        .where(func.lower(User.email) == email.lower())
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


def _activation_expiration() -> timedelta:
    return timedelta(hours=get_settings().activation_token_ttl_hours)


def _password_reset_expiration() -> timedelta:
    return timedelta(hours=get_settings().password_reset_token_ttl_hours)


def _refresh_expiration() -> timedelta:
    return timedelta(days=get_settings().refresh_token_ttl_days)


async def _send_activation_email(user: User, token: str) -> None:
    settings = get_settings()
    activation_link = f"{settings.frontend_base_url}/activate?token={token}"
    await email_service.send_email(
        recipient=user.email,
        subject="Activate your Online Cinema account",
        body=f"Use this link to activate your account within 24 hours: {activation_link}",
    )


async def _send_password_reset_email(user: User, token: str) -> None:
    settings = get_settings()
    reset_link = f"{settings.frontend_base_url}/reset-password?token={token}"
    await email_service.send_email(
        recipient=user.email,
        subject="Reset your Online Cinema password",
        body=f"Use this link to reset your password: {reset_link}",
    )


async def register_user(session: AsyncSession, payload: RegistrationRequest) -> MessageResponse:
    existing_user = await _get_user_by_email(session, payload.email)
    if existing_user is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email is already registered.",
        )

    validate_password_complexity(payload.password)
    user_group = await _get_user_group(session, UserGroupEnum.USER)

    user = User(
        email=str(payload.email),
        hashed_password=hash_password(payload.password),
        is_active=False,
        group_id=user_group.id,
    )
    session.add(user)
    await session.flush()

    session.add(
        UserProfile(
            user_id=user.id,
            first_name=payload.first_name,
            last_name=payload.last_name,
        )
    )

    token_value = str(uuid4())
    session.add(
        ActivationToken(
            user_id=user.id,
            token=token_value,
            expires_at=utcnow() + _activation_expiration(),
        )
    )
    await session.commit()
    await _send_activation_email(user, token_value)
    return MessageResponse(
        message="Registration successful. Check your email to activate the account."
    )


async def activate_account(session: AsyncSession, token: str) -> MessageResponse:
    stmt = (
        select(ActivationToken)
        .options(selectinload(ActivationToken.user))
        .where(ActivationToken.token == token)
    )
    activation_token = await session.scalar(stmt)
    if activation_token is None or ensure_utc(activation_token.expires_at) < utcnow():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Activation token is invalid.",
        )

    activation_token.user.is_active = True
    await session.delete(activation_token)
    await session.commit()
    return MessageResponse(message="Account activated successfully.")


async def resend_activation_token(session: AsyncSession, email: str) -> MessageResponse:
    user = await _get_user_by_email(session, email)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    if user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Account is already active.",
        )

    if user.activation_token is not None:
        await session.delete(user.activation_token)
        await session.flush()

    token_value = str(uuid4())
    session.add(
        ActivationToken(
            user_id=user.id,
            token=token_value,
            expires_at=utcnow() + _activation_expiration(),
        )
    )
    await session.commit()
    await _send_activation_email(user, token_value)
    return MessageResponse(message="A new activation link has been sent.")


async def login_user(session: AsyncSession, payload: LoginRequest) -> TokenPairResponse:
    user = await _get_user_by_email(session, payload.email)
    if user is None or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials.")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is inactive.")

    refresh_identifier = str(uuid4())
    refresh_expires_at = utcnow() + _refresh_expiration()
    session.add(
        RefreshToken(
            user_id=user.id,
            token=refresh_identifier,
            expires_at=refresh_expires_at,
        )
    )
    await session.commit()

    access_token = create_token(
        subject=str(user.id),
        token_type="access",
        expires_delta=timedelta(minutes=get_settings().access_token_ttl_minutes),
    )
    refresh_token = create_token(
        subject=str(user.id),
        token_type="refresh",
        expires_delta=_refresh_expiration(),
        extra_claims={"jti": refresh_identifier},
    )
    return TokenPairResponse(access_token=access_token, refresh_token=refresh_token)


async def refresh_access_token(session: AsyncSession, refresh_token: str) -> TokenPairResponse:
    payload = decode_token(refresh_token, expected_type="refresh")
    if payload.jti is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed refresh token.",
        )

    token_record = await session.scalar(
        select(RefreshToken).where(RefreshToken.token == payload.jti)
    )
    if token_record is None or ensure_utc(token_record.expires_at) < utcnow():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token is revoked.",
        )

    access_token = create_token(
        subject=payload.sub,
        token_type="access",
        expires_delta=timedelta(minutes=get_settings().access_token_ttl_minutes),
    )
    return TokenPairResponse(access_token=access_token, refresh_token=refresh_token)


async def logout_user(session: AsyncSession, refresh_token: str) -> MessageResponse:
    payload = decode_token(refresh_token, expected_type="refresh")
    if payload.jti is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed refresh token.",
        )

    token_record = await session.scalar(
        select(RefreshToken).where(RefreshToken.token == payload.jti)
    )
    if token_record is not None:
        await session.delete(token_record)
        await session.commit()
    return MessageResponse(message="Logged out successfully.")


async def change_password(
    session: AsyncSession,
    user: User,
    payload: ChangePasswordRequest,
) -> MessageResponse:
    if not verify_password(payload.old_password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Old password is incorrect.",
        )

    validate_password_complexity(payload.new_password)
    user.hashed_password = hash_password(payload.new_password)
    await session.execute(delete(RefreshToken).where(RefreshToken.user_id == user.id))
    await session.commit()
    return MessageResponse(message="Password updated successfully.")


async def request_password_reset(session: AsyncSession, email: str) -> MessageResponse:
    user = await _get_user_by_email(session, email)
    if user is None or not user.is_active:
        return MessageResponse(message="If the account exists, a reset link has been sent.")

    if user.password_reset_token is not None:
        await session.delete(user.password_reset_token)
        await session.flush()

    token_value = str(uuid4())
    session.add(
        PasswordResetToken(
            user_id=user.id,
            token=token_value,
            expires_at=utcnow() + _password_reset_expiration(),
        )
    )
    await session.commit()
    await _send_password_reset_email(user, token_value)
    return MessageResponse(message="If the account exists, a reset link has been sent.")


async def reset_password(session: AsyncSession, token: str, new_password: str) -> MessageResponse:
    validate_password_complexity(new_password)
    stmt = (
        select(PasswordResetToken)
        .options(selectinload(PasswordResetToken.user))
        .where(PasswordResetToken.token == token)
    )
    reset_token = await session.scalar(stmt)
    if reset_token is None or ensure_utc(reset_token.expires_at) < utcnow():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reset token is invalid.",
        )

    reset_token.user.hashed_password = hash_password(new_password)
    await session.execute(delete(RefreshToken).where(RefreshToken.user_id == reset_token.user_id))
    await session.delete(reset_token)
    await session.commit()
    return MessageResponse(message="Password has been reset successfully.")


async def cleanup_expired_tokens(session: AsyncSession) -> int:
    now = utcnow()
    activation_count = await session.scalar(
        select(func.count()).select_from(ActivationToken).where(ActivationToken.expires_at < now)
    )
    password_count = await session.scalar(
        select(func.count())
        .select_from(PasswordResetToken)
        .where(PasswordResetToken.expires_at < now)
    )
    refresh_count = await session.scalar(
        select(func.count()).select_from(RefreshToken).where(RefreshToken.expires_at < now)
    )

    await session.execute(delete(ActivationToken).where(ActivationToken.expires_at < now))
    await session.execute(delete(PasswordResetToken).where(PasswordResetToken.expires_at < now))
    await session.execute(delete(RefreshToken).where(RefreshToken.expires_at < now))
    await session.commit()
    return (activation_count or 0) + (password_count or 0) + (refresh_count or 0)
