"""用户模型。表名 user（Postgres 保留字，使用原生引号）。"""
from datetime import datetime
from sqlalchemy import Boolean, DateTime, Integer, String, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class User(Base):
    __tablename__ = "user"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    icbc_license_no: Mapped[str | None] = mapped_column(String(50))
    icbc_last_name: Mapped[str | None] = mapped_column(String(100))
    preferred_pos: Mapped[list[str] | None] = mapped_column(ARRAY(String))
    time_windows: Mapped[dict | None] = mapped_column(JSONB)
    max_wait_days: Mapped[int] = mapped_column(Integer, default=60, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    secret: Mapped["Secret | None"] = relationship(  # noqa: F821
        "Secret", back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    bookings: Mapped[list["Booking"]] = relationship(  # noqa: F821
        "Booking", back_populates="user", cascade="all, delete-orphan"
    )
