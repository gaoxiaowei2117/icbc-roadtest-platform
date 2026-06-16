"""用户模型。表名 user（Postgres 保留字，使用原生引号）。"""
from datetime import date, datetime
from sqlalchemy import Boolean, Date, DateTime, Integer, String, func
from sqlalchemy import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class User(Base):
    __tablename__ = "user"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    verify_code: Mapped[str | None] = mapped_column(String(6))
    verify_code_expires: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    icbc_license_no: Mapped[str | None] = mapped_column(String(50))
    icbc_last_name: Mapped[str | None] = mapped_column(String(100))
    exam_class: Mapped[str | None] = mapped_column(String(10))
    pos_ids: Mapped[list[int] | None] = mapped_column(JSON)
    expect_after_date: Mapped[date | None] = mapped_column(Date)
    expect_before_date: Mapped[date | None] = mapped_column(Date)
    expect_time_range: Mapped[str | None] = mapped_column(String(20))
    pref_days_of_week: Mapped[list[int] | None] = mapped_column(JSON)
    pref_parts_of_day: Mapped[list[int] | None] = mapped_column(JSON)

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
