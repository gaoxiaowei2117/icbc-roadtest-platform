"""一次性抢号执行权限。"""
import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.core.database import Base


class ExecutionPassStatus(str, enum.Enum):
    available = "available"
    reserved = "reserved"
    consumed = "consumed"
    released = "released"


class ExecutionPass(Base):
    __tablename__ = "execution_pass"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True
    )
    booking_id: Mapped[int | None] = mapped_column(
        ForeignKey("booking.id", ondelete="SET NULL"), nullable=True, unique=True, index=True
    )
    status: Mapped[ExecutionPassStatus] = mapped_column(
        SAEnum(
            ExecutionPassStatus,
            name="execution_pass_status",
            native_enum=False,
            length=20,
        ),
        default=ExecutionPassStatus.available,
        nullable=False,
        index=True,
    )
    approved_by: Mapped[int | None] = mapped_column(ForeignKey("user.id", ondelete="SET NULL"))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped["User"] = relationship(  # noqa: F821
        "User", back_populates="execution_passes", foreign_keys=[user_id]
    )
    booking: Mapped["Booking | None"] = relationship("Booking")  # noqa: F821
