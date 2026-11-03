"""VK identities and durable commerce; Telegram identifiers stay separate."""
from datetime import datetime, timezone
from sqlalchemy import BigInteger, String, Integer, ForeignKey, JSON, DateTime, Boolean, Text
from sqlalchemy.orm import Mapped, mapped_column
from database.base import Base


def utcnow():
    return datetime.now(timezone.utc)


class VKAccount(Base):
    __tablename__ = "vk_accounts"
    vk_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    state: Mapped[str] = mapped_column(String(50), default="menu")
    data: Mapped[dict] = mapped_column(JSON, default=dict)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    manual_support: Mapped[bool] = mapped_column(Boolean, default=False)
    referrer_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class VKOrder(Base):
    __tablename__ = "vk_orders"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    vk_id: Mapped[int] = mapped_column(BigInteger, index=True)
    product: Mapped[str] = mapped_column(String(40))
    amount: Mapped[int] = mapped_column(Integer)
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="draft")
    payment_id: Mapped[str | None] = mapped_column(String(100), unique=True, nullable=True)
    checkout_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    report_id: Mapped[int | None] = mapped_column(ForeignKey("user_reports.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class VKInbox(Base):
    __tablename__ = "vk_inbox"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_key: Mapped[str] = mapped_column(String(160), unique=True)
    vk_id: Mapped[int] = mapped_column(BigInteger, index=True)
    message: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class VKOutbox(Base):
    __tablename__ = "vk_outbox"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(200), unique=True)
    vk_id: Mapped[int] = mapped_column(BigInteger, index=True)
    body: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class VKReferralReward(Base):
    __tablename__ = "vk_referral_rewards"
    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    vk_id: Mapped[int] = mapped_column(BigInteger, index=True)
    threshold: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
