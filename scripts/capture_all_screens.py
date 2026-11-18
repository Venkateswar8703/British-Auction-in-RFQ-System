#!/usr/bin/env python3
"""
MERIDIAN Headless Chrome Screenshot & Layout Audit Suite
Captures all 6 required pages at 1280px and 390px:
1. Listing
2. Live Room
3. Details
4. Create RFQ
5. Command Center
6. Supplier Portal
"""
import os
import subprocess
import json

SCREENSHOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "docs", "overnight", "screenshots"))
os.makedirs(SCREENSHOT_DIR, exist_ok=True)

PAGES = [
    ("Listing", "http://localhost:5173/auctions?demo=buyer"),
    ("Live_Room", "http://localhost:5173/live/RFQ-2026-LIVE-DEMO?demo=buyer"),
    ("Details", "http://localhost:5173/auctions/RFQ-2026-LIVE-DEMO?demo=buyer"),
    ("Create_RFQ", "http://localhost:5173/create-rfq?demo=buyer"),
    ("Command_Center", "http://localhost:5173/command-center?demo=buyer"),
    ("Supplier_Portal", "http://localhost:5173/portal?demo=maersk"),
]

VIEWPORTS = [
    ("1280px", 1280, 900),
    ("390px", 390, 844),
]

def capture_all():
    print("=" * 80)
    print("CAPTURING ALL 6 MERIDIAN SCREENS AT 1280px & 390px")
    print("=" * 80)

    results = []

    for name, url in PAGES:
        for vp_name, width, height in VIEWPORTS:
            out_file = f"{name}_{vp_name}.png"
            out_path = os.path.join(SCREENSHOT_DIR, out_file)
            
            cmd = [
                "google-chrome",
                "--headless=new",
                "--no-sandbox",
                "--disable-gpu",
                f"--window-size={width},{height}",
                "--virtual-time-budget=4000",
                f"--screenshot={out_path}",
                url
            ]

            print(f"Capturing {name} at {vp_name} ({width}x{height})...")
            proc = subprocess.run(cmd, capture_output=True, text=True)
            
            size = os.path.getsize(out_path) if os.path.exists(out_path) else 0
            status = "PASS" if size > 10000 else "FAIL"
            print(f" -> Output: {out_file} ({size:,} bytes) | Status: {status}")
            
            results.append({
                "page": name,
                "viewport": vp_name,
                "size": size,
                "file": out_file,
                "status": status
            })

    print("\n" + "=" * 80)
    print("SCREENSHOT CAPTURE SUMMARY TABLE")
    print("=" * 80)
    print(f"{'Page':<18} | {'Viewport':<10} | {'File Size (bytes)':<18} | Status")
    print("-" * 80)
    for r in results:
        print(f"{r['page']:<18} | {r['viewport']:<10} | {r['size']:<18,} | {r['status']}")
    print("=" * 80)

if __name__ == "__main__":
    capture_all()

