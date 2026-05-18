from aiogram import Router
from aiogram.filters import CommandStart, Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession
from models.user import User
from keyboards.main import main_menu_keyboard

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, current_user: User):
    await message.answer(
        f"👋 Welcome, <b>{current_user.full_name}</b>!\n\n"
        "I'm your <b>Trip Expense Bot</b> — your Splitwise for travel groups.\n\n"
        "Here's what I can do:\n"
        "✈️ Create & manage trips\n"
        "💰 Track shared expenses\n"
        "⚖️ Calculate who owes whom\n"
        "📊 Generate trip summaries\n"
        "📤 Export CSV reports\n\n"
        "Use the menu below to get started!",
        parse_mode="HTML",
        reply_markup=main_menu_keyboard(),
    )


@router.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "📖 <b>Commands:</b>\n\n"
        "/start — Main menu\n"
        "/newtrip — Create a new trip\n"
        "/join — Join trip by invite code\n"
        "/trips — List your trips\n"
        "/today — Today's expenses\n"
        "/summary — Trip summary & balances\n"
        "/settings — Notification settings\n"
        "/help — This message",
        parse_mode="HTML",
    )
