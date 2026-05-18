from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from models.user import User
from models.notification import NotificationSetting


async def get_or_create_user(
    session: AsyncSession,
    telegram_id: int,
    username: str | None,
    full_name: str,
) -> tuple[User, bool]:
    result = await session.execute(select(User).where(User.telegram_id == telegram_id))
    user = result.scalar_one_or_none()
    if user:
        # Update name/username on every interaction
        user.username = username
        user.full_name = full_name
        await session.commit()
        return user, False

    user = User(telegram_id=telegram_id, username=username, full_name=full_name)
    session.add(user)
    await session.flush()

    notif = NotificationSetting(user_id=user.id, enabled=False, timezone="UTC")
    session.add(notif)
    await session.commit()
    await session.refresh(user)
    return user, True


async def get_user_by_telegram_id(session: AsyncSession, telegram_id: int) -> User | None:
    result = await session.execute(select(User).where(User.telegram_id == telegram_id))
    return result.scalar_one_or_none()


async def get_user_by_id(session: AsyncSession, user_id: int) -> User | None:
    result = await session.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()
