import json
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


def test_endpoints_rfq_patch_invitations_and_suppliers(client, buyer_user, suppliers, supplier_users, db_session):
    # Login buyer
    buyer_login = client.post(
        "/api/v1/auth/login",
        json={"email": buyer_user.email, "password": "MeridianPass2026!"},
    )
    buyer_token = buyer_login.json()["access_token"]
    headers = {"Authorization": f"Bearer {buyer_token}"}

    # 1. Test GET /api/v1/suppliers is buyer-only, and unprefixed /suppliers is 404
    supp_api_resp = client.get("/api/v1/suppliers", headers=headers)
    assert supp_api_resp.status_code == 200
    assert len(supp_api_resp.json()) >= len(suppliers)

    supp_unprefixed = client.get("/suppliers", headers=headers)
    assert supp_unprefixed.status_code == 404

    s0_login = client.post(
        "/api/v1/auth/login",
        json={"email": suppliers[0].contact_email, "password": "SupplierPass2026!"},
    )
    s0_token = s0_login.json()["access_token"]
    supp_forbidden = client.get("/api/v1/suppliers", headers={"Authorization": f"Bearer {s0_token}"})
    assert supp_forbidden.status_code == 403

    # 2. Create SCHEDULED RFQ (future start time)
    now = datetime.now(timezone.utc)
    rfq_payload = {
        "reference_id": f"RFQ-PATCH-{int(now.timestamp())}",
        "title": "Scheduled RFQ for Patch Testing",
        "description": "Test patch and invitation routes",
        "origin": "Rotterdam (NLRTM)",
        "destination": "Singapore (SGSIN)",
        "bid_start": (now + timedelta(hours=2)).isoformat(),
        "bid_close": (now + timedelta(hours=4)).isoformat(),
        "forced_close": (now + timedelta(hours=6)).isoformat(),
        "pickup_date": (now + timedelta(days=20)).isoformat(),
        "trigger_window_minutes": 10,
        "extension_minutes": 5,
        "trigger_type": "L1_CHANGE",
        "bid_visibility": "OPEN",
        "invited_supplier_ids": [suppliers[0].id],
    }
    create_resp = client.post("/api/v1/rfqs", json=rfq_payload, headers=headers)
    assert create_resp.status_code == 201
    rfq_id = create_resp.json()["id"]

    # 3. PATCH /api/v1/rfqs/{id} while SCHEDULED succeeds
    patch_resp = client.patch(
        f"/api/v1/rfqs/{rfq_id}",
        json={"title": "Updated Scheduled RFQ Title", "extension_minutes": 8},
        headers=headers,
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["title"] == "Updated Scheduled RFQ Title"
    assert patch_resp.json()["config"]["extension_minutes"] == 8

    # Test invalid timing revalidation
    bad_forced = client.patch(
        f"/api/v1/rfqs/{rfq_id}",
        json={"forced_close": (now + timedelta(hours=3)).isoformat()},
        headers=headers,
    )
    assert bad_forced.status_code == 400
    assert bad_forced.json()["code"] == "INVALID_TIMING"

    bad_bid_close = client.patch(
        f"/api/v1/rfqs/{rfq_id}",
        json={"bid_close": (now + timedelta(hours=1)).isoformat()},
        headers=headers,
    )
    assert bad_bid_close.status_code == 400
    assert bad_bid_close.json()["code"] == "INVALID_TIMING"

    # 4. Add invitation POST /api/v1/rfqs/{id}/invitations while SCHEDULED
    inv_post_resp = client.post(
        f"/api/v1/rfqs/{rfq_id}/invitations",
        json={"supplier_id": suppliers[1].id},
        headers=headers,
    )
    assert inv_post_resp.status_code == 201
    assert any(inv["supplier_id"] == suppliers[1].id for inv in inv_post_resp.json()["invitations"])

    # 5. Delete invitation DELETE /api/v1/rfqs/{id}/invitations/{supplier_id} while SCHEDULED
    del_inv_resp = client.delete(
        f"/api/v1/rfqs/{rfq_id}/invitations/{suppliers[1].id}",
        headers=headers,
    )
    assert del_inv_resp.status_code == 200
    assert not any(inv["supplier_id"] == suppliers[1].id for inv in del_inv_resp.json()["invitations"])

    # 6. Reject edits in ACTIVE, CLOSED, and FORCE_CLOSED
    rfq_obj = db_session.query(RFQ).filter(RFQ.id == rfq_id).first()
    for locked_status in ["ACTIVE", "CLOSED", "FORCE_CLOSED"]:
        rfq_obj.status = locked_status
        db_session.commit()
        locked_patch = client.patch(f"/api/v1/rfqs/{rfq_id}", json={"title": "Hacked"}, headers=headers)
        assert locked_patch.status_code == 400
        assert locked_patch.json()["code"] == "RFQ_LOCKED"


def test_bid_visibility_masked_payloads(client, buyer_user, suppliers, supplier_users):
    # Login buyer
    buyer_login = client.post(
        "/api/v1/auth/login",
        json={"email": buyer_user.email, "password": "MeridianPass2026!"},
    )
    buyer_token = buyer_login.json()["access_token"]

    # Login supplier 0
    s0_login = client.post(
        "/api/v1/auth/login",
        json={"email": suppliers[0].contact_email, "password": "SupplierPass2026!"},
    )
    s0_token = s0_login.json()["access_token"]

    # Login supplier 1
    s1_login = client.post(
        "/api/v1/auth/login",
        json={"email": suppliers[1].contact_email, "password": "SupplierPass2026!"},
    )
    s1_token = s1_login.json()["access_token"]

    now = datetime.now(timezone.utc)
    rfq_payload = {
        "reference_id": f"RFQ-MASKED-{int(now.timestamp())}",
        "title": "Masked Auction Confidential RFQ",
        "origin": "Busan (KRPUS)",
        "destination": "Los Angeles (USLAX)",
        "bid_start": (now - timedelta(hours=1)).isoformat(),
        "bid_close": (now + timedelta(hours=2)).isoformat(),
        "forced_close": (now + timedelta(hours=3)).isoformat(),
        "pickup_date": (now + timedelta(days=15)).isoformat(),
        "trigger_window_minutes": 10,
        "extension_minutes": 5,
        "trigger_type": "L1_CHANGE",
        "bid_visibility": "MASKED",
        "invited_supplier_ids": [suppliers[0].id, suppliers[1].id],
    }

    create_resp = client.post(
        "/api/v1/rfqs",
        json=rfq_payload,
        headers={"Authorization": f"Bearer {buyer_token}"},
    )
    assert create_resp.status_code == 201
    rfq_id = create_resp.json()["id"]

    # Supplier 0 places bid $2000 (L1)
    s0_bid_resp = client.post(
        f"/api/v1/rfqs/{rfq_id}/bids",
        json={
            "freight_charges": 1800.00,
            "origin_charges": 100.00,
            "destination_charges": 100.00,
            "transit_time_days": 14,
            "quote_validity_date": (now + timedelta(days=20)).isoformat(),
            "carrier_name": "Maersk Confidential",
        },
        headers={"Authorization": f"Bearer {s0_token}"},
    )
    assert s0_bid_resp.status_code == 201

    # Supplier 1 places bid $2200 (Rank 2)
    s1_bid_resp = client.post(
        f"/api/v1/rfqs/{rfq_id}/bids",
        json={
            "freight_charges": 2000.00,
            "origin_charges": 100.00,
            "destination_charges": 100.00,
            "transit_time_days": 16,
            "quote_validity_date": (now + timedelta(days=20)).isoformat(),
            "carrier_name": "Hapag Confidential",
        },
        headers={"Authorization": f"Bearer {s1_token}"},
    )
    assert s1_bid_resp.status_code == 201

    # 1. Supplier 1 fetches RFQ:
    # Supplier 1 is rank 2. Rival Supplier 0 is L1 (total $2000).
    # Supplier 1 must see:
    # - Their own rank 2 with unmasked amounts ($2200)
    # - L1 leader with L1 price ($2000), but carrier name and supplier name MASKED
    # - Supplier 1 must NEVER see rival breakdown charges or rival carrier name
    s1_rfq_resp = client.get(
        f"/api/v1/rfqs/{rfq_id}",
        headers={"Authorization": f"Bearer {s1_token}"},
    )
    assert s1_rfq_resp.status_code == 200
    s1_rfq_data = s1_rfq_resp.json()
    rankings = s1_rfq_data["rankings"]
    assert len(rankings) == 2

    # Check L1 rival from Supplier 1's perspective:
    l1 = rankings[0]
    assert l1["rank"] == 1
    assert float(l1["total"]) == 2000.00  # L1 price visible
    assert "Maersk" not in l1["supplier_name"]  # Name masked
    assert l1["carrier_name"] == "Masked Carrier"  # Carrier masked
    assert l1["freight_charges"] is None  # Rival breakdown hidden

    # Check Supplier 1's own rank:
    my_rank = rankings[1]
    assert my_rank["supplier_id"] == suppliers[1].id
    assert float(my_rank["total"]) == 2200.00
    assert my_rank["carrier_name"] == "Hapag Confidential"

    # 2. Supplier 1 lists bids: should ONLY contain Supplier 1's bids
    bids_resp = client.get(
        f"/api/v1/rfqs/{rfq_id}/bids",
        headers={"Authorization": f"Bearer {s1_token}"},
    )
    assert bids_resp.status_code == 200
    supplier_bids = bids_resp.json()
    assert len(supplier_bids) == 1
    assert supplier_bids[0]["supplier_id"] == suppliers[1].id

    # 3. Supplier 1 checks /events: rival events must be sanitized (zero leaks of carrier name, breakdown)
    events_resp = client.get(
        f"/api/v1/rfqs/{rfq_id}/events",
        headers={"Authorization": f"Bearer {s1_token}"},
    )
    assert events_resp.status_code == 200
    events_text = events_resp.text
    assert "Maersk Confidential" not in events_text
    for ev in events_resp.json():
        if ev.get("payload"):
            p = ev["payload"]
            assert "freight_charges" not in p or p.get("supplier_id") == suppliers[1].id or p.get("freight_charges") is None
            assert "carrier_name" not in p or p.get("supplier_id") == suppliers[1].id or p.get("carrier_name") == "Masked Carrier"

    # 4. Supplier 1 checks /export-csv: must ONLY contain Supplier 1's own bids, never rival bids
    csv_resp = client.get(
        f"/api/v1/rfqs/{rfq_id}/export-csv",
        headers={"Authorization": f"Bearer {s1_token}"},
    )
    assert csv_resp.status_code == 200
    assert "Maersk Confidential" not in csv_resp.text
    assert "Hapag Confidential" in csv_resp.text

    # 5. Capture WebSocket messages for Supplier 1 and verify ZERO rival leaks
    # Get a single-use ws-ticket for Supplier 1
    s1_ticket_resp = client.post(
        "/api/v1/auth/ws-ticket",
        headers={"Authorization": f"Bearer {s1_token}"},
    )
    assert s1_ticket_resp.status_code == 200
    s1_ws_ticket = s1_ticket_resp.json()["ticket"]

    with client.websocket_connect(f"/api/v1/ws/rfqs/{rfq_id}?ticket={s1_ws_ticket}") as ws:
        # Initial clock sync message
        sync_msg = ws.receive_json(mode="text")
        assert sync_msg.get("event_type") == "CLOCK_SYNC"

        # Supplier 0 places a lower bid $1900 (triggering BID_SUBMITTED, L1_CHANGED, etc.)
        s0_bid_resp2 = client.post(
            f"/api/v1/rfqs/{rfq_id}/bids",
            json={
                "freight_charges": 1700.00,
                "origin_charges": 100.00,
                "destination_charges": 100.00,
                "transit_time_days": 13,
                "quote_validity_date": (now + timedelta(days=20)).isoformat(),
                "carrier_name": "Maersk Confidential",
            },
            headers={"Authorization": f"Bearer {s0_token}"},
        )
        assert s0_bid_resp2.status_code == 201

        # Read broadcast messages sent to Supplier 1
        received_messages = []
        for _ in range(2):
            msg = ws.receive_json(mode="text")
            received_messages.append(msg)

        assert len(received_messages) > 0
        for msg in received_messages:
            msg_str = json.dumps(msg)
            # ZERO rival carrier leaks anywhere in any message payload or notification text
            assert "Maersk Confidential" not in msg_str
            data = msg.get("data", {})
            if msg.get("event_type") == "BID_SUBMITTED":
                assert data.get("carrier_name") == "Masked Carrier"
                assert data.get("freight_charges") is None
                assert data.get("total") is None
            elif msg.get("event_type") == "L1_CHANGED":
                assert data.get("new_l1_supplier_id") == "competitor"
                assert "Maersk" not in data.get("notification_text", "")
            elif msg.get("event_type") == "RANK_CHANGED":
                assert "previous_ranks" in data
                assert "Maersk" not in data.get("notification_text", "")
            elif msg.get("event_type") == "NEW_BID":
                assert data.get("carrier_name") == "Masked Carrier"
                assert data.get("freight_charges") is None

    # 6. Buyer fetches RFQ: sees completely UNMASKED data
    buyer_rfq_resp = client.get(
        f"/api/v1/rfqs/{rfq_id}",
        headers={"Authorization": f"Bearer {buyer_token}"},
    )
    buyer_rankings = buyer_rfq_resp.json()["rankings"]
    assert "Maersk" in buyer_rankings[0]["supplier_name"]
    assert buyer_rankings[0]["carrier_name"] == "Maersk Confidential"


def test_ws_ticket_and_first_message_auth(client, buyer_user, suppliers):
    import pytest
    from starlette.websockets import WebSocketDisconnect
    from app.services.auth import create_access_token

    # Login buyer
    buyer_login = client.post(
        "/api/v1/auth/login",
        json={"email": buyer_user.email, "password": "MeridianPass2026!"},
    )
    buyer_token = buyer_login.json()["access_token"]

    now = datetime.now(timezone.utc)
    rfq_resp = client.post(
        "/api/v1/rfqs",
        json={
            "reference_id": f"RFQ-WS-{int(now.timestamp())}",
            "title": "WebSocket Ticket Test RFQ",
            "origin": "Rotterdam (NLRTM)",
            "destination": "Singapore (SGSIN)",
            "bid_start": (now - timedelta(hours=1)).isoformat(),
            "bid_close": (now + timedelta(hours=2)).isoformat(),
            "forced_close": (now + timedelta(hours=3)).isoformat(),
            "pickup_date": (now + timedelta(days=10)).isoformat(),
            "trigger_window_minutes": 10,
            "extension_minutes": 5,
            "trigger_type": "L1_CHANGE",
            "invited_supplier_ids": [suppliers[0].id],
        },
        headers={"Authorization": f"Bearer {buyer_token}"},
    )
    rfq_id = rfq_resp.json()["id"]

    # 1. Request short-lived ticket
    ticket_resp = client.post(
        "/api/v1/auth/ws-ticket",
        headers={"Authorization": f"Bearer {buyer_token}"},
    )
    assert ticket_resp.status_code == 200
    ticket_data = ticket_resp.json()
    assert "ticket" in ticket_data
    assert ticket_data["expires_in"] == 60
    single_ticket = ticket_data["ticket"]

    # 2. Connect with ticket - first use succeeds
    with client.websocket_connect(f"/api/v1/ws/rfqs/{rfq_id}?ticket={single_ticket}") as ws:
        pass

    # 3. Single-use enforcement: re-using the exact same ticket MUST fail (closed with code 4001)
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect(f"/api/v1/ws/rfqs/{rfq_id}?ticket={single_ticket}") as ws2:
            ws2.receive_text()
    assert exc_info.value.code == 4001

    # 4. Confirm query-string ?token= auth is gone (does not authenticate via query param)
    with pytest.raises(WebSocketDisconnect) as exc_info_token:
        with client.websocket_connect(f"/api/v1/ws/rfqs/{rfq_id}?token={buyer_token}") as ws3:
            # Server does not authenticate query ?token=, expects AUTH message or closes with 4001
            ws3.send_text(json.dumps({"action": "PING"}))
            ws3.receive_text()
    assert exc_info_token.value.code == 4001

    # 5. Expired ticket fails after expiry (>60s)
    expired_ticket = create_access_token(
        data={"sub": buyer_user.id, "email": buyer_user.email, "role": "buyer", "ticket": True, "jti": "expired-jti"},
        expires_delta=timedelta(seconds=-10),
    )
    with pytest.raises(WebSocketDisconnect) as exc_info_exp:
        with client.websocket_connect(f"/api/v1/ws/rfqs/{rfq_id}?ticket={expired_ticket}") as ws4:
            ws4.receive_text()
    assert exc_info_exp.value.code == 4001


def test_rate_limiting_returns_429(client, buyer_user):
    headers = {"X-Test-Rate-Limit": "3", "X-Test-Client-Id": "rate-limit-tester-ip"}
    # First 3 requests succeed
    for _ in range(3):
        r = client.get("/api/v1/suppliers", headers=headers)
        assert r.status_code in [200, 401]

    # 4th request exceeds rate limit and returns 429
    r_throttled = client.get("/api/v1/suppliers", headers=headers)
    assert r_throttled.status_code == 429
    data = r_throttled.json()
    assert data["code"] == "RATE_LIMIT_EXCEEDED"
    assert "Retry-After" in r_throttled.headers

    # Normal browsing (listing RFQs, live room) does not trigger 429 under reasonable usage
    browse_headers = {"X-Test-Client-Id": "normal-browser-ip"}
    for _ in range(10):
        r_browse = client.get("/api/v1/rfqs", headers=browse_headers)
        assert r_browse.status_code in [200, 401]
    assert "Retry-After" in r_throttled.headers


def test_cors_headers_and_jwt_expiry(client, buyer_user):
    from app.services.auth import create_access_token
    # 1. CORS headers check
    cors_resp = client.options(
        "/api/v1/suppliers",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert cors_resp.status_code == 200
    assert cors_resp.headers.get("access-control-allow-origin") in ["http://localhost:5173", "*"]

    # 2. Expired JWT token returns 401
    expired_token = create_access_token(
        data={"sub": buyer_user.id, "email": buyer_user.email, "role": "buyer"},
        expires_delta=timedelta(seconds=-10),  # expired in past
    )
    unauth_resp = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {expired_token}"},
    )
    assert unauth_resp.status_code == 401


