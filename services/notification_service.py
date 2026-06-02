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

# Данг — Asia/Ho_Chi_Minh (UTC+7)
DANANG_TZ = "Asia/Ho_Chi_Minh"
REMINDER_HOUR = 21  # 21:00 по Дананге


async def get_notification_setting(session: AsyncSession, user_id: int) -> NotificationSetting | None:
    result = await session.execute(
        select(NotificationSetting).where(NotificationSetting.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def update_notification_setting(
    session: AsyncSession,
    user_id: int,
    enabled: bool,
    timezone_str: str = DANANG_TZ,
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
    logger.info("Цикл ежедневных напоминаний запущен")
    sent_today: set[int] = set()  # user_ids которым уже отправили сегодня

    while True:
        try:
            now_utc = datetime.now(timezone.utc)
            tz = pytz.timezone(DANANG_TZ)
            local_now = now_utc.astimezone(tz)

            # Сбрасываем отметки в полночь
            if local_now.hour == 0 and local_now.minute == 0:
                sent_today.clear()

            # Отправляем в 21:00 по Дананге
            if local_now.hour == REMINDER_HOUR and local_now.minute == 0:
                await _send_reminders(bot, sent_today)

        except Exception as e:
            logger.error(f"Ошибка в цикле напоминаний: {e}")

        await asyncio.sleep(60)


async def _send_reminders(bot: Bot, sent_today: set[int]) -> None:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(NotificationSetting)
            .options(selectinload(NotificationSetting.user))
            .where(NotificationSetting.enabled == True)
        )
        settings = result.scalars().all()

        for setting in settings:
            if setting.user_id in sent_today:
                continue
            try:
                await bot.send_message(
                    setting.user.telegram_id,
                    "🌙 <b>Не забудь внести траты за сегодня!</b>\n\n"
                    "Открой поездку и нажми ➕ Добавить трату.\n"
                    "Это займёт 10 секунд 😊",
                    parse_mode="HTML",
                )
                sent_today.add(setting.user_id)
                logger.info(f"Напоминание отправлено пользователю {setting.user_id}")
            except Exception as e:
                logger.warning(f"Не удалось отправить напоминание {setting.user_id}: {e}")
