from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from online_cinema.api.dependencies.auth import get_current_active_user, require_roles
from online_cinema.db.models import User, UserGroupEnum
from online_cinema.db.session import get_db_session
from online_cinema.schemas.auth import GroupChangeRequest, MessageResponse
from online_cinema.schemas.movies import NotificationRead
from online_cinema.schemas.user import UserProfileRead, UserProfileUpdate, UserRead
from online_cinema.services.movies import list_notifications, mark_notification_read
from online_cinema.services.users import (
    activate_user_manually,
    change_user_group,
    get_current_user_profile,
    list_users,
    update_current_user_profile,
)

router = APIRouter()
admin_router = APIRouter()


@router.get("/me", response_model=UserRead)
async def read_current_user(user: User = Depends(get_current_active_user)) -> UserRead:
    return await get_current_user_profile(user)


@router.patch("/me", response_model=UserProfileRead)
async def update_profile(
    payload: UserProfileUpdate,
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_active_user),
) -> UserProfileRead:
    return await update_current_user_profile(session=session, user=user, payload=payload)


@router.get("/me/notifications", response_model=list[NotificationRead])
async def get_notifications(
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_active_user),
) -> list[NotificationRead]:
    return await list_notifications(session, user)


@router.post("/me/notifications/{notification_id}/read", response_model=MessageResponse)
async def read_notification(
    notification_id: int,
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_active_user),
) -> MessageResponse:
    return await mark_notification_read(session, user, notification_id)


@admin_router.get(
    "/users",
    response_model=list[UserRead],
    dependencies=[Depends(require_roles(UserGroupEnum.ADMIN))],
)
async def admin_list_users(
    session: AsyncSession = Depends(get_db_session),
    group: UserGroupEnum | None = Query(default=None),
    is_active: bool | None = Query(default=None),
) -> list[UserRead]:
    return await list_users(session=session, group=group, is_active=is_active)


@admin_router.patch(
    "/users/{user_id}/group",
    response_model=MessageResponse,
    dependencies=[Depends(require_roles(UserGroupEnum.ADMIN))],
)
async def admin_change_group(
    user_id: int,
    payload: GroupChangeRequest,
    session: AsyncSession = Depends(get_db_session),
) -> MessageResponse:
    return await change_user_group(session=session, user_id=user_id, target_group=payload.group)


@admin_router.post(
    "/users/{user_id}/activate",
    response_model=MessageResponse,
    dependencies=[Depends(require_roles(UserGroupEnum.ADMIN))],
)
async def admin_activate_user(
    user_id: int,
    session: AsyncSession = Depends(get_db_session),
) -> MessageResponse:
    return await activate_user_manually(session=session, user_id=user_id)
