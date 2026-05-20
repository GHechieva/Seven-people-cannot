from models.expense import Expense, CATEGORY_EMOJI


def fmt_amount(amount: float, currency: str) -> str:
    return f"{amount:,.2f} {currency}"


def fmt_expense_line(exp: Expense) -> str:
    emoji = CATEGORY_EMOJI.get(exp.category, "📦")
    comment = f"\n   💬 {exp.ocr_raw[:50]}" if exp.ocr_raw else ""
    return (
        f"{emoji} <b>{exp.description}</b>\n"
        f"   💰 {fmt_amount(exp.amount, exp.currency)}"
        + (f" (~{fmt_amount(exp.amount_in_base, exp.base_currency)})" if exp.currency != exp.base_currency else "")
        + f"\n   👤 Оплатил: {exp.payer.display_name}\n"
        f"   🕐 {exp.created_at.strftime('%d.%m %H:%M')}"
        + comment
    )


def fmt_balance_line(debtor, creditor, amount: float, currency: str) -> str:
    return f"💸 {debtor.display_name} должен {creditor.display_name} <b>{fmt_amount(amount, currency)}</b>"


def fmt_trip_header(trip, member_count: int = 0) -> str:
    status = "✅ Активна" if trip.is_active else "🔒 Закрыта"
    return (
        f"✈️ <b>{trip.name}</b>\n"
        f"Статус: {status}\n"
        f"Валюта: {trip.base_currency}\n"
        f"Участников: {member_count}\n"
        f"Код приглашения: <code>{trip.invite_code}</code>"
    )
