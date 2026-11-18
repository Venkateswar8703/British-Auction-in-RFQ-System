import uuid
from decimal import Decimal
from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    String,
    Text,
    DateTime,
    Numeric,
    Integer,
    Boolean,
    ForeignKey,
    CheckConstraint,
    UniqueConstraint,
    Index,
    JSON,
)
from sqlalchemy.types import TypeDecorator
from sqlalchemy.orm import relationship
from app.database import Base
from app.models.enums import UserRole, RFQStatus, TriggerType, BidVisibility, InvitationStatus, AuctionEventType


class TZDateTime(TypeDecorator):
    """Ensures datetimes are always timezone-aware UTC across SQLite and PostgreSQL."""
    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None:
            if value.tzinfo is None:
                value = value.replace(tzinfo=timezone.utc)
            else:
                value = value.astimezone(timezone.utc)
        return value

    def process_result_value(self, value, dialect):
        if value is not None and value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value


def generate_uuid() -> str:
    return str(uuid.uuid4())


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False, default=UserRole.BUYER.value)
    supplier_id = Column(String(36), ForeignKey("suppliers.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(TZDateTime, default=utc_now, nullable=False)
    updated_at = Column(TZDateTime, default=utc_now, onupdate=utc_now, nullable=False)

    supplier = relationship("Supplier", back_populates="users")
    rfqs_created = relationship("RFQ", back_populates="creator")
    bids = relationship("Bid", back_populates="submitter")


class Supplier(Base):
    __tablename__ = "suppliers"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(255), unique=True, nullable=False)
    code = Column(String(50), unique=True, nullable=False, index=True)
    contact_email = Column(String(255), nullable=False)
    contact_phone = Column(String(50), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(TZDateTime, default=utc_now, nullable=False)
    updated_at = Column(TZDateTime, default=utc_now, onupdate=utc_now, nullable=False)

    users = relationship("User", back_populates="supplier")
    invitations = relationship("RFQInvitation", back_populates="supplier")
    bids = relationship("Bid", back_populates="supplier")


class RFQ(Base):
    __tablename__ = "rfqs"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    reference_id = Column(String(64), unique=True, nullable=False, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    origin = Column(String(255), nullable=False)
    destination = Column(String(255), nullable=False)
    pickup_date = Column(TZDateTime, nullable=False)
    bid_start = Column(TZDateTime, nullable=False)
    bid_close = Column(TZDateTime, nullable=False)
    effective_close = Column(TZDateTime, nullable=False)
    forced_close = Column(TZDateTime, nullable=False)
    status = Column(String(20), nullable=False, default=RFQStatus.SCHEDULED.value)
    created_by = Column(String(36), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    created_at = Column(TZDateTime, default=utc_now, nullable=False)
    updated_at = Column(TZDateTime, default=utc_now, onupdate=utc_now, nullable=False)

    __table_args__ = (
        CheckConstraint("forced_close > bid_close", name="chk_forced_close_gt_bid_close"),
        CheckConstraint("bid_close > bid_start", name="chk_bid_close_gt_bid_start"),
        CheckConstraint("pickup_date > bid_close", name="chk_pickup_date_gt_bid_close"),
        Index("idx_rfqs_status_effective", "status", "effective_close"),
    )

    creator = relationship("User", back_populates="rfqs_created")
    config = relationship("AuctionConfig", back_populates="rfq", uselist=False, cascade="all, delete-orphan")
    invitations = relationship("RFQInvitation", back_populates="rfq", cascade="all, delete-orphan")
    bids = relationship("Bid", back_populates="rfq", cascade="all, delete-orphan", order_by="Bid.created_at.desc()")
    events = relationship("AuctionEvent", back_populates="rfq", cascade="all, delete-orphan", order_by="AuctionEvent.created_at.asc()")
    extensions = relationship("AuctionExtension", back_populates="rfq", cascade="all, delete-orphan", order_by="AuctionExtension.created_at.asc()")


class AuctionConfig(Base):
    __tablename__ = "auction_configs"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    rfq_id = Column(String(36), ForeignKey("rfqs.id", ondelete="CASCADE"), unique=True, nullable=False)
    trigger_window_minutes = Column(Integer, nullable=False, default=10)
    extension_minutes = Column(Integer, nullable=False, default=5)
    trigger_type = Column(String(30), nullable=False, default=TriggerType.L1_CHANGE.value)
    bid_visibility = Column(String(20), nullable=False, default=BidVisibility.OPEN.value)
    min_decrement = Column(Numeric(12, 2), nullable=True, default=Decimal("0.00"))
    created_at = Column(TZDateTime, default=utc_now, nullable=False)
    updated_at = Column(TZDateTime, default=utc_now, onupdate=utc_now, nullable=False)

    __table_args__ = (
        CheckConstraint("trigger_window_minutes > 0", name="chk_trigger_window_pos"),
        CheckConstraint("extension_minutes > 0", name="chk_extension_minutes_pos"),
    )

    rfq = relationship("RFQ", back_populates="config")


class RFQInvitation(Base):
    __tablename__ = "rfq_invitations"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    rfq_id = Column(String(36), ForeignKey("rfqs.id", ondelete="CASCADE"), nullable=False)
    supplier_id = Column(String(36), ForeignKey("suppliers.id", ondelete="CASCADE"), nullable=False)
    status = Column(String(20), nullable=False, default=InvitationStatus.INVITED.value)
    created_at = Column(TZDateTime, default=utc_now, nullable=False)

    __table_args__ = (
        UniqueConstraint("rfq_id", "supplier_id", name="uq_rfq_supplier_invitation"),
        Index("idx_invitations_rfq", "rfq_id"),
        Index("idx_invitations_supplier", "supplier_id"),
    )

    rfq = relationship("RFQ", back_populates="invitations")
    supplier = relationship("Supplier", back_populates="invitations")


class Bid(Base):
    __tablename__ = "bids"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    rfq_id = Column(String(36), ForeignKey("rfqs.id", ondelete="CASCADE"), nullable=False)
    supplier_id = Column(String(36), ForeignKey("suppliers.id", ondelete="CASCADE"), nullable=False)
    submitted_by = Column(String(36), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    freight_charges = Column(Numeric(12, 2), nullable=False)
    origin_charges = Column(Numeric(12, 2), nullable=False)
    destination_charges = Column(Numeric(12, 2), nullable=False)
    total = Column(Numeric(12, 2), nullable=False)
    transit_time_days = Column(Integer, nullable=False)
    quote_validity_date = Column(TZDateTime, nullable=False)
    carrier_name = Column(String(255), nullable=False)
    idempotency_key = Column(String(128), unique=True, nullable=True, index=True)
    created_at = Column(TZDateTime, default=utc_now, nullable=False)

    __table_args__ = (
        CheckConstraint("freight_charges > 0", name="chk_freight_pos"),
        CheckConstraint("origin_charges >= 0", name="chk_origin_non_neg"),
        CheckConstraint("destination_charges >= 0", name="chk_destination_non_neg"),
        CheckConstraint("total > 0", name="chk_total_pos"),
        CheckConstraint("transit_time_days > 0", name="chk_transit_pos"),
        Index("idx_bids_rfq_created", "rfq_id", "created_at"),
        Index("idx_bids_rfq_total", "rfq_id", "total"),
        Index("idx_bids_supplier_rfq", "supplier_id", "rfq_id", "created_at"),
    )

    rfq = relationship("RFQ", back_populates="bids")
    supplier = relationship("Supplier", back_populates="bids")
    submitter = relationship("User", back_populates="bids")
    extension_triggered = relationship("AuctionExtension", back_populates="triggering_bid", uselist=False)
    events = relationship("AuctionEvent", back_populates="bid")


class AuctionExtension(Base):
    __tablename__ = "auction_extensions"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    rfq_id = Column(String(36), ForeignKey("rfqs.id", ondelete="CASCADE"), nullable=False)
    triggering_bid_id = Column(String(36), ForeignKey("bids.id", ondelete="SET NULL"), nullable=True)
    previous_close = Column(TZDateTime, nullable=False)
    new_close = Column(TZDateTime, nullable=False)
    trigger_type = Column(String(30), nullable=False)
    reason = Column(Text, nullable=False)
    is_clamped = Column(Boolean, nullable=False, default=False)
    created_at = Column(TZDateTime, default=utc_now, nullable=False)

    __table_args__ = (
        Index("idx_extensions_rfq", "rfq_id", "created_at"),
    )

    rfq = relationship("RFQ", back_populates="extensions")
    triggering_bid = relationship("Bid", back_populates="extension_triggered")


class AuctionEvent(Base):
    __tablename__ = "auction_events"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    rfq_id = Column(String(36), ForeignKey("rfqs.id", ondelete="CASCADE"), nullable=False)
    bid_id = Column(String(36), ForeignKey("bids.id", ondelete="SET NULL"), nullable=True)
    event_type = Column(String(50), nullable=False)
    payload = Column(JSON, nullable=False)
    created_at = Column(TZDateTime, default=utc_now, nullable=False)

    __table_args__ = (
        Index("idx_auction_events_rfq_created", "rfq_id", "created_at"),
    )

    rfq = relationship("RFQ", back_populates="events")
    bid = relationship("Bid", back_populates="events")

