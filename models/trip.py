from datetime import datetime
import secrets
from sqlalchemy import String, DateTime, Boolean, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import Base


class Trip(Base):
    __tablename__ = "trips"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    invite_code: Mapped[str] = mapped_column(String(16), unique=True, nullable=False, index=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    base_currency: Mapped[str] = mapped_column(String(3), default="EUR", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    owner: Mapped["User"] = relationship("User", foreign_keys=[owner_id])
    members: Mapped[list["TripMember"]] = relationship("TripMember", back_populates="trip")
    expenses: Mapped[list["Expense"]] = relationship("Expense", back_populates="trip")

    @staticmethod
    def generate_invite_code() -> str:
        return secrets.token_urlsafe(8)[:8].upper()


class TripMember(Base):
    __tablename__ = "trip_members"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    trip_id: Mapped[int] = mapped_column(ForeignKey("trips.id"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    joined_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    trip: Mapped["Trip"] = relationship("Trip", back_populates="members")
    user: Mapped["User"] = relationship("User", back_populates="trips")
