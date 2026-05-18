from datetime import datetime
from sqlalchemy import String, DateTime, Float, ForeignKey, Integer, Boolean, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import Base

CATEGORIES = ["food", "transport", "housing", "entertainment", "shopping", "other"]
CATEGORY_EMOJI = {
    "food": "🍽️",
    "transport": "🚌",
    "housing": "🏨",
    "entertainment": "🎭",
    "shopping": "🛍️",
    "other": "📦",
}


class Expense(Base):
    __tablename__ = "expenses"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    trip_id: Mapped[int] = mapped_column(ForeignKey("trips.id"), nullable=False, index=True)
    payer_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    description: Mapped[str] = mapped_column(String(512), nullable=False)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    amount_in_base: Mapped[float] = mapped_column(Float, nullable=False)
    base_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    category: Mapped[str] = mapped_column(String(32), nullable=False, default="other")
    receipt_photo_id: Mapped[str | None] = mapped_column(String(256), nullable=True)
    ocr_raw: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    trip: Mapped["Trip"] = relationship("Trip", back_populates="expenses")
    payer: Mapped["User"] = relationship("User", back_populates="expenses_paid")
    participants: Mapped[list["ExpenseParticipant"]] = relationship(
        "ExpenseParticipant", back_populates="expense", cascade="all, delete-orphan"
    )

    @property
    def category_emoji(self) -> str:
        return CATEGORY_EMOJI.get(self.category, "📦")


class ExpenseParticipant(Base):
    __tablename__ = "expense_participants"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    expense_id: Mapped[int] = mapped_column(ForeignKey("expenses.id"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    share_percent: Mapped[float] = mapped_column(Float, nullable=False)
    share_amount: Mapped[float] = mapped_column(Float, nullable=False)

    expense: Mapped["Expense"] = relationship("Expense", back_populates="participants")
    user: Mapped["User"] = relationship("User", back_populates="expense_participations")
