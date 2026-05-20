from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from models.trip import Trip


def trips_list_keyboard(trips: list[Trip]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for trip in trips:
        status = "✅" if trip.is_active else "🔒"
        builder.button(text=f"{status} {trip.name}", callback_data=f"trip:{trip.id}")
    builder.adjust(1)
    return builder.as_markup()


def trip_menu_keyboard(trip_id: int, is_owner: bool = False) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="➕ Добавить трату", callback_data=f"add_expense:{trip_id}")
    builder.button(text="📋 Список трат", callback_data=f"list_expenses:{trip_id}")
    builder.button(text="⚖️ Долги", callback_data=f"balances:{trip_id}")
    builder.button(text="📅 Сегодня", callback_data=f"today:{trip_id}")
    builder.button(text="📊 Итоги", callback_data=f"summary:{trip_id}")
    builder.button(text="📤 Экспорт CSV", callback_data=f"export:{trip_id}")
    builder.button(text="🔗 Код приглашения", callback_data=f"invite:{trip_id}")
    if is_owner:
        builder.button(text="👑 Управление", callback_data=f"admin:{trip_id}")
    builder.button(text="🔙 Назад", callback_data="back_to_trips")
    builder.adjust(2)
    return builder.as_markup()


def expense_page_keyboard(trip_id: int, page: int, total_pages: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if page > 0:
        builder.button(text="⬅️ Назад", callback_data=f"exp_page:{trip_id}:{page - 1}")
    if page < total_pages - 1:
        builder.button(text="Вперёд ➡️", callback_data=f"exp_page:{trip_id}:{page + 1}")
    builder.button(text="🔙 В меню", callback_data=f"trip:{trip_id}")
    builder.adjust(2)
    return builder.as_markup()


def expense_detail_keyboard(expense_id: int, is_owner: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if is_owner:
        builder.button(text="✏️ Изменить", callback_data=f"edit_exp:{expense_id}")
        builder.button(text="🗑️ Удалить", callback_data=f"delete_exp:{expense_id}")
    builder.button(text="🔙 Назад", callback_data="back_to_trips")
    builder.adjust(2)
    return builder.as_markup()


def admin_keyboard(trip_id: int, members: list) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for member in members:
        builder.button(
            text=f"🚫 Удалить {member.user.display_name}",
            callback_data=f"remove_member:{trip_id}:{member.user_id}",
        )
    builder.button(text="🔒 Закрыть поездку", callback_data=f"close_trip:{trip_id}")
    builder.button(text="🔙 Назад", callback_data=f"trip:{trip_id}")
    builder.adjust(1)
    return builder.as_markup()
