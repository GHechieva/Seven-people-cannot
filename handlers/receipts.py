import io
from aiogram import Router, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from sqlalchemy.ext.asyncio import AsyncSession

from models.user import User
from services import (
    get_user_trips, get_trip_by_id, get_active_trip_members,
    add_expense, extract_from_receipt,
)
from keyboards.main import main_menu_keyboard, cancel_keyboard
from keyboards.trips import trips_list_keyboard, trip_menu_keyboard
from keyboards.expenses import currency_keyboard, payer_keyboard, category_keyboard, participants_keyboard, split_type_keyboard
from utils.states import ReceiptStates
from utils.formatting import fmt_amount, fmt_expense_line

router = Router()


@router.message(F.photo)
async def handle_receipt_photo(
    message: Message, state: FSMContext, bot: Bot, session: AsyncSession, current_user: User
):
    trips = await get_user_trips(session, current_user)
    if not trips:
        await message.answer("You need to be in a trip first.")
        return

    # Download photo (largest size)
    photo = message.photo[-1]
    file = await bot.get_file(photo.file_id)
    buf = io.BytesIO()
    await bot.download_file(file.file_path, buf)
    photo_bytes = buf.getvalue()

    await message.answer("🔍 Scanning receipt...")
    ocr_result = await extract_from_receipt(photo_bytes)

    amount = ocr_result.get("amount")
    merchant = ocr_result.get("merchant")
    raw_text = ocr_result.get("raw_text", "")

    prefill_msg = "📸 <b>Receipt scanned!</b>\n\n"
    if amount:
        prefill_msg += f"💰 Detected amount: <b>{amount}</b>\n"
    if merchant:
        prefill_msg += f"🏪 Merchant: <b>{merchant}</b>\n"
    if not amount and not merchant:
        prefill_msg += "⚠️ Could not extract data automatically.\n"

    await state.update_data(
        receipt_photo_id=photo.file_id,
        ocr_raw=raw_text[:500],
        prefill_amount=amount,
        prefill_description=merchant,
    )

    # Pick trip if only one
    if len(trips) == 1:
        await state.update_data(trip_id=trips[0].id)
        description = merchant or ""
        await state.update_data(description=description or "Receipt expense")
        await state.set_state(ReceiptStates.amount)

        prompt = prefill_msg + f"\nTrip: <b>{trips[0].name}</b>\n\n"
        if amount:
            prompt += f"Confirm amount <b>{amount}</b> or type a new one:"
        else:
            prompt += "Enter the amount:"
        await message.answer(prompt, parse_mode="HTML", reply_markup=cancel_keyboard())
    else:
        await state.set_state(ReceiptStates.description)
        prefill_msg += "\nSelect trip:"
        await message.answer(
            prefill_msg,
            parse_mode="HTML",
            reply_markup=trips_list_keyboard(trips),
        )


@router.callback_query(ReceiptStates.description, F.data.startswith("trip:"))
async def receipt_trip_selected(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    trip_id = int(callback.data.split(":")[1])
    await state.update_data(trip_id=trip_id)
    data = await state.get_data()
    description = data.get("prefill_description") or ""
    await state.update_data(description=description or "Receipt expense")
    await state.set_state(ReceiptStates.amount)
    amount = data.get("prefill_amount")
    if amount:
        await callback.message.edit_text(
            f"Confirm amount <b>{amount}</b> or type a new one:",
            parse_mode="HTML",
        )
    else:
        await callback.message.edit_text("Enter the amount:")
    await callback.answer()


@router.message(ReceiptStates.amount)
async def receipt_amount(message: Message, state: FSMContext, session: AsyncSession, current_user: User):
    if message.text == "❌ Cancel":
        await state.clear()
        await message.answer("Cancelled.", reply_markup=main_menu_keyboard())
        return
    data = await state.get_data()
    # Accept blank = use prefill
    raw = message.text.strip() if message.text else ""
    if not raw and data.get("prefill_amount"):
        amount = float(data["prefill_amount"])
    else:
        try:
            amount = float(raw.replace(",", "."))
            if amount <= 0:
                raise ValueError
        except ValueError:
            await message.answer("❌ Invalid amount. Enter a positive number:")
            return
    await state.update_data(amount=amount)
    await state.set_state(ReceiptStates.currency)
    await message.answer("💱 Choose currency:", reply_markup=currency_keyboard())


@router.callback_query(ReceiptStates.currency, F.data.startswith("currency:"))
async def receipt_currency(callback: CallbackQuery, state: FSMContext, session: AsyncSession, current_user: User):
    currency = callback.data.split(":")[1]
    await state.update_data(currency=currency)
    data = await state.get_data()
    members_objs = await get_active_trip_members(session, data["trip_id"])
    members = [m.user for m in members_objs]
    await state.update_data(members=[{"id": u.id, "name": u.full_name, "username": u.username} for u in members])
    await state.set_state(ReceiptStates.payer)
    await callback.message.edit_text("👤 Who paid?", reply_markup=payer_keyboard(members, current_user.id))
    await callback.answer()


@router.callback_query(ReceiptStates.payer, F.data.startswith("payer:"))
async def receipt_payer(callback: CallbackQuery, state: FSMContext):
    payer_id = int(callback.data.split(":")[1])
    await state.update_data(payer_id=payer_id)
    await state.set_state(ReceiptStates.category)
    await callback.message.edit_text("🗂️ Choose category:", reply_markup=category_keyboard())
    await callback.answer()


@router.callback_query(ReceiptStates.category, F.data.startswith("category:"))
async def receipt_category(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    category = callback.data.split(":")[1]
    await state.update_data(category=category)
    data = await state.get_data()
    members_objs = await get_active_trip_members(session, data["trip_id"])
    members = [m.user for m in members_objs]
    all_ids = {u.id for u in members}
    await state.update_data(selected_participants=list(all_ids))
    await state.set_state(ReceiptStates.participants)
    await callback.message.edit_text(
        "👥 Choose participants:",
        reply_markup=participants_keyboard(members, all_ids),
    )
    await callback.answer()


@router.callback_query(ReceiptStates.participants, F.data.startswith("participant:"))
async def receipt_toggle_participant(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    uid = int(callback.data.split(":")[1])
    data = await state.get_data()
    selected = set(data.get("selected_participants", []))
    if uid in selected:
        selected.discard(uid)
    else:
        selected.add(uid)
    await state.update_data(selected_participants=list(selected))
    members_objs = await get_active_trip_members(session, data["trip_id"])
    members = [m.user for m in members_objs]
    await callback.message.edit_reply_markup(reply_markup=participants_keyboard(members, selected))
    await callback.answer()


@router.callback_query(ReceiptStates.participants, F.data == "participants_done")
async def receipt_participants_done(callback: CallbackQuery, state: FSMContext):
    await state.set_state(ReceiptStates.split_type)
    await callback.message.edit_text("⚖️ How to split?", reply_markup=split_type_keyboard())
    await callback.answer()


@router.callback_query(ReceiptStates.split_type, F.data.startswith("split:"))
async def receipt_split_done(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession, current_user: User
):
    split = callback.data.split(":")[1]
    await state.update_data(split_type=split)
    data = await state.get_data()
    trip = await get_trip_by_id(session, data["trip_id"])
    members_objs = await get_active_trip_members(session, trip.id)
    all_members = {m.user.id: m.user for m in members_objs}
    payer = all_members.get(data["payer_id"])
    participants = [all_members[uid] for uid in data["selected_participants"] if uid in all_members]

    expense = await add_expense(
        session=session,
        trip=trip,
        payer=payer,
        description=data.get("description", "Receipt"),
        amount=data["amount"],
        currency=data["currency"],
        category=data["category"],
        participants=participants,
        split_type=split,
        receipt_photo_id=data.get("receipt_photo_id"),
        ocr_raw=data.get("ocr_raw"),
    )
    await state.clear()
    await callback.message.edit_text(
        f"✅ <b>Receipt expense saved!</b>\n\n{fmt_expense_line(expense)}",
        parse_mode="HTML",
        reply_markup=trip_menu_keyboard(trip.id),
    )
    await callback.answer("Saved!")
