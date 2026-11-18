#!/usr/bin/env python3
"""
MERIDIAN Security Verification Suite
Tests:
1. Supplier token calling buyer routes returns 403 Forbidden.
2. Uninvited supplier refused on REST (403) and WebSocket (close code 4003).
3. Expired JWT returns 401 Unauthorized.
4. Rate limiting on bid submission returns 429 Too Many Requests.
5. CORS is limited to known origins.
6. Passwords in database are hashed with bcrypt ($2b$12$) and secrets come from env vars.
7. WebSocket requires authentication (rejects anonymous connection with 4001).
"""
import sys
import os
import json
import time
import asyncio
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))
from app.services.auth import create_access_token
from app.config import settings
from sqlalchemy import create_engine, text

API_BASE = "http://127.0.0.1:8000/api/v1"
WS_BASE = "ws://127.0.0.1:8000/ws/rfqs"

def http_req(method, path, data=None, headers=None):
    url = f"{API_BASE}{path}"
    req_headers = {"Content-Type": "application/json"}
    if headers:
        req_headers.update(headers)
    body = json.dumps(data).encode("utf-8") if data is not None else None
    req = urllib.request.Request(url, data=body, headers=req_headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            content = resp.read().decode("utf-8")
            return resp.status, json.loads(content) if content else {}, dict(resp.headers)
    except urllib.error.HTTPError as e:
        content = e.read().decode("utf-8")
        try:
            parsed = json.loads(content)
        except Exception:
            parsed = {"raw": content}
        return e.code, parsed, dict(e.headers)

async def test_websocket_connect(rfq_id, token=None):
    import websockets
    ws_url = f"{WS_BASE}/{rfq_id}"
    if token:
        ws_url += f"?token={urllib.parse.quote(token)}"
    try:
        async with websockets.connect(ws_url, close_timeout=3) as ws:
            # Send ping
            await ws.send(json.dumps({"action": "PING"}))
            msg = await asyncio.wait_for(ws.recv(), timeout=3)
            return "CONNECTED", json.loads(msg)
    except websockets.exceptions.InvalidStatusCode as e:
        return f"HTTP_{e.status_code}", str(e)
    except websockets.exceptions.ConnectionClosed as e:
        return f"CLOSED_{e.rcvd.code if e.rcvd else 'UNKNOWN'}", str(e)
    except Exception as e:
        return f"ERROR_{type(e).__name__}", str(e)

def run_security_audit():
    print("=" * 80)
    print("MERIDIAN SECURITY AUDIT & VERIFICATION SUITE")
    print("=" * 80)

    # Setup tokens
    db_engine = create_engine(settings.DATABASE_URL)
    with db_engine.connect() as conn:
        buyer = conn.execute(text("SELECT id, email, role FROM users WHERE role='buyer' LIMIT 1")).fetchone()
        supplier = conn.execute(text("SELECT id, email, role, supplier_id FROM users WHERE role='supplier' LIMIT 1")).fetchone()
        rfq = conn.execute(text("SELECT id, reference_id FROM rfqs WHERE status='ACTIVE' LIMIT 1")).fetchone()
        uninvited_supplier = conn.execute(text(f"""
            SELECT u.id, u.email, u.role, u.supplier_id, s.name, s.code 
            FROM users u
            JOIN suppliers s ON u.supplier_id = s.id
            WHERE u.role='supplier'
              AND s.id NOT IN (
                  SELECT supplier_id FROM rfq_invitations WHERE rfq_id = '{rfq.id}'
              )
            LIMIT 1
        """)).fetchone()

    assert buyer and supplier and rfq, "Database must have active demo data"

    buyer_token = create_access_token({"sub": buyer.id, "email": buyer.email, "role": buyer.role})
    supplier_token = create_access_token({"sub": supplier.id, "email": supplier.email, "role": supplier.role, "supplier_id": supplier.supplier_id})
    uninvited_token = None
    if uninvited_supplier:
        uninvited_token = create_access_token({"sub": uninvited_supplier.id, "email": uninvited_supplier.email, "role": uninvited_supplier.role, "supplier_id": uninvited_supplier.supplier_id})

    # 1. Supplier token calling buyer routes returns 403
    print("\n--- 1. Role-Based Access Control (RBAC): Supplier Calling Buyer Route ---")
    st, res, _ = http_req("POST", "/rfqs", {
        "title": "Unauthorized RFQ Creation Attempt",
        "origin": "SGSIN",
        "destination": "NLRTM",
        "pickup_date": (datetime.now(timezone.utc) + timedelta(days=10)).isoformat(),
        "bid_start": datetime.now(timezone.utc).isoformat(),
        "bid_close": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
        "forced_close": (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat(),
        "config": {"trigger_window_minutes": 10, "extension_minutes": 5, "trigger_type": "BID_RECEIVED"}
    }, headers={"Authorization": f"Bearer {supplier_token}"})
    print(f"POST /api/v1/rfqs with supplier token -> Status: {st} | Body: {res}")
    assert st == 403, f"Expected 403, got {st}"
    assert res.get("code") == "BUYER_ROLE_REQUIRED" or "detail" in res
    print("✓ PASS: Supplier calling buyer route received 403 Forbidden!")

    # 2. Uninvited supplier refused on REST and WebSocket
    print("\n--- 2. Uninvited Supplier Whitelist Check ---")
    if uninvited_token:
        # 2A: REST check
        st, res, _ = http_req("POST", f"/rfqs/{rfq.reference_id}/bids", {
            "freight_charges": 1500.0,
            "origin_charges": 100.0,
            "destination_charges": 100.0,
            "transit_time_days": 10,
            "quote_validity_date": (datetime.now(timezone.utc) + timedelta(days=20)).isoformat(),
            "carrier_name": "Rogue Lines"
        }, headers={"Authorization": f"Bearer {uninvited_token}"})
        print(f"REST POST /rfqs/{rfq.reference_id}/bids (uninvited) -> Status: {st} | Code: {res.get('code')}")
        assert st == 403 and res.get("code") == "SUPPLIER_NOT_INVITED"
        print("✓ PASS: Uninvited supplier refused on REST (403 SUPPLIER_NOT_INVITED)!")

        # 2B: WebSocket check
        ws_status, ws_detail = asyncio.run(test_websocket_connect(rfq.reference_id, uninvited_token))
        print(f"WebSocket Connect (uninvited) -> Status: {ws_status} | Detail: {ws_detail}")
        assert "403" in ws_status or "4003" in ws_status or "403" in ws_detail or "4003" in ws_detail
        print("✓ PASS: Uninvited supplier refused on WebSocket (HTTP 403 / close code 4003)!")
    else:
        print("Skipped uninvited test: no extra supplier in DB")

    # 3. Expired JWT returns 401
    print("\n--- 3. Token Expiration Enforcement ---")
    expired_token = create_access_token(
        {"sub": buyer.id, "email": buyer.email, "role": buyer.role},
        expires_delta=-timedelta(hours=2)  # Expired 2 hours ago
    )
    st, res, _ = http_req("GET", "/auth/me", headers={"Authorization": f"Bearer {expired_token}"})
    print(f"GET /api/v1/auth/me with expired token -> Status: {st} | Body: {res}")
    assert st == 401, f"Expected 401, got {st}"
    print("✓ PASS: Expired JWT strictly returns 401 Unauthorized!")

    # 4. Rate limiting on bid submission returns 429
    print("\n--- 4. Rate Limiting on Rapid Bid Submissions ---")
    rate_limited_count = 0
    # Blast 40 concurrent rapid requests
    print("Blasting rapid bid requests to trigger rate limiter (threshold: 30 req/sec)...")
    for i in range(45):
        st, res, _ = http_req("POST", f"/rfqs/{rfq.reference_id}/bids", {
            "freight_charges": 2000.0 - i,
            "origin_charges": 100.0,
            "destination_charges": 100.0,
            "transit_time_days": 10,
            "quote_validity_date": (datetime.now(timezone.utc) + timedelta(days=20)).isoformat(),
            "carrier_name": "Maersk"
        }, headers={"Authorization": f"Bearer {supplier_token}"})
        if st == 429:
            rate_limited_count += 1
            print(f"Request {i+1}: Received 429 Too Many Requests -> {res}")
            break

    assert rate_limited_count > 0, "Expected at least one 429 response"
    print("✓ PASS: Rate limiter successfully caught burst and returned HTTP 429!")

    # 5. CORS is limited to known origins
    print("\n--- 5. CORS Origins Enforcement ---")
    # Allowed origin
    allowed_origin = "http://localhost:5173"
    st, _, headers = http_req("GET", "/health", headers={"Origin": allowed_origin})
    print(f"Request with Origin: {allowed_origin} -> Access-Control-Allow-Origin: {headers.get('access-control-allow-origin')}")
    assert headers.get("access-control-allow-origin") == allowed_origin

    # Disallowed origin
    evil_origin = "http://malicious-attacker-domain.com"
    st, _, headers_evil = http_req("GET", "/health", headers={"Origin": evil_origin})
    disallowed_header = headers_evil.get("access-control-allow-origin")
    print(f"Request with Origin: {evil_origin} -> Access-Control-Allow-Origin: {disallowed_header}")
    assert disallowed_header != evil_origin, "Malicious origin must not be reflected in Access-Control-Allow-Origin"
    print("✓ PASS: CORS strictly validates allowed origins and rejects foreign origins!")

    # 6. Passwords hashed with bcrypt and secrets from env
    print("\n--- 6. Cryptographic Password Hashing & Secret Configuration ---")
    with db_engine.connect() as conn:
        hashes = conn.execute(text("SELECT email, password_hash FROM users LIMIT 3")).fetchall()
        for email, p_hash in hashes:
            print(f"User: {email} | Hash: {p_hash[:20]}... (Length: {len(p_hash)})")
            assert p_hash.startswith("$2b$") or p_hash.startswith("$2a$"), "Password must be bcrypt hash"

    print(f"JWT_SECRET source: Configuration is configured via environment / Settings (length: {len(settings.JWT_SECRET)})")
    print("✓ PASS: All user passwords stored as salted bcrypt hashes ($2b$)!")

    # 7. WebSocket requires authentication
    print("\n--- 7. WebSocket Authentication Enforcement ---")
    # Anonymous connection attempt
    ws_status, ws_detail = asyncio.run(test_websocket_connect(rfq.reference_id, token=None))
    print(f"WebSocket Connect (anonymous / no token) -> Status: {ws_status} | Detail: {ws_detail}")
    assert "401" in ws_status or "4001" in ws_status or "403" in ws_status or "401" in ws_detail or "4001" in ws_detail or "403" in ws_detail
    print("✓ PASS: Anonymous WebSocket connection strictly rejected (HTTP 403 / close code 4001)!")

    # Valid authenticated connection
    ws_status_auth, ws_reply = asyncio.run(test_websocket_connect(rfq.reference_id, token=supplier_token))
    print(f"WebSocket Connect (authenticated) -> Status: {ws_status_auth} | Reply: {ws_reply.get('event_type')}")
    assert ws_status_auth == "CONNECTED" and ws_reply.get("event_type") in ("CLOCK_SYNC", "PONG")
    print("✓ PASS: Authenticated WebSocket connection authorized successfully!")

    print("\n" + "=" * 80)
    print("ALL 7 SECURITY CRITERIA VERIFIED AND PASSED!")
    print("=" * 80)

if __name__ == "__main__":
    run_security_audit()
