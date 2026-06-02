from models.expense import Expense, CATEGORY_EMOJI, CATEGORY_RU


def fmt_amount(amount: float, currency: str) -> str:
    return f"{amount:,.2f} {currency}"


def fmt_expense_line(exp: Expense) -> str:
    emoji = CATEGORY_EMOJI.get(exp.category, "📦")
    rub_str = ""
    if exp.currency != "RUB" and exp.amount_in_rub and exp.amount_in_rub > 0:
        rub_str = f" <i>({exp.amount_in_rub:,.0f} ₽)</i>"
    comment_str = f"\n   💬 {exp.comment}" if exp.comment else ""

    paid_count = sum(1 for p in exp.participants if p.is_paid)
    total_count = len(exp.participants)
    paid_str = ""
    if total_count > 0:
        paid_str = f"\n   ✅ Погашено: {paid_count}/{total_count}"

    return (
        f"{emoji} <b>{exp.description}</b>  #{exp.id}\n"
        f"   💰 {fmt_amount(exp.amount, exp.currency)}{rub_str}\n"
        f"   👤 Платил: {exp.payer.display_name}\n"
        f"   🗂 {CATEGORY_RU.get(exp.category, exp.category)}\n"
        f"   🕐 {exp.created_at.strftime('%d.%m %H:%M')}"
        + paid_str
        + comment_str
    )


def fmt_trip_header(trip, member_count: int = 0) -> str:
    status = "✅ Активна" if trip.is_active else "🔒 Закрыта"
    return (
        f"✈️ <b>{trip.name}</b>\n"
        f"Статус: {status}\n"
        f"Валюта: {trip.base_currency}\n"
        f"Участников: {member_count}\n"
        f"Код приглашения: <code>{trip.invite_code}</code>"
    )
