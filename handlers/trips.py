from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from models.user import User
from services import (
    create_trip, get_trip_by_invite_code, get_trip_by_id,
    get_user_trips, join_trip, remove_member,
    close_trip, get_active_trip_members,
)
from keyboards.main import main_menu_keyboard, cancel_keyboard
from keyboards.trips import trips_list_keyboard, trip_menu_keyboard, admin_keyboard
from utils.states import TripCreateStates, TripJoinStates
from utils.formatting import fmt_trip_header
import config

router = Router()


@router.message(F.text == "➕ Новая поездка")
@router.message(Command("newtrip"))
async def start_create_trip(message: Message, state: FSMContext, **kwargs):
    await state.set_state(TripCreateStates.name)
    await message.answer("✈️ <b>Новая поездка</b>\n\nВведи название поездки:", parse_mode="HTML", reply_markup=cancel_keyboard())


@router.message(TripCreateStates.name)
async def trip_name_received(message: Message, state: FSMContext, **kwargs):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено.", reply_markup=main_menu_keyboard())
        return
    if not message.text or len(message.text.strip()) < 2:
        await message.answer("Название должно быть не короче 2 символов. Попробуй ещё раз:")
        return
    await state.update_data(name=message.text.strip())
    await state.set_state(TripCreateStates.description)
    await message.answer("Добавь описание (или напиши <b>пропустить</b>):", parse_mode="HTML")


@router.message(TripCreateStates.description)
async def trip_description_received(message: Message, state: FSMContext, **kwargs):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено.", reply_markup=main_menu_keyboard())
        return
    desc = None if message.text and message.text.lower() in ("пропустить", "skip") else (message.text or "").strip()
    await state.update_data(description=desc)
    await state.set_state(TripCreateStates.currency)
    lines = "\n".join(f"{cur} — {name}" for cur, name in config.CURRENCY_NAMES.items())
    await message.answer(f"Выбери основную валюту поездки (напиши например <b>RUB</b>):\n\n{lines}", parse_mode="HTML")


@router.message(TripCreateStates.currency)
async def trip_currency_received(message: Message, state: FSMContext, session: AsyncSession, current_user: User, **kwargs):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено.", reply_markup=main_menu_keyboard())
        return
    currency = (message.text or "").strip().upper()
    if currency not in config.SUPPORTED_CURRENCIES:
        await message.answer(f"Неизвестная валюта. Введи одну из: {', '.join(config.SUPPORTED_CURRENCIES)}")
        return
    data = await state.get_data()
    trip = await create_trip(session, current_user, data["name"], data.get("description"), currency)
    members = await get_active_trip_members(session, trip.id)
    await state.clear()
    await message.answer(
        f"🎉 <b>Поездка создана!</b>\n\n{fmt_trip_header(trip, len(members))}\n\nПоделись кодом <code>{trip.invite_code}</code> с друзьями!",
        parse_mode="HTML",
        reply_markup=trip_menu_keyboard(trip.id, is_owner=True),
    )


@router.message(F.text == "🔗 Вступить в поездку")
@router.message(Command("join"))
async def start_join_trip(message: Message, state: FSMContext, **kwargs):
    await state.set_state(TripJoinStates.code)
    await message.answer("🔗 Введи код приглашения:", reply_markup=cancel_keyboard())


@router.message(TripJoinStates.code)
async def join_code_received(message: Message, state: FSMContext, session: AsyncSession, current_user: User, **kwargs):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено.", reply_markup=main_menu_keyboard())
        return
    code = (message.text or "").strip().upper()
    trip = await get_trip_by_invite_code(session, code)
    if not trip:
        await message.answer("❌ Поездка не найдена. Проверь код и попробуй снова.")
        return
    success, reason = await join_trip(session, trip, current_user)
    members = await get_active_trip_members(session, trip.id)
    if reason == "already_member":
        await message.answer(f"Ты уже участник поездки <b>{trip.name}</b>!", parse_mode="HTML", reply_markup=trip_menu_keyboard(trip.id))
    else:
        await message.answer(f"✅ Ты вступил в поездку <b>{trip.name}</b>!\n\n{fmt_trip_header(trip, len(members))}", parse_mode="HTML", reply_markup=trip_menu_keyboard(trip.id))
    await state.clear()


@router.message(F.text == "✈️ Мои поездки")
@router.message(Command("trips"))
async def list_trips(message: Message, session: AsyncSession, current_user: User, **kwargs):
    trips = await get_user_trips(session, current_user)
    if not trips:
        await message.answer("У тебя пока нет активных поездок.\nСоздай новую ➕ или вступи по коду 🔗", reply_markup=main_menu_keyboard())
        return
    await message.answer("✈️ <b>Твои поездки:</b>", parse_mode="HTML", reply_markup=trips_list_keyboard(trips))


@router.callback_query(F.data == "back_to_trips")
async def back_to_trips(callback: CallbackQuery, session: AsyncSession, current_user: User, **kwargs):
    trips = await get_user_trips(session, current_user)
    await callback.message.edit_text("✈️ <b>Твои поездки:</b>", parse_mode="HTML", reply_markup=trips_list_keyboard(trips) if trips else None)
    await callback.answer()


@router.callback_query(F.data.startswith("trip:"))
async def show_trip_menu(callback: CallbackQuery, session: AsyncSession, current_user: User, **kwargs):
    trip_id = int(callback.data.split(":")[1])
    trip = await get_trip_by_id(session, trip_id)
    if not trip:
        await callback.answer("Поездка не найдена.", show_alert=True)
        return
    members = await get_active_trip_members(session, trip_id)
    is_owner = trip.owner_id == current_user.id
    await callback.message.edit_text(fmt_trip_header(trip, len(members)), parse_mode="HTML", reply_markup=trip_menu_keyboard(trip.id, is_owner=is_owner))
    await callback.answer()


@router.callback_query(F.data.startswith("invite:"))
async def show_invite_code(callback: CallbackQuery, session: AsyncSession, **kwargs):
    trip_id = int(callback.data.split(":")[1])
    trip = await get_trip_by_id(session, trip_id)
    await callback.answer(f"Код приглашения: {trip.invite_code}", show_alert=True)


@router.callback_query(F.data.startswith("admin:"))
async def show_admin(callback: CallbackQuery, session: AsyncSession, current_user: User, **kwargs):
    trip_id = int(callback.data.split(":")[1])
    trip = await get_trip_by_id(session, trip_id)
    if not trip or trip.owner_id != current_user.id:
        await callback.answer("Только владелец поездки может управлять ею.", show_alert=True)
        return
    members = await get_active_trip_members(session, trip_id)
    non_owner = [m for m in members if m.user_id != current_user.id]
    await callback.message.edit_text(f"👑 <b>Управление — {trip.name}</b>\n\nУчастников: {len(members)}", parse_mode="HTML", reply_markup=admin_keyboard(trip_id, non_owner))
    await callback.answer()


@router.callback_query(F.data.startswith("remove_member:"))
async def do_remove_member(callback: CallbackQuery, session: AsyncSession, current_user: User, **kwargs):
    _, trip_id_s, user_id_s = callback.data.split(":")
    trip_id, target_user_id = int(trip_id_s), int(user_id_s)
    trip = await get_trip_by_id(session, trip_id)
    if not trip or trip.owner_id != current_user.id:
        await callback.answer("Нет доступа.", show_alert=True)
        return
    removed = await remove_member(session, trip, target_user_id)
    await callback.answer("✅ Участник удалён." if removed else "Участник не найден.", show_alert=True)
    members = await get_active_trip_members(session, trip_id)
    non_owner = [m for m in members if m.user_id != current_user.id]
    await callback.message.edit_reply_markup(reply_markup=admin_keyboard(trip_id, non_owner))


@router.callback_query(F.data.startswith("close_trip:"))
async def do_close_trip(callback: CallbackQuery, session: AsyncSession, current_user: User, **kwargs):
    trip_id = int(callback.data.split(":")[1])
    trip = await get_trip_by_id(session, trip_id)
    if not trip or trip.owner_id != current_user.id:
        await callback.answer("Нет доступа.", show_alert=True)
        return
    await close_trip(session, trip)
    await callback.answer("🔒 Поездка закрыта.", show_alert=True)
    await callback.message.edit_text(f"🔒 Поездка <b>{trip.name}</b> закрыта.", parse_mode="HTML")
