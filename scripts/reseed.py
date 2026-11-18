#!/usr/bin/env python3
import sys
import os

# Put backend root on python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from app.seeds.seed_data import seed_database, reseed_live_demo

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--live-demo-only":
        reseed_live_demo()
        print("✓ Reset Live Demo Auction (RFQ-2026-LIVE-DEMO) into its trigger window.")
    else:
        seed_database(reset=True)
        print("✓ Successfully initialized MERIDIAN database with complete seed dataset.")

