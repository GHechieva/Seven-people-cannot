from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from models.expense import CATEGORIES, CATEGORY_EMOJI
from models.user import User
import config


def currency_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    common = ["EUR", "USD", "GBP", "CHF", "JPY", "PLN", "CZK", "SEK", "NOK", "DKK"]
    for cur in common:
        builder.button(text=cur, callback_data=f"currency:{cur}")
    builder.adjust(4)
    return builder.as_markup()


def payer_keyboard(members: list[User], current_user_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for user in members:
        label = f"👤 {user.display_name}"
        if user.id == current_user_id:
            label = f"⭐ {user.display_name} (me)"
        builder.button(text=label, callback_data=f"payer:{user.id}")
    builder.adjust(2)
    return builder.as_markup()


def category_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for cat in CATEGORIES:
        emoji = CATEGORY_EMOJI[cat]
        builder.button(text=f"{emoji} {cat.title()}", callback_data=f"category:{cat}")
    builder.adjust(3)
    return builder.as_markup()


def participants_keyboard(
    members: list[User],
    selected_ids: set[int],
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for user in members:
        check = "✅" if user.id in selected_ids else "⬜"
        builder.button(
            text=f"{check} {user.display_name}",
            callback_data=f"participant:{user.id}",
        )
    builder.button(text="✅ Done", callback_data="participants_done")
    builder.adjust(2)
    return builder.as_markup()


def split_type_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="⚖️ Split Equally", callback_data="split:equal")
    builder.button(text="📐 Custom %", callback_data="split:custom")
    builder.adjust(2)
    return builder.as_markup()


def notification_keyboard(enabled: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if enabled:
        builder.button(text="🔕 Disable Reminders", callback_data="notif:disable")
    else:
        builder.button(text="🔔 Enable Reminders", callback_data="notif:enable")
    builder.adjust(1)
    return builder.as_markup()
