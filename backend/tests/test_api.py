import pytest
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from fastapi.testclient import TestClient

from app.main import app
from app.database import Base, get_db
from app.models.entities import User, Supplier, RFQ, AuctionConfig, RFQInvitation, Bid
from app.models.enums import UserRole, RFQStatus, TriggerType
from app.services.auth import hash_password


@pytest.fixture
def client(db_session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_auth_and_profile_flow(client, db_session):
    # 1. Register a buyer
    resp = client.post(
        "/api/v1/auth/register",
        json={
            "email": "testbuyer@meridian.com",
            "password": "SecurePassword123!",
            "full_name": "Test Logistics Director",
            "role": "buyer",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    token = data["access_token"]
    assert token is not None
    assert data["user"]["email"] == "testbuyer@meridian.com"
    assert data["user"]["role"] == "buyer"

    # 2. Access /auth/me with bearer token
    me_resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_resp.status_code == 200
    assert me_resp.json()["email"] == "testbuyer@meridian.com"

    # 3. Login with registered credentials
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": "testbuyer@meridian.com", "password": "SecurePassword123!"},
    )
    assert login_resp.status_code == 200
    assert "access_token" in login_resp.json()


def test_rfq_creation_and_role_access(client, buyer_user, suppliers, supplier_users):
    # Login buyer
    buyer_login = client.post(
        "/api/v1/auth/login",
        json={"email": buyer_user.email, "password": "MeridianPass2026!"},
    )
    buyer_token = buyer_login.json()["access_token"]

    # Login supplier
    supplier_login = client.post(
        "/api/v1/auth/login",
        json={"email": suppliers[0].contact_email, "password": "SupplierPass2026!"},
    )
    supplier_token = supplier_login.json()["access_token"]

    now = datetime.now(timezone.utc)
    rfq_payload = {
        "reference_id": f"RFQ-API-{int(now.timestamp())}",
        "title": "API Automated Test RFQ",
        "description": "Direct container freight from Qingdao to Hamburg",
        "origin": "Qingdao (CNTAO)",
        "destination": "Hamburg (DEHAM)",
        "bid_start": (now - timedelta(hours=1)).isoformat(),
        "bid_close": (now + timedelta(hours=2)).isoformat(),
        "forced_close": (now + timedelta(hours=3)).isoformat(),
        "pickup_date": (now + timedelta(days=10)).isoformat(),
        "trigger_window_minutes": 10,
        "extension_minutes": 5,
        "trigger_type": "L1_CHANGE",
        "invited_supplier_ids": [suppliers[0].id],
    }

    # 1. Supplier cannot create RFQ (forbidden)
    forbidden_resp = client.post(
        "/api/v1/rfqs",
        json=rfq_payload,
        headers={"Authorization": f"Bearer {supplier_token}"},
    )
    assert forbidden_resp.status_code == 403

    # 2. Buyer creates RFQ
    create_resp = client.post(
        "/api/v1/rfqs",
        json=rfq_payload,
        headers={"Authorization": f"Bearer {buyer_token}"},
    )
    assert create_resp.status_code == 201
    created_rfq = create_resp.json()
    rfq_id = created_rfq["id"]
    assert created_rfq["reference_id"] == rfq_payload["reference_id"]
    assert created_rfq["status"] == "ACTIVE"

    # 3. Supplier submits bid on invited RFQ
    bid_payload = {
        "freight_charges": 2200.00,
        "origin_charges": 150.00,
        "destination_charges": 250.00,
        "transit_time_days": 21,
        "quote_validity_date": (now + timedelta(days=15)).isoformat(),
        "carrier_name": "Test Ocean Carrier",
    }
    bid_resp = client.post(
        f"/api/v1/rfqs/{rfq_id}/bids",
        json=bid_payload,
        headers={"Authorization": f"Bearer {supplier_token}"},
    )
    assert bid_resp.status_code == 201
    bid_data = bid_resp.json()
    assert float(bid_data["total"]) == 2600.00
    assert bid_data["rank"] == 1

    # 4. Supplier tries to submit a non-lower bid -> 400 BID_NOT_LOWER
    bid_higher_payload = {
        "freight_charges": 2500.00,
        "origin_charges": 150.00,
        "destination_charges": 250.00,
        "transit_time_days": 21,
        "quote_validity_date": (now + timedelta(days=15)).isoformat(),
        "carrier_name": "Test Ocean Carrier",
    }
    bad_bid_resp = client.post(
        f"/api/v1/rfqs/{rfq_id}/bids",
        json=bid_higher_payload,
        headers={"Authorization": f"Bearer {supplier_token}"},
    )
    assert bad_bid_resp.status_code == 400
    err = bad_bid_resp.json()
    assert err["code"] == "BID_NOT_LOWER"

