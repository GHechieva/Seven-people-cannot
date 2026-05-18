from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from models.user import User
from services import (
    get_user_trips, get_trip_by_id, get_active_trip_members,
    add_expense, get_trip_expenses, get_expense_by_id,
    delete_expense, update_expense_description,
)
from keyboards.main import main_menu_keyboard, cancel_keyboard
from keyboards.trips import trips_list_keyboard, trip_menu_keyboard, expense_page_keyboard, expense_detail_keyboard
from keyboards.expenses import (
    currency_keyboard, payer_keyboard, category_keyboard,
    participants_keyboard, split_type_keyboard,
)
from utils.states import ExpenseStates, EditExpenseStates
from utils.formatting import fmt_amount, fmt_expense_line

router = Router()
PAGE_SIZE = 5


# ─── Start Add Expense ───────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("add_expense:"))
async def start_add_expense(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession, current_user: User
):
    trip_id = int(callback.data.split(":")[1])
    trip = await get_trip_by_id(session, trip_id)
    if not trip:
        await callback.answer("Trip not found.", show_alert=True)
        return
    await state.update_data(trip_id=trip_id)
    await state.set_state(ExpenseStates.description)
    await callback.message.answer(
        f"➕ <b>Add Expense — {trip.name}</b>\n\nEnter a description (e.g. <i>Lunch at market</i>):",
        parse_mode="HTML",
        reply_markup=cancel_keyboard(),
    )
    await callback.answer()


@router.message(ExpenseStates.description)
async def expense_description(message: Message, state: FSMContext):
    if message.text == "❌ Cancel":
        await state.clear()
        await message.answer("Cancelled.", reply_markup=main_menu_keyboard())
        return
    if not message.text or len(message.text.strip()) < 1:
        await message.answer("Please enter a description.")
        return
    await state.update_data(description=message.text.strip())
    await state.set_state(ExpenseStates.amount)
    await message.answer("💰 Enter the amount (numbers only, e.g. <b>24.50</b>):", parse_mode="HTML")


@router.message(ExpenseStates.amount)
async def expense_amount(message: Message, state: FSMContext):
    if message.text == "❌ Cancel":
        await state.clear()
        await message.answer("Cancelled.", reply_markup=main_menu_keyboard())
        return
    try:
        amount = float(message.text.replace(",", "."))
        if amount <= 0:
            raise ValueError
    except (ValueError, AttributeError):
        await message.answer("❌ Invalid amount. Enter a positive number like <b>24.50</b>:", parse_mode="HTML")
        return
    await state.update_data(amount=amount)
    await state.set_state(ExpenseStates.currency)
    await message.answer("💱 Choose currency:", reply_markup=currency_keyboard())


@router.callback_query(ExpenseStates.currency, F.data.startswith("currency:"))
async def expense_currency(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession, current_user: User
):
    currency = callback.data.split(":")[1]
    await state.update_data(currency=currency)
    data = await state.get_data()
    trip = await get_trip_by_id(session, data["trip_id"])
    members_objs = await get_active_trip_members(session, trip.id)
    members = [m.user for m in members_objs]
    await state.update_data(members=[{"id": u.id, "name": u.full_name, "username": u.username} for u in members])
    await state.set_state(ExpenseStates.payer)
    await callback.message.edit_text(
        "👤 Who paid?",
        reply_markup=payer_keyboard(members, current_user.id),
    )
    await callback.answer()


@router.callback_query(ExpenseStates.payer, F.data.startswith("payer:"))
async def expense_payer(callback: CallbackQuery, state: FSMContext):
    payer_id = int(callback.data.split(":")[1])
    await state.update_data(payer_id=payer_id)
    await state.set_state(ExpenseStates.category)
    await callback.message.edit_text("🗂️ Choose category:", reply_markup=category_keyboard())
    await callback.answer()


@router.callback_query(ExpenseStates.category, F.data.startswith("category:"))
async def expense_category(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    category = callback.data.split(":")[1]
    await state.update_data(category=category, selected_participants=set())
    data = await state.get_data()
    trip = await get_trip_by_id(session, data["trip_id"])
    members_objs = await get_active_trip_members(session, trip.id)
    members = [m.user for m in members_objs]
    all_ids = {u.id for u in members}
    await state.update_data(selected_participants=list(all_ids))  # default: all selected
    await state.set_state(ExpenseStates.participants)
    await callback.message.edit_text(
        "👥 Choose participants (tap to toggle, all selected by default):",
        reply_markup=participants_keyboard(members, all_ids),
    )
    await callback.answer()


@router.callback_query(ExpenseStates.participants, F.data.startswith("participant:"))
async def toggle_participant(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    uid = int(callback.data.split(":")[1])
    data = await state.get_data()
    selected = set(data.get("selected_participants", []))
    if uid in selected:
        selected.discard(uid)
    else:
        selected.add(uid)
    await state.update_data(selected_participants=list(selected))
    trip = await get_trip_by_id(session, data["trip_id"])
    members_objs = await get_active_trip_members(session, trip.id)
    members = [m.user for m in members_objs]
    await callback.message.edit_reply_markup(
        reply_markup=participants_keyboard(members, selected)
    )
    await callback.answer()


@router.callback_query(ExpenseStates.participants, F.data == "participants_done")
async def participants_done(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    if not data.get("selected_participants"):
        await callback.answer("Select at least one participant!", show_alert=True)
        return
    await state.set_state(ExpenseStates.split_type)
    await callback.message.edit_text("⚖️ How to split?", reply_markup=split_type_keyboard())
    await callback.answer()


@router.callback_query(ExpenseStates.split_type, F.data.startswith("split:"))
async def expense_split(callback: CallbackQuery, state: FSMContext):
    split = callback.data.split(":")[1]
    await state.update_data(split_type=split)
    if split == "equal":
        await _confirm_expense(callback, state)
    else:
        data = await state.get_data()
        await state.set_state(ExpenseStates.custom_percentages)
        participant_ids = data.get("selected_participants", [])
        members_data = data.get("members", [])
        names = {m["id"]: m.get("username") or m["name"] for m in members_data}
        lines = "\n".join(f"• {names.get(uid, uid)}" for uid in participant_ids)
        await callback.message.edit_text(
            f"📐 Enter custom percentages.\n\n"
            f"Participants:\n{lines}\n\n"
            f"Send as: <code>user_id:percent user_id:percent</code>\n"
            f"Example: <code>{participant_ids[0]}:60 {participant_ids[1] if len(participant_ids) > 1 else participant_ids[0]}:40</code>\n"
            f"Must sum to 100.",
            parse_mode="HTML",
        )
    await callback.answer()


@router.message(ExpenseStates.custom_percentages)
async def custom_percentages(message: Message, state: FSMContext):
    if message.text == "❌ Cancel":
        await state.clear()
        await message.answer("Cancelled.", reply_markup=main_menu_keyboard())
        return
    try:
        parts = message.text.strip().split()
        percentages = {}
        for p in parts:
            uid_s, pct_s = p.split(":")
            percentages[int(uid_s)] = float(pct_s)
        total = sum(percentages.values())
        if abs(total - 100.0) > 0.5:
            raise ValueError(f"Sum is {total}, must be 100")
    except Exception as e:
        await message.answer(f"❌ Invalid format: {e}\nTry again (e.g. <code>1:60 2:40</code>):", parse_mode="HTML")
        return
    await state.update_data(custom_percentages=percentages)
    await _confirm_expense_msg(message, state)


async def _confirm_expense(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    members_data = data.get("members", [])
    names = {m["id"]: m.get("username") or m["name"] for m in members_data}
    payer_name = names.get(data["payer_id"], "?")
    participants = [names.get(i, str(i)) for i in data.get("selected_participants", [])]
    text = (
        f"✅ <b>Confirm Expense</b>\n\n"
        f"📝 {data['description']}\n"
        f"💰 {fmt_amount(data['amount'], data['currency'])}\n"
        f"👤 Paid by: {payer_name}\n"
        f"🗂️ {data['category'].title()}\n"
        f"👥 Split among: {', '.join(participants)}\n"
        f"⚖️ Split: {data['split_type']}"
    )
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Save", callback_data="confirm_expense")
    builder.button(text="❌ Cancel", callback_data="cancel_expense")
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=builder.as_markup())
    await state.set_state(ExpenseStates.confirm)


async def _confirm_expense_msg(message: Message, state: FSMContext):
    data = await state.get_data()
    members_data = data.get("members", [])
    names = {m["id"]: m.get("username") or m["name"] for m in members_data}
    payer_name = names.get(data["payer_id"], "?")
    participants = [names.get(i, str(i)) for i in data.get("selected_participants", [])]
    text = (
        f"✅ <b>Confirm Expense</b>\n\n"
        f"📝 {data['description']}\n"
        f"💰 {fmt_amount(data['amount'], data['currency'])}\n"
        f"👤 Paid by: {payer_name}\n"
        f"🗂️ {data['category'].title()}\n"
        f"👥 Split among: {', '.join(participants)}\n"
        f"⚖️ Split: {data['split_type']}"
    )
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Save", callback_data="confirm_expense")
    builder.button(text="❌ Cancel", callback_data="cancel_expense")
    await message.answer(text, parse_mode="HTML", reply_markup=builder.as_markup())
    await state.set_state(ExpenseStates.confirm)


@router.callback_query(ExpenseStates.confirm, F.data == "cancel_expense")
async def cancel_expense(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ Cancelled.")
    await callback.answer()


@router.callback_query(ExpenseStates.confirm, F.data == "confirm_expense")
async def save_expense(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession, current_user: User
):
    data = await state.get_data()
    trip = await get_trip_by_id(session, data["trip_id"])
    members_objs = await get_active_trip_members(session, trip.id)
    all_members = {m.user.id: m.user for m in members_objs}

    payer = all_members.get(data["payer_id"])
    participants = [all_members[uid] for uid in data["selected_participants"] if uid in all_members]

    custom_pct = data.get("custom_percentages")
    if custom_pct:
        custom_pct = {int(k): v for k, v in custom_pct.items()}

    expense = await add_expense(
        session=session,
        trip=trip,
        payer=payer,
        description=data["description"],
        amount=data["amount"],
        currency=data["currency"],
        category=data["category"],
        participants=participants,
        split_type=data["split_type"],
        custom_percentages=custom_pct,
    )
    await state.clear()
    await callback.message.edit_text(
        f"✅ <b>Expense saved!</b>\n\n{fmt_expense_line(expense)}",
        parse_mode="HTML",
        reply_markup=trip_menu_keyboard(trip.id, is_owner=trip.owner_id == current_user.id),
    )
    await callback.answer("Saved!")


# ─── List Expenses ────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("list_expenses:"))
async def list_expenses(
    callback: CallbackQuery, session: AsyncSession, current_user: User
):
    trip_id = int(callback.data.split(":")[1])
    await _show_expense_page(callback, session, trip_id, 0, current_user)
    await callback.answer()


@router.callback_query(F.data.startswith("exp_page:"))
async def expense_page(callback: CallbackQuery, session: AsyncSession, current_user: User):
    _, trip_id_s, page_s = callback.data.split(":")
    await _show_expense_page(callback, session, int(trip_id_s), int(page_s), current_user)
    await callback.answer()


async def _show_expense_page(callback, session, trip_id, page, current_user):
    expenses = await get_trip_expenses(session, trip_id)
    if not expenses:
        await callback.message.edit_text(
            "📋 No expenses yet!",
            reply_markup=trip_menu_keyboard(trip_id),
        )
        return
    total_pages = max(1, (len(expenses) + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(0, min(page, total_pages - 1))
    chunk = expenses[page * PAGE_SIZE: (page + 1) * PAGE_SIZE]
    lines = [fmt_expense_line(e) for e in chunk]
    text = f"📋 <b>Expenses (page {page + 1}/{total_pages})</b>\n\n" + "\n\n".join(lines)
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=expense_page_keyboard(trip_id, page, total_pages),
    )


# ─── Delete / Edit Expense ────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("delete_exp:"))
async def delete_expense_cb(
    callback: CallbackQuery, session: AsyncSession, current_user: User
):
    expense_id = int(callback.data.split(":")[1])
    expense = await get_expense_by_id(session, expense_id)
    if not expense:
        await callback.answer("Expense not found.", show_alert=True)
        return
    if expense.payer_id != current_user.id:
        await callback.answer("You can only delete your own expenses.", show_alert=True)
        return
    await delete_expense(session, expense)
    await callback.answer("🗑️ Deleted.", show_alert=True)
    await callback.message.edit_text("🗑️ Expense deleted.")


@router.callback_query(F.data.startswith("edit_exp:"))
async def start_edit_expense(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession, current_user: User
):
    expense_id = int(callback.data.split(":")[1])
    expense = await get_expense_by_id(session, expense_id)
    if not expense or expense.payer_id != current_user.id:
        await callback.answer("Not authorized.", show_alert=True)
        return
    await state.update_data(expense_id=expense_id)
    await state.set_state(EditExpenseStates.new_description)
    await callback.message.answer(
        f"✏️ Current description: <b>{expense.description}</b>\n\nEnter new description:",
        parse_mode="HTML",
        reply_markup=cancel_keyboard(),
    )
    await callback.answer()


@router.message(EditExpenseStates.new_description)
async def save_edit_expense(
    message: Message, state: FSMContext, session: AsyncSession
):
    if message.text == "❌ Cancel":
        await state.clear()
        await message.answer("Cancelled.", reply_markup=main_menu_keyboard())
        return
    data = await state.get_data()
    expense = await get_expense_by_id(session, data["expense_id"])
    if not expense:
        await message.answer("Expense not found.")
        await state.clear()
        return
    await update_expense_description(session, expense, message.text.strip())
    await state.clear()
    await message.answer(
        f"✅ Description updated to: <b>{expense.description}</b>",
        parse_mode="HTML",
        reply_markup=main_menu_keyboard(),
    )
