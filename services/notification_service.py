import asyncio
import logging
from datetime import datetime, timezone
import pytz
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from aiogram import Bot
from models.notification import NotificationSetting
from models.user import User
from database import AsyncSessionLocal

logger = logging.getLogger(__name__)


async def get_notification_setting(session: AsyncSession, user_id: int) -> NotificationSetting | None:
    result = await session.execute(
        select(NotificationSetting).where(NotificationSetting.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def update_notification_setting(
    session: AsyncSession,
    user_id: int,
    enabled: bool,
    timezone_str: str = "UTC",
) -> NotificationSetting:
    setting = await get_notification_setting(session, user_id)
    if setting:
        setting.enabled = enabled
        setting.timezone = timezone_str
    else:
        setting = NotificationSetting(user_id=user_id, enabled=enabled, timezone=timezone_str)
        session.add(setting)
    await session.commit()
    return setting


async def run_daily_reminder_loop(bot: Bot) -> None:
    """Background task that fires daily reminders at 21:00 user-local time."""
    logger.info("Daily reminder loop started")
    while True:
        try:
            await _check_and_send_reminders(bot)
        except Exception as e:
            logger.error(f"Reminder loop error: {e}")
        # Check every minute
        await asyncio.sleep(60)


async def _check_and_send_reminders(bot: Bot) -> None:
    now_utc = datetime.now(timezone.utc)
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(NotificationSetting)
            .options(selectinload(NotificationSetting.user))
            .where(NotificationSetting.enabled == True)
        )
        settings = result.scalars().all()

        for setting in settings:
            try:
                tz = pytz.timezone(setting.timezone)
                local_now = now_utc.astimezone(tz)
                if local_now.hour == setting.reminder_hour and local_now.minute == 0:
                    await bot.send_message(
                        setting.user.telegram_id,
                        "🌙 <b>Daily Reminder</b>\n\n"
                        "Don't forget to log today's expenses!\n"
                        "Use /today to see what's been added.",
                        parse_mode="HTML",
                    )
            except Exception as e:
                logger.warning(f"Failed to send reminder to user {setting.user_id}: {e}")
