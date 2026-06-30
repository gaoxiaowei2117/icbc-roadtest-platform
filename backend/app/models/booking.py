"""抢约任务。"""
import enum
from datetime import datetime
from sqlalchemy import JSON, DateTime, Enum as SAEnum, ForeignKey, Index, Integer, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.core.database import Base


class BookingStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    done = "done"
    failed = "failed"
    cancelled = "cancelled"


class Booking(Base):
    __tablename__ = "booking"
    __table_args__ = (
        # 数据库层兜底"每用户最多一个进行中任务"，防止 has_active 的 TOCTOU 竞态：
        # 并发两次创建时，第二条 INSERT 会撞唯一索引报错，由接口转成 409。
        Index(
            "uq_booking_one_active_per_user",
            "user_id",
            unique=True,
            postgresql_where=text("status IN ('pending', 'running')"),
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

    user: Mapped["User"] = relationship("User", back_populates="bookings")  # noqa: F821
