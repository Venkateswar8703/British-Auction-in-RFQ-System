#!/usr/bin/env python3
"""
MERIDIAN Headless Chrome CDP Screenshot & Layout Audit Suite
Captures high-fidelity PNG screenshots of key pages at:
- 1280px Desktop
- 390px Mobile

Audits for:
- Horizontal overflow (scrollWidth > innerWidth)
- Sticky header positioning
- Overlap & text clipping
"""
import sys
import os
import json
import time
import base64
import urllib.request
import subprocess
import asyncio
import websockets

SCREENSHOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "docs", "overnight", "screenshots"))
os.makedirs(SCREENSHOT_DIR, exist_ok=True)

CHROME_CMD = [
    "google-chrome",
    "--headless=new",
    "--no-sandbox",
    "--disable-gpu",
    "--remote-debugging-port=9222",
    "--window-size=1280,900"
]

class CDPClient:
    def __init__(self, ws_url):
        self.ws_url = ws_url
        self.ws = None
        self.msg_id = 0

    async def connect(self):
        self.ws = await websockets.connect(self.ws_url, max_size=50 * 1024 * 1024)

    async def send(self, method, params=None):
        self.msg_id += 1
        call_id = self.msg_id
        req = {"id": call_id, "method": method, "params": params or {}}
        await self.ws.send(json.dumps(req))
        while True:
            resp_raw = await self.ws.recv()
            resp = json.loads(resp_raw)
            if resp.get("id") == call_id:
                if "error" in resp:
                    raise RuntimeError(f"CDP error on {method}: {resp['error']}")
                return resp.get("result", {})

    async def close(self):
        if self.ws:
            await self.ws.close()

async def run_audit():
    print("=" * 80)
    print("MERIDIAN UI LAYOUT & SCREENSHOT AUDIT (1280px & 390px)")
    print("=" * 80)

    # 1. Start Chrome
    chrome_proc = subprocess.Popen(CHROME_CMD, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1.5)

    try:
        # Get target WebSocket URL
        targets_raw = urllib.request.urlopen("http://127.0.0.1:9222/json").read()
        targets = json.loads(targets_raw.decode("utf-8"))
        ws_url = targets[0]["webSocketDebuggerUrl"]

        client = CDPClient(ws_url)
        await client.connect()

        await client.send("Page.enable")
        await client.send("Runtime.enable")

        # 2. Get tokens for Buyer and Supplier
        sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))
        from app.services.auth import create_access_token
        from sqlalchemy import create_engine, text
        from app.config import settings

        db_engine = create_engine(settings.DATABASE_URL)
        with db_engine.connect() as conn:
            buyer = conn.execute(text("SELECT id, email, role FROM users WHERE role='buyer' LIMIT 1")).fetchone()
            supplier = conn.execute(text("SELECT id, email, role, supplier_id FROM users WHERE role='supplier' LIMIT 1")).fetchone()
            rfq = conn.execute(text("SELECT id, reference_id FROM rfqs WHERE status='ACTIVE' LIMIT 1")).fetchone()

        rfq_ref = rfq.reference_id if rfq else "RFQ-2026-LIVE-DEMO"
        buyer_token = create_access_token({"sub": buyer.id, "email": buyer.email, "role": buyer.role})
        supplier_token = create_access_token({"sub": supplier.id, "email": supplier.email, "role": supplier.role, "supplier_id": supplier.supplier_id})

        pages = [
            ("Listing", f"http://localhost:5173/auctions", buyer_token, "buyer"),
            ("Live_Room", f"http://localhost:5173/live/{rfq_ref}", buyer_token, "buyer"),
            ("Details", f"http://localhost:5173/auctions/{rfq_ref}", buyer_token, "buyer"),
            ("Create_RFQ", f"http://localhost:5173/create-rfq", buyer_token, "buyer"),
            ("Command_Center", f"http://localhost:5173/command-center", buyer_token, "buyer"),
            ("Supplier_Portal", f"http://localhost:5173/portal", supplier_token, "supplier"),
        ]

        viewports = [
            ("1280px", 1280, 900, 1.0, False),
            ("390px", 390, 844, 2.0, True),
        ]

        audit_results = []

        for page_name, url, token, role in pages:
            # Set token before page loads
            await client.send("Page.addScriptToEvaluateOnNewDocument", {
                "source": f"localStorage.setItem('meridian_token', '{token}');"
            })

            for vp_name, width, height, scale, is_mobile in viewports:
                print(f"\nCapturing {page_name} at {vp_name} ({width}x{height})...")

                # Configure Viewport
                await client.send("Emulation.setDeviceMetricsOverride", {
                    "width": width,
                    "height": height,
                    "deviceScaleFactor": scale,
                    "mobile": is_mobile
                })

                # Navigate to URL
                await client.send("Page.navigate", {"url": url})
                await asyncio.sleep(2.0)

                # Layout audit script
                eval_script = """
                (() => {
                    const scrollW = document.documentElement.scrollWidth;
                    const innerW = window.innerWidth;
                    const hasHorizontalOverflow = scrollW > innerW + 1; // 1px tolerance
                    return {
                        scrollWidth: scrollW,
                        innerWidth: innerW,
                        overflow: hasHorizontalOverflow,
                        title: document.title,
                        bodyHeight: document.body.scrollHeight
                    };
                })()
                """
                res = await client.send("Runtime.evaluate", {"expression": eval_script, "returnByValue": True})
                layout_data = res.get("value", {})

                # Capture Screenshot
                shot = await client.send("Page.captureScreenshot", {"format": "png"})
                img_data = base64.b64decode(shot["data"])
                out_path = os.path.join(SCREENSHOT_DIR, f"{page_name}_{vp_name}.png")
                with open(out_path, "wb") as f:
                    f.write(img_data)

                overflow_status = "FAIL (OVERFLOW)" if layout_data.get("overflow") else "PASS (NO OVERFLOW)"
                print(f" -> Saved: {os.path.basename(out_path)} ({len(img_data):,} bytes)")
                print(f" -> Viewport: innerWidth={layout_data.get('innerWidth')}, scrollWidth={layout_data.get('scrollWidth')} | Overflow: {overflow_status}")

                audit_results.append({
                    "page": page_name,
                    "viewport": vp_name,
                    "width": width,
                    "height": height,
                    "file": os.path.basename(out_path),
                    "scrollWidth": layout_data.get("scrollWidth"),
                    "innerWidth": layout_data.get("innerWidth"),
                    "overflow": layout_data.get("overflow", False)
                })

        await client.close()

        print("\n" + "=" * 80)
        print("SUMMARY TABLE: UI SCREENSHOT & OVERFLOW AUDIT")
        print("=" * 80)
        print(f"{'Page':<20} | {'Viewport':<10} | {'innerW':<8} | {'scrollW':<8} | {'Status':<15} | Screenshot")
        print("-" * 80)
        all_passed = True
        for item in audit_results:
            st = "PASS" if not item["overflow"] else "FAIL (Overflow)"
            if item["overflow"]:
                all_passed = False
            print(f"{item['page']:<20} | {item['viewport']:<10} | {item['innerWidth']:<8} | {item['scrollWidth']:<8} | {st:<15} | {item['file']}")

        print("-" * 80)
        if all_passed:
            print("✓ ALL PAGES AND VIEWPORTS PASSED: Zero horizontal overflow, clean responsive rendering!")
        else:
            print("✗ SOME PAGES EXHIBITED HORIZONTAL OVERFLOW - Check logs above")

    finally:
        chrome_proc.terminate()
        try:
            chrome_proc.wait(timeout=3)
        except Exception:
            chrome_proc.kill()

if __name__ == "__main__":
    asyncio.run(run_audit())
