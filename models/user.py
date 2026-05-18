from datetime import datetime
from sqlalchemy import BigInteger, String, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True)
    username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    full_name: Mapped[str] = mapped_column(String(256), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    trips: Mapped[list["TripMember"]] = relationship("TripMember", back_populates="user")
    expenses_paid: Mapped[list["Expense"]] = relationship("Expense", back_populates="payer")
    expense_participations: Mapped[list["ExpenseParticipant"]] = relationship(
        "ExpenseParticipant", back_populates="user"
    )
    notification_setting: Mapped["NotificationSetting | None"] = relationship(
        "NotificationSetting", back_populates="user", uselist=False
    )

    @property
    def display_name(self) -> str:
        if self.username:
            return f"@{self.username}"
        return self.full_name
