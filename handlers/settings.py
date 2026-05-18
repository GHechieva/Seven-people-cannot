from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from sqlalchemy.ext.asyncio import AsyncSession

from models.user import User
from services import (
    get_user_trips, get_trip_by_id, export_trip_csv,
    get_notification_setting, update_notification_setting,
)
from keyboards.main import main_menu_keyboard, cancel_keyboard
from keyboards.expenses import notification_keyboard
from utils.states import NotificationStates
import pytz

router = Router()


# ─── Export CSV ───────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("export:"))
async def export_csv(
    callback: CallbackQuery, session: AsyncSession, current_user: User, bot: Bot
):
    trip_id = int(callback.data.split(":")[1])
    trip = await get_trip_by_id(session, trip_id)
    if not trip:
        await callback.answer("Trip not found.", show_alert=True)
        return
    await callback.answer("⏳ Generating CSV...")
    csv_bytes = await export_trip_csv(session, trip)
    filename = f"{trip.name.replace(' ', '_')}_expenses.csv"
    await bot.send_document(
        callback.from_user.id,
        BufferedInputFile(csv_bytes, filename=filename),
        caption=f"📤 <b>{trip.name}</b> — expense export",
        parse_mode="HTML",
    )


# ─── Settings ────────────────────────────────────────────────────────────────

@router.message(F.text == "⚙️ Settings")
@router.message(Command("settings"))
async def show_settings(message: Message, session: AsyncSession, current_user: User):
    setting = await get_notification_setting(session, current_user.id)
    enabled = setting.enabled if setting else False
    tz = setting.timezone if setting else "UTC"
    await message.answer(
        f"⚙️ <b>Settings</b>\n\n"
        f"🔔 Daily reminder: {'<b>ON</b>' if enabled else 'OFF'}\n"
        f"🕙 Time: 21:00 {tz}\n\n"
        f"Toggle reminders below. To change timezone, use /timezone",
        parse_mode="HTML",
        reply_markup=notification_keyboard(enabled),
    )


@router.callback_query(F.data == "notif:enable")
async def enable_notif(callback: CallbackQuery, session: AsyncSession, current_user: User):
    setting = await get_notification_setting(session, current_user.id)
    tz = setting.timezone if setting else "UTC"
    await update_notification_setting(session, current_user.id, enabled=True, timezone_str=tz)
    await callback.message.edit_text(
        "🔔 <b>Daily reminders enabled!</b>\nYou'll get a reminder at 21:00 your local time.\n\nUse /timezone to set your timezone.",
        parse_mode="HTML",
        reply_markup=notification_keyboard(True),
    )
    await callback.answer("Enabled!")


@router.callback_query(F.data == "notif:disable")
async def disable_notif(callback: CallbackQuery, session: AsyncSession, current_user: User):
    await update_notification_setting(session, current_user.id, enabled=False)
    await callback.message.edit_text(
        "🔕 <b>Daily reminders disabled.</b>",
        parse_mode="HTML",
        reply_markup=notification_keyboard(False),
    )
    await callback.answer("Disabled.")


@router.message(Command("timezone"))
async def start_set_timezone(message: Message, state: FSMContext):
    await state.set_state(NotificationStates.timezone)
    await message.answer(
        "🌍 Enter your timezone (e.g. <code>Europe/Riga</code>, <code>Europe/Berlin</code>, <code>America/New_York</code>):\n\n"
        "Full list: https://en.wikipedia.org/wiki/List_of_tz_database_time_zones",
        parse_mode="HTML",
        reply_markup=cancel_keyboard(),
    )


@router.message(NotificationStates.timezone)
async def save_timezone(message: Message, state: FSMContext, session: AsyncSession, current_user: User):
    if message.text == "❌ Cancel":
        await state.clear()
        await message.answer("Cancelled.", reply_markup=main_menu_keyboard())
        return
    tz_str = (message.text or "").strip()
    try:
        pytz.timezone(tz_str)  # validate
    except pytz.exceptions.UnknownTimeZoneError:
        await message.answer(
            f"❌ Unknown timezone: <code>{tz_str}</code>\n"
            "Try something like <code>Europe/Riga</code> or <code>UTC</code>.",
            parse_mode="HTML",
        )
        return
    setting = await get_notification_setting(session, current_user.id)
    enabled = setting.enabled if setting else False
    await update_notification_setting(session, current_user.id, enabled=enabled, timezone_str=tz_str)
    await state.clear()
    await message.answer(
        f"✅ Timezone set to <b>{tz_str}</b>",
        parse_mode="HTML",
        reply_markup=main_menu_keyboard(),
    )
