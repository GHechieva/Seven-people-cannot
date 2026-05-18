from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from models.user import User
from models.trip import Trip
from services import (
    create_trip, get_trip_by_invite_code, get_trip_by_id,
    get_user_trips, join_trip, is_trip_member, remove_member,
    close_trip, get_active_trip_members,
)
from keyboards.main import main_menu_keyboard, cancel_keyboard
from keyboards.trips import trips_list_keyboard, trip_menu_keyboard, admin_keyboard
from utils.states import TripCreateStates, TripJoinStates
from utils.formatting import fmt_trip_header
import config

router = Router()

# ─── Create Trip ────────────────────────────────────────────────────────────

@router.message(F.text == "➕ New Trip")
@router.message(Command("newtrip"))
async def start_create_trip(message: Message, state: FSMContext):
    await state.set_state(TripCreateStates.name)
    await message.answer(
        "✈️ <b>Create a New Trip</b>\n\nEnter the trip name:",
        parse_mode="HTML",
        reply_markup=cancel_keyboard(),
    )


@router.message(TripCreateStates.name)
async def trip_name_received(message: Message, state: FSMContext):
    if message.text == "❌ Cancel":
        await state.clear()
        await message.answer("Cancelled.", reply_markup=main_menu_keyboard())
        return
    if not message.text or len(message.text.strip()) < 2:
        await message.answer("Name must be at least 2 characters. Try again:")
        return
    await state.update_data(name=message.text.strip())
    await state.set_state(TripCreateStates.description)
    await message.answer("Add a short description (or type <b>skip</b>):", parse_mode="HTML")


@router.message(TripCreateStates.description)
async def trip_description_received(message: Message, state: FSMContext):
    if message.text == "❌ Cancel":
        await state.clear()
        await message.answer("Cancelled.", reply_markup=main_menu_keyboard())
        return
    desc = None if message.text and message.text.lower() == "skip" else (message.text or "").strip()
    await state.update_data(description=desc)
    await state.set_state(TripCreateStates.currency)
    currencies = " / ".join(config.SUPPORTED_CURRENCIES[:10])
    await message.answer(
        f"Choose base currency (e.g. <b>EUR</b>):\n{currencies}",
        parse_mode="HTML",
    )


@router.message(TripCreateStates.currency)
async def trip_currency_received(
    message: Message, state: FSMContext, session: AsyncSession, current_user: User
):
    if message.text == "❌ Cancel":
        await state.clear()
        await message.answer("Cancelled.", reply_markup=main_menu_keyboard())
        return
    currency = (message.text or "").strip().upper()
    if currency not in config.SUPPORTED_CURRENCIES:
        await message.answer(f"Unknown currency. Please use one of: {', '.join(config.SUPPORTED_CURRENCIES[:10])}")
        return
    data = await state.get_data()
    trip = await create_trip(
        session,
        current_user,
        data["name"],
        data.get("description"),
        currency,
    )
    await state.clear()
    await message.answer(
        f"🎉 <b>Trip created!</b>\n\n"
        f"{fmt_trip_header(trip)}\n\n"
        f"Share the invite code <code>{trip.invite_code}</code> with friends!",
        parse_mode="HTML",
        reply_markup=trip_menu_keyboard(trip.id, is_owner=True),
    )


# ─── Join Trip ───────────────────────────────────────────────────────────────

@router.message(F.text == "🔗 Join Trip")
@router.message(Command("join"))
async def start_join_trip(message: Message, state: FSMContext):
    await state.set_state(TripJoinStates.code)
    await message.answer(
        "🔗 Enter the invite code:",
        reply_markup=cancel_keyboard(),
    )


@router.message(TripJoinStates.code)
async def join_code_received(
    message: Message, state: FSMContext, session: AsyncSession, current_user: User
):
    if message.text == "❌ Cancel":
        await state.clear()
        await message.answer("Cancelled.", reply_markup=main_menu_keyboard())
        return
    code = (message.text or "").strip().upper()
    trip = await get_trip_by_invite_code(session, code)
    if not trip:
        await message.answer("❌ Trip not found. Check the code and try again.")
        return
    success, reason = await join_trip(session, trip, current_user)
    if reason == "already_member":
        await message.answer(
            f"You're already a member of <b>{trip.name}</b>!",
            parse_mode="HTML",
            reply_markup=trip_menu_keyboard(trip.id),
        )
    else:
        await message.answer(
            f"✅ Joined <b>{trip.name}</b>!\n\n{fmt_trip_header(trip)}",
            parse_mode="HTML",
            reply_markup=trip_menu_keyboard(trip.id),
        )
    await state.clear()


# ─── List Trips ──────────────────────────────────────────────────────────────

@router.message(F.text == "✈️ My Trips")
@router.message(Command("trips"))
async def list_trips(message: Message, session: AsyncSession, current_user: User):
    trips = await get_user_trips(session, current_user)
    if not trips:
        await message.answer(
            "You have no active trips.\nCreate one with ➕ New Trip or join with 🔗 Join Trip.",
            reply_markup=main_menu_keyboard(),
        )
        return
    await message.answer(
        "✈️ <b>Your Trips:</b>",
        parse_mode="HTML",
        reply_markup=trips_list_keyboard(trips),
    )


@router.callback_query(F.data == "back_to_trips")
async def back_to_trips(callback: CallbackQuery, session: AsyncSession, current_user: User):
    trips = await get_user_trips(session, current_user)
    await callback.message.edit_text(
        "✈️ <b>Your Trips:</b>",
        parse_mode="HTML",
        reply_markup=trips_list_keyboard(trips) if trips else None,
    )
    await callback.answer()


# ─── Trip Menu ───────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("trip:"))
async def show_trip_menu(
    callback: CallbackQuery, session: AsyncSession, current_user: User
):
    trip_id = int(callback.data.split(":")[1])
    trip = await get_trip_by_id(session, trip_id)
    if not trip:
        await callback.answer("Trip not found.", show_alert=True)
        return
    is_owner = trip.owner_id == current_user.id
    await callback.message.edit_text(
        fmt_trip_header(trip),
        parse_mode="HTML",
        reply_markup=trip_menu_keyboard(trip.id, is_owner=is_owner),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("invite:"))
async def show_invite_code(callback: CallbackQuery, session: AsyncSession):
    trip_id = int(callback.data.split(":")[1])
    trip = await get_trip_by_id(session, trip_id)
    await callback.answer(f"Invite code: {trip.invite_code}", show_alert=True)


# ─── Admin Panel ─────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("admin:"))
async def show_admin(
    callback: CallbackQuery, session: AsyncSession, current_user: User
):
    trip_id = int(callback.data.split(":")[1])
    trip = await get_trip_by_id(session, trip_id)
    if not trip or trip.owner_id != current_user.id:
        await callback.answer("Only the trip owner can access admin.", show_alert=True)
        return
    members = await get_active_trip_members(session, trip_id)
    non_owner = [m for m in members if m.user_id != current_user.id]
    await callback.message.edit_text(
        f"👑 <b>Admin Panel — {trip.name}</b>\n\nMembers: {len(members)}",
        parse_mode="HTML",
        reply_markup=admin_keyboard(trip_id, non_owner),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("remove_member:"))
async def do_remove_member(
    callback: CallbackQuery, session: AsyncSession, current_user: User
):
    _, trip_id_s, user_id_s = callback.data.split(":")
    trip_id, target_user_id = int(trip_id_s), int(user_id_s)
    trip = await get_trip_by_id(session, trip_id)
    if not trip or trip.owner_id != current_user.id:
        await callback.answer("Not authorized.", show_alert=True)
        return
    removed = await remove_member(session, trip, target_user_id)
    await callback.answer("✅ Member removed." if removed else "Member not found.", show_alert=True)
    members = await get_active_trip_members(session, trip_id)
    non_owner = [m for m in members if m.user_id != current_user.id]
    await callback.message.edit_reply_markup(
        reply_markup=admin_keyboard(trip_id, non_owner)
    )


@router.callback_query(F.data.startswith("close_trip:"))
async def do_close_trip(
    callback: CallbackQuery, session: AsyncSession, current_user: User
):
    trip_id = int(callback.data.split(":")[1])
    trip = await get_trip_by_id(session, trip_id)
    if not trip or trip.owner_id != current_user.id:
        await callback.answer("Not authorized.", show_alert=True)
        return
    await close_trip(session, trip)
    await callback.answer("🔒 Trip closed.", show_alert=True)
    await callback.message.edit_text(
        f"🔒 Trip <b>{trip.name}</b> has been closed.",
        parse_mode="HTML",
    )
