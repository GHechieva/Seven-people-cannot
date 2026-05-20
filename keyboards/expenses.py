from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from models.expense import CATEGORIES, CATEGORY_EMOJI
from models.user import User
import config


def currency_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for cur, name in config.CURRENCY_NAMES.items():
        builder.button(text=name, callback_data=f"currency:{cur}")
    builder.adjust(2)
    return builder.as_markup()


def payer_keyboard(members: list[User], current_user_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for user in members:
        label = f"⭐ {user.display_name} (я)" if user.id == current_user_id else f"👤 {user.display_name}"
        builder.button(text=label, callback_data=f"payer:{user.id}")
    builder.adjust(2)
    return builder.as_markup()


def category_keyboard() -> InlineKeyboardMarkup:
    CATEGORY_RU = {
        "food": "Еда",
        "transport": "Транспорт",
        "housing": "Жильё",
        "entertainment": "Развлечения",
        "shopping": "Покупки",
        "other": "Другое",
    }
    builder = InlineKeyboardBuilder()
    for cat in CATEGORIES:
        emoji = CATEGORY_EMOJI[cat]
        builder.button(text=f"{emoji} {CATEGORY_RU[cat]}", callback_data=f"category:{cat}")
    builder.adjust(3)
    return builder.as_markup()


def participants_keyboard(members: list[User], selected_ids: set[int]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for user in members:
        check = "✅" if user.id in selected_ids else "⬜"
        builder.button(text=f"{check} {user.display_name}", callback_data=f"participant:{user.id}")
    builder.button(text="✅ Готово", callback_data="participants_done")
    builder.adjust(2)
    return builder.as_markup()


def split_type_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="⚖️ Поровну", callback_data="split:equal")
    builder.button(text="📐 Свои проценты", callback_data="split:custom")
    builder.adjust(2)
    return builder.as_markup()


def notification_keyboard(enabled: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if enabled:
        builder.button(text="🔕 Выключить напоминания", callback_data="notif:disable")
    else:
        builder.button(text="🔔 Включить напоминания", callback_data="notif:enable")
    builder.adjust(1)
    return builder.as_markup()
