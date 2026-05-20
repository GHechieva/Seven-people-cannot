from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession
from aiogram.utils.keyboard import InlineKeyboardBuilder

from models.user import User
from services import (
    get_trip_by_id, get_active_trip_members,
    add_expense, get_trip_expenses, get_expense_by_id,
    delete_expense, update_expense_description,
)
from keyboards.main import main_menu_keyboard, cancel_keyboard
from keyboards.trips import trip_menu_keyboard, expense_page_keyboard
from keyboards.expenses import currency_keyboard, payer_keyboard, category_keyboard, participants_keyboard
from utils.states import ExpenseStates, EditExpenseStates
from utils.formatting import fmt_amount, fmt_expense_line

router = Router()
PAGE_SIZE = 5

CATEGORY_RU = {
    "food": "Еда", "transport": "Транспорт", "housing": "Жильё",
    "entertainment": "Развлечения", "shopping": "Покупки", "other": "Другое",
}


@router.callback_query(F.data.startswith("add_expense:"))
async def start_add_expense(callback: CallbackQuery, state: FSMContext, session: AsyncSession, current_user: User, **kwargs):
    trip_id = int(callback.data.split(":")[1])
    trip = await get_trip_by_id(session, trip_id)
    if not trip:
        await callback.answer("Поездка не найдена.", show_alert=True)
        return
    await state.update_data(trip_id=trip_id)
    await state.set_state(ExpenseStates.description)
    await callback.message.answer(
        f"➕ <b>Новая трата</b>\n\n"
        f"Напиши одним сообщением:\n"
        f"<b>Описание сумма</b>\n\n"
        f"Примеры:\n"
        f"• <code>Обед 1500</code>\n"
        f"• <code>Такси 350</code>\n"
        f"• <code>Пиво 200</code>",
        parse_mode="HTML",
        reply_markup=cancel_keyboard(),
    )
    await callback.answer()


@router.message(ExpenseStates.description)
async def expense_quick_input(message: Message, state: FSMContext, session: AsyncSession, current_user: User, **kwargs):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено.", reply_markup=main_menu_keyboard())
        return

    text = message.text.strip()
    # Попытка распарсить "Описание сумма" из одного сообщения
    parts = text.rsplit(" ", 1)
    if len(parts) == 2:
        try:
            amount = float(parts[1].replace(",", "."))
            description = parts[0].strip()
            await state.update_data(description=description, amount=amount)
            # Сразу к валюте
            await state.set_state(ExpenseStates.currency)
            await message.answer(
                f"✅ <b>{description}</b> — {amount:,.0f}\n\n💱 Валюта:",
                parse_mode="HTML",
                reply_markup=currency_keyboard(),
            )
            return
        except ValueError:
            pass

    # Если не распарсилось — просим отдельно
    await state.update_data(description=text)
    await state.set_state(ExpenseStates.amount)
    await message.answer("💰 Введи сумму:")


@router.message(ExpenseStates.amount)
async def expense_amount(message: Message, state: FSMContext, **kwargs):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено.", reply_markup=main_menu_keyboard())
        return
    try:
        amount = float(message.text.replace(",", ".").replace(" ", ""))
        if amount <= 0:
            raise ValueError
    except (ValueError, AttributeError):
        await message.answer("❌ Неверная сумма. Введи число, например <b>1500</b>:", parse_mode="HTML")
        return
    await state.update_data(amount=amount)
    await state.set_state(ExpenseStates.currency)
    await message.answer("💱 Валюта:", reply_markup=currency_keyboard())


@router.callback_query(ExpenseStates.currency, F.data.startswith("currency:"))
async def expense_currency(callback: CallbackQuery, state: FSMContext, session: AsyncSession, current_user: User, **kwargs):
    currency = callback.data.split(":")[1]
    await state.update_data(currency=currency)
    data = await state.get_data()
    members_objs = await get_active_trip_members(session, data["trip_id"])
    members = [m.user for m in members_objs]
    await state.update_data(members=[{"id": u.id, "name": u.full_name, "username": u.username} for u in members])

    # Если только один участник — он и платил, пропускаем выбор
    if len(members) == 1:
        await state.update_data(payer_id=members[0].id)
        await state.set_state(ExpenseStates.category)
        await callback.message.edit_text("🗂️ Категория:", reply_markup=category_keyboard())
    else:
        await state.set_state(ExpenseStates.payer)
        await callback.message.edit_text("👤 Кто платил?", reply_markup=payer_keyboard(members, current_user.id))
    await callback.answer()


@router.callback_query(ExpenseStates.payer, F.data.startswith("payer:"))
async def expense_payer(callback: CallbackQuery, state: FSMContext, **kwargs):
    payer_id = int(callback.data.split(":")[1])
    await state.update_data(payer_id=payer_id)
    await state.set_state(ExpenseStates.category)
    await callback.message.edit_text("🗂️ Категория:", reply_markup=category_keyboard())
    await callback.answer()


@router.callback_query(ExpenseStates.category, F.data.startswith("category:"))
async def expense_category(callback: CallbackQuery, state: FSMContext, session: AsyncSession, current_user: User, **kwargs):
    category = callback.data.split(":")[1]
    await state.update_data(category=category)
    data = await state.get_data()
    members_objs = await get_active_trip_members(session, data["trip_id"])
    members = [m.user for m in members_objs]
    all_ids = {u.id for u in members}

    # Если один участник — сразу сохраняем
    if len(members) == 1:
        await state.update_data(selected_participants=list(all_ids), split_type="equal")
        await _save_expense(callback.message, state, session, current_user, edit=True)
    else:
        await state.update_data(selected_participants=list(all_ids))
        await state.set_state(ExpenseStates.participants)

        # Кнопка "все поровну" — один тап и готово
        builder = InlineKeyboardBuilder()
        builder.button(text="⚡ Все поровну — сохранить!", callback_data="split_equal_save")
        builder.button(text="👥 Выбрать участников", callback_data="choose_participants")
        builder.adjust(1)
        data = await state.get_data()
        desc = data.get("description", "")
        amount = data.get("amount", 0)
        currency = data.get("currency", "")
        await callback.message.edit_text(
            f"✅ <b>{desc}</b> — {amount:,.0f} {currency}\n\nКак делить между {len(members)} участниками?",
            parse_mode="HTML",
            reply_markup=builder.as_markup(),
        )
    await callback.answer()


@router.callback_query(ExpenseStates.participants, F.data == "split_equal_save")
async def split_equal_save(callback: CallbackQuery, state: FSMContext, session: AsyncSession, current_user: User, **kwargs):
    await state.update_data(split_type="equal")
    await _save_expense(callback.message, state, session, current_user, edit=True)
    await callback.answer()


@router.callback_query(ExpenseStates.participants, F.data == "choose_participants")
async def choose_participants(callback: CallbackQuery, state: FSMContext, session: AsyncSession, **kwargs):
    data = await state.get_data()
    members_objs = await get_active_trip_members(session, data["trip_id"])
    members = [m.user for m in members_objs]
    all_ids = {u.id for u in members}
    await callback.message.edit_text(
        "👥 Отметь участников (все выбраны по умолчанию):",
        reply_markup=participants_keyboard(members, all_ids),
    )
    await callback.answer()


@router.callback_query(ExpenseStates.participants, F.data.startswith("participant:"))
async def toggle_participant(callback: CallbackQuery, state: FSMContext, session: AsyncSession, **kwargs):
    uid = int(callback.data.split(":")[1])
    data = await state.get_data()
    selected = set(data.get("selected_participants", []))
    selected = selected.symmetric_difference({uid})
    await state.update_data(selected_participants=list(selected))
    members_objs = await get_active_trip_members(session, data["trip_id"])
    members = [m.user for m in members_objs]
    await callback.message.edit_reply_markup(reply_markup=participants_keyboard(members, selected))
    await callback.answer()


@router.callback_query(ExpenseStates.participants, F.data == "participants_done")
async def participants_done(callback: CallbackQuery, state: FSMContext, session: AsyncSession, current_user: User, **kwargs):
    data = await state.get_data()
    if not data.get("selected_participants"):
        await callback.answer("Выбери хотя бы одного!", show_alert=True)
        return
    await state.update_data(split_type="equal")
    await _save_expense(callback.message, state, session, current_user, edit=True)
    await callback.answer()


async def _save_expense(message, state: FSMContext, session: AsyncSession, current_user: User, edit: bool = False):
    data = await state.get_data()
    trip = await get_trip_by_id(session, data["trip_id"])
    members_objs = await get_active_trip_members(session, trip.id)
    all_members = {m.user.id: m.user for m in members_objs}
    payer = all_members.get(data["payer_id"])
    participants = [all_members[uid] for uid in data.get("selected_participants", []) if uid in all_members]
    if not participants:
        participants = list(all_members.values())

    expense = await add_expense(
        session=session, trip=trip, payer=payer,
        description=data["description"], amount=data["amount"],
        currency=data["currency"], category=data["category"],
        participants=participants, split_type="equal",
    )
    await state.clear()
    text = f"✅ <b>Сохранено!</b>\n\n{fmt_expense_line(expense)}"
    kb = trip_menu_keyboard(trip.id, is_owner=trip.owner_id == current_user.id)
    if edit:
        await message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    else:
        await message.answer(text, parse_mode="HTML", reply_markup=kb)


@router.callback_query(F.data.startswith("list_expenses:"))
async def list_expenses(callback: CallbackQuery, session: AsyncSession, current_user: User, **kwargs):
    trip_id = int(callback.data.split(":")[1])
    await _show_expense_page(callback, session, trip_id, 0)
    await callback.answer()


@router.callback_query(F.data.startswith("exp_page:"))
async def expense_page(callback: CallbackQuery, session: AsyncSession, current_user: User, **kwargs):
    _, trip_id_s, page_s = callback.data.split(":")
    await _show_expense_page(callback, session, int(trip_id_s), int(page_s))
    await callback.answer()


async def _show_expense_page(callback, session, trip_id, page):
    expenses = await get_trip_expenses(session, trip_id)
    if not expenses:
        await callback.message.edit_text("📋 Трат пока нет!", reply_markup=trip_menu_keyboard(trip_id))
        return
    total_pages = max(1, (len(expenses) + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(0, min(page, total_pages - 1))
    chunk = expenses[page * PAGE_SIZE:(page + 1) * PAGE_SIZE]
    text = f"📋 <b>Траты (стр. {page + 1}/{total_pages})</b>\n\n" + "\n\n".join(fmt_expense_line(e) for e in chunk)
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=expense_page_keyboard(trip_id, page, total_pages))


@router.callback_query(F.data.startswith("delete_exp:"))
async def delete_expense_cb(callback: CallbackQuery, session: AsyncSession, current_user: User, **kwargs):
    expense_id = int(callback.data.split(":")[1])
    expense = await get_expense_by_id(session, expense_id)
    if not expense or expense.payer_id != current_user.id:
        await callback.answer("Можно удалять только свои траты.", show_alert=True)
        return
    await delete_expense(session, expense)
    await callback.answer("🗑️ Удалено.", show_alert=True)
    await callback.message.edit_text("🗑️ Трата удалена.")


@router.callback_query(F.data.startswith("edit_exp:"))
async def start_edit_expense(callback: CallbackQuery, state: FSMContext, session: AsyncSession, current_user: User, **kwargs):
    expense_id = int(callback.data.split(":")[1])
    expense = await get_expense_by_id(session, expense_id)
    if not expense or expense.payer_id != current_user.id:
        await callback.answer("Нет доступа.", show_alert=True)
        return
    await state.update_data(expense_id=expense_id)
    await state.set_state(EditExpenseStates.new_description)
    await callback.message.answer(
        f"✏️ Сейчас: <b>{expense.description}</b>\n\nВведи новое описание:",
        parse_mode="HTML", reply_markup=cancel_keyboard(),
    )
    await callback.answer()


@router.message(EditExpenseStates.new_description)
async def save_edit_expense(message: Message, state: FSMContext, session: AsyncSession, **kwargs):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено.", reply_markup=main_menu_keyboard())
        return
    data = await state.get_data()
    expense = await get_expense_by_id(session, data["expense_id"])
    if not expense:
        await message.answer("Трата не найдена.")
        await state.clear()
        return
    await update_expense_description(session, expense, message.text.strip())
    await state.clear()
    await message.answer(f"✅ Обновлено: <b>{expense.description}</b>", parse_mode="HTML", reply_markup=main_menu_keyboard())
