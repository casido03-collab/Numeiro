from sqlalchemy import BigInteger, String, Date, Boolean, DateTime, Text, JSON, Integer, Float, ForeignKey, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from database.base import Base
import enum


class GenderEnum(str, enum.Enum):
    male = "male"
    female = "female"
    unknown = "unknown"


class PlanEnum(str, enum.Enum):
    free = "free"
    lite = "lite"
    premium = "premium"
    pro = "pro"


class SubscriptionStatusEnum(str, enum.Enum):
    active = "active"
    expired = "expired"
    cancelled = "cancelled"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    first_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    birth_date: Mapped[str | None] = mapped_column(String(10), nullable=True)
    gender: Mapped[GenderEnum] = mapped_column(Enum(GenderEnum), default=GenderEnum.unknown)
    timezone: Mapped[str] = mapped_column(String(50), default="Europe/Moscow")
    is_blocked: Mapped[bool] = mapped_column(Boolean, default=False)
    referral_code: Mapped[str | None] = mapped_column(String(20), nullable=True, unique=True)
    invited_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    profile: Mapped["UserProfile"] = relationship("UserProfile", back_populates="user", uselist=False)
    subscription: Mapped["Subscription"] = relationship("Subscription", back_populates="user", uselist=False)
    usage_limits: Mapped[list["UsageLimits"]] = relationship("UsageLimits", back_populates="user")
    payments: Mapped[list["Payment"]] = relationship("Payment", back_populates="user")
    ai_requests: Mapped[list["AIRequest"]] = relationship("AIRequest", back_populates="user")
    predictions: Mapped[list["Prediction"]] = relationship("Prediction", back_populates="user")
    compatibility_reports: Mapped[list["CompatibilityReport"]] = relationship("CompatibilityReport", back_populates="user")
    reports: Mapped[list["UserReport"]] = relationship("UserReport", back_populates="user")


class UserProfile(Base):
    __tablename__ = "user_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), unique=True)
    life_path_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    destiny_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    personality_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    matrix_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    preferences: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    user: Mapped["User"] = relationship("User", back_populates="profile")


class Subscription(Base):
    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), unique=True)
    plan: Mapped[PlanEnum] = mapped_column(Enum(PlanEnum), default=PlanEnum.free)
    status: Mapped[SubscriptionStatusEnum] = mapped_column(
        Enum(SubscriptionStatusEnum), default=SubscriptionStatusEnum.active
    )
    expires_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user: Mapped["User"] = relationship("User", back_populates="subscription")


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"))
    telegram_payment_charge_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    amount: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(10), default="XTR")
    product_type: Mapped[str] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(20), default="pending")
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship("User", back_populates="payments")


class AIRequest(Base):
    __tablename__ = "ai_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"))
    request_type: Mapped[str] = mapped_column(String(50))
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    model: Mapped[str] = mapped_column(String(50))
    estimated_cost: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship("User", back_populates="ai_requests")


class Prediction(Base):
    __tablename__ = "predictions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"))
    prediction_type: Mapped[str] = mapped_column(String(50))
    sphere: Mapped[str | None] = mapped_column(String(50), nullable=True)
    period_start: Mapped[str | None] = mapped_column(String(10), nullable=True)
    period_end: Mapped[str | None] = mapped_column(String(10), nullable=True)
    content: Mapped[str] = mapped_column(Text)
    cache_key: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship("User", back_populates="predictions")


class CompatibilityReport(Base):
    __tablename__ = "compatibility_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"))
    user_birth_date: Mapped[str] = mapped_column(String(10))
    partner_birth_date: Mapped[str] = mapped_column(String(10))
    relation_type: Mapped[str] = mapped_column(String(50))
    content: Mapped[str] = mapped_column(Text)
    cache_key: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship("User", back_populates="compatibility_reports")


class UsageLimits(Base):
    __tablename__ = "usage_limits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), index=True)
    period_start: Mapped[str] = mapped_column(String(10), index=True)
    ai_messages: Mapped[int] = mapped_column(Integer, default=0)
    personal_questions: Mapped[int] = mapped_column(Integer, default=0)
    weekly_reports: Mapped[int] = mapped_column(Integer, default=0)
    compatibility: Mapped[int] = mapped_column(Integer, default=0)
    daily_forecasts: Mapped[int] = mapped_column(Integer, default=0)
    mini_readings: Mapped[int] = mapped_column(Integer, default=0)
    date_selections: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user: Mapped["User"] = relationship("User", back_populates="usage_limits")


class Referral(Base):
    __tablename__ = "referrals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    inviter_telegram_id: Mapped[int] = mapped_column(BigInteger, index=True)
    invited_telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    purchase_status: Mapped[bool] = mapped_column(Boolean, default=False)
    reward_given: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class UserActivity(Base):
    """Трекинг активности пользователя для retention push-системы."""
    __tablename__ = "user_activity"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), unique=True, index=True)
    last_activity_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_push_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    push_index: Mapped[int] = mapped_column(Integer, default=0)
    trial_upsell_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class UserReport(Base):
    """История разборов пользователя (прогнозы, совместимости, вопросы и т.д.)."""
    __tablename__ = "user_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), index=True)
    report_type: Mapped[str] = mapped_column(String(50), index=True)
    title: Mapped[str] = mapped_column(String(255))
    short_preview: Mapped[str] = mapped_column(String(400))
    content: Mapped[str] = mapped_column(Text)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user: Mapped["User"] = relationship("User", back_populates="reports")
