import csv
import io
from sqlalchemy.ext.asyncio import AsyncSession
from models.trip import Trip
from services.expense_service import get_trip_expenses


async def export_trip_csv(session: AsyncSession, trip: Trip) -> bytes:
    expenses = await get_trip_expenses(session, trip.id)

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow([
        "Date", "Description", "Category", "Payer", "Amount",
        "Currency", f"Amount ({trip.base_currency})", "Participants", "Split %"
    ])

    for exp in expenses:
        participants_str = "; ".join(
            f"{ep.user.display_name} ({ep.share_percent:.1f}%)"
            for ep in exp.participants
        )
        split_str = "; ".join(
            f"{ep.share_percent:.1f}%"
            for ep in exp.participants
        )
        writer.writerow([
            exp.created_at.strftime("%Y-%m-%d %H:%M"),
            exp.description,
            exp.category,
            exp.payer.display_name,
            f"{exp.amount:.2f}",
            exp.currency,
            f"{exp.amount_in_base:.2f}",
            participants_str,
            split_str,
        ])

    return output.getvalue().encode("utf-8-sig")  # utf-8-sig for Excel compatibility
