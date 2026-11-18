#!/usr/bin/env python3
"""
Measures real WebSocket broadcast latency from HTTP bid placement to WebSocket event receipt.
"""
import sys
import os
import time
import json
import asyncio
import httpx
import websockets

BACKEND_HTTP = "http://127.0.0.1:8000"
BACKEND_WS = "ws://127.0.0.1:8000"

async def measure_single_bid_broadcast_latency(client: httpx.AsyncClient, token: str, rfq_id: str, supplier_id: str, start_freight: float, round_num: int):
    ws_url = f"{BACKEND_WS}/ws/rfqs/{rfq_id}?token={token}"
    async with websockets.connect(ws_url) as ws:
        # Prepare strictly lower bid payload
        bid_payload = {
            "freight_charges": start_freight - (round_num * 25),
            "origin_charges": 100.00,
            "destination_charges": 100.00,
            "transit_time_days": 18,
            "quote_validity_date": "2026-12-31T00:00:00Z",
            "carrier_name": "Maersk Global Line"
        }
        
        t_before = time.perf_counter()
        
        # Fire bid and await response
        post_resp = await client.post(
            f"{BACKEND_HTTP}/api/v1/rfqs/{rfq_id}/bids",
            json=bid_payload,
            headers={"Authorization": f"Bearer {token}"}
        )
        if post_resp.status_code != 201:
            print(f"Error submitting bid: {post_resp.status_code} - {post_resp.text}")
            return None

        # Wait for WebSocket broadcast
        msg = await asyncio.wait_for(ws.recv(), timeout=5.0)
        t_received = time.perf_counter()
        data = json.loads(msg)
        latency_ms = (t_received - t_before) * 1000
        return latency_ms

async def main():
    async with httpx.AsyncClient() as client:
        # Login as Maersk
        login_resp = await client.post(
            f"{BACKEND_HTTP}/api/v1/auth/login",
            json={"email": "bids@maersk.com", "password": "SupplierPass2026!"}
        )
        assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
        token = login_resp.json()["access_token"]
        
        # Get active demo RFQ
        rfqs_resp = await client.get(
            f"{BACKEND_HTTP}/api/v1/rfqs",
            headers={"Authorization": f"Bearer {token}"}
        )
        rfqs = rfqs_resp.json()
        demo_rfq = next((r for r in rfqs if r["reference_id"] == "RFQ-2026-LIVE-DEMO"), None)
        if not demo_rfq:
            # Fallback to first active
            demo_rfq = next((r for r in rfqs if r["status"] == "ACTIVE"), rfqs[0])
            
        rfq_id = demo_rfq["id"]
        supplier_id = demo_rfq.get("supplier_id")
        
        # Get current supplier's latest bid
        bids_resp = await client.get(
            f"{BACKEND_HTTP}/api/v1/rfqs/{rfq_id}/bids",
            headers={"Authorization": f"Bearer {token}"}
        )
        bids = bids_resp.json()
        if bids:
            min_freight = min(float(b["freight_charges"]) for b in bids)
            start_freight = min_freight - 100.0
        else:
            start_freight = 1800.0

        print(f"Measuring WebSocket broadcast latency on RFQ {demo_rfq['reference_id']} ({rfq_id})...")
        latencies = []
        for i in range(5):
            lat = await measure_single_bid_broadcast_latency(client, token, rfq_id, supplier_id, start_freight, i + 1)
            if lat is not None:
                latencies.append(lat)
                print(f"  Sample {len(latencies)}: {lat:.2f} ms")
            await asyncio.sleep(0.5)
            
        avg_lat = sum(latencies) / len(latencies)
        min_lat = min(latencies)
        max_lat = max(latencies)
        print(f"\n--- Empirical Latency Results ---")
        print(f"Samples: {len(latencies)}")
        print(f"Min: {min_lat:.2f} ms")
        print(f"Avg: {avg_lat:.2f} ms")
        print(f"Max: {max_lat:.2f} ms")

if __name__ == "__main__":
    asyncio.run(main())
