from datetime import datetime, date
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
from sqlalchemy.orm import selectinload
from models.expense import Expense, ExpenseParticipant
from models.trip import Trip
from models.user import User
from services.currency_service import convert_amount


async def add_expense(
    session: AsyncSession,
    trip: Trip,
    payer: User,
    description: str,
    amount: float,
    currency: str,
    category: str,
    participants: list[User],
    split_type: str = "equal",
    custom_percentages: dict[int, float] | None = None,
    receipt_photo_id: str | None = None,
    ocr_raw: str | None = None,
) -> Expense:
    amount_in_base = await convert_amount(amount, currency, trip.base_currency)

    expense = Expense(
        trip_id=trip.id,
        payer_id=payer.id,
        description=description,
        amount=amount,
        currency=currency,
        amount_in_base=amount_in_base,
        base_currency=trip.base_currency,
        category=category,
        receipt_photo_id=receipt_photo_id,
        ocr_raw=ocr_raw,
    )
    session.add(expense)
    await session.flush()

    if split_type == "equal":
        share = round(100.0 / len(participants), 4)
        shares = {u.id: share for u in participants}
        # Fix rounding on last participant
        total = sum(shares.values())
        last_id = participants[-1].id
        shares[last_id] = round(100.0 - sum(v for k, v in shares.items() if k != last_id), 4)
    else:
        shares = custom_percentages or {}

    for participant in participants:
        pct = shares.get(participant.id, 0.0)
        share_amount = round(amount_in_base * pct / 100.0, 4)
        ep = ExpenseParticipant(
            expense_id=expense.id,
            user_id=participant.id,
            share_percent=pct,
            share_amount=share_amount,
        )
        session.add(ep)

    await session.commit()
    await session.refresh(expense)
    return expense


async def get_trip_expenses(
    session: AsyncSession,
    trip_id: int,
    include_deleted: bool = False,
) -> list[Expense]:
    q = select(Expense).options(
        selectinload(Expense.payer),
        selectinload(Expense.participants).selectinload(ExpenseParticipant.user),
    ).where(Expense.trip_id == trip_id)
    if not include_deleted:
        q = q.where(Expense.is_deleted == False)
    q = q.order_by(Expense.created_at.desc())
    result = await session.execute(q)
    return list(result.scalars().all())


async def get_today_expenses(session: AsyncSession, trip_id: int) -> list[Expense]:
    today_start = datetime.combine(date.today(), datetime.min.time())
    result = await session.execute(
        select(Expense)
        .options(
            selectinload(Expense.payer),
            selectinload(Expense.participants).selectinload(ExpenseParticipant.user),
        )
        .where(
            and_(
                Expense.trip_id == trip_id,
                Expense.is_deleted == False,
                Expense.created_at >= today_start,
            )
        )
        .order_by(Expense.created_at.desc())
    )
    return list(result.scalars().all())


async def get_expense_by_id(session: AsyncSession, expense_id: int) -> Expense | None:
    result = await session.execute(
        select(Expense)
        .options(
            selectinload(Expense.payer),
            selectinload(Expense.participants).selectinload(ExpenseParticipant.user),
            selectinload(Expense.trip),
        )
        .where(Expense.id == expense_id)
    )
    return result.scalar_one_or_none()


async def delete_expense(session: AsyncSession, expense: Expense) -> None:
    expense.is_deleted = True
    await session.commit()


async def update_expense_description(
    session: AsyncSession, expense: Expense, new_description: str
) -> None:
    expense.description = new_description
    expense.updated_at = datetime.utcnow()
    await session.commit()


async def calculate_balances(
    session: AsyncSession, trip_id: int
) -> dict[int, float]:
    """
    Returns {user_id: net_balance} where positive = owed money, negative = owes money.
    """
    expenses = await get_trip_expenses(session, trip_id)
    balances: dict[int, float] = {}

    for expense in expenses:
        payer_id = expense.payer_id
        balances[payer_id] = balances.get(payer_id, 0.0) + expense.amount_in_base
        for ep in expense.participants:
            balances[ep.user_id] = balances.get(ep.user_id, 0.0) - ep.share_amount

    return balances


def simplify_debts(balances: dict[int, float]) -> list[tuple[int, int, float]]:
    """
    Debt simplification algorithm.
    Returns list of (debtor_id, creditor_id, amount).
    """
    # Separate into creditors (positive) and debtors (negative)
    creditors = sorted(
        [(uid, bal) for uid, bal in balances.items() if bal > 0.005],
        key=lambda x: -x[1],
    )
    debtors = sorted(
        [(uid, -bal) for uid, bal in balances.items() if bal < -0.005],
        key=lambda x: -x[1],
    )

    creditors = list(creditors)
    debtors = list(debtors)
    transfers: list[tuple[int, int, float]] = []

    ci, di = 0, 0
    while ci < len(creditors) and di < len(debtors):
        cid, credit = creditors[ci]
        did, debt = debtors[di]

        amount = min(credit, debt)
        transfers.append((did, cid, round(amount, 2)))

        creditors[ci] = (cid, credit - amount)
        debtors[di] = (did, debt - amount)

        if creditors[ci][1] < 0.005:
            ci += 1
        if debtors[di][1] < 0.005:
            di += 1

    return transfers


async def get_category_totals(
    session: AsyncSession, trip_id: int, today_only: bool = False
) -> dict[str, float]:
    expenses = (
        await get_today_expenses(session, trip_id)
        if today_only
        else await get_trip_expenses(session, trip_id)
    )
    totals: dict[str, float] = {}
    for exp in expenses:
        totals[exp.category] = totals.get(exp.category, 0.0) + exp.amount_in_base
    return totals


async def get_user_totals(
    session: AsyncSession, trip_id: int
) -> dict[int, float]:
    expenses = await get_trip_expenses(session, trip_id)
    totals: dict[int, float] = {}
    for exp in expenses:
        totals[exp.payer_id] = totals.get(exp.payer_id, 0.0) + exp.amount_in_base
    return totals
