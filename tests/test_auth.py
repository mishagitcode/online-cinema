from datetime import timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from online_cinema.core.security import utcnow
from online_cinema.db.models import (
    ActivationToken,
    PasswordResetToken,
    RefreshToken,
    User,
    UserGroupEnum,
)
from online_cinema.services.auth import cleanup_expired_tokens


async def register_user(
    client, email: str = "user@example.com", password: str = "Password1!"
) -> None:
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "first_name": "John"},
    )
    assert response.status_code == 201


@pytest.mark.asyncio
async def test_user_registration_creates_inactive_account_and_activation_token(
    client, db_session
) -> None:
    await register_user(client)

    user = await db_session.scalar(select(User).where(User.email == "user@example.com"))
    activation_token = await db_session.scalar(
        select(ActivationToken).join(User).where(User.email == "user@example.com")
    )

    assert user is not None
    assert user.is_active is False
    assert activation_token is not None


@pytest.mark.asyncio
async def test_account_activation_and_login_flow(client, db_session) -> None:
    await register_user(client)
    activation_token = await db_session.scalar(
        select(ActivationToken).join(User).where(User.email == "user@example.com")
    )
    assert activation_token is not None

    activation_response = await client.get(f"/api/v1/auth/activate/{activation_token.token}")
    login_response = await client.post(
        "/api/v1/auth/login",
        json={"email": "user@example.com", "password": "Password1!"},
    )

    assert activation_response.status_code == 200
    assert login_response.status_code == 200
    assert "access_token" in login_response.json()
    assert "refresh_token" in login_response.json()


@pytest.mark.asyncio
async def test_refresh_and_logout_revoke_token(client, db_session) -> None:
    await register_user(client)
    activation_token = await db_session.scalar(select(ActivationToken))
    assert activation_token is not None
    await client.get(f"/api/v1/auth/activate/{activation_token.token}")

    login_response = await client.post(
        "/api/v1/auth/login",
        json={"email": "user@example.com", "password": "Password1!"},
    )
    tokens = login_response.json()
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    refresh_response = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    logout_response = await client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": tokens["refresh_token"]},
        headers=headers,
    )
    refresh_after_logout = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    )

    assert refresh_response.status_code == 200
    assert logout_response.status_code == 200
    assert refresh_after_logout.status_code == 401


@pytest.mark.asyncio
async def test_change_password_requires_old_password_and_invalidates_refresh_tokens(
    client, db_session
) -> None:
    await register_user(client)
    activation_token = await db_session.scalar(select(ActivationToken))
    assert activation_token is not None
    await client.get(f"/api/v1/auth/activate/{activation_token.token}")

    login_response = await client.post(
        "/api/v1/auth/login",
        json={"email": "user@example.com", "password": "Password1!"},
    )
    tokens = login_response.json()
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    change_response = await client.post(
        "/api/v1/auth/change-password",
        json={"old_password": "Password1!", "new_password": "NewPass1!"},
        headers=headers,
    )
    refresh_response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    )

    assert change_response.status_code == 200
    assert refresh_response.status_code == 401


@pytest.mark.asyncio
async def test_password_reset_flow(client, db_session) -> None:
    await register_user(client)
    activation_token = await db_session.scalar(select(ActivationToken))
    assert activation_token is not None
    await client.get(f"/api/v1/auth/activate/{activation_token.token}")

    forgot_response = await client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "user@example.com"},
    )
    reset_token = await db_session.scalar(select(PasswordResetToken))
    assert reset_token is not None

    reset_response = await client.post(
        f"/api/v1/auth/reset-password/{reset_token.token}",
        json={"new_password": "ResetPass1!"},
    )
    login_response = await client.post(
        "/api/v1/auth/login",
        json={"email": "user@example.com", "password": "ResetPass1!"},
    )

    assert forgot_response.status_code == 200
    assert reset_response.status_code == 200
    assert login_response.status_code == 200


@pytest.mark.asyncio
async def test_admin_can_change_group_and_activate_user(client, db_session) -> None:
    await register_user(client, email="inactive@example.com")

    login_response = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "Admin123!"},
    )
    admin_tokens = login_response.json()
    headers = {"Authorization": f"Bearer {admin_tokens['access_token']}"}

    inactive_user = await db_session.scalar(
        select(User).where(User.email == "inactive@example.com")
    )
    assert inactive_user is not None
    inactive_user_id = inactive_user.id

    activate_response = await client.post(
        f"/api/v1/admin/users/{inactive_user_id}/activate", headers=headers
    )
    group_response = await client.patch(
        f"/api/v1/admin/users/{inactive_user_id}/group",
        json={"group": "MODERATOR"},
        headers=headers,
    )

    db_session.expire_all()
    inactive_user = await db_session.scalar(
        select(User).options(selectinload(User.group)).where(User.id == inactive_user_id)
    )

    assert activate_response.status_code == 200
    assert group_response.status_code == 200
    assert inactive_user is not None
    assert inactive_user.is_active is True
    assert inactive_user.group.name == UserGroupEnum.MODERATOR


@pytest.mark.asyncio
async def test_cleanup_expired_tokens_removes_stale_records(db_session) -> None:
    user = await db_session.scalar(select(User).where(User.email == "admin@example.com"))
    assert user is not None

    db_session.add(
        ActivationToken(
            user_id=user.id,
            token="expired-activation",
            expires_at=utcnow() - timedelta(hours=1),
        )
    )
    db_session.add(
        PasswordResetToken(
            user_id=user.id,
            token="expired-reset",
            expires_at=utcnow() - timedelta(hours=1),
        )
    )
    db_session.add(
        RefreshToken(
            user_id=user.id,
            token="expired-refresh",
            expires_at=utcnow() - timedelta(days=1),
        )
    )
    await db_session.commit()

    removed_count = await cleanup_expired_tokens(db_session)

    assert removed_count == 3
