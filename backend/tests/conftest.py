import os
import sys

os.environ["TESTING"] = "1"
import pytest
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Ensure app is importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.database import Base
from app.models.entities import User, Supplier, RFQ, AuctionConfig, RFQInvitation, Bid
from app.models.enums import UserRole, RFQStatus, TriggerType, InvitationStatus
from app.services.auth import hash_password


@pytest.fixture(scope="session")
def db_engine():
    db_url = os.environ.get("TEST_DATABASE_URL")
    if not db_url:
        db_url = os.environ.get("DATABASE_URL")
        if db_url and "meridian_db" in db_url:
            db_url = db_url.replace("meridian_db", "meridian_test_db")

    if db_url and db_url.startswith("postgresql"):
        engine = create_engine(db_url, pool_size=25, max_overflow=10)
    else:
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    return engine


@pytest.fixture(scope="function")
def db_session(db_engine):
    Session = sessionmaker(bind=db_engine)
    session = Session()

    yield session

    session.close()
    with db_engine.connect() as conn:
        with conn.begin():
            if db_engine.dialect.name.startswith("postgresql"):
                conn.execute(text("ALTER TABLE auction_events DISABLE TRIGGER ALL;"))
            for table in reversed(Base.metadata.sorted_tables):
                conn.execute(table.delete())
            if db_engine.dialect.name.startswith("postgresql"):
                conn.execute(text("ALTER TABLE auction_events ENABLE TRIGGER ALL;"))


@pytest.fixture
def buyer_user(db_session):
    user = User(
        email="procurement@meridian-freight.com",
        password_hash=hash_password("MeridianPass2026!"),
        full_name="Eleanor Vance (Head of Logistics)",
        role=UserRole.BUYER.value,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def suppliers(db_session):
    supps = []
    supplier_data = [
        ("Maersk Global Logistics", "MAERSK", "bids@maersk.com"),
        ("Hapag-Lloyd Ocean", "HAPAG", "quotes@hapag-lloyd.com"),
        ("MSC Mediterranean Shipping", "MSC", "rfq@msc.com"),
        ("CMA CGM Logistics", "CMACGM", "ocean@cma-cgm.com"),
        ("Evergreen Marine Corp", "EVERGREEN", "pricing@evergreen.com"),
        ("COSCO Shipping", "COSCO", "commercial@cosco.com"),
        ("ONE Ocean Network Express", "ONE", "rates@one-line.com"),
        ("Kuehne+Nagel Intermodal", "KN", "rfq@kuehne-nagel.com"),
    ]
    for name, code, email in supplier_data:
        s = Supplier(name=name, code=code, contact_email=email, is_active=True)
        db_session.add(s)
        supps.append(s)
    db_session.commit()
    for s in supps:
        db_session.refresh(s)
    return supps


@pytest.fixture
def supplier_users(db_session, suppliers):
    users = []
    for s in suppliers:
        u = User(
            email=s.contact_email,
            password_hash=hash_password("SupplierPass2026!"),
            full_name=f"{s.code} Agent",
            role=UserRole.SUPPLIER.value,
            supplier_id=s.id,
        )
        db_session.add(u)
        users.append(u)
    db_session.commit()
    for u in users:
        db_session.refresh(u)
    return users
