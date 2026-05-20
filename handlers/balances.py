from aiogram import Router, F
from aiogram.filters import Command
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

CATEGORY_RU = {
    "food": "Еда", "transport": "Транспорт", "housing": "Жильё",
    "entertainment": "Развлечения", "shopping": "Покупки", "other": "Другое",
}


@router.callback_query(F.data.startswith("balances:"))
async def show_balances(callback: CallbackQuery, session: AsyncSession, current_user: User, **kwargs):
    trip_id = int(callback.data.split(":")[1])
    trip = await get_trip_by_id(session, trip_id)
    if not trip:
        await callback.answer("Поездка не найдена.", show_alert=True)
        return
    members_objs = await get_active_trip_members(session, trip_id)
    user_map = {m.user.id: m.user for m in members_objs}
    balances = await calculate_balances(session, trip_id)
    transfers = simplify_debts(balances)
    if not transfers:
        text = f"⚖️ <b>Долги — {trip.name}</b>\n\n✅ Все расчёты завершены!"
    else:
        lines = []
        for debtor_id, creditor_id, amount in transfers:
            debtor = user_map.get(debtor_id)
            creditor = user_map.get(creditor_id)
            if debtor and creditor:
                lines.append(f"💸 <b>{debtor.display_name}</b> → <b>{creditor.display_name}</b>: {fmt_amount(amount, trip.base_currency)}")
        text = f"⚖️ <b>Долги — {trip.name}</b>\n\n" + "\n".join(lines)
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=trip_menu_keyboard(trip_id, is_owner=trip.owner_id == current_user.id))
    await callback.answer()


@router.callback_query(F.data.startswith("today:"))
async def show_today(callback: CallbackQuery, session: AsyncSession, current_user: User, **kwargs):
    trip_id = int(callback.data.split(":")[1])
    trip = await get_trip_by_id(session, trip_id)
    if not trip:
        await callback.answer("Поездка не найдена.", show_alert=True)
        return
    expenses = await get_today_expenses(session, trip_id)
    if not expenses:
        text = f"📅 <b>Сегодня — {trip.name}</b>\n\nТрат ещё не было!"
    else:
        total = sum(e.amount_in_base for e in expenses)
        category_totals = await get_category_totals(session, trip_id, today_only=True)
        members_objs = await get_active_trip_members(session, trip_id)
        user_map = {m.user.id: m.user for m in members_objs}
        paid_map: dict[int, float] = {}
        for e in expenses:
            paid_map[e.payer_id] = paid_map.get(e.payer_id, 0.0) + e.amount_in_base
        top_payer_id = max(paid_map, key=lambda x: paid_map[x])
        top_payer = user_map.get(top_payer_id)
        cat_lines = "\n".join(
            f"  {CATEGORY_EMOJI.get(cat, '📦')} {CATEGORY_RU.get(cat, cat)}: {fmt_amount(amt, trip.base_currency)}"
            for cat, amt in sorted(category_totals.items(), key=lambda x: -x[1])
        )
        exp_lines = [f"• {e.description} — {fmt_amount(e.amount, e.currency)} ({e.payer.display_name})" for e in expenses[:10]]
        text = (
            f"📅 <b>Сегодня — {trip.name}</b>\n\n"
            f"💰 Итого: <b>{fmt_amount(total, trip.base_currency)}</b>\n\n"
            f"🗂️ По категориям:\n{cat_lines}\n\n"
            f"🏆 Больше всех потратил: <b>{top_payer.display_name if top_payer else '?'}</b>\n\n"
            f"📝 Траты:\n" + "\n".join(exp_lines)
        )
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=trip_menu_keyboard(trip_id, is_owner=trip.owner_id == current_user.id))
    await callback.answer()


@router.callback_query(F.data.startswith("summary:"))
async def show_summary(callback: CallbackQuery, session: AsyncSession, current_user: User, **kwargs):
    trip_id = int(callback.data.split(":")[1])
    trip = await get_trip_by_id(session, trip_id)
    if not trip:
        await callback.answer("Поездка не найдена.", show_alert=True)
        return
    expenses = await get_trip_expenses(session, trip_id)
    if not expenses:
        text = f"📊 <b>Итоги — {trip.name}</b>\n\nТрат пока нет."
    else:
        total = sum(e.amount_in_base for e in expenses)
        category_totals = await get_category_totals(session, trip_id)
        user_totals = await get_user_totals(session, trip_id)
        members_objs = await get_active_trip_members(session, trip_id)
        user_map = {m.user.id: m.user for m in members_objs}
        balances = await calculate_balances(session, trip_id)
        transfers = simplify_debts(balances)
        cat_lines = "\n".join(
            f"  {CATEGORY_EMOJI.get(cat, '📦')} {CATEGORY_RU.get(cat, cat)}: {fmt_amount(amt, trip.base_currency)}"
            for cat, amt in sorted(category_totals.items(), key=lambda x: -x[1])
        )
        user_lines = "\n".join(
            f"  👤 {user_map[uid].display_name}: {fmt_amount(amt, trip.base_currency)}"
            for uid, amt in sorted(user_totals.items(), key=lambda x: -x[1])
            if uid in user_map
        )
        bal_lines = "\n".join(
            f"  💸 {user_map.get(d, '?').display_name if user_map.get(d) else d} → {user_map.get(c, '?').display_name if user_map.get(c) else c}: {fmt_amount(a, trip.base_currency)}"
            for d, c, a in transfers
        ) if transfers else "  ✅ Все расчёты завершены!"
        text = (
            f"📊 <b>Итоги — {trip.name}</b>\n\n"
            f"💰 <b>Всего потрачено: {fmt_amount(total, trip.base_currency)}</b>\n"
            f"📝 Трат: {len(expenses)} | Участников: {len(members_objs)}\n\n"
            f"🗂️ <b>По категориям:</b>\n{cat_lines}\n\n"
            f"👤 <b>По людям:</b>\n{user_lines}\n\n"
            f"⚖️ <b>Кто кому должен:</b>\n{bal_lines}"
        )
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=trip_menu_keyboard(trip_id, is_owner=trip.owner_id == current_user.id))
    await callback.answer()
