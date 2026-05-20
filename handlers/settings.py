from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from sqlalchemy.ext.asyncio import AsyncSession

from models.user import User
from services import get_trip_by_id, export_trip_csv, get_notification_setting, update_notification_setting
from keyboards.main import main_menu_keyboard, cancel_keyboard
from keyboards.expenses import notification_keyboard
from utils.states import NotificationStates
import pytz

router = Router()


@router.callback_query(F.data.startswith("export:"))
async def export_csv(callback: CallbackQuery, session: AsyncSession, current_user: User, bot: Bot, **kwargs):
    trip_id = int(callback.data.split(":")[1])
    trip = await get_trip_by_id(session, trip_id)
    if not trip:
        await callback.answer("Поездка не найдена.", show_alert=True)
        return
    await callback.answer("⏳ Генерирую CSV...")
    csv_bytes = await export_trip_csv(session, trip)
    filename = f"{trip.name.replace(' ', '_')}_расходы.csv"
    await bot.send_document(
        callback.from_user.id,
        BufferedInputFile(csv_bytes, filename=filename),
        caption=f"📤 <b>{trip.name}</b> — экспорт расходов",
        parse_mode="HTML",
    )


@router.message(F.text == "⚙️ Настройки")
@router.message(Command("settings"))
@router.message(Command("настройки"))
async def show_settings(message: Message, session: AsyncSession, current_user: User, **kwargs):
    setting = await get_notification_setting(session, current_user.id)
    enabled = setting.enabled if setting else False
    tz = setting.timezone if setting else "UTC"
    await message.answer(
        f"⚙️ <b>Настройки</b>\n\n"
        f"🔔 Ежедневное напоминание: {'<b>ВКЛ</b>' if enabled else 'ВЫКЛ'}\n"
        f"🕙 Время: 21:00 {tz}\n\n"
        f"Чтобы сменить часовой пояс: /часовой_пояс",
        parse_mode="HTML",
        reply_markup=notification_keyboard(enabled),
    )


@router.callback_query(F.data == "notif:enable")
async def enable_notif(callback: CallbackQuery, session: AsyncSession, current_user: User, **kwargs):
    setting = await get_notification_setting(session, current_user.id)
    tz = setting.timezone if setting else "UTC"
    await update_notification_setting(session, current_user.id, enabled=True, timezone_str=tz)
    await callback.message.edit_text("🔔 <b>Напоминания включены!</b>", parse_mode="HTML", reply_markup=notification_keyboard(True))
    await callback.answer("Включено!")


@router.callback_query(F.data == "notif:disable")
async def disable_notif(callback: CallbackQuery, session: AsyncSession, current_user: User, **kwargs):
    await update_notification_setting(session, current_user.id, enabled=False)
    await callback.message.edit_text("🔕 <b>Напоминания выключены.</b>", parse_mode="HTML", reply_markup=notification_keyboard(False))
    await callback.answer("Выключено.")


@router.message(Command("timezone"))
@router.message(Command("часовой_пояс"))
async def start_set_timezone(message: Message, state: FSMContext, **kwargs):
    await state.set_state(NotificationStates.timezone)
    await message.answer(
        "🌍 Введи часовой пояс (например: <code>Europe/Moscow</code>, <code>Asia/Bangkok</code>):",
        parse_mode="HTML", reply_markup=cancel_keyboard(),
    )


@router.message(NotificationStates.timezone)
async def save_timezone(message: Message, state: FSMContext, session: AsyncSession, current_user: User, **kwargs):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено.", reply_markup=main_menu_keyboard())
        return
    tz_str = (message.text or "").strip()
    try:
        pytz.timezone(tz_str)
    except pytz.exceptions.UnknownTimeZoneError:
        await message.answer(f"❌ Неизвестный часовой пояс: <code>{tz_str}</code>", parse_mode="HTML")
        return
    setting = await get_notification_setting(session, current_user.id)
    enabled = setting.enabled if setting else False
    await update_notification_setting(session, current_user.id, enabled=enabled, timezone_str=tz_str)
    await state.clear()
    await message.answer(f"✅ Часовой пояс установлен: <b>{tz_str}</b>", parse_mode="HTML", reply_markup=main_menu_keyboard())
