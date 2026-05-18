from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from models.user import User
from models.expense import CATEGORY_EMOJI
from services import (
    get_trip_by_id, get_active_trip_members, calculate_balances,
    simplify_debts, get_today_expenses, get_category_totals,
    get_user_totals, get_user_trips, get_trip_expenses,
)
from keyboards.trips import trip_menu_keyboard
from keyboards.main import main_menu_keyboard
from utils.formatting import fmt_amount

router = Router()


# ─── Balances ─────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("balances:"))
async def show_balances(
    callback: CallbackQuery, session: AsyncSession, current_user: User
):
    trip_id = int(callback.data.split(":")[1])
    trip = await get_trip_by_id(session, trip_id)
    if not trip:
        await callback.answer("Trip not found.", show_alert=True)
        return

    members_objs = await get_active_trip_members(session, trip_id)
    user_map = {m.user.id: m.user for m in members_objs}
    balances = await calculate_balances(session, trip_id)
    transfers = simplify_debts(balances)

    if not transfers:
        text = f"⚖️ <b>Balances — {trip.name}</b>\n\n✅ Everyone is settled up!"
    else:
        lines = []
        for debtor_id, creditor_id, amount in transfers:
            debtor = user_map.get(debtor_id)
            creditor = user_map.get(creditor_id)
            if debtor and creditor:
                lines.append(
                    f"💸 <b>{debtor.display_name}</b> owes "
                    f"<b>{creditor.display_name}</b> "
                    f"{fmt_amount(amount, trip.base_currency)}"
                )
        text = f"⚖️ <b>Balances — {trip.name}</b>\n\n" + "\n".join(lines)

    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=trip_menu_keyboard(trip_id, is_owner=trip.owner_id == current_user.id),
    )
    await callback.answer()


# ─── Today ────────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("today:"))
@router.message(Command("today"))
async def show_today(event, session: AsyncSession, current_user: User):
    is_callback = isinstance(event, CallbackQuery)

    if is_callback:
        trip_id = int(event.data.split(":")[1])
    else:
        # /today command — pick first active trip
        trips = await get_user_trips(session, current_user)
        if not trips:
            await event.answer("You have no active trips.")
            return
        trip_id = trips[0].id

    trip = await get_trip_by_id(session, trip_id)
    if not trip:
        if is_callback:
            await event.answer("Trip not found.", show_alert=True)
        return

    expenses = await get_today_expenses(session, trip_id)
    category_totals = await get_category_totals(session, trip_id, today_only=True)

    if not expenses:
        text = f"📅 <b>Today — {trip.name}</b>\n\nNo expenses yet today!"
    else:
        total = sum(e.amount_in_base for e in expenses)
        # Who spent most (by amount paid)
        paid_map: dict[int, float] = {}
        for e in expenses:
            paid_map[e.payer_id] = paid_map.get(e.payer_id, 0.0) + e.amount_in_base
        members_objs = await get_active_trip_members(session, trip_id)
        user_map = {m.user.id: m.user for m in members_objs}

        top_payer_id = max(paid_map, key=lambda x: paid_map[x])
        top_payer = user_map.get(top_payer_id)

        cat_lines = "\n".join(
            f"  {CATEGORY_EMOJI.get(cat, '📦')} {cat.title()}: {fmt_amount(amt, trip.base_currency)}"
            for cat, amt in sorted(category_totals.items(), key=lambda x: -x[1])
        )

        exp_lines = []
        for e in expenses[:10]:
            exp_lines.append(
                f"• {e.description} — {fmt_amount(e.amount, e.currency)} (paid by {e.payer.display_name})"
            )

        text = (
            f"📅 <b>Today — {trip.name}</b>\n\n"
            f"💰 Total: <b>{fmt_amount(total, trip.base_currency)}</b>\n\n"
            f"🗂️ By category:\n{cat_lines}\n\n"
            f"🏆 Top spender: <b>{top_payer.display_name if top_payer else '?'}</b> "
            f"({fmt_amount(paid_map[top_payer_id], trip.base_currency)})\n\n"
            f"📝 Expenses:\n" + "\n".join(exp_lines)
        )

    kb = trip_menu_keyboard(trip_id, is_owner=trip.owner_id == current_user.id)
    if is_callback:
        await event.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
        await event.answer()
    else:
        await event.answer(text, parse_mode="HTML", reply_markup=kb)


# ─── Summary ──────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("summary:"))
@router.message(Command("summary"))
async def show_summary(event, session: AsyncSession, current_user: User):
    is_callback = isinstance(event, CallbackQuery)

    if is_callback:
        trip_id = int(event.data.split(":")[1])
    else:
        trips = await get_user_trips(session, current_user)
        if not trips:
            await event.answer("You have no active trips.")
            return
        trip_id = trips[0].id

    trip = await get_trip_by_id(session, trip_id)
    if not trip:
        if is_callback:
            await event.answer("Trip not found.", show_alert=True)
        return

    expenses = await get_trip_expenses(session, trip_id)
    if not expenses:
        text = f"📊 <b>Summary — {trip.name}</b>\n\nNo expenses yet."
    else:
        total = sum(e.amount_in_base for e in expenses)
        category_totals = await get_category_totals(session, trip_id)
        user_totals = await get_user_totals(session, trip_id)
        members_objs = await get_active_trip_members(session, trip_id)
        user_map = {m.user.id: m.user for m in members_objs}
        balances = await calculate_balances(session, trip_id)
        transfers = simplify_debts(balances)

        cat_lines = "\n".join(
            f"  {CATEGORY_EMOJI.get(cat, '📦')} {cat.title()}: {fmt_amount(amt, trip.base_currency)}"
            for cat, amt in sorted(category_totals.items(), key=lambda x: -x[1])
        )
        user_lines = "\n".join(
            f"  👤 {user_map[uid].display_name}: {fmt_amount(amt, trip.base_currency)}"
            for uid, amt in sorted(user_totals.items(), key=lambda x: -x[1])
            if uid in user_map
        )
        if transfers:
            bal_lines = "\n".join(
                f"  💸 {user_map.get(d, '?').display_name if user_map.get(d) else d} → "
                f"{user_map.get(c, '?').display_name if user_map.get(c) else c}: "
                f"{fmt_amount(a, trip.base_currency)}"
                for d, c, a in transfers
            )
        else:
            bal_lines = "  ✅ Everyone is settled up!"

        text = (
            f"📊 <b>Trip Summary — {trip.name}</b>\n\n"
            f"💰 <b>Total spent: {fmt_amount(total, trip.base_currency)}</b>\n"
            f"📝 Expenses: {len(expenses)}\n"
            f"👥 Members: {len(members_objs)}\n\n"
            f"🗂️ <b>By category:</b>\n{cat_lines}\n\n"
            f"👤 <b>Per person:</b>\n{user_lines}\n\n"
            f"⚖️ <b>Final balances:</b>\n{bal_lines}"
        )

    kb = trip_menu_keyboard(trip_id, is_owner=trip.owner_id == current_user.id)
    if is_callback:
        await event.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
        await event.answer()
    else:
        await event.answer(text, parse_mode="HTML", reply_markup=kb)
