"""Payment records for manual and Stripe execution-pass purchases."""
import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.core.database import Base


class PaymentProvider(str, enum.Enum):
    stripe = "stripe"
    manual = "manual"


class PaymentRecordStatus(str, enum.Enum):
    created = "created"
    pending = "pending"
    paid = "paid"
    failed = "failed"
    expired = "expired"
    refunded = "refunded"


class Payment(Base):
    __tablename__ = "payment"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True
    )
    booking_id: Mapped[int | None] = mapped_column(
        ForeignKey("booking.id", ondelete="SET NULL"), nullable=True, index=True
    )
    provider: Mapped[PaymentProvider] = mapped_column(
        SAEnum(PaymentProvider, name="payment_provider", native_enum=False, length=20),
        nullable=False,
    )
    status: Mapped[PaymentRecordStatus] = mapped_column(
        SAEnum(
            PaymentRecordStatus,
            name="payment_record_status",
            native_enum=False,
            length=20,
        ),
        default=PaymentRecordStatus.created,
        nullable=False,
        index=True,
    )
    amount: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="cad")
    provider_session_id: Mapped[str | None] = mapped_column(String(255), unique=True, index=True)
    provider_payment_intent_id: Mapped[str | None] = mapped_column(String(255), index=True)
    provider_event_id: Mapped[str | None] = mapped_column(String(255), unique=True, index=True)
    checkout_url: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped["User"] = relationship("User", back_populates="payments")  # noqa: F821
    booking: Mapped["Booking | None"] = relationship("Booking")  # noqa: F821
