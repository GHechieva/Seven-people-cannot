from datetime import datetime
from models.expense import Expense, CATEGORY_EMOJI
from models.user import User


def fmt_amount(amount: float, currency: str) -> str:
    return f"{amount:,.2f} {currency}"


def fmt_expense_line(exp: Expense) -> str:
    emoji = CATEGORY_EMOJI.get(exp.category, "📦")
    return (
        f"{emoji} <b>{exp.description}</b>\n"
        f"   💰 {fmt_amount(exp.amount, exp.currency)}"
        + (f" (~{fmt_amount(exp.amount_in_base, exp.base_currency)})" if exp.currency != exp.base_currency else "")
        + f"\n   👤 Paid by {exp.payer.display_name}\n"
        f"   🕐 {exp.created_at.strftime('%d %b %H:%M')}"
    )


def fmt_balance_line(debtor: User, creditor: User, amount: float, currency: str) -> str:
    return f"💸 {debtor.display_name} owes {creditor.display_name} <b>{fmt_amount(amount, currency)}</b>"


def fmt_trip_header(trip) -> str:
    status = "✅ Active" if trip.is_active else "🔒 Closed"
    return (
        f"✈️ <b>{trip.name}</b>\n"
        f"Status: {status}\n"
        f"Currency: {trip.base_currency}\n"
        f"Members: {sum(1 for m in trip.members if m.is_active)}\n"
        f"Invite code: <code>{trip.invite_code}</code>"
    )
