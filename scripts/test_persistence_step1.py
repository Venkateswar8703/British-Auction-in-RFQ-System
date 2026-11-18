import urllib.request
import json
import time

def main():
    # 1. Login as Maersk
    req = urllib.request.Request(
        'http://localhost:8000/api/v1/auth/login',
        data=json.dumps({'email': 'bids@maersk.com', 'password': 'SupplierPass2026!'}).encode(),
        headers={'Content-Type': 'application/json'},
        method='POST'
    )
    with urllib.request.urlopen(req) as resp:
        token = json.loads(resp.read().decode())['access_token']

    # 2. Submit bid
    bid_payload = {
        'freight_charges': 1750.0,
        'origin_charges': 100.0,
        'destination_charges': 100.0,
        'transit_time_days': 12,
        'quote_validity_date': '2026-12-15T00:00:00Z',
        'carrier_name': 'Maersk Line'
    }
    req2 = urllib.request.Request(
        'http://localhost:8000/api/v1/rfqs/RFQ-2026-LIVE-DEMO/bids',
        data=json.dumps(bid_payload).encode(),
        headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {token}'},
        method='POST'
    )
    with urllib.request.urlopen(req2) as resp:
        bid_res = json.loads(resp.read().decode())
        print("=== BEFORE BACKEND RESTART ===")
        print(f"Bid ID: {bid_res['id']}")
        print(f"Carrier: {bid_res['carrier_name']}")
        print(f"Total: ${bid_res['total']}")
        print(f"Rank: L{bid_res.get('rank')}")
        bid_id = bid_res['id']

    # 3. Verify RFQ Detail before restart
    req3 = urllib.request.Request(
        'http://localhost:8000/api/v1/rfqs/RFQ-2026-LIVE-DEMO',
        headers={'Authorization': f'Bearer {token}'},
        method='GET'
    )
    with urllib.request.urlopen(req3) as resp:
        rfq_res = json.loads(resp.read().decode())
        print(f"Current L1: ${rfq_res.get('lowest_bid_total')}")
        print(f"Leader Carrier: {rfq_res['rankings'][0]['carrier_name']}")

if __name__ == '__main__':
    main()
