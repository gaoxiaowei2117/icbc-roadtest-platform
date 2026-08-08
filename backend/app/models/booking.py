"""抢约任务。"""
import enum
from datetime import datetime
from sqlalchemy import JSON, DateTime, Enum as SAEnum, ForeignKey, Index, Integer, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.core.database import Base


class BookingStatus(str, enum.Enum):
    awaiting_payment = "awaiting_payment"
    awaiting_review = "awaiting_review"
    payment_rejected = "payment_rejected"
    pending = "pending"
    running = "running"
    done = "done"
    failed = "failed"
    cancelled = "cancelled"


class PaymentStatus(str, enum.Enum):
    """Payment/entitlement state for a booking.

    ``not_required`` is retained for bookings created before the paid execution
    flow was introduced.
    """

    not_required = "not_required"
    awaiting_payment = "awaiting_payment"
    awaiting_review = "awaiting_review"
    approved = "approved"
    rejected = "rejected"


class Booking(Base):
    __tablename__ = "booking"
    __table_args__ = (
        # 数据库层兜底"每用户最多一个进行中任务"，防止 has_active 的 TOCTOU 竞态：
        # 并发两次创建时，第二条 INSERT 会撞唯一索引报错，由接口转成 409。
        Index(
            "uq_booking_one_active_per_user",
            "user_id",
            unique=True,
            postgresql_where=text(
                "status IN ('awaiting_payment', 'awaiting_review', 'pending', 'running')"
            ),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[BookingStatus] = mapped_column(
        SAEnum(BookingStatus, name="booking_status", native_enum=False, length=20),
        default=BookingStatus.pending,
        nullable=False,
        index=True,
    )
    payment_status: Mapped[PaymentStatus] = mapped_column(
        SAEnum(PaymentStatus, name="payment_status", native_enum=False, length=20),
        default=PaymentStatus.not_required,
        nullable=False,
        index=True,
    )
    payment_reference: Mapped[str | None] = mapped_column(Text)
    payment_submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reviewed_by: Mapped[int | None] = mapped_column(ForeignKey("user.id", ondelete="SET NULL"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_reason: Mapped[str | None] = mapped_column(Text)

    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    progress_rounds: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_progress: Mapped[str | None] = mapped_column(Text)
    last_progress_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
    result: Mapped[dict | None] = mapped_column(JSON)

    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped["User"] = relationship(  # noqa: F821
        "User", back_populates="bookings", foreign_keys=[user_id]
    )
