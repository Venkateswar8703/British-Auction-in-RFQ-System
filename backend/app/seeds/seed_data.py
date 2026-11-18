import logging
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import List, Dict, Any
from sqlalchemy.orm import Session

from app.database import SessionLocal, engine, Base
from app.models.entities import (
    User,
    Supplier,
    RFQ,
    AuctionConfig,
    RFQInvitation,
    Bid,
    AuctionExtension,
    AuctionEvent,
    utc_now,
)
from app.models.enums import (
    UserRole,
    RFQStatus,
    TriggerType,
    InvitationStatus,
    AuctionEventType,
)
from app.services.auth import hash_password
from app.services.auction_engine import (
    process_bid_submission,
    check_and_update_rfq_status,
    calculate_rankings,
)

logger = logging.getLogger(__name__)


def seed_database(reset: bool = True):
    """
    Populates database with realistic enterprise procurement data:
    - 2 Buyer users (1 buyer organization)
    - 8 Supplier organizations with dedicated user accounts
    - 14 RFQs spanning SCHEDULED, ACTIVE, CLOSED, and FORCE_CLOSED
    - Rich bid histories and extension records
    - 1 Live Demo Auction primed inside its trigger window (effective_close in ~2 minutes)
    """
    db = SessionLocal()
    try:
        if reset:
            # Drop and recreate all tables for a clean slate
            Base.metadata.drop_all(bind=engine)
            Base.metadata.create_all(bind=engine)
            if engine.dialect.name.startswith("postgresql"):
                from sqlalchemy import text
                with engine.connect() as conn:
                    with conn.begin():
                        conn.execute(text("""
                            CREATE OR REPLACE FUNCTION prevent_audit_tampering()
                            RETURNS TRIGGER AS $$
                            BEGIN
                                RAISE EXCEPTION 'Audit trail is append-only. UPDATE and DELETE operations are strictly prohibited on auction_events.';
                            END;
                            $$ LANGUAGE plpgsql;

                            DROP TRIGGER IF EXISTS trg_prevent_audit_tampering ON auction_events;
                            CREATE TRIGGER trg_prevent_audit_tampering
                            BEFORE UPDATE OR DELETE ON auction_events
                            FOR EACH ROW
                            EXECUTE FUNCTION prevent_audit_tampering();
                        """))

        # 1. Create Buyers
        buyers = [
            User(
                email="buyer@meridian.com",
                password_hash=hash_password("MeridianBuyer2026!"),
                full_name="Eleanor Vance (VP Global Procurement)",
                role=UserRole.BUYER.value,
            ),
            User(
                email="alex.chen@meridian.com",
                password_hash=hash_password("MeridianBuyer2026!"),
                full_name="Alex Chen (Senior Freight Buyer)",
                role=UserRole.BUYER.value,
            ),
        ]
        db.add_all(buyers)
        db.flush()
        primary_buyer = buyers[0]

        # 2. Create 8 Suppliers and Supplier Users
        supplier_profiles = [
            ("Maersk Global Line", "MAERSK", "bids@maersk.com", "+45 33 63 33 63"),
            ("Hapag-Lloyd Ocean", "HAPAG", "quotes@hapag-lloyd.com", "+49 40 3001 0"),
            ("MSC Mediterranean Shipping", "MSC", "rfq@msc.com", "+41 22 703 8888"),
            ("CMA CGM Logistics", "CMACGM", "ocean@cma-cgm.com", "+33 4 88 91 90 00"),
            ("Evergreen Marine Corp", "EVERGREEN", "pricing@evergreen.com", "+886 2 2501 1111"),
            ("COSCO Shipping", "COSCO", "commercial@cosco.com", "+86 21 6596 6666"),
            ("ONE Ocean Network Express", "ONE", "rates@one-line.com", "+65 6890 1800"),
            ("Kuehne+Nagel Intermodal", "KN", "freight@kuehne-nagel.com", "+41 44 786 9511"),
        ]

        suppliers: List[Supplier] = []
        supplier_users: List[User] = []

        for name, code, email, phone in supplier_profiles:
            s = Supplier(
                name=name,
                code=code,
                contact_email=email,
                contact_phone=phone,
                is_active=True,
            )
            db.add(s)
            db.flush()
            suppliers.append(s)

            u = User(
                email=email,
                password_hash=hash_password("SupplierPass2026!"),
                full_name=f"{code} Key Account Rep",
                role=UserRole.SUPPLIER.value,
                supplier_id=s.id,
            )
            db.add(u)
            supplier_users.append(u)

        db.flush()

        now = utc_now()

        # 3. Create RFQs Across All Statuses
        # RFQ 1: LIVE DEMO AUCTION (Signature showcase)
        # Inside trigger window right now! Closes in 2.5 minutes, forced close in 15 minutes!
        demo_start = now - timedelta(minutes=45)
        demo_close = now + timedelta(minutes=2, seconds=30)  # Inside 10m window!
        demo_forced = now + timedelta(minutes=15)
        demo_pickup = now + timedelta(days=14)

        demo_rfq = RFQ(
            reference_id="RFQ-2026-LIVE-DEMO",
            title="Transpacific 40ft HC: Shanghai (CNSHA) → Long Beach (USLGB)",
            description="500 FEU high-cube containers. Direct liner service with refrigerated cargo capability. Strict cutoff.",
            origin="Shanghai Port (CNSHA)",
            destination="Port of Long Beach (USLGB)",
            pickup_date=demo_pickup,
            bid_start=demo_start,
            bid_close=demo_close,
            effective_close=demo_close,
            forced_close=demo_forced,
            status=RFQStatus.ACTIVE.value,
            created_by=primary_buyer.id,
        )
        db.add(demo_rfq)
        db.flush()

        demo_config = AuctionConfig(
            rfq_id=demo_rfq.id,
            trigger_window_minutes=5,  # 5 min window
            extension_minutes=3,       # 3 min extension
            trigger_type=TriggerType.L1_CHANGE.value,
        )
        db.add(demo_config)

        # Invite all suppliers to demo
        for s in suppliers:
            db.add(RFQInvitation(rfq_id=demo_rfq.id, supplier_id=s.id))
        db.flush()

        # Seed initial bids on demo RFQ
        # Maersk initial bid
        process_bid_submission(
            db=db,
            rfq_id=demo_rfq.id,
            supplier_id=suppliers[0].id,
            user_id=supplier_users[0].id,
            freight_charges=Decimal("2600.00"),
            origin_charges=Decimal("250.00"),
            destination_charges=Decimal("350.00"),
            transit_time_days=14,
            quote_validity_date=demo_pickup + timedelta(days=10),
            carrier_name="Maersk Triple-E",
            current_time=now - timedelta(minutes=30),
        )
        # Hapag bid
        process_bid_submission(
            db=db,
            rfq_id=demo_rfq.id,
            supplier_id=suppliers[1].id,
            user_id=supplier_users[1].id,
            freight_charges=Decimal("2500.00"),
            origin_charges=Decimal("220.00"),
            destination_charges=Decimal("330.00"),
            transit_time_days=15,
            quote_validity_date=demo_pickup + timedelta(days=12),
            carrier_name="Hapag Hamburg Express",
            current_time=now - timedelta(minutes=20),
        )
        # MSC bid taking L1
        process_bid_submission(
            db=db,
            rfq_id=demo_rfq.id,
            supplier_id=suppliers[2].id,
            user_id=supplier_users[2].id,
            freight_charges=Decimal("2350.00"),
            origin_charges=Decimal("200.00"),
            destination_charges=Decimal("300.00"),
            transit_time_days=14,
            quote_validity_date=demo_pickup + timedelta(days=15),
            carrier_name="MSC Gülsün",
            current_time=now - timedelta(minutes=10),
        )

        # Seed 13 additional RFQs across statuses
        rfq_catalog = [
            # ACTIVE RFQs
            {
                "ref": "RFQ-2026-002",
                "title": "Asia-Europe Loop: Ningbo (CNNGB) → Rotterdam (NLRTM)",
                "desc": "Heavy machinery breakbulk + 120 FEU dry containers. Premium fast-transit.",
                "origin": "Ningbo-Zhoushan Port (CNNGB)",
                "dest": "Port of Rotterdam (NLRTM)",
                "start": now - timedelta(hours=2),
                "close": now + timedelta(hours=3),
                "forced": now + timedelta(hours=5),
                "pickup": now + timedelta(days=20),
                "status": RFQStatus.ACTIVE.value,
                "window": 15,
                "ext": 10,
                "trigger": TriggerType.ANY_RANK_CHANGE.value,
                "suppliers": suppliers[:6],
                "bids": [
                    (0, 0, 3100, 300, 400, 24, now - timedelta(hours=1, minutes=45)),
                    (1, 1, 2950, 280, 390, 25, now - timedelta(hours=1, minutes=30)),
                    (2, 2, 2800, 250, 380, 23, now - timedelta(hours=1)),
                    (3, 3, 2750, 240, 370, 24, now - timedelta(minutes=45)),
                ],
            },
            {
                "ref": "RFQ-2026-003",
                "title": "Transatlantic Westbound: Antwerp (BEANR) → New York (USNYC)",
                "desc": "Pharmaceutical Grade Reefer containers with active telematics monitoring.",
                "origin": "Port of Antwerp (BEANR)",
                "dest": "Port of New York & New Jersey (USNYC)",
                "start": now - timedelta(hours=1),
                "close": now + timedelta(minutes=11),  # Closing soon (<15m)
                "forced": now + timedelta(hours=2),
                "pickup": now + timedelta(days=18),
                "status": RFQStatus.ACTIVE.value,
                "window": 10,
                "ext": 5,
                "trigger": TriggerType.L1_CHANGE.value,
                "suppliers": suppliers[2:7],
                "bids": [
                    (2, 2, 2200, 200, 250, 11, now - timedelta(minutes=40)),
                    (3, 3, 2150, 190, 240, 10, now - timedelta(minutes=25)),
                    (4, 4, 2050, 180, 230, 11, now - timedelta(minutes=15)),
                ],
            },
            {
                "ref": "RFQ-2026-004",
                "title": "South America East Coast: Santos (BRSSZ) → Hamburg (DEHAM)",
                "desc": "Agricultural export containers (Soybeans & Coffee beans).",
                "origin": "Port of Santos (BRSSZ)",
                "dest": "Port of Hamburg (DEHAM)",
                "start": now - timedelta(hours=3),
                "close": now + timedelta(hours=4),
                "forced": now + timedelta(hours=7),
                "pickup": now + timedelta(days=30),
                "status": RFQStatus.ACTIVE.value,
                "window": 20,
                "ext": 10,
                "trigger": TriggerType.BID_RECEIVED.value,
                "suppliers": suppliers[1:5],
                "bids": [
                    (1, 1, 1850, 150, 200, 20, now - timedelta(hours=2)),
                    (2, 2, 1750, 140, 190, 19, now - timedelta(hours=1, minutes=10)),
                ],
            },
            # SCHEDULED RFQs
            {
                "ref": "RFQ-2026-005",
                "title": "Middle East Gulf Feeder: Jebel Ali (AEJEA) → Nhava Sheva (INNSA)",
                "desc": "Regional short-sea feeder service for retail consumer electronics.",
                "origin": "Jebel Ali Port (AEJEA)",
                "dest": "Jawaharlal Nehru Port (INNSA)",
                "start": now + timedelta(hours=4),
                "close": now + timedelta(hours=12),
                "forced": now + timedelta(hours=16),
                "pickup": now + timedelta(days=25),
                "status": RFQStatus.SCHEDULED.value,
                "window": 15,
                "ext": 5,
                "trigger": TriggerType.L1_CHANGE.value,
                "suppliers": suppliers[:5],
                "bids": [],
            },
            {
                "ref": "RFQ-2026-006",
                "title": "Intra-Asia Express: Tokyo (JPTYO) → Ho Chi Minh City (VNSGN)",
                "desc": "Automotive assembly components. Guaranteed priority berthing required.",
                "origin": "Port of Tokyo (JPTYO)",
                "dest": "Cat Lai Port (VNSGN)",
                "start": now + timedelta(days=1),
                "close": now + timedelta(days=2),
                "forced": now + timedelta(days=2, hours=6),
                "pickup": now + timedelta(days=35),
                "status": RFQStatus.SCHEDULED.value,
                "window": 10,
                "ext": 5,
                "trigger": TriggerType.BID_RECEIVED.value,
                "suppliers": suppliers[3:],
                "bids": [],
            },
            {
                "ref": "RFQ-2026-007",
                "title": "Scandinavia Baltic: Gothenburg (SEGOT) → Gdansk (PLGDN)",
                "desc": "Forestry products and paper rolls. 80 Standard 40ft units.",
                "origin": "Port of Gothenburg (SEGOT)",
                "dest": "Baltic Hub Gdansk (PLGDN)",
                "start": now + timedelta(days=2),
                "close": now + timedelta(days=3),
                "forced": now + timedelta(days=3, hours=4),
                "pickup": now + timedelta(days=40),
                "status": RFQStatus.SCHEDULED.value,
                "window": 15,
                "ext": 10,
                "trigger": TriggerType.ANY_RANK_CHANGE.value,
                "suppliers": suppliers[:4],
                "bids": [],
            },
            # CLOSED RFQs (Completed auctions with rich bid history and extensions)
            {
                "ref": "RFQ-2026-008",
                "title": "Transpacific Eastbound: Yantian (CNYAT) → Oakland (USOAK)",
                "desc": "Solar equipment modules. 250 FEU. Extended twice during final 15 minutes.",
                "origin": "Yantian International Container Terminals (CNYAT)",
                "dest": "Port of Oakland (USOAK)",
                "start": now - timedelta(days=3),
                "close": now - timedelta(days=2, hours=10),
                "forced": now - timedelta(days=2, hours=6),
                "pickup": now + timedelta(days=10),
                "status": RFQStatus.CLOSED.value,
                "window": 10,
                "ext": 5,
                "trigger": TriggerType.L1_CHANGE.value,
                "suppliers": suppliers[:6],
                "bids": [
                    (0, 0, 2800, 250, 300, 15, now - timedelta(days=3, hours=2)),
                    (1, 1, 2650, 240, 290, 16, now - timedelta(days=2, hours=12)),
                    (2, 2, 2500, 220, 280, 14, now - timedelta(days=2, hours=10, minutes=8)),
                    (3, 3, 2420, 210, 270, 14, now - timedelta(days=2, hours=10, minutes=4)),
                ],
            },
            {
                "ref": "RFQ-2026-009",
                "title": "Mediterranean Direct: Valencia (ESVLC) → Port Said (EGPSD)",
                "desc": "Ceramic tiles and construction materials. Standard 20ft heavy boxes.",
                "origin": "Port of Valencia (ESVLC)",
                "dest": "Port Said East (EGPSD)",
                "start": now - timedelta(days=4),
                "close": now - timedelta(days=3),
                "forced": now - timedelta(days=2, hours=20),
                "pickup": now + timedelta(days=12),
                "status": RFQStatus.CLOSED.value,
                "window": 15,
                "ext": 5,
                "trigger": TriggerType.BID_RECEIVED.value,
                "suppliers": suppliers[2:7],
                "bids": [
                    (2, 2, 1450, 120, 180, 7, now - timedelta(days=3, hours=6)),
                    (3, 3, 1380, 110, 170, 6, now - timedelta(days=3, hours=2)),
                    (4, 4, 1320, 100, 160, 7, now - timedelta(days=3, minutes=10)),
                ],
            },
            {
                "ref": "RFQ-2026-010",
                "title": "Oceania Loop: Singapore (SGSIN) → Melbourne (AUMEL)",
                "desc": "Consumer white goods and FMCG pallets. High volume seasonal contract.",
                "origin": "PSA Singapore (SGSIN)",
                "dest": "Port of Melbourne (AUMEL)",
                "start": now - timedelta(days=5),
                "close": now - timedelta(days=4),
                "forced": now - timedelta(days=3, hours=18),
                "pickup": now + timedelta(days=15),
                "status": RFQStatus.CLOSED.value,
                "window": 20,
                "ext": 10,
                "trigger": TriggerType.ANY_RANK_CHANGE.value,
                "suppliers": suppliers[1:6],
                "bids": [
                    (1, 1, 2100, 180, 220, 13, now - timedelta(days=4, hours=8)),
                    (2, 2, 1980, 170, 210, 12, now - timedelta(days=4, hours=4)),
                    (3, 3, 1890, 160, 200, 13, now - timedelta(days=4, minutes=14)),
                ],
            },
            {
                "ref": "RFQ-2026-011",
                "title": "UK Gateway: Felixstowe (GBFXT) → Bremerhaven (DEBRV)",
                "desc": "Cross-channel short-sea shuttle. Fast turnaround roll-on containers.",
                "origin": "Port of Felixstowe (GBFXT)",
                "dest": "Bremerhaven Container Terminal (DEBRV)",
                "start": now - timedelta(days=6),
                "close": now - timedelta(days=5),
                "forced": now - timedelta(days=4, hours=22),
                "pickup": now + timedelta(days=8),
                "status": RFQStatus.CLOSED.value,
                "window": 10,
                "ext": 5,
                "trigger": TriggerType.L1_CHANGE.value,
                "suppliers": suppliers[:4],
                "bids": [
                    (0, 0, 950, 80, 110, 3, now - timedelta(days=5, hours=5)),
                    (1, 1, 910, 75, 105, 3, now - timedelta(days=5, hours=2)),
                    (2, 2, 870, 70, 100, 2, now - timedelta(days=5, minutes=7)),
                ],
            },
            # FORCE_CLOSED RFQs (Auctions extended repeatedly until reaching forced close ceiling)
            {
                "ref": "RFQ-2026-012",
                "title": "High-Demand Spot Lane: Busan (KRPUS) → Los Angeles (USLAX)",
                "desc": "Surge capacity peak-season auction. Hit hard forced close ceiling after 4 consecutive bidding extensions.",
                "origin": "Busan New Port (KRPUS)",
                "dest": "Port of Los Angeles (USLAX)",
                "start": now - timedelta(days=2),
                "close": now - timedelta(days=1, hours=8),  # Originally closed
                "forced": now - timedelta(days=1, hours=7),  # Hit forced ceiling
                "pickup": now + timedelta(days=16),
                "status": RFQStatus.FORCE_CLOSED.value,
                "window": 15,
                "ext": 10,
                "trigger": TriggerType.BID_RECEIVED.value,
                "suppliers": suppliers[:7],
                "bids": [
                    (0, 0, 2900, 250, 350, 13, now - timedelta(days=1, hours=9)),
                    (1, 1, 2750, 240, 340, 12, now - timedelta(days=1, hours=8, minutes=10)),
                    (2, 2, 2600, 230, 330, 13, now - timedelta(days=1, hours=7, minutes=50)),
                    (3, 3, 2480, 220, 320, 12, now - timedelta(days=1, hours=7, minutes=30)),
                    (4, 4, 2390, 210, 310, 12, now - timedelta(days=1, hours=7, minutes=5)),
                ],
            },
            {
                "ref": "RFQ-2026-013",
                "title": "Bulk Raw Materials: Durban (ZADUR) → Rotterdam (NLRTM)",
                "desc": "Heavy mineral sands and ores. Reached forced close limit after fierce bidding between European carriers.",
                "origin": "Port of Durban (ZADUR)",
                "dest": "Port of Rotterdam (NLRTM)",
                "start": now - timedelta(days=3),
                "close": now - timedelta(days=2),
                "forced": now - timedelta(days=1, hours=22),
                "pickup": now + timedelta(days=22),
                "status": RFQStatus.FORCE_CLOSED.value,
                "window": 20,
                "ext": 10,
                "trigger": TriggerType.ANY_RANK_CHANGE.value,
                "suppliers": suppliers[2:8],
                "bids": [
                    (2, 2, 2100, 190, 260, 22, now - timedelta(days=2, hours=2)),
                    (3, 3, 1990, 180, 250, 21, now - timedelta(days=2, minutes=15)),
                    (4, 4, 1910, 170, 240, 20, now - timedelta(days=1, hours=23)),
                    (5, 5, 1840, 160, 230, 21, now - timedelta(days=1, hours=22, minutes=5)),
                ],
            },
            {
                "ref": "RFQ-2026-014",
                "title": "Automotive Tier-1: Bremerhaven (DEBRV) → Charleston (USCHS)",
                "desc": "Luxury vehicle sub-assemblies. Forced close triggered due to fixed plant production scheduling.",
                "origin": "Bremerhaven BLG AutoTerminal (DEBRV)",
                "dest": "Port of Charleston (USCHS)",
                "start": now - timedelta(days=4),
                "close": now - timedelta(days=3),
                "forced": now - timedelta(days=2, hours=21),
                "pickup": now + timedelta(days=14),
                "status": RFQStatus.FORCE_CLOSED.value,
                "window": 10,
                "ext": 5,
                "trigger": TriggerType.L1_CHANGE.value,
                "suppliers": suppliers[:5],
                "bids": [
                    (0, 0, 2400, 220, 280, 12, now - timedelta(days=3, hours=4)),
                    (1, 1, 2280, 210, 270, 11, now - timedelta(days=3, minutes=8)),
                    (2, 2, 2190, 200, 260, 12, now - timedelta(days=2, hours=21, minutes=4)),
                ],
            },
        ]

        for item in rfq_catalog:
            # For force closed items, effective_close equals forced
            eff_close = item["forced"] if item["status"] == RFQStatus.FORCE_CLOSED.value else item["close"]
            rfq_obj = RFQ(
                reference_id=item["ref"],
                title=item["title"],
                description=item["desc"],
                origin=item["origin"],
                destination=item["dest"],
                pickup_date=item["pickup"],
                bid_start=item["start"],
                bid_close=item["close"],
                effective_close=eff_close,
                forced_close=item["forced"],
                status=item["status"],
                created_by=primary_buyer.id,
            )
            db.add(rfq_obj)
            db.flush()

            cfg = AuctionConfig(
                rfq_id=rfq_obj.id,
                trigger_window_minutes=item["window"],
                extension_minutes=item["ext"],
                trigger_type=item["trigger"],
            )
            db.add(cfg)

            for s in item["suppliers"]:
                db.add(RFQInvitation(rfq_id=rfq_obj.id, supplier_id=s.id))
            db.flush()

            # Insert bids
            for s_idx, u_idx, freight, origin, dest, transit, bid_time in item["bids"]:
                s_obj = suppliers[s_idx]
                u_obj = supplier_users[u_idx]
                tot = Decimal(str(freight + origin + dest))
                b = Bid(
                    rfq_id=rfq_obj.id,
                    supplier_id=s_obj.id,
                    submitted_by=u_obj.id,
                    freight_charges=Decimal(str(freight)),
                    origin_charges=Decimal(str(origin)),
                    destination_charges=Decimal(str(dest)),
                    total=tot,
                    transit_time_days=transit,
                    quote_validity_date=item["pickup"] + timedelta(days=10),
                    carrier_name=f"{s_obj.code} Commercial Line",
                    created_at=bid_time,
                )
                db.add(b)
                db.flush()

                # Add event
                ev = AuctionEvent(
                    rfq_id=rfq_obj.id,
                    bid_id=b.id,
                    event_type=AuctionEventType.BID_SUBMITTED.value,
                    payload={
                        "bid_id": b.id,
                        "supplier_id": s_obj.id,
                        "total": float(tot),
                        "server_time": bid_time.isoformat(),
                    },
                    created_at=bid_time,
                )
                db.add(ev)

            # If forced close, add extension records demonstrating it was clamped
            if item["status"] == RFQStatus.FORCE_CLOSED.value:
                ext = AuctionExtension(
                    rfq_id=rfq_obj.id,
                    triggering_bid_id=None,
                    previous_close=item["close"],
                    new_close=item["forced"],
                    trigger_type=item["trigger"],
                    reason=f"Auction extended to forced close deadline ({item['forced'].isoformat()}) due to competitive activity.",
                    is_clamped=True,
                    created_at=item["forced"] - timedelta(minutes=15),
                )
                db.add(ext)

        db.commit()
        logger.info("Successfully seeded MERIDIAN database with %d RFQs and 8 suppliers.", len(rfq_catalog) + 1)
        return True

    except Exception as e:
        db.rollback()
        logger.error("Error during seed_database: %s", e)
        raise
    finally:
        db.close()


def reseed_live_demo():
    """
    Specifically resets the Live Demo Auction (RFQ-2026-LIVE-DEMO)
    so the live countdown is ~2.5 minutes from now, allowing quick testing of extensions.
    """
    db = SessionLocal()
    try:
        now = utc_now()
        rfq = db.query(RFQ).filter(RFQ.reference_id == "RFQ-2026-LIVE-DEMO").first()
        if not rfq:
            # If database not seeded, seed everything
            seed_database(reset=False)
            return

        # Reset timeline
        rfq.bid_start = now - timedelta(minutes=45)
        rfq.bid_close = now + timedelta(minutes=2, seconds=30)
        rfq.effective_close = now + timedelta(minutes=2, seconds=30)
        rfq.forced_close = now + timedelta(minutes=15)
        rfq.status = RFQStatus.ACTIVE.value
        db.commit()
        logger.info("Reset Live Demo Auction RFQ-2026-LIVE-DEMO to close at %s", rfq.effective_close.isoformat())
    finally:
        db.close()


if __name__ == "__main__":
    seed_database(reset=True)
    print("MERIDIAN database seeded successfully.")

