from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from online_cinema.core.config import get_settings
from online_cinema.core.security import hash_password
from online_cinema.db.base import Base
from online_cinema.db.models import User, UserGroup, UserGroupEnum, UserProfile
from online_cinema.db.session import SessionLocal, engine


async def init_database() -> None:
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with SessionLocal() as session:
        await seed_database(session)


async def seed_database(session: AsyncSession) -> None:
    for group_name in UserGroupEnum:
        existing_group = await session.scalar(select(UserGroup).where(UserGroup.name == group_name))
        if existing_group is None:
            session.add(UserGroup(name=group_name))

    await session.commit()

    settings = get_settings()
    admin = await session.scalar(
        select(User).where(User.email == str(settings.bootstrap_admin_email))
    )
    if admin is not None:
        return

    admin_group = await session.scalar(
        select(UserGroup).where(UserGroup.name == UserGroupEnum.ADMIN)
    )
    if admin_group is None:
        return

    admin = User(
        email=str(settings.bootstrap_admin_email),
        hashed_password=hash_password(settings.bootstrap_admin_password),
        is_active=True,
        group_id=admin_group.id,
    )
    session.add(admin)
    await session.flush()
    session.add(UserProfile(user_id=admin.id))
    await session.commit()
