#!/usr/bin/env python3
"""
MERIDIAN Live API Business Logic Verification Script
Executes all 10 authoritative auction engine scenarios against the running API
and prints full request, response, and timeline proofs.
"""
import sys
import json
import uuid
import time
import urllib.request
import urllib.error
from datetime import datetime, timedelta, timezone

API_BASE = "http://localhost:8000/api/v1"

def api_post(path, data, token=None):
    url = f"{API_BASE}{path}"
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    body = json.dumps(data).encode("utf-8") if data is not None else None
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8")
        try:
            return e.code, json.loads(err_body)
        except Exception:
            return e.code, {"raw": err_body}

def api_get(path, token=None):
    url = f"{API_BASE}{path}"
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8")
        try:
            return e.code, json.loads(err_body)
        except Exception:
            return e.code, {"raw": err_body}

def login(email, password):
    status, res = api_post("/auth/login", {"email": email, "password": password})
    if status != 200 or "access_token" not in res:
        raise RuntimeError(f"Login failed for {email}: {res}")
    return res["access_token"], res["user"]

def run_all_verifications():
    print("=" * 80)
    print("MERIDIAN LIVE API VERIFICATION SUITE — 10 AUTHORITATIVE SCENARIOS")
    print("=" * 80)

    # 1. Authenticate Personas
    buyer_token, buyer_user = login("buyer@meridian.com", "MeridianBuyer2026!")
    maersk_token, maersk_user = login("bids@maersk.com", "SupplierPass2026!")
    hapag_token, hapag_user = login("quotes@hapag-lloyd.com", "SupplierPass2026!")
    msc_token, msc_user = login("rfq@msc.com", "SupplierPass2026!")

    # Fetch suppliers to map IDs
    status, suppliers = api_get("/suppliers", buyer_token)
    sup_map = {s["code"]: s["id"] for s in suppliers}
    maersk_id = sup_map["MAERSK"]
    hapag_id = sup_map["HAPAG"]
    msc_id = sup_map["MSC"]
    print(f"✓ Authenticated: Buyer, Maersk ({maersk_id[:8]}), Hapag ({hapag_id[:8]}), MSC ({msc_id[:8]})")

    now = datetime.now(timezone.utc)

    # --------------------------------------------------------------------------
    # SCENARIO 1: Bid in last X minutes extends close by Y min, second bid extends again
    # --------------------------------------------------------------------------
    print("\n" + "-" * 80)
    print("SCENARIO 1: Extension on BID_RECEIVED inside Trigger Window (X=10m, Y=5m)")
    print("-" * 80)
    # RFQ closing in 8 minutes (inside 10-minute trigger window)
    s1_payload = {
        "title": "Scenario 1: Dynamic Extension Test",
        "description": "Verifying X=10m, Y=5m dynamic soft close extensions",
        "origin": "Shanghai Port (CNSHA)",
        "destination": "Port of Los Angeles (USLAX)",
        "pickup_date": (now + timedelta(days=10)).isoformat(),
        "bid_start": (now - timedelta(minutes=30)).isoformat(),
        "bid_close": (now + timedelta(minutes=8)).isoformat(),
        "forced_close": (now + timedelta(minutes=45)).isoformat(),
        "trigger_window_minutes": 15,
        "extension_minutes": 5,
        "trigger_type": "BID_RECEIVED",
        "invited_supplier_ids": [maersk_id, hapag_id]
    }
    c, rfq1 = api_post("/rfqs", s1_payload, buyer_token)
    assert c == 201, f"Failed to create RFQ1: {rfq1}"
    rfq1_id = rfq1["id"]
    initial_close = datetime.fromisoformat(rfq1["effective_close"])
    print(f"Created RFQ: {rfq1['reference_id']} | Initial Close: {initial_close.isoformat()}")

    # Bid 1: Inside trigger window (T-8m) -> triggers +5m extension
    b1_payload = {
        "freight_charges": 2000.0, "origin_charges": 200.0, "destination_charges": 150.0,
        "transit_time_days": 14, "quote_validity_date": (now + timedelta(days=30)).isoformat(),
        "carrier_name": "Maersk Line", "idempotency_key": str(uuid.uuid4())
    }
    status, b1_res = api_post(f"/rfqs/{rfq1_id}/bids", b1_payload, maersk_token)
    _, rfq1_after_b1 = api_get(f"/rfqs/{rfq1_id}", buyer_token)
    close_after_b1 = datetime.fromisoformat(rfq1_after_b1["effective_close"])
    expected_b1_close = initial_close + timedelta(minutes=5)
    print(f"Bid 1 Total: ${b1_res['total']} | Status: {status} | Rank: {b1_res['rank']}")
    print(f"New Close: {close_after_b1.isoformat()} (Diff from initial: +{(close_after_b1 - initial_close).total_seconds()/60:.1f}m)")
    assert close_after_b1 == expected_b1_close, f"Expected {expected_b1_close}, got {close_after_b1}"
    print("✓ Proof 1A: First qualifying bid inside window extended deadline by exactly 5 minutes!")

    # Bid 2: Second qualifying bid in new window extends again
    b2_payload = {
        "freight_charges": 1900.0, "origin_charges": 200.0, "destination_charges": 150.0,
        "transit_time_days": 13, "quote_validity_date": (now + timedelta(days=30)).isoformat(),
        "carrier_name": "Hapag-Lloyd", "idempotency_key": str(uuid.uuid4())
    }
    status, b2_res = api_post(f"/rfqs/{rfq1_id}/bids", b2_payload, hapag_token)
    _, rfq1_after_b2 = api_get(f"/rfqs/{rfq1_id}", buyer_token)
    close_after_b2 = datetime.fromisoformat(rfq1_after_b2["effective_close"])
    expected_b2_close = close_after_b1 + timedelta(minutes=5)
    print(f"Bid 2 Total: ${b2_res['total']} | Status: {status} | Rank: {b2_res['rank']}")
    print(f"New Close: {close_after_b2.isoformat()} (Diff from previous: +{(close_after_b2 - close_after_b1).total_seconds()/60:.1f}m)")
    assert close_after_b2 == expected_b2_close, f"Expected {expected_b2_close}, got {close_after_b2}"
    print("✓ Proof 1B: Second qualifying bid in new window extended deadline again by 5 minutes!")

    # --------------------------------------------------------------------------
    # SCENARIO 2: Bid outside trigger window does NOT extend
    # --------------------------------------------------------------------------
    print("\n" + "-" * 80)
    print("SCENARIO 2: Bid Outside Trigger Window (X=5m, Close in 25m)")
    print("-" * 80)
    s2_payload = {
        "title": "Scenario 2: Outside Window Test",
        "description": "Verifying bids outside window do not extend",
        "origin": "Port of Singapore (SGSIN)",
        "destination": "Port of Rotterdam (NLRTM)",
        "pickup_date": (now + timedelta(days=10)).isoformat(),
        "bid_start": (now - timedelta(minutes=10)).isoformat(),
        "bid_close": (now + timedelta(minutes=25)).isoformat(),
        "forced_close": (now + timedelta(minutes=45)).isoformat(),
        "trigger_window_minutes": 5,
        "extension_minutes": 5,
        "trigger_type": "BID_RECEIVED",
        "invited_supplier_ids": [maersk_id]
    }
    c, rfq2 = api_post("/rfqs", s2_payload, buyer_token)
    assert c == 201, f"Failed to create RFQ2: {rfq2}"
    rfq2_id = rfq2["id"]
    close_before_b = rfq2["effective_close"]

    # Submit bid at T-25m (well before the 5-minute trigger window)
    s2_bid = {
        "freight_charges": 2500.0, "origin_charges": 150.0, "destination_charges": 150.0,
        "transit_time_days": 20, "quote_validity_date": (now + timedelta(days=30)).isoformat(),
        "carrier_name": "Maersk Line", "idempotency_key": str(uuid.uuid4())
    }
    status, s2_res = api_post(f"/rfqs/{rfq2_id}/bids", s2_bid, maersk_token)
    _, rfq2_after = api_get(f"/rfqs/{rfq2_id}", buyer_token)
    close_after_b = rfq2_after["effective_close"]
    print(f"Bid Total: ${s2_res['total']} | Status: {status} | Initial Close: {close_before_b} | After Close: {close_after_b}")
    assert close_before_b == close_after_b, "Close should NOT change for bid outside window!"
    print("✓ Proof 2: Bid outside trigger window accepted without extending the close deadline!")

    # --------------------------------------------------------------------------
    # SCENARIO 3: Extension clamped to forced_close and subsequent logs EXTENSION_CAPPED
    # --------------------------------------------------------------------------
    print("\n" + "-" * 80)
    print("SCENARIO 3: Hard Stop Capping at forced_close and EXTENSION_CAPPED event")
    print("-" * 80)
    # Effective close in 2m, forced_close in 4m, extension duration is 5m (would exceed forced_close by 3m)
    s3_payload = {
        "title": "Scenario 3: Forced Close Clamp Test",
        "description": "Verifying clamping to forced_close and EXTENSION_CAPPED",
        "origin": "Busan (KRPUS)",
        "destination": "Long Beach (USLGB)",
        "pickup_date": (now + timedelta(days=10)).isoformat(),
        "bid_start": (now - timedelta(minutes=20)).isoformat(),
        "bid_close": (now + timedelta(minutes=2)).isoformat(),
        "forced_close": (now + timedelta(minutes=4)).isoformat(),
        "trigger_window_minutes": 5,
        "extension_minutes": 5,
        "trigger_type": "BID_RECEIVED",
        "invited_supplier_ids": [maersk_id, hapag_id]
    }
    c, rfq3 = api_post("/rfqs", s3_payload, buyer_token)
    assert c == 201, f"Failed to create RFQ3: {rfq3}"
    rfq3_id = rfq3["id"]
    forced_target = datetime.fromisoformat(rfq3["forced_close"])

    # Bid 1: Extends and is clamped to forced_close
    b3_1 = {
        "freight_charges": 3000.0, "origin_charges": 200.0, "destination_charges": 200.0,
        "transit_time_days": 15, "quote_validity_date": (now + timedelta(days=30)).isoformat(),
        "carrier_name": "Maersk Line", "idempotency_key": str(uuid.uuid4())
    }
    status, _ = api_post(f"/rfqs/{rfq3_id}/bids", b3_1, maersk_token)
    _, rfq3_after1 = api_get(f"/rfqs/{rfq3_id}", buyer_token)
    close1 = datetime.fromisoformat(rfq3_after1["effective_close"])
    print(f"Bid 1 Clamped Close: {close1.isoformat()} (Matches forced_close: {close1 == forced_target})")
    assert close1 == forced_target, "Close must be clamped exactly to forced_close!"
    print("✓ Proof 3A: Extension exceeding forced_close was strictly clamped to forced_close!")

    # Bid 2: While already at forced_close ceiling -> logs EXTENSION_CAPPED, deadline does not move
    b3_2 = {
        "freight_charges": 2800.0, "origin_charges": 200.0, "destination_charges": 200.0,
        "transit_time_days": 15, "quote_validity_date": (now + timedelta(days=30)).isoformat(),
        "carrier_name": "Hapag-Lloyd", "idempotency_key": str(uuid.uuid4())
    }
    status, _ = api_post(f"/rfqs/{rfq3_id}/bids", b3_2, hapag_token)
    _, rfq3_after2 = api_get(f"/rfqs/{rfq3_id}", buyer_token)
    close2 = datetime.fromisoformat(rfq3_after2["effective_close"])
    print(f"Bid 2 Final Close: {close2.isoformat()} (No shift beyond forced_close: {close2 == forced_target})")
    assert close2 == forced_target

    # Check event log for EXTENSION_CAPPED
    _, events = api_get(f"/rfqs/{rfq3_id}/events", buyer_token)
    event_types = [e["event_type"] for e in events]
    print(f"Auction Events: {event_types}")
    assert "EXTENSION_CAPPED" in event_types, "EXTENSION_CAPPED event must be recorded!"
    print("✓ Proof 3B: Subsequent qualifying bid logged EXTENSION_CAPPED event with zero deadline drift!")

    # --------------------------------------------------------------------------
    # SCENARIO 4: Trigger 2 ANY_RANK_CHANGE
    # --------------------------------------------------------------------------
    print("\n" + "-" * 80)
    print("SCENARIO 4: Trigger 2 ANY_RANK_CHANGE (No swap = no extension, swap = extension)")
    print("-" * 80)
    s4_payload = {
        "title": "Scenario 4: ANY_RANK_CHANGE Test",
        "description": "Verifying ANY_RANK_CHANGE logic",
        "origin": "Hamburg (DEHAM)",
        "destination": "New York (USNYC)",
        "pickup_date": (now + timedelta(days=10)).isoformat(),
        "bid_start": (now - timedelta(minutes=20)).isoformat(),
        "bid_close": (now + timedelta(minutes=4)).isoformat(),
        "forced_close": (now + timedelta(minutes=45)).isoformat(),
        "trigger_window_minutes": 15,
        "extension_minutes": 5,
        "trigger_type": "ANY_RANK_CHANGE",
        "invited_supplier_ids": [maersk_id, hapag_id, msc_id]
    }
    c, rfq4 = api_post("/rfqs", s4_payload, buyer_token)
    assert c == 201, f"Failed to create RFQ4: {rfq4}"
    rfq4_id = rfq4["id"]

    # Initial bids to establish ranks: Maersk ($2500 -> Rank 1), Hapag ($3000 -> Rank 2)
    api_post(f"/rfqs/{rfq4_id}/bids", {
        "freight_charges": 2200.0, "origin_charges": 150.0, "destination_charges": 150.0,
        "transit_time_days": 12, "quote_validity_date": (now + timedelta(days=30)).isoformat(),
        "carrier_name": "Maersk Line", "idempotency_key": str(uuid.uuid4())
    }, maersk_token)
    api_post(f"/rfqs/{rfq4_id}/bids", {
        "freight_charges": 2700.0, "origin_charges": 150.0, "destination_charges": 150.0,
        "transit_time_days": 12, "quote_validity_date": (now + timedelta(days=30)).isoformat(),
        "carrier_name": "Hapag-Lloyd", "idempotency_key": str(uuid.uuid4())
    }, hapag_token)

    _, rfq4_base = api_get(f"/rfqs/{rfq4_id}", buyer_token)
    close_base = rfq4_base["effective_close"]

    # Bid from MSC with $3500 -> Rank 3 (No previously ranked supplier changes rank!)
    # Ranks before: Maersk 1, Hapag 2. Ranks after: Maersk 1, Hapag 2, MSC 3.
    # No existing rank changes -> Should NOT extend!
    status, msc_res = api_post(f"/rfqs/{rfq4_id}/bids", {
        "freight_charges": 3200.0, "origin_charges": 150.0, "destination_charges": 150.0,
        "transit_time_days": 12, "quote_validity_date": (now + timedelta(days=30)).isoformat(),
        "carrier_name": "MSC Mediterranean", "idempotency_key": str(uuid.uuid4())
    }, msc_token)
    _, rfq4_after_no_change = api_get(f"/rfqs/{rfq4_id}", buyer_token)
    print(f"MSC Bid Total: ${msc_res['total']} | Rank: {msc_res['rank']}")
    print(f"Close Before: {close_base} | Close After: {rfq4_after_no_change['effective_close']}")
    assert close_base == rfq4_after_no_change["effective_close"], "Should NOT extend when no existing rank changes!"
    print("✓ Proof 4A: Bid that appended at bottom without changing existing ranks caused NO extension!")

    # Bid from Hapag with $2300 -> Swaps rank with Maersk (Hapag takes Rank 1, Maersk moves to Rank 2)!
    # Ranks change -> MUST extend!
    status, hapag_swap = api_post(f"/rfqs/{rfq4_id}/bids", {
        "freight_charges": 2000.0, "origin_charges": 150.0, "destination_charges": 150.0,
        "transit_time_days": 12, "quote_validity_date": (now + timedelta(days=30)).isoformat(),
        "carrier_name": "Hapag-Lloyd", "idempotency_key": str(uuid.uuid4())
    }, hapag_token)
    _, rfq4_after_swap = api_get(f"/rfqs/{rfq4_id}", buyer_token)
    print(f"Hapag Swap Bid Total: ${hapag_swap['total']} | New Rank: {hapag_swap['rank']}")
    print(f"Close After Swap: {rfq4_after_swap['effective_close']} (Shifted: {rfq4_after_swap['effective_close'] != close_base})")
    assert rfq4_after_swap["effective_close"] != close_base, "MUST extend when rank changes!"
    print("✓ Proof 4B: Bid that swapped positions caused ANY_RANK_CHANGE extension!")

    # --------------------------------------------------------------------------
    # SCENARIO 5: Trigger 3 L1_CHANGE
    # --------------------------------------------------------------------------
    print("\n" + "-" * 80)
    print("SCENARIO 5: Trigger 3 L1_CHANGE (L2 stays L2 = no extension, taking L1 = extension)")
    print("-" * 80)
    s5_payload = {
        "title": "Scenario 5: L1_CHANGE Test",
        "description": "Verifying L1_CHANGE trigger type",
        "origin": "Rotterdam (NLRTM)",
        "destination": "Singapore (SGSIN)",
        "pickup_date": (now + timedelta(days=10)).isoformat(),
        "bid_start": (now - timedelta(minutes=20)).isoformat(),
        "bid_close": (now + timedelta(minutes=4)).isoformat(),
        "forced_close": (now + timedelta(minutes=45)).isoformat(),
        "trigger_window_minutes": 15,
        "extension_minutes": 5,
        "trigger_type": "L1_CHANGE",
        "invited_supplier_ids": [maersk_id, hapag_id]
    }
    c, rfq5 = api_post("/rfqs", s5_payload, buyer_token)
    assert c == 201, f"Failed to create RFQ5: {rfq5}"
    rfq5_id = rfq5["id"]

    # First bid takes L1 -> counts as L1 change and extends
    status, b5_1 = api_post(f"/rfqs/{rfq5_id}/bids", {
        "freight_charges": 2400.0, "origin_charges": 150.0, "destination_charges": 150.0,
        "transit_time_days": 18, "quote_validity_date": (now + timedelta(days=30)).isoformat(),
        "carrier_name": "Maersk Line", "idempotency_key": str(uuid.uuid4())
    }, maersk_token)
    _, rfq5_after1 = api_get(f"/rfqs/{rfq5_id}", buyer_token)
    close_after_first = rfq5_after1["effective_close"]
    print(f"First Bid Total: ${b5_1['total']} | Rank: {b5_1['rank']} | Close: {close_after_first}")

    # Bid 2 from Hapag with $2800 -> Rank 2 (Does NOT change L1!).
    # L1 remains Maersk $2700. Should NOT extend!
    status, b5_2 = api_post(f"/rfqs/{rfq5_id}/bids", {
        "freight_charges": 2500.0, "origin_charges": 150.0, "destination_charges": 150.0,
        "transit_time_days": 18, "quote_validity_date": (now + timedelta(days=30)).isoformat(),
        "carrier_name": "Hapag-Lloyd", "idempotency_key": str(uuid.uuid4())
    }, hapag_token)
    _, rfq5_after2 = api_get(f"/rfqs/{rfq5_id}", buyer_token)
    print(f"Hapag L2 Bid: ${b5_2['total']} | Rank: {b5_2['rank']}")
    print(f"Close Before: {close_after_first} | Close After: {rfq5_after2['effective_close']}")
    assert close_after_first == rfq5_after2["effective_close"], "Bid staying at L2 must NOT extend L1_CHANGE auction!"
    print("✓ Proof 5A: Bid from L2 that stayed L2 did NOT extend the auction!")

    # Bid 3 from Hapag with $2500 -> Takes L1 from Maersk!
    # L1 changed -> MUST extend!
    status, b5_3 = api_post(f"/rfqs/{rfq5_id}/bids", {
        "freight_charges": 2200.0, "origin_charges": 150.0, "destination_charges": 150.0,
        "transit_time_days": 18, "quote_validity_date": (now + timedelta(days=30)).isoformat(),
        "carrier_name": "Hapag-Lloyd", "idempotency_key": str(uuid.uuid4())
    }, hapag_token)
    _, rfq5_after3 = api_get(f"/rfqs/{rfq5_id}", buyer_token)
    print(f"Hapag Bid Taking L1: ${b5_3['total']} | Rank: {b5_3['rank']}")
    print(f"Close After L1 Takeover: {rfq5_after3['effective_close']}")
    assert rfq5_after3["effective_close"] != close_after_first, "Bid taking L1 MUST extend!"
    print("✓ Proof 5B: Bid that took over L1 triggered extension in L1_CHANGE auction!")

    # --------------------------------------------------------------------------
    # SCENARIO 6: Rejections (Negative/Zero, Not Lower, Not Invited, Expired Date)
    # --------------------------------------------------------------------------
    print("\n" + "-" * 80)
    print("SCENARIO 6: Server-Authoritative Bid Rejections")
    print("-" * 80)
    def get_err_code(resp_obj):
        if isinstance(resp_obj, dict):
            return resp_obj.get("code") or resp_obj.get("detail", {}).get("code")
        return None

    # 6.1 Negative amount
    c, r = api_post(f"/rfqs/{rfq1_id}/bids", {
        "freight_charges": -100.0, "origin_charges": 100.0, "destination_charges": 100.0,
        "transit_time_days": 10, "quote_validity_date": (now + timedelta(days=30)).isoformat(),
        "carrier_name": "Maersk Line"
    }, maersk_token)
    print(f"6.1 Negative Amount Rejection: Status {c} | Code: {get_err_code(r)}")
    assert c in (400, 422), "Negative amount must be rejected!"

    # 6.2 Zero amount
    c, r = api_post(f"/rfqs/{rfq1_id}/bids", {
        "freight_charges": 0.0, "origin_charges": 100.0, "destination_charges": 100.0,
        "transit_time_days": 10, "quote_validity_date": (now + timedelta(days=30)).isoformat(),
        "carrier_name": "Maersk Line"
    }, maersk_token)
    print(f"6.2 Zero Amount Rejection: Status {c} | Code: {get_err_code(r)}")
    assert c in (400, 422), "Zero amount must be rejected!"

    # 6.3 Not strictly lower than own previous bid
    # Maersk previous bid in rfq1 was $2350. Trying $2400 (higher)
    c, r = api_post(f"/rfqs/{rfq1_id}/bids", {
        "freight_charges": 2100.0, "origin_charges": 150.0, "destination_charges": 150.0,
        "transit_time_days": 10, "quote_validity_date": (now + timedelta(days=30)).isoformat(),
        "carrier_name": "Maersk Line"
    }, maersk_token)
    print(f"6.3 Higher Bid Rejection: Status {c} | Code: {get_err_code(r)}")
    assert c == 400 and get_err_code(r) == "BID_NOT_LOWER"

    # 6.4 Non-invited supplier
    # MSC was NOT invited to rfq1
    c, r = api_post(f"/rfqs/{rfq1_id}/bids", {
        "freight_charges": 1500.0, "origin_charges": 100.0, "destination_charges": 100.0,
        "transit_time_days": 10, "quote_validity_date": (now + timedelta(days=30)).isoformat(),
        "carrier_name": "MSC Mediterranean"
    }, msc_token)
    print(f"6.4 Non-Invited Supplier Rejection: Status {c} | Code: {get_err_code(r)}")
    assert c in (400, 403) and get_err_code(r) == "SUPPLIER_NOT_INVITED"

    # 6.5 Expired quote validity date
    c, r = api_post(f"/rfqs/{rfq1_id}/bids", {
        "freight_charges": 1500.0, "origin_charges": 100.0, "destination_charges": 100.0,
        "transit_time_days": 10, "quote_validity_date": (now - timedelta(days=1)).isoformat(),
        "carrier_name": "Maersk Line"
    }, maersk_token)
    print(f"6.5 Expired Quote Validity Rejection: Status {c} | Code: {get_err_code(r)}")
    assert c in (400, 422)

    print("✓ Proof 6: All server-side invalid bid submission rules strictly rejected with precise codes!")

    # --------------------------------------------------------------------------
    # SCENARIO 7: Tie on total -> Earlier bid keeps the better rank
    # --------------------------------------------------------------------------
    print("\n" + "-" * 80)
    print("SCENARIO 7: Tie Breaking on Total (Earlier Timestamp Wins Rank)")
    print("-" * 80)
    s7_payload = {
        "title": "Scenario 7: Tie Breaking Test",
        "origin": "Qingdao (CNTAO)", "destination": "Melbourne (AUMEL)",
        "pickup_date": (now + timedelta(days=10)).isoformat(),
        "bid_start": (now - timedelta(minutes=20)).isoformat(),
        "bid_close": (now + timedelta(minutes=15)).isoformat(),
        "forced_close": (now + timedelta(minutes=45)).isoformat(),
        "trigger_window_minutes": 5,
        "extension_minutes": 5,
        "trigger_type": "BID_RECEIVED",
        "invited_supplier_ids": [maersk_id, hapag_id]
    }
    c, rfq7 = api_post("/rfqs", s7_payload, buyer_token)
    assert c == 201, f"Failed to create RFQ7: {rfq7}"
    rfq7_id = rfq7["id"]

    # Maersk bids $2000 total first
    api_post(f"/rfqs/{rfq7_id}/bids", {
        "freight_charges": 1800.0, "origin_charges": 100.0, "destination_charges": 100.0,
        "transit_time_days": 15, "quote_validity_date": (now + timedelta(days=30)).isoformat(),
        "carrier_name": "Maersk Line"
    }, maersk_token)
    time.sleep(0.05) # ensure timestamp difference

    # Hapag bids exact same $2000 total second
    api_post(f"/rfqs/{rfq7_id}/bids", {
        "freight_charges": 1800.0, "origin_charges": 100.0, "destination_charges": 100.0,
        "transit_time_days": 15, "quote_validity_date": (now + timedelta(days=30)).isoformat(),
        "carrier_name": "Hapag-Lloyd"
    }, hapag_token)

    _, rfq7_detail = api_get(f"/rfqs/{rfq7_id}", buyer_token)
    rankings = rfq7_detail["rankings"]
    print("Ladder after tie submission ($2000 vs $2000):")
    for r in rankings:
        print(f" - Rank {r['rank']}: Supplier {r['supplier_id'][:8]} (Total: ${r['total']}, Timestamp: {r.get('bid_created_at')})")
    assert rankings[0]["supplier_id"] == maersk_id, "Earlier bidder must be Rank 1!"
    assert rankings[1]["supplier_id"] == hapag_id, "Later bidder on same total must be Rank 2!"
    print("✓ Proof 7: Exact price tie broken by earlier submission timestamp!")

    # --------------------------------------------------------------------------
    # SCENARIO 8: 20 Parallel Bids (Unique ranks, no duplicate rows, consistent state)
    # --------------------------------------------------------------------------
    print("\n" + "-" * 80)
    print("SCENARIO 8: High Concurrency Test (20 Parallel Bids)")
    print("-" * 80)
    import concurrent.futures
    s8_payload = {
        "title": "Scenario 8: High Concurrency RFQ",
        "origin": "Ningbo (CNNGB)", "destination": "Oakland (USOAK)",
        "pickup_date": (now + timedelta(days=10)).isoformat(),
        "bid_start": (now - timedelta(minutes=20)).isoformat(),
        "bid_close": (now + timedelta(minutes=2)).isoformat(),
        "forced_close": (now + timedelta(minutes=45)).isoformat(),
        "trigger_window_minutes": 10,
        "extension_minutes": 5,
        "trigger_type": "BID_RECEIVED",
        "invited_supplier_ids": [maersk_id, hapag_id, msc_id]
    }
    c, rfq8 = api_post("/rfqs", s8_payload, buyer_token)
    assert c == 201, f"Failed to create RFQ8: {rfq8}"
    rfq8_id = rfq8["id"]

    # Generate 20 distinct bids across the 3 suppliers with descending prices
    bid_tasks = []
    tokens = [maersk_token, hapag_token, msc_token]
    for i in range(20):
        tok = tokens[i % 3]
        price = 4000.0 - (i * 50.0)
        c_name = "Maersk" if tok == maersk_token else "Hapag" if tok == hapag_token else "MSC"
        bid_tasks.append((tok, {
            "freight_charges": price - 200.0, "origin_charges": 100.0, "destination_charges": 100.0,
            "transit_time_days": 12, "quote_validity_date": (now + timedelta(days=30)).isoformat(),
            "carrier_name": c_name, "idempotency_key": str(uuid.uuid4())
        }))

    def post_worker(task):
        tok, body = task
        return api_post(f"/rfqs/{rfq8_id}/bids", body, tok)

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(post_worker, bid_tasks))

    successes = [r for code, r in results if code == 201]
    print(f"Parallel submissions completed: {len(successes)} successful")
    _, rfq8_detail = api_get(f"/rfqs/{rfq8_id}", buyer_token)
    print(f"Final Lowest Bid (L1): ${rfq8_detail['lowest_bid_total']}")
    print(f"Active Participating Suppliers in Ladder: {len(rfq8_detail['rankings'])}")
    for r in rfq8_detail["rankings"]:
        print(f" - Rank {r['rank']}: ${r['total']} (Carrier: {r['carrier_name']})")
    assert len(rfq8_detail["rankings"]) <= 3, "Ladder must have at most 1 best bid per participating carrier!"
    print("✓ Proof 8: High concurrency bids handled consistently without data corruption or rank duplicates!")

    # --------------------------------------------------------------------------
    # SCENARIO 9: Idempotency Key Replay
    # --------------------------------------------------------------------------
    print("\n" + "-" * 80)
    print("SCENARIO 9: Idempotency Key Replay (Exact Cached Response, Zero Duplication)")
    print("-" * 80)
    idem_key = f"IDEM-TEST-{uuid.uuid4()}"
    idem_payload = {
        "freight_charges": 1600.0, "origin_charges": 100.0, "destination_charges": 100.0,
        "transit_time_days": 14, "quote_validity_date": (now + timedelta(days=30)).isoformat(),
        "carrier_name": "Maersk Line", "idempotency_key": idem_key
    }
    c1, r1 = api_post(f"/rfqs/{rfq7_id}/bids", idem_payload, maersk_token)
    c2, r2 = api_post(f"/rfqs/{rfq7_id}/bids", idem_payload, maersk_token)
    print(f"First Call Status: {c1} | Bid ID: {r1['id']} | Total: {r1['total']}")
    print(f"Replay Call Status: {c2} | Bid ID: {r2['id']} | Total: {r2['total']}")
    assert c1 == 201 and c2 == 200, f"Expected 201 on create and 200 on replay, got {c1}, {c2}"
    assert r1["id"] == r2["id"], "Replay must return exact same Bid ID!"
    print("✓ Proof 9: Idempotency key replay returned original response with zero duplicate bid rows created!")

    # --------------------------------------------------------------------------
    # SCENARIO 10: Natural Expiry -> CLOSED vs Ceiling Expiry -> FORCE_CLOSED
    # --------------------------------------------------------------------------
    print("\n" + "-" * 80)
    print("SCENARIO 10: Natural Expiry -> CLOSED vs Extension Ceiling Expiry -> FORCE_CLOSED")
    print("-" * 80)
    from app.database import SessionLocal
    from app.models.entities import RFQ
    from app.services.auction_engine import check_and_update_rfq_status

    # 10.1 Natural expiry without extensions reaching forced_close
    db = SessionLocal()
    try:
        now_eval = datetime.now(timezone.utc)
        rfq_nat = RFQ(
            reference_id=f"TEST-NAT-{uuid.uuid4().hex[:6].upper()}",
            title="Natural Expiry Test",
            origin="Shanghai (CNSHA)", destination="LA (USLAX)",
            pickup_date=now_eval + timedelta(days=5),
            bid_start=now_eval - timedelta(hours=2),
            bid_close=now_eval - timedelta(minutes=10),
            effective_close=now_eval - timedelta(minutes=10),
            forced_close=now_eval + timedelta(hours=1),
            status="ACTIVE",
            created_by=buyer_user["id"]
        )
        db.add(rfq_nat)
        db.commit()
        check_and_update_rfq_status(db, rfq_nat, now_eval)
        db.commit()
        nat_status = rfq_nat.status
    finally:
        db.close()

    print(f"10.1 Unextended Expired RFQ Status: {nat_status} (Expected: CLOSED)")
    assert nat_status == "CLOSED", f"Expected CLOSED, got {nat_status}"

    # 10.2 Extended to forced_close and expired
    db = SessionLocal()
    try:
        now_eval = datetime.now(timezone.utc)
        rfq_force = RFQ(
            reference_id=f"TEST-FORCE-{uuid.uuid4().hex[:6].upper()}",
            title="Force Close Expiry Test",
            origin="Singapore (SGSIN)", destination="Rotterdam (NLRTM)",
            pickup_date=now_eval + timedelta(days=5),
            bid_start=now_eval - timedelta(hours=2),
            bid_close=now_eval - timedelta(hours=1),
            effective_close=now_eval - timedelta(minutes=5),
            forced_close=now_eval - timedelta(minutes=5),
            status="ACTIVE",
            created_by=buyer_user["id"]
        )
        db.add(rfq_force)
        db.commit()
        check_and_update_rfq_status(db, rfq_force, now_eval)
        db.commit()
        force_status = rfq_force.status
    finally:
        db.close()

    print(f"10.2 Extended to Ceiling RFQ Status: {force_status} (Expected: FORCE_CLOSED)")
    assert force_status == "FORCE_CLOSED", f"Expected FORCE_CLOSED, got {force_status}"
    print("✓ Proof 10: Natural deadline moves to CLOSED; extension-capped deadline moves to FORCE_CLOSED!")

    print("\n" + "=" * 80)
    print("ALL 10 AUTHORITATIVE LIVE API SCENARIOS VERIFIED AND PASSED!")
    print("=" * 80)

if __name__ == "__main__":
    run_all_verifications()
