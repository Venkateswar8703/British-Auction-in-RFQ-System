import pytest
from datetime import datetime, timezone, timedelta
from decimal import Decimal

from app.models.entities import RFQ, AuctionConfig, RFQInvitation, Bid, AuctionEvent
from app.models.enums import RFQStatus, TriggerType, AuctionEventType
from app.services.auction_engine import (
    process_bid_submission,
    check_and_update_rfq_status,
    calculate_rankings,
)
from app.services.exceptions import (
    AuctionNotStartedError,
    BidAfterCloseError,
    BidAfterForcedCloseError,
    AuctionClosedError,
    SupplierNotInvitedError,
    BidNotLowerError,
    InvalidValidityDateError,
)


def create_rfq_helper(
    db,
    buyer,
    suppliers,
    bid_start,
    bid_close,
    forced_close,
    pickup_date,
    trigger_window_minutes=10,
    extension_minutes=5,
    trigger_type=TriggerType.L1_CHANGE.value,
    status=RFQStatus.ACTIVE.value,
):
    rfq = RFQ(
        reference_id=f"RFQ-TEST-{int(datetime.now(timezone.utc).timestamp() * 1000)}",
        title="Transpacific 40ft High Cube Container Freight",
        description="Dry van shipment from Shanghai to Long Beach",
        origin="Shanghai Port (CNSHA)",
        destination="Long Beach Port (USLGB)",
        pickup_date=pickup_date,
        bid_start=bid_start,
        bid_close=bid_close,
        effective_close=bid_close,
        forced_close=forced_close,
        status=status,
        created_by=buyer.id,
    )
    db.add(rfq)
    db.flush()

    config = AuctionConfig(
        rfq_id=rfq.id,
        trigger_window_minutes=trigger_window_minutes,
        extension_minutes=extension_minutes,
        trigger_type=trigger_type,
    )
    db.add(config)

    for s in suppliers:
        inv = RFQInvitation(rfq_id=rfq.id, supplier_id=s.id)
        db.add(inv)

    db.commit()
    db.refresh(rfq)
    return rfq


# -------------------------------------------------------------
# Test 1: Authoritative Example Scenario from Section 9
# Close 6:00 PM, X=10, Y=5, forced close 6:30 PM.
# Bid at 5:55 PM gives 6:05 PM.
# Bid at 6:03 PM gives 6:08 PM.
# -------------------------------------------------------------
def test_example_scenario_close_extension(db_session, buyer_user, suppliers, supplier_users):
    base_time = datetime(2026, 6, 1, 17, 0, 0, tzinfo=timezone.utc)
    bid_start = base_time
    bid_close = datetime(2026, 6, 1, 18, 0, 0, tzinfo=timezone.utc)  # 6:00 PM
    forced_close = datetime(2026, 6, 1, 18, 30, 0, tzinfo=timezone.utc)  # 6:30 PM
    pickup_date = datetime(2026, 6, 10, 0, 0, 0, tzinfo=timezone.utc)

    rfq = create_rfq_helper(
        db_session,
        buyer_user,
        suppliers[:3],
        bid_start=bid_start,
        bid_close=bid_close,
        forced_close=forced_close,
        pickup_date=pickup_date,
        trigger_window_minutes=10,  # X = 10
        extension_minutes=5,        # Y = 5
        trigger_type=TriggerType.BID_RECEIVED.value,
    )

    # Initial close is 6:00 PM
    assert rfq.effective_close == datetime(2026, 6, 1, 18, 0, 0, tzinfo=timezone.utc)

    # Bid 1: at 5:55 PM (inside [5:50 PM, 6:00 PM))
    bid_time_1 = datetime(2026, 6, 1, 17, 55, 0, tzinfo=timezone.utc)
    res_1 = process_bid_submission(
        db=db_session,
        rfq_id=rfq.id,
        supplier_id=suppliers[0].id,
        user_id=supplier_users[0].id,
        freight_charges=Decimal("3000.00"),
        origin_charges=Decimal("200.00"),
        destination_charges=Decimal("300.00"),
        transit_time_days=14,
        quote_validity_date=pickup_date + timedelta(days=5),
        carrier_name="Ocean Express",
        current_time=bid_time_1,
    )

    assert res_1["extension_applied"] is True
    db_session.refresh(rfq)
    # New effective close should be 6:05 PM
    expected_close_1 = datetime(2026, 6, 1, 18, 5, 0, tzinfo=timezone.utc)
    assert rfq.effective_close == expected_close_1

    # Bid 2: at 6:03 PM (inside new window [5:55 PM, 6:05 PM))
    bid_time_2 = datetime(2026, 6, 1, 18, 3, 0, tzinfo=timezone.utc)
    res_2 = process_bid_submission(
        db=db_session,
        rfq_id=rfq.id,
        supplier_id=suppliers[1].id,
        user_id=supplier_users[1].id,
        freight_charges=Decimal("2800.00"),
        origin_charges=Decimal("200.00"),
        destination_charges=Decimal("300.00"),
        transit_time_days=14,
        quote_validity_date=pickup_date + timedelta(days=5),
        carrier_name="Ocean Express",
        current_time=bid_time_2,
    )

    assert res_2["extension_applied"] is True
    db_session.refresh(rfq)
    # New effective close should be 6:10 PM (effective_close + 5m)
    expected_close_2 = datetime(2026, 6, 1, 18, 10, 0, tzinfo=timezone.utc)
    assert rfq.effective_close == expected_close_2


# -------------------------------------------------------------
# Test 2: Trigger Type L1_CHANGE
# -------------------------------------------------------------
def test_trigger_type_l1_change(db_session, buyer_user, suppliers, supplier_users):
    bid_start = datetime(2026, 6, 1, 10, 0, 0, tzinfo=timezone.utc)
    bid_close = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
    forced_close = datetime(2026, 6, 1, 13, 0, 0, tzinfo=timezone.utc)
    pickup_date = datetime(2026, 6, 15, 0, 0, 0, tzinfo=timezone.utc)

    rfq = create_rfq_helper(
        db_session,
        buyer_user,
        suppliers[:3],
        bid_start=bid_start,
        bid_close=bid_close,
        forced_close=forced_close,
        pickup_date=pickup_date,
        trigger_window_minutes=10,
        extension_minutes=5,
        trigger_type=TriggerType.L1_CHANGE.value,
    )

    # 1. First bid inside window: at 11:55 AM -> establishes L1, must extend!
    res_1 = process_bid_submission(
        db=db_session,
        rfq_id=rfq.id,
        supplier_id=suppliers[0].id,
        user_id=supplier_users[0].id,
        freight_charges=Decimal("2000.00"),
        origin_charges=Decimal("100.00"),
        destination_charges=Decimal("100.00"),
        transit_time_days=10,
        quote_validity_date=pickup_date,
        carrier_name="Carrier A",
        current_time=datetime(2026, 6, 1, 11, 55, 0, tzinfo=timezone.utc),
    )
    assert res_1["extension_applied"] is True
    db_session.refresh(rfq)
    assert rfq.effective_close == datetime(2026, 6, 1, 12, 5, 0, tzinfo=timezone.utc)

    # 2. Supplier 1 (already L1) lowers their own price at 12:01 PM.
    # L1 identity does NOT change (still Supplier 0). Must NOT extend!
    res_2 = process_bid_submission(
        db=db_session,
        rfq_id=rfq.id,
        supplier_id=suppliers[0].id,
        user_id=supplier_users[0].id,
        freight_charges=Decimal("1900.00"),
        origin_charges=Decimal("100.00"),
        destination_charges=Decimal("100.00"),
        transit_time_days=10,
        quote_validity_date=pickup_date,
        carrier_name="Carrier A",
        current_time=datetime(2026, 6, 1, 12, 1, 0, tzinfo=timezone.utc),
    )
    assert res_2["extension_applied"] is False
    db_session.refresh(rfq)
    assert rfq.effective_close == datetime(2026, 6, 1, 12, 5, 0, tzinfo=timezone.utc)

    # 3. Supplier 2 bids at 12:02 PM with a higher price ($2500 total).
    # L1 identity does NOT change (still Supplier 0). Must NOT extend!
    res_3 = process_bid_submission(
        db=db_session,
        rfq_id=rfq.id,
        supplier_id=suppliers[1].id,
        user_id=supplier_users[1].id,
        freight_charges=Decimal("2300.00"),
        origin_charges=Decimal("100.00"),
        destination_charges=Decimal("100.00"),
        transit_time_days=10,
        quote_validity_date=pickup_date,
        carrier_name="Carrier B",
        current_time=datetime(2026, 6, 1, 12, 2, 0, tzinfo=timezone.utc),
    )
    assert res_3["extension_applied"] is False
    db_session.refresh(rfq)
    assert rfq.effective_close == datetime(2026, 6, 1, 12, 5, 0, tzinfo=timezone.utc)

    # 4. Supplier 2 bids at 12:04 PM with a lower price ($1800 total).
    # Supplier 2 becomes new L1! Identity changed! MUST extend!
    res_4 = process_bid_submission(
        db=db_session,
        rfq_id=rfq.id,
        supplier_id=suppliers[1].id,
        user_id=supplier_users[1].id,
        freight_charges=Decimal("1600.00"),
        origin_charges=Decimal("100.00"),
        destination_charges=Decimal("100.00"),
        transit_time_days=10,
        quote_validity_date=pickup_date,
        carrier_name="Carrier B",
        current_time=datetime(2026, 6, 1, 12, 4, 0, tzinfo=timezone.utc),
    )
    assert res_4["extension_applied"] is True
    db_session.refresh(rfq)
    # Close extended from 12:05 to 12:05 + 5 = 12:10 PM
    assert rfq.effective_close == datetime(2026, 6, 1, 12, 10, 0, tzinfo=timezone.utc)


# -------------------------------------------------------------
# Test 3: Trigger Type ANY_RANK_CHANGE
# -------------------------------------------------------------
def test_trigger_type_any_rank_change(db_session, buyer_user, suppliers, supplier_users):
    bid_start = datetime(2026, 6, 1, 10, 0, 0, tzinfo=timezone.utc)
    bid_close = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
    forced_close = datetime(2026, 6, 1, 13, 0, 0, tzinfo=timezone.utc)
    pickup_date = datetime(2026, 6, 15, 0, 0, 0, tzinfo=timezone.utc)

    rfq = create_rfq_helper(
        db_session,
        buyer_user,
        suppliers[:4],
        bid_start=bid_start,
        bid_close=bid_close,
        forced_close=forced_close,
        pickup_date=pickup_date,
        trigger_window_minutes=10,
        extension_minutes=5,
        trigger_type=TriggerType.ANY_RANK_CHANGE.value,
    )

    # Pre-populate bids outside the window (at 10:30 AM and 10:35 AM)
    # Supplier 0: $2000 (Rank 1)
    # Supplier 1: $2500 (Rank 2)
    process_bid_submission(
        db=db_session,
        rfq_id=rfq.id,
        supplier_id=suppliers[0].id,
        user_id=supplier_users[0].id,
        freight_charges=Decimal("1800.00"),
        origin_charges=Decimal("100.00"),
        destination_charges=Decimal("100.00"),
        transit_time_days=10,
        quote_validity_date=pickup_date,
        carrier_name="Carrier A",
        current_time=datetime(2026, 6, 1, 10, 30, 0, tzinfo=timezone.utc),
    )
    process_bid_submission(
        db=db_session,
        rfq_id=rfq.id,
        supplier_id=suppliers[1].id,
        user_id=supplier_users[1].id,
        freight_charges=Decimal("2300.00"),
        origin_charges=Decimal("100.00"),
        destination_charges=Decimal("100.00"),
        transit_time_days=10,
        quote_validity_date=pickup_date,
        carrier_name="Carrier B",
        current_time=datetime(2026, 6, 1, 10, 35, 0, tzinfo=timezone.utc),
    )

    db_session.refresh(rfq)
    assert rfq.effective_close == bid_close  # Still 12:00 PM

    # Scenario A: New supplier 2 enters at the bottom ($3000 total) at 11:55 AM.
    # Existing ranks: Supplier 0 is 1, Supplier 1 is 2.
    # New ranks: Supplier 0 is 1, Supplier 1 is 2, Supplier 2 is 3.
    # No previously ranked supplier's position changed!
    # "A new supplier entering at the bottom ... does not qualify."
    res_a = process_bid_submission(
        db=db_session,
        rfq_id=rfq.id,
        supplier_id=suppliers[2].id,
        user_id=supplier_users[2].id,
        freight_charges=Decimal("2800.00"),
        origin_charges=Decimal("100.00"),
        destination_charges=Decimal("100.00"),
        transit_time_days=10,
        quote_validity_date=pickup_date,
        carrier_name="Carrier C",
        current_time=datetime(2026, 6, 1, 11, 55, 0, tzinfo=timezone.utc),
    )
    assert res_a["extension_applied"] is False
    db_session.refresh(rfq)
    assert rfq.effective_close == bid_close

    # Scenario B: Supplier 0 (already rank 1) lowers price from $2000 to $1900 at 11:56 AM.
    # "or a supplier lowering their price without changing any positions, does not qualify."
    res_b = process_bid_submission(
        db=db_session,
        rfq_id=rfq.id,
        supplier_id=suppliers[0].id,
        user_id=supplier_users[0].id,
        freight_charges=Decimal("1700.00"),
        origin_charges=Decimal("100.00"),
        destination_charges=Decimal("100.00"),
        transit_time_days=10,
        quote_validity_date=pickup_date,
        carrier_name="Carrier A",
        current_time=datetime(2026, 6, 1, 11, 56, 0, tzinfo=timezone.utc),
    )
    assert res_b["extension_applied"] is False
    db_session.refresh(rfq)
    assert rfq.effective_close == bid_close

    # Scenario C: Supplier 1 (rank 2, $2500) lowers price to $1800 at 11:57 AM.
    # Supplier 1 becomes rank 1, Supplier 0 becomes rank 2!
    # Positions of previously ranked suppliers CHANGED! Must qualify and extend!
    res_c = process_bid_submission(
        db=db_session,
        rfq_id=rfq.id,
        supplier_id=suppliers[1].id,
        user_id=supplier_users[1].id,
        freight_charges=Decimal("1600.00"),
        origin_charges=Decimal("100.00"),
        destination_charges=Decimal("100.00"),
        transit_time_days=10,
        quote_validity_date=pickup_date,
        carrier_name="Carrier B",
        current_time=datetime(2026, 6, 1, 11, 57, 0, tzinfo=timezone.utc),
    )
    assert res_c["extension_applied"] is True
    db_session.refresh(rfq)
    assert rfq.effective_close > bid_close


# -------------------------------------------------------------
# Test 4: Extension Clamped at Forced Close and Capped when Reached
# -------------------------------------------------------------
def test_extension_clamped_and_capped(db_session, buyer_user, suppliers, supplier_users):
    bid_start = datetime(2026, 6, 1, 10, 0, 0, tzinfo=timezone.utc)
    bid_close = datetime(2026, 6, 1, 12, 28, 0, tzinfo=timezone.utc)  # 12:28 PM
    forced_close = datetime(2026, 6, 1, 12, 30, 0, tzinfo=timezone.utc)  # 12:30 PM (only 2 mins away!)
    pickup_date = datetime(2026, 6, 15, 0, 0, 0, tzinfo=timezone.utc)

    rfq = create_rfq_helper(
        db_session,
        buyer_user,
        suppliers[:2],
        bid_start=bid_start,
        bid_close=bid_close,
        forced_close=forced_close,
        pickup_date=pickup_date,
        trigger_window_minutes=10,
        extension_minutes=5,  # Y = 5 would exceed 12:30 PM
        trigger_type=TriggerType.BID_RECEIVED.value,
    )

    # Bid at 12:25 PM: inside window. Target close would be 12:30 or 12:33, clamped to 12:30 PM.
    res = process_bid_submission(
        db=db_session,
        rfq_id=rfq.id,
        supplier_id=suppliers[0].id,
        user_id=supplier_users[0].id,
        freight_charges=Decimal("2000.00"),
        origin_charges=Decimal("100.00"),
        destination_charges=Decimal("100.00"),
        transit_time_days=10,
        quote_validity_date=pickup_date,
        carrier_name="Carrier A",
        current_time=datetime(2026, 6, 1, 12, 25, 0, tzinfo=timezone.utc),
    )

    assert res["extension_applied"] is True
    db_session.refresh(rfq)
    assert rfq.effective_close == forced_close
    assert res["extension"].is_clamped is True

    # Now effective_close equals forced_close (12:30 PM).
    # Submit another bid at 12:29 PM.
    # "If effective_close already equals forced_close, no extension happens. Log an event noting that the extension was capped."
    res_capped = process_bid_submission(
        db=db_session,
        rfq_id=rfq.id,
        supplier_id=suppliers[1].id,
        user_id=supplier_users[1].id,
        freight_charges=Decimal("1800.00"),
        origin_charges=Decimal("100.00"),
        destination_charges=Decimal("100.00"),
        transit_time_days=10,
        quote_validity_date=pickup_date,
        carrier_name="Carrier B",
        current_time=datetime(2026, 6, 1, 12, 29, 0, tzinfo=timezone.utc),
    )

    assert res_capped["extension_applied"] is False
    assert res_capped["extension_capped"] is True
    db_session.refresh(rfq)
    assert rfq.effective_close == forced_close


# -------------------------------------------------------------
# Test 5: Strict Validation Rejections
# -------------------------------------------------------------
def test_bid_validation_rejections(db_session, buyer_user, suppliers, supplier_users):
    bid_start = datetime(2026, 6, 1, 10, 0, 0, tzinfo=timezone.utc)
    bid_close = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
    forced_close = datetime(2026, 6, 1, 13, 0, 0, tzinfo=timezone.utc)
    pickup_date = datetime(2026, 6, 15, 0, 0, 0, tzinfo=timezone.utc)

    # Helper for fresh RFQ
    def make_rfq():
        return create_rfq_helper(
            db_session,
            buyer_user,
            [suppliers[0]],
            bid_start=bid_start,
            bid_close=bid_close,
            forced_close=forced_close,
            pickup_date=pickup_date,
        )

    # 1. Reject before start
    rfq1 = make_rfq()
    with pytest.raises(AuctionNotStartedError):
        process_bid_submission(
            db=db_session,
            rfq_id=rfq1.id,
            supplier_id=suppliers[0].id,
            user_id=supplier_users[0].id,
            freight_charges=Decimal("2000.00"),
            origin_charges=Decimal("100.00"),
            destination_charges=Decimal("100.00"),
            transit_time_days=10,
            quote_validity_date=pickup_date,
            carrier_name="Carrier A",
            current_time=datetime(2026, 6, 1, 9, 59, 0, tzinfo=timezone.utc),
        )

    # 2. Reject uninvited supplier (at 10:30 AM during active auction)
    rfq2 = make_rfq()
    with pytest.raises(SupplierNotInvitedError):
        process_bid_submission(
            db=db_session,
            rfq_id=rfq2.id,
            supplier_id=suppliers[1].id,  # not invited
            user_id=supplier_users[1].id,
            freight_charges=Decimal("2000.00"),
            origin_charges=Decimal("100.00"),
            destination_charges=Decimal("100.00"),
            transit_time_days=10,
            quote_validity_date=pickup_date,
            carrier_name="Carrier B",
            current_time=datetime(2026, 6, 1, 10, 30, 0, tzinfo=timezone.utc),
        )

    # 3. Reject after effective close (at 12:00:00 PM)
    rfq3 = make_rfq()
    with pytest.raises(BidAfterCloseError):
        process_bid_submission(
            db=db_session,
            rfq_id=rfq3.id,
            supplier_id=suppliers[0].id,
            user_id=supplier_users[0].id,
            freight_charges=Decimal("2000.00"),
            origin_charges=Decimal("100.00"),
            destination_charges=Decimal("100.00"),
            transit_time_days=10,
            quote_validity_date=pickup_date,
            carrier_name="Carrier A",
            current_time=datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc),
        )

    # 4. First valid bid succeeds
    rfq4 = make_rfq()
    res_1 = process_bid_submission(
        db=db_session,
        rfq_id=rfq4.id,
        supplier_id=suppliers[0].id,
        user_id=supplier_users[0].id,
        freight_charges=Decimal("2000.00"),
        origin_charges=Decimal("100.00"),
        destination_charges=Decimal("100.00"),
        transit_time_days=10,
        quote_validity_date=pickup_date,
        carrier_name="Carrier A",
        current_time=datetime(2026, 6, 1, 10, 30, 0, tzinfo=timezone.utc),
    )
    assert res_1["bid"].total == Decimal("2200.00")

    # 5. Reject equal or higher bid from same supplier
    with pytest.raises(BidNotLowerError):
        process_bid_submission(
            db=db_session,
            rfq_id=rfq4.id,
            supplier_id=suppliers[0].id,
            user_id=supplier_users[0].id,
            freight_charges=Decimal("2000.00"),
            origin_charges=Decimal("100.00"),
            destination_charges=Decimal("100.00"),  # Total = 2200 (not strictly lower!)
            transit_time_days=10,
            quote_validity_date=pickup_date,
            carrier_name="Carrier A",
            current_time=datetime(2026, 6, 1, 10, 35, 0, tzinfo=timezone.utc),
        )

    # 6. Reject invalid validity date (before pickup_date)
    with pytest.raises(InvalidValidityDateError):
        process_bid_submission(
            db=db_session,
            rfq_id=rfq4.id,
            supplier_id=suppliers[0].id,
            user_id=supplier_users[0].id,
            freight_charges=Decimal("1900.00"),
            origin_charges=Decimal("100.00"),
            destination_charges=Decimal("100.00"),
            transit_time_days=10,
            quote_validity_date=pickup_date - timedelta(days=1),
            carrier_name="Carrier A",
            current_time=datetime(2026, 6, 1, 10, 36, 0, tzinfo=timezone.utc),
        )


# -------------------------------------------------------------
# Test 6: Tie-breaking by Timestamp and Ranking
# -------------------------------------------------------------
def test_ranking_and_tie_breaking(db_session, buyer_user, suppliers, supplier_users):
    bid_start = datetime(2026, 6, 1, 10, 0, 0, tzinfo=timezone.utc)
    bid_close = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
    forced_close = datetime(2026, 6, 1, 13, 0, 0, tzinfo=timezone.utc)
    pickup_date = datetime(2026, 6, 15, 0, 0, 0, tzinfo=timezone.utc)

    rfq = create_rfq_helper(
        db_session,
        buyer_user,
        suppliers[:3],
        bid_start=bid_start,
        bid_close=bid_close,
        forced_close=forced_close,
        pickup_date=pickup_date,
    )

    # Supplier 0 bids $2500 total at 10:10:00
    process_bid_submission(
        db=db_session,
        rfq_id=rfq.id,
        supplier_id=suppliers[0].id,
        user_id=supplier_users[0].id,
        freight_charges=Decimal("2300.00"),
        origin_charges=Decimal("100.00"),
        destination_charges=Decimal("100.00"),
        transit_time_days=10,
        quote_validity_date=pickup_date,
        carrier_name="Carrier A",
        current_time=datetime(2026, 6, 1, 10, 10, 0, tzinfo=timezone.utc),
    )

    # Supplier 1 bids identical $2500 total at 10:10:05 (5 seconds later)
    process_bid_submission(
        db=db_session,
        rfq_id=rfq.id,
        supplier_id=suppliers[1].id,
        user_id=supplier_users[1].id,
        freight_charges=Decimal("2300.00"),
        origin_charges=Decimal("100.00"),
        destination_charges=Decimal("100.00"),
        transit_time_days=10,
        quote_validity_date=pickup_date,
        carrier_name="Carrier B",
        current_time=datetime(2026, 6, 1, 10, 10, 5, tzinfo=timezone.utc),
    )

    # Supplier 2 bids $3000 total at 10:10:10
    process_bid_submission(
        db=db_session,
        rfq_id=rfq.id,
        supplier_id=suppliers[2].id,
        user_id=supplier_users[2].id,
        freight_charges=Decimal("2800.00"),
        origin_charges=Decimal("100.00"),
        destination_charges=Decimal("100.00"),
        transit_time_days=10,
        quote_validity_date=pickup_date,
        carrier_name="Carrier C",
        current_time=datetime(2026, 6, 1, 10, 10, 10, tzinfo=timezone.utc),
    )

    rankings = calculate_rankings(db_session, rfq.id)
    assert len(rankings) == 3
    # Supplier 0 earlier timestamp breaks tie on $2500 -> Rank 1 (L1)
    assert rankings[0]["supplier_id"] == suppliers[0].id
    assert rankings[0]["rank"] == 1
    # Supplier 1 -> Rank 2 (L2)
    assert rankings[1]["supplier_id"] == suppliers[1].id
    assert rankings[1]["rank"] == 2
    # Supplier 2 -> Rank 3 (L3)
    assert rankings[2]["supplier_id"] == suppliers[2].id
    assert rankings[2]["rank"] == 3


# -------------------------------------------------------------
# Test 7: Idempotency Key Replay
# -------------------------------------------------------------
def test_idempotency_key_replay(db_session, buyer_user, suppliers, supplier_users):
    bid_start = datetime(2026, 6, 1, 10, 0, 0, tzinfo=timezone.utc)
    bid_close = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
    forced_close = datetime(2026, 6, 1, 13, 0, 0, tzinfo=timezone.utc)
    pickup_date = datetime(2026, 6, 15, 0, 0, 0, tzinfo=timezone.utc)

    rfq = create_rfq_helper(
        db_session,
        buyer_user,
        [suppliers[0]],
        bid_start=bid_start,
        bid_close=bid_close,
        forced_close=forced_close,
        pickup_date=pickup_date,
    )

    key = "idem-key-unique-12345"
    res1 = process_bid_submission(
        db=db_session,
        rfq_id=rfq.id,
        supplier_id=suppliers[0].id,
        user_id=supplier_users[0].id,
        freight_charges=Decimal("2000.00"),
        origin_charges=Decimal("100.00"),
        destination_charges=Decimal("100.00"),
        transit_time_days=10,
        quote_validity_date=pickup_date,
        carrier_name="Carrier A",
        idempotency_key=key,
        current_time=datetime(2026, 6, 1, 10, 15, 0, tzinfo=timezone.utc),
    )
    assert res1["is_replay"] is False

    # Second submission with same idempotency key
    res2 = process_bid_submission(
        db=db_session,
        rfq_id=rfq.id,
        supplier_id=suppliers[0].id,
        user_id=supplier_users[0].id,
        freight_charges=Decimal("2000.00"),
        origin_charges=Decimal("100.00"),
        destination_charges=Decimal("100.00"),
        transit_time_days=10,
        quote_validity_date=pickup_date,
        carrier_name="Carrier A",
        idempotency_key=key,
        current_time=datetime(2026, 6, 1, 10, 16, 0, tzinfo=timezone.utc),
    )
    assert res2["is_replay"] is True
    assert res2["bid"].id == res1["bid"].id


# -------------------------------------------------------------
# Test 8: Status Transitions (CLOSED vs FORCE_CLOSED)
# -------------------------------------------------------------
def test_status_transitions(db_session, buyer_user, suppliers):
    bid_start = datetime(2026, 6, 1, 10, 0, 0, tzinfo=timezone.utc)
    bid_close = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
    forced_close = datetime(2026, 6, 1, 13, 0, 0, tzinfo=timezone.utc)
    pickup_date = datetime(2026, 6, 15, 0, 0, 0, tzinfo=timezone.utc)

    # 1. Normal close (effective_close < forced_close)
    rfq_normal = create_rfq_helper(
        db_session,
        buyer_user,
        [suppliers[0]],
        bid_start=bid_start,
        bid_close=bid_close,
        forced_close=forced_close,
        pickup_date=pickup_date,
    )
    # Check at 12:01 (past effective close, before forced close)
    changed, ev = check_and_update_rfq_status(
        db_session, rfq_normal, current_time=datetime(2026, 6, 1, 12, 1, 0, tzinfo=timezone.utc)
    )
    assert changed is True
    assert rfq_normal.status == RFQStatus.CLOSED.value
    assert ev == AuctionEventType.AUCTION_CLOSED.value

    # Crucial test: Check again at 14:00 (past forced_close) - must STAY CLOSED, never mutate to FORCE_CLOSED
    changed_later, _ = check_and_update_rfq_status(
        db_session, rfq_normal, current_time=datetime(2026, 6, 1, 14, 0, 0, tzinfo=timezone.utc)
    )
    assert changed_later is False
    assert rfq_normal.status == RFQStatus.CLOSED.value

    # Another RFQ whose first check happens long after forced_close, but effective_close was never extended:
    rfq_unextended_late = create_rfq_helper(
        db_session,
        buyer_user,
        [suppliers[0]],
        bid_start=bid_start,
        bid_close=bid_close,
        forced_close=forced_close,
        pickup_date=pickup_date,
    )
    # First evaluated at 14:00 (past forced_close): since effective_close (12:00) < forced_close (13:00), must be CLOSED!
    changed_late, ev_late = check_and_update_rfq_status(
        db_session, rfq_unextended_late, current_time=datetime(2026, 6, 1, 14, 0, 0, tzinfo=timezone.utc)
    )
    assert changed_late is True
    assert rfq_unextended_late.status == RFQStatus.CLOSED.value
    assert ev_late == AuctionEventType.AUCTION_CLOSED.value

    # 2. Forced close (effective_close == forced_close)
    rfq_forced = create_rfq_helper(
        db_session,
        buyer_user,
        [suppliers[0]],
        bid_start=bid_start,
        bid_close=bid_close,
        forced_close=forced_close,
        pickup_date=pickup_date,
    )
    rfq_forced.effective_close = forced_close
    db_session.commit()
    changed_f, ev_f = check_and_update_rfq_status(
        db_session, rfq_forced, current_time=datetime(2026, 6, 1, 13, 1, 0, tzinfo=timezone.utc)
    )
    assert changed_f is True
    assert rfq_forced.status == RFQStatus.FORCE_CLOSED.value
    assert ev_f == AuctionEventType.FORCED_CLOSE.value
