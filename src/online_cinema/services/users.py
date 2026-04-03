from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from online_cinema.db.models import ActivationToken, User, UserGroup, UserGroupEnum
from online_cinema.schemas.auth import MessageResponse
from online_cinema.schemas.user import UserProfileRead, UserProfileUpdate, UserRead


async def get_current_user_profile(user: User) -> UserRead:
    return UserRead.model_validate(user)


async def update_current_user_profile(
    session: AsyncSession,
    user: User,
    payload: UserProfileUpdate,
) -> UserProfileRead:
    if user.profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found.")

    for field_name, value in payload.model_dump(exclude_unset=True).items():
        setattr(user.profile, field_name, value)

    await session.commit()
    await session.refresh(user.profile)
    return UserProfileRead.model_validate(user.profile)


async def list_users(
    session: AsyncSession,
    group: UserGroupEnum | None,
    is_active: bool | None,
) -> list[UserRead]:
    stmt = select(User).options(selectinload(User.group), selectinload(User.profile))
    if group is not None:
        stmt = stmt.join(User.group).where(UserGroup.name == group)
    if is_active is not None:
        stmt = stmt.where(User.is_active.is_(is_active))

    users = (await session.scalars(stmt.order_by(User.id))).all()
    return [UserRead.model_validate(user) for user in users]


async def change_user_group(
    session: AsyncSession,
    user_id: int,
    target_group: UserGroupEnum,
) -> MessageResponse:
    user = await session.scalar(
        select(User).options(selectinload(User.group)).where(User.id == user_id)
    )
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    group = await session.scalar(select(UserGroup).where(UserGroup.name == target_group))
    if group is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found.")

    user.group_id = group.id
    await session.commit()
    return MessageResponse(message="User group updated.")


async def activate_user_manually(session: AsyncSession, user_id: int) -> MessageResponse:
    user = await session.scalar(select(User).where(User.id == user_id))
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    user.is_active = True
    activation_token = await session.scalar(
        select(ActivationToken).where(ActivationToken.user_id == user.id)
    )
    if activation_token is not None:
        await session.delete(activation_token)
    await session.commit()
    return MessageResponse(message="User activated.")
