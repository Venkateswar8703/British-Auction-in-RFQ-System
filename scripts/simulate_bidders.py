#!/usr/bin/env python3
"""
MERIDIAN: Real-Time Competitive Bidder Simulator
Places authentic competitive bids through the live REST API as invited suppliers
to demonstrate live bidding, dynamic rank ladder changes, extensions, and caps.
"""
import time
import requests
import sys
import os
from decimal import Decimal
from datetime import datetime, timezone, timedelta

BASE_URL = os.getenv("MERIDIAN_API_URL", "http://localhost:8000/api/v1")

# Supplier Accounts
SUPPLIERS = [
    {"email": "bids@maersk.com", "password": "SupplierPass2026!", "name": "Maersk", "carrier": "Maersk Line Triple-E"},
    {"email": "quotes@hapag-lloyd.com", "password": "SupplierPass2026!", "name": "Hapag-Lloyd", "carrier": "Hapag Express Liner"},
    {"email": "rfq@msc.com", "password": "SupplierPass2026!", "name": "MSC", "carrier": "MSC Oscar Direct"},
    {"email": "ocean@cma-cgm.com", "password": "SupplierPass2026!", "name": "CMA CGM", "carrier": "CMA CGM Jacques Saadé"},
    {"email": "pricing@evergreen.com", "password": "SupplierPass2026!", "name": "Evergreen", "carrier": "Ever Given Commercial"},
]


def login_supplier(supp):
    try:
        resp = requests.post(f"{BASE_URL}/auth/login", json={"email": supp["email"], "password": supp["password"]}, timeout=5)
        if resp.status_code == 200:
            supp["token"] = resp.json()["access_token"]
            supp["id"] = resp.json()["user"]["supplier_id"]
            return True
        else:
            print(f"[!] Login failed for {supp['email']}: {resp.text}")
            return False
    except Exception as e:
        print(f"[!] Error connecting to {BASE_URL}: {e}")
        return False


def get_demo_rfq(token=None):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    resp = requests.get(f"{BASE_URL}/rfqs?search=LIVE-DEMO", headers=headers, timeout=5)
    if resp.status_code == 200 and resp.json():
        return resp.json()[0]
    # Fallback to any active RFQ
    resp = requests.get(f"{BASE_URL}/rfqs?status=ACTIVE", headers=headers, timeout=5)
    if resp.status_code == 200 and resp.json():
        return resp.json()[0]
    return None


def run_simulation(rfq_id=None, interval_seconds=4, rounds=5):
    print("=" * 65)
    print("  MERIDIAN LIVE BIDDER SIMULATOR")
    print("  Submitting competitive bids through the authentic REST API")
    print("=" * 65)

    # 1. Login all simulated suppliers
    print("\n[1/3] Authenticating simulated carrier accounts...")
    logged_in = []
    for s in SUPPLIERS:
        if login_supplier(s):
            print(f"  ✓ Authenticated: {s['name']} ({s['email']})")
            logged_in.append(s)

    if not logged_in:
        print("[ERROR] Could not authenticate any suppliers. Is the backend running at", BASE_URL, "?")
        sys.exit(1)

    # 2. Locate Target RFQ
    print("\n[2/3] Locating Target RFQ...")
    target_rfq = None
    auth_header = {"Authorization": f"Bearer {logged_in[0]['token']}"}
    if rfq_id:
        r = requests.get(f"{BASE_URL}/rfqs/{rfq_id}", headers=auth_header, timeout=5)
        if r.status_code == 200:
            target_rfq = r.json()
    else:
        target_rfq = get_demo_rfq(logged_in[0]["token"])

    if not target_rfq:
        print("[!] Live Demo RFQ not found. Attempting to fetch first active RFQ...")
        r = requests.get(f"{BASE_URL}/rfqs?status=ACTIVE", headers=auth_header, timeout=5)
        if r.status_code == 200 and r.json():
            target_rfq = r.json()[0]

    if not target_rfq:
        print("[ERROR] No active RFQ found to simulate bidding on.")
        sys.exit(1)

    rfq_id = target_rfq["id"]
    print(f"  ✓ Target RFQ: {target_rfq['reference_id']} - \"{target_rfq['title']}\"")
    print(f"    Status: {target_rfq['status']} | Effective Close: {target_rfq['effective_close']}")
    current_lowest = float(target_rfq["lowest_bid_total"] or 3000.0)
    print(f"    Current Lowest Bid (L1): ${current_lowest:,.2f}")

    # 3. Simulate rounds of competitive downward bids
    print(f"\n[3/3] Commencing {rounds} rounds of competitive bidding (interval: {interval_seconds}s)...\n")

    current_price = current_lowest if current_lowest > 500 else 2800.0
    for r_idx in range(1, rounds + 1):
        # Pick supplier
        supplier = logged_in[(r_idx - 1) % len(logged_in)]

        # Determine price reduction: decrease by $35 - $80 each round
        drop = 45.0 + (r_idx * 5)
        new_total = round(current_price - drop, 2)
        if new_total < 500:
            new_total = 500.0

        freight = round(new_total * 0.82, 2)
        origin = round(new_total * 0.08, 2)
        dest = round(new_total - freight - origin, 2)
        transit = 12 + (r_idx % 3)

        payload = {
            "freight_charges": freight,
            "origin_charges": origin,
            "destination_charges": dest,
            "transit_time_days": transit,
            "quote_validity_date": (datetime.now(timezone.utc) + timedelta(days=20)).isoformat(),
            "carrier_name": supplier["carrier"],
        }

        headers = {
            "Authorization": f"Bearer {supplier['token']}",
            "Idempotency-Key": f"sim-{rfq_id[:8]}-r{r_idx}-{int(time.time())}",
        }

        print(f"[Round {r_idx}/{rounds}] {supplier['name']} submitting quote: Total ${new_total:,.2f} (${freight} + ${origin} + ${dest})...")
        try:
            bid_resp = requests.post(f"{BASE_URL}/rfqs/{rfq_id}/bids", json=payload, headers=headers, timeout=5)
            if bid_resp.status_code == 201:
                bid_data = bid_resp.json()
                print(f"  → SUCCESS! Bid ID: {bid_data['id'][:8]}... | New Rank: L{bid_data.get('rank', 1)}")

                # Check if extended
                rfq_check = requests.get(f"{BASE_URL}/rfqs/{rfq_id}", headers=headers, timeout=5).json()
                print(f"  → Effective Close: {rfq_check.get('effective_close', 'N/A')}")
                current_price = new_total
            else:
                err = bid_resp.json()
                print(f"  → Rejected: [{err.get('code', 'ERROR')}] {err.get('message', bid_resp.text)}")
        except Exception as ex:
            print(f"  → Connection error: {ex}")

        if r_idx < rounds:
            time.sleep(interval_seconds)

    print("\n✓ Simulation complete! Live auction state updated.")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Simulate competitive bids on MERIDIAN RFQ")
    parser.add_argument("--rfq-id", help="Target RFQ UUID (defaults to Live Demo)")
    parser.add_argument("--interval", type=int, default=4, help="Seconds between bids")
    parser.add_argument("--rounds", type=int, default=6, help="Number of competitive bid rounds")
    args = parser.parse_args()

    run_simulation(rfq_id=args.rfq_id, interval_seconds=args.interval, rounds=args.rounds)

