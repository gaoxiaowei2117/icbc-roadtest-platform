"""Route pack purchases: a user's access to one test centre's practice-route links."""
import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.core.database import Base


class RoutePackPurchaseStatus(str, enum.Enum):
    active = "active"
    revoked = "revoked"


class RoutePackPurchaseSource(str, enum.Enum):
    stripe = "stripe"
    manual = "manual"


class RoutePackPurchase(Base):
    """One row per (user, pack). Re-granting a revoked pack reactivates the row."""

    __tablename__ = "route_pack_purchase"
    __table_args__ = (
        UniqueConstraint("user_id", "pack_slug", name="uq_route_pack_purchase_user_pack"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True
    )
    pack_slug: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    payment_id: Mapped[int | None] = mapped_column(
        ForeignKey("payment.id", ondelete="SET NULL"), nullable=True, index=True
    )
    status: Mapped[RoutePackPurchaseStatus] = mapped_column(
        SAEnum(
            RoutePackPurchaseStatus,
            name="route_pack_purchase_status",
            native_enum=False,
            length=20,
        ),
        default=RoutePackPurchaseStatus.active,
        nullable=False,
        index=True,
    )
    source: Mapped[RoutePackPurchaseSource] = mapped_column(
        SAEnum(
            RoutePackPurchaseSource,
            name="route_pack_purchase_source",
            native_enum=False,
            length=20,
        ),
        nullable=False,
    )
    granted_by: Mapped[int | None] = mapped_column(ForeignKey("user.id", ondelete="SET NULL"))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped["User"] = relationship(  # noqa: F821
        "User", back_populates="route_pack_purchases", foreign_keys=[user_id]
    )
    payment: Mapped["Payment | None"] = relationship("Payment")  # noqa: F821
