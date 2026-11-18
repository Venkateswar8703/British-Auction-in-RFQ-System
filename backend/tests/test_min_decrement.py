import pytest
from decimal import Decimal
from datetime import datetime, timezone, timedelta
from app.models.enums import TriggerType
from app.models.entities import RFQ, AuctionConfig, RFQInvitation, Bid
from app.services.auction_engine import process_bid_submission
from app.services.exceptions import BidNotLowerError

def test_configurable_min_decrement_enforcement(db_session, buyer_user, suppliers, supplier_users):
    now = datetime.now(timezone.utc)
    pickup_date = now + timedelta(days=15)
    
    # Create RFQ with min_decrement = $50.00
    rfq = RFQ(
        reference_id=f"TEST-DECR-{now.strftime('%H%M%S')}",
        title="Min Decrement Test Auction",
        origin="SGSIN",
        destination="NLRTM",
        pickup_date=pickup_date,
        bid_start=now - timedelta(hours=1),
        bid_close=now + timedelta(hours=1),
        effective_close=now + timedelta(hours=1),
        forced_close=now + timedelta(hours=2),
        status="ACTIVE",
        created_by=buyer_user.id
    )
    db_session.add(rfq)
    db_session.flush()

    config = AuctionConfig(
        rfq_id=rfq.id,
        trigger_window_minutes=10,
        extension_minutes=5,
        trigger_type=TriggerType.L1_CHANGE.value,
        min_decrement=Decimal("50.00")
    )
    db_session.add(config)
    inv = RFQInvitation(rfq_id=rfq.id, supplier_id=suppliers[0].id)
    db_session.add(inv)
    db_session.commit()

    # 1. Initial Bid ($2000.00 total) -> Succeeded
    bid1 = process_bid_submission(
        db=db_session,
        rfq_id=rfq.id,
        supplier_id=suppliers[0].id,
        user_id=supplier_users[0].id,
        freight_charges=Decimal("1800.00"),
        origin_charges=Decimal("100.00"),
        destination_charges=Decimal("100.00"),
        transit_time_days=14,
        quote_validity_date=pickup_date,
        carrier_name="Ocean Liner",
        current_time=now,
    )
    assert bid1["bid"].total == Decimal("2000.00")

    # 2. Subsequent Bid with only $20 reduction ($1980.00 total < $50 decrement) -> Rejected
    with pytest.raises(BidNotLowerError) as exc_info:
        process_bid_submission(
            db=db_session,
            rfq_id=rfq.id,
            supplier_id=suppliers[0].id,
            user_id=supplier_users[0].id,
            freight_charges=Decimal("1780.00"),
            origin_charges=Decimal("100.00"),
            destination_charges=Decimal("100.00"),
            transit_time_days=14,
            quote_validity_date=pickup_date,
            carrier_name="Ocean Liner",
            current_time=now,
        )
    assert "must decrement by at least $50.00" in str(exc_info.value)

    # 3. Subsequent Bid with $60 reduction ($1940.00 total >= $50 decrement) -> Succeeded
    bid2 = process_bid_submission(
        db=db_session,
        rfq_id=rfq.id,
        supplier_id=suppliers[0].id,
        user_id=supplier_users[0].id,
        freight_charges=Decimal("1740.00"),
        origin_charges=Decimal("100.00"),
        destination_charges=Decimal("100.00"),
        transit_time_days=14,
        quote_validity_date=pickup_date,
        carrier_name="Ocean Liner",
        current_time=now,
    )
    assert bid2["bid"].total == Decimal("1940.00")

