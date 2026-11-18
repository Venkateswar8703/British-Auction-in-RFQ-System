import urllib.request
import json

def main():
    req = urllib.request.Request(
        'http://localhost:8000/api/v1/auth/login',
        data=json.dumps({'email': 'bids@maersk.com', 'password': 'SupplierPass2026!'}).encode(),
        headers={'Content-Type': 'application/json'},
        method='POST'
    )
    with urllib.request.urlopen(req) as resp:
        token = json.loads(resp.read().decode())['access_token']

    req2 = urllib.request.Request(
        'http://localhost:8000/api/v1/rfqs/RFQ-2026-LIVE-DEMO',
        headers={'Authorization': f'Bearer {token}'},
        method='GET'
    )
    with urllib.request.urlopen(req2) as resp:
        rfq_res = json.loads(resp.read().decode())
        print("=== AFTER BACKEND RESTART ===")
        print(f"RFQ Reference: {rfq_res['reference_id']}")
        print(f"Current L1 Total: ${rfq_res.get('lowest_bid_total')}")
        print(f"Ladder Rankings Count: {len(rfq_res['rankings'])}")
        print(f"Leader Carrier: {rfq_res['rankings'][0]['carrier_name']}")
        print(f"Leader Price: ${rfq_res['rankings'][0]['total']}")

    req_bids = urllib.request.Request(
        'http://localhost:8000/api/v1/rfqs/RFQ-2026-LIVE-DEMO/bids',
        headers={'Authorization': f'Bearer {token}'},
        method='GET'
    )
    with urllib.request.urlopen(req_bids) as resp:
        bids = json.loads(resp.read().decode())
        print(f"Total Bids In Ledger: {len(bids)}")
        placed_bids = [b for b in bids if float(b['total']) == 1950.0]
        assert len(placed_bids) > 0, "Placed bid must survive backend restart!"
        print(f"Confirmed Surviving Bid: ID={placed_bids[0]['id']}, Total=${placed_bids[0]['total']}, Carrier={placed_bids[0]['carrier_name']}")
        print("SUCCESS: Full persistence verified across backend restart on PostgreSQL!")

if __name__ == '__main__':
    main()
