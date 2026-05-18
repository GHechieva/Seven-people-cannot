from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload
from models.trip import Trip, TripMember
from models.user import User


async def create_trip(
    session: AsyncSession,
    owner: User,
    name: str,
    description: str | None = None,
    base_currency: str = "EUR",
) -> Trip:
    trip = Trip(
        name=name,
        description=description,
        invite_code=Trip.generate_invite_code(),
        owner_id=owner.id,
        base_currency=base_currency,
    )
    session.add(trip)
    await session.flush()

    member = TripMember(trip_id=trip.id, user_id=owner.id)
    session.add(member)
    await session.commit()
    await session.refresh(trip)
    return trip


async def get_trip_by_invite_code(session: AsyncSession, code: str) -> Trip | None:
    result = await session.execute(
        select(Trip)
        .options(selectinload(Trip.members).selectinload(TripMember.user))
        .where(and_(Trip.invite_code == code.upper(), Trip.is_active == True))
    )
    return result.scalar_one_or_none()


async def get_trip_by_id(session: AsyncSession, trip_id: int) -> Trip | None:
    result = await session.execute(
        select(Trip)
        .options(
            selectinload(Trip.members).selectinload(TripMember.user),
            selectinload(Trip.owner),
        )
        .where(Trip.id == trip_id)
    )
    return result.scalar_one_or_none()


async def get_user_trips(session: AsyncSession, user: User) -> list[Trip]:
    result = await session.execute(
        select(Trip)
        .join(TripMember, TripMember.trip_id == Trip.id)
        .options(selectinload(Trip.members).selectinload(TripMember.user))
        .where(
            and_(
                TripMember.user_id == user.id,
                TripMember.is_active == True,
                Trip.is_active == True,
            )
        )
        .order_by(Trip.created_at.desc())
    )
    return list(result.scalars().all())


async def join_trip(session: AsyncSession, trip: Trip, user: User) -> tuple[bool, str]:
    # Check already member
    result = await session.execute(
        select(TripMember).where(
            and_(TripMember.trip_id == trip.id, TripMember.user_id == user.id)
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        if existing.is_active:
            return False, "already_member"
        existing.is_active = True
        await session.commit()
        return True, "rejoined"

    member = TripMember(trip_id=trip.id, user_id=user.id)
    session.add(member)
    await session.commit()
    return True, "joined"


async def is_trip_member(session: AsyncSession, trip_id: int, user_id: int) -> bool:
    result = await session.execute(
        select(TripMember).where(
            and_(
                TripMember.trip_id == trip_id,
                TripMember.user_id == user_id,
                TripMember.is_active == True,
            )
        )
    )
    return result.scalar_one_or_none() is not None


async def remove_member(
    session: AsyncSession, trip: Trip, target_user_id: int
) -> bool:
    result = await session.execute(
        select(TripMember).where(
            and_(
                TripMember.trip_id == trip.id,
                TripMember.user_id == target_user_id,
                TripMember.is_active == True,
            )
        )
    )
    member = result.scalar_one_or_none()
    if not member:
        return False
    member.is_active = False
    await session.commit()
    return True


async def close_trip(session: AsyncSession, trip: Trip) -> None:
    from datetime import datetime
    trip.is_active = False
    trip.closed_at = datetime.utcnow()
    await session.commit()


async def get_active_trip_members(session: AsyncSession, trip_id: int) -> list[TripMember]:
    result = await session.execute(
        select(TripMember)
        .options(selectinload(TripMember.user))
        .where(and_(TripMember.trip_id == trip_id, TripMember.is_active == True))
    )
    return list(result.scalars().all())
