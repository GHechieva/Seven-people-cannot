from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder


def main_menu_keyboard() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.button(text="✈️ My Trips")
    builder.button(text="➕ New Trip")
    builder.button(text="🔗 Join Trip")
    builder.button(text="⚙️ Settings")
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True)


def cancel_keyboard() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.button(text="❌ Cancel")
    return builder.as_markup(resize_keyboard=True)


def confirm_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Confirm", callback_data="confirm")
    builder.button(text="❌ Cancel", callback_data="cancel")
    builder.adjust(2)
    return builder.as_markup()
