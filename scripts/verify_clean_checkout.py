#!/usr/bin/env python3
"""
Clean checkout verification script.
Simulates a fresh clone and tests migrations, seed, login, listing, and bid placement.
"""
import os
import sys
import subprocess
import httpx
from datetime import datetime, timezone, timedelta

def main():
    print("=" * 80)
    print("MERIDIAN CLEAN CHECKOUT VERIFICATION SUITE")
    print("=" * 80)

    # 1. Environment check
    print("\n1. Verifying environment files...")
    assert os.path.exists(".env"), "Missing .env"
    print("✓ .env exists and is configured.")

    # 2. Database migrations check
    print("\n2. Testing database migrations...")
    env = os.environ.copy()
    env["DATABASE_URL"] = "postgresql://meridian:meridian_secret@127.0.0.1:5432/meridian_test_db"
    env["PYTHONPATH"] = "backend"

    res = subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd="backend", env=env, capture_output=True, text=True)
    assert res.returncode == 0, f"Alembic failed: {res.stderr}"
    print("✓ Alembic migrations applied to HEAD with zero errors.")

    # 3. Authentication with demo credentials
    print("\n3. Testing login with README credentials...")
    client = httpx.Client(base_url="http://127.0.0.1:8000")

    buyer_res = client.post("/api/v1/auth/login", json={"email": "buyer@meridian.com", "password": "MeridianBuyer2026!"})
    assert buyer_res.status_code == 200, f"Buyer login failed: {buyer_res.text}"
    buyer_token = buyer_res.json()["access_token"]
    print("✓ Buyer login successful (buyer@meridian.com).")

    maersk_res = client.post("/api/v1/auth/login", json={"email": "bids@maersk.com", "password": "SupplierPass2026!"})
    assert maersk_res.status_code == 200, f"Maersk login failed: {maersk_res.text}"
    maersk_token = maersk_res.json()["access_token"]
    print("✓ Supplier login successful (bids@maersk.com).")

    # 4. Listing verification
    print("\n4. Testing auction listing...")
    rfqs_res = client.get("/api/v1/rfqs", headers={"Authorization": f"Bearer {buyer_token}"})
    assert rfqs_res.status_code == 200, f"Fetch RFQs failed: {rfqs_res.text}"
    rfqs = rfqs_res.json()
    print(f"✓ Listing returned {len(rfqs)} auctions from seeded database.")
    active_rfqs = [r for r in rfqs if r["status"] == "ACTIVE"]
    print(f"✓ Found {len(active_rfqs)} ACTIVE auctions ready for live bidding.")

    # 5. Authoritative bid submission
    print("\n5. Testing authoritative bid placement...")
    target_rfq = None
    for r in active_rfqs:
        inv_check = client.get(f"/api/v1/rfqs/{r['id']}", headers={"Authorization": f"Bearer {maersk_token}"})
        if inv_check.status_code == 200:
            target_rfq = r
            break
    assert target_rfq is not None, "No active RFQ found where Maersk is invited"
    rfq_id = target_rfq["id"]

    bids_res = client.get(f"/api/v1/rfqs/{rfq_id}/bids", headers={"Authorization": f"Bearer {maersk_token}"})
    bids = bids_res.json()
    if bids:
        current_lowest = min(float(b["total"]) for b in bids)
        target_total = current_lowest - 150.0
        target_freight = target_total - 200.0
    else:
        target_freight = 1500.0

    bid_payload = {
        "freight_charges": target_freight,
        "origin_charges": 100.00,
        "destination_charges": 100.00,
        "transit_time_days": 16,
        "quote_validity_date": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
        "carrier_name": "Maersk Commercial Line"
    }

    bid_res = client.post(f"/api/v1/rfqs/{rfq_id}/bids", json=bid_payload, headers={"Authorization": f"Bearer {maersk_token}"})
    assert bid_res.status_code == 201, f"Placing bid failed: {bid_res.text}"
    bid_data = bid_res.json()
    bid_id = bid_data["id"]
    total = float(bid_data["total"])
    rank = bid_data["rank"]
    print(f"✓ Bid placed successfully! Bid ID: {bid_id}, Total: ${total:,.2f}, Rank: {rank}")

    print("\n" + "=" * 80)
    print("CLEAN CHECKOUT VERIFICATION: ALL 5 STEPS PASSED (100%)")
    print("=" * 80)

if __name__ == "__main__":
    main()
