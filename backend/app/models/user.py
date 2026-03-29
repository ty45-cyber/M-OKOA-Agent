"""
User ORM model — represents a registered M-Okoa client.
Updated to include:
  - domain_mode (Money in Motion challenge area persona)
  - mpesa_identity_token (Daraja 3.0 Security API — replaces raw MSISDN storage)

Maps to the `users` table.
"""
from sqlalchemy import BigInteger, Boolean, DateTime, Enum, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from datetime import datetime
import enum

from app.core.database import Base


class SubscriptionTier(str, enum.Enum):
    msingi     = "msingi"
    biashara   = "biashara"
    enterprise = "enterprise"


class DomainMode(str, enum.Enum):
    """
    Money in Motion hackathon challenge area personas.
    Controls agent behaviour, tool prioritisation, and dashboard UX.
    """
    merchant  = "merchant"   # Lipa na M-Pesa reconciliation via Transaction Status API
    farmer    = "farmer"     # Crop payout disbursements via B2C API
    student   = "student"    # School fee payments via Bill Pay / STK Push
    community = "community"  # Chama wallet transparency via Account Balance API
    general   = "general"    # Full co-pilot mode — all APIs


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    public_id: Mapped[str] = mapped_column(
        String(26), nullable=False, unique=True,
        comment="ULID for public-facing exposure"
    )
    full_name: Mapped[str] = mapped_column(String(120), nullable=False)

    # ── Phone number ─────────────────────────────────────────
    # For users who register via the web/Telegram → full E.164 number
    # For users who register via the Mini App → masked number e.g. 2547****5678
    # Raw MSISDNs are never stored for Mini App users — Daraja 3.0 compliance
    phone_number: Mapped[str] = mapped_column(
        String(20), nullable=False, unique=True,
        comment="E.164 format or masked for Mini App users"
    )

    email: Mapped[str | None] = mapped_column(
        String(254), unique=True, nullable=True
    )
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    # ── Daraja 3.0 Security API identity token ───────────────
    # Issued when a user authenticates via the M-Pesa Mini App.
    # Stable per user — used as the lookup key for Mini App logins.
    # The raw MSISDN is never returned by the Security API — by design.
    # OWASP A02: Cryptographic Failures — no raw phone stored for Mini App users.
    mpesa_identity_token: Mapped[str | None] = mapped_column(
        String(255), unique=True, nullable=True,
        comment="Daraja 3.0 Security API opaque identity token — no raw MSISDN"
    )

    # ── Linked interfaces ────────────────────────────────────
    telegram_chat_id: Mapped[int | None] = mapped_column(
        BigInteger, unique=True, nullable=True,
        comment="Bound Telegram session — set via /link command or Settings"
    )

    # ── Account state ────────────────────────────────────────
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    is_verified: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False,
        comment="True once phone OTP confirmed or Mini App KYC passed"
    )

    # ── Subscription ─────────────────────────────────────────
    subscription_tier: Mapped[SubscriptionTier] = mapped_column(
        Enum(SubscriptionTier),
        nullable=False,
        default=SubscriptionTier.msingi,
    )

    # ── Money in Motion domain mode ──────────────────────────
    # Drives agent persona, tool priority, and dashboard UX.
    # Changed by the user via the Challenge Areas page or DomainModeSwitcher.
    domain_mode: Mapped[DomainMode] = mapped_column(
        Enum(DomainMode),
        nullable=False,
        default=DomainMode.general,
        comment="Active Money in Motion challenge area — controls agent behaviour"
    )

    # ── Timestamps ───────────────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # ── Relationships ────────────────────────────────────────
    tills: Mapped[list["Till"]] = relationship(
        "Till", back_populates="user", lazy="noload"
    )
    transactions: Mapped[list["Transaction"]] = relationship(
        "Transaction", back_populates="user", lazy="noload"
    )
    tax_locks: Mapped[list["TaxLock"]] = relationship(
        "TaxLock", back_populates="user", lazy="noload"
    )
    sms_inbox: Mapped[list["SmsInbox"]] = relationship(
        "SmsInbox", back_populates="user", lazy="noload"
    )
    agent_sessions: Mapped[list["AgentSession"]] = relationship(
        "AgentSession", back_populates="user", lazy="noload"
    )
    bill_payees: Mapped[list["BillPayee"]] = relationship(
        "BillPayee", back_populates="user", lazy="noload"
    )
    smart_float_rules: Mapped[list["SmartFloatRule"]] = relationship(
        "SmartFloatRule", back_populates="user", lazy="noload"
    )

    def __repr__(self) -> str:
        return (
            f"<User id={self.id} phone={self.phone_number} "
            f"tier={self.subscription_tier} mode={self.domain_mode}>"
        )

    @property
    def is_mini_app_user(self) -> bool:
        """True if this account was created via the M-Pesa Mini App."""
        return self.mpesa_identity_token is not None

    @property
    def display_phone(self) -> str:
        """
        Safe phone number for display in logs and UI.
        Full number for web/Telegram users.
        Already-masked number for Mini App users.
        """
        return self.phone_number