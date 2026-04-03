from collections.abc import Awaitable, Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from online_cinema.core.security import decode_token
from online_cinema.db.models import User, UserGroupEnum
from online_cinema.db.session import get_db_session

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    session: AsyncSession = Depends(get_db_session),
) -> User:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
        )

    payload = decode_token(credentials.credentials, expected_type="access")
    stmt = (
        select(User)
        .options(selectinload(User.group), selectinload(User.profile))
        .where(User.id == int(payload.sub))
    )
    user = await session.scalar(stmt)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found.")
    return user


async def get_current_active_user(user: User = Depends(get_current_user)) -> User:
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive.",
        )
    return user


def require_roles(*roles: UserGroupEnum) -> Callable[[User], Awaitable[User]]:
    async def dependency(user: User = Depends(get_current_active_user)) -> User:
        if user.group.name not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions.",
            )
        return user

    return dependency
