from aiogram import Router
from aiogram.filters import CommandStart, Command
from aiogram.types import Message
from keyboards.main import main_menu_keyboard

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, **kwargs):
    name = message.from_user.full_name if message.from_user else "друг"
    await message.answer(
        f"👋 Привет, <b>{name}</b>!\n\n"
        "Я бот для учёта совместных расходов в поездках.\n\n"
        "Что я умею:\n"
        "✈️ Создавать поездки и приглашать друзей\n"
        "💰 Записывать траты в рублях, долларах, юанях и донгах\n"
        "⚖️ Считать кто кому сколько должен\n"
        "📊 Показывать статистику по категориям\n"
        "📸 Сканировать чеки\n"
        "📤 Выгружать отчёт в Excel\n\n"
        "Используй меню ниже 👇",
        parse_mode="HTML",
        reply_markup=main_menu_keyboard(),
    )


@router.message(Command("help"))
@router.message(Command("помощь"))
async def cmd_help(message: Message, **kwargs):
    await message.answer(
        "📖 <b>Как пользоваться ботом:</b>\n\n"
        "<b>1. Создай поездку</b>\n"
        "Нажми ➕ Новая поездка, придумай название и выбери валюту.\n\n"
        "<b>2. Пригласи друзей</b>\n"
        "Поделись кодом приглашения — они напишут боту /start и нажмут 🔗 Вступить в поездку.\n\n"
        "<b>3. Добавляй траты</b>\n"
        "Зайди в поездку → ➕ Добавить трату.\n"
        "Укажи: описание, сумму, валюту, кто платил, категорию, на кого делить.\n\n"
        "<b>4. Смотри долги</b>\n"
        "⚖️ Долги — кто кому должен с минимальным числом переводов.\n\n"
        "<b>5. Сканируй чеки</b>\n"
        "Просто отправь фото чека — бот попробует распознать сумму автоматически.\n\n"
        "<b>Команды:</b>\n"
        "/start — главное меню\n"
        "/помощь — эта инструкция\n"
        "/настройки — уведомления\n",
        parse_mode="HTML",
        reply_markup=main_menu_keyboard(),
    )
