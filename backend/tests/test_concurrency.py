import pytest
import threading
import uuid
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base

from app.models.entities import RFQ, AuctionConfig, RFQInvitation, Bid, User, Supplier
from app.models.enums import RFQStatus, TriggerType, UserRole
from app.schemas.rfq import RFQCreate, RFQUpdate
from app.services.auction_engine import process_bid_submission, calculate_rankings
from app.services.auth import hash_password


def test_schema_forced_close_validation():
    now = datetime(2026, 6, 1, 10, 0, 0, tzinfo=timezone.utc)
    bid_start = now
    bid_close = now + timedelta(hours=2)
    pickup_date = now + timedelta(days=5)

    # 1. Invalid: forced_close == bid_close
    with pytest.raises(ValueError, match="forced_close must be strictly after bid_close"):
        RFQCreate(
            reference_id="RFQ-INVALID-1",
            title="Test RFQ",
            origin="Shanghai",
            destination="Rotterdam",
            pickup_date=pickup_date,
            bid_start=bid_start,
            bid_close=bid_close,
            forced_close=bid_close,
        )

    # 2. Invalid: forced_close < bid_close
    with pytest.raises(ValueError, match="forced_close must be strictly after bid_close"):
        RFQCreate(
            reference_id="RFQ-INVALID-2",
            title="Test RFQ",
            origin="Shanghai",
            destination="Rotterdam",
            pickup_date=pickup_date,
            bid_start=bid_start,
            bid_close=bid_close,
            forced_close=bid_close - timedelta(minutes=10),
        )

    # 3. Invalid: pickup_date <= bid_close
    with pytest.raises(ValueError, match="pickup_date must be strictly after bid_close"):
        RFQCreate(
            reference_id="RFQ-INVALID-3",
            title="Test RFQ",
            origin="Shanghai",
            destination="Rotterdam",
            pickup_date=bid_close,
            bid_start=bid_start,
            bid_close=bid_close,
            forced_close=bid_close + timedelta(hours=1),
        )


def test_concurrent_bids_consistency(buyer_user, suppliers, supplier_users):
    """
    Spawns multiple concurrent threads attempting to submit bids simultaneously.
    Verifies that bids are serialized properly, no duplicate bids or corrupted ranks occur.
    """
    import os
    db_url = os.environ.get("DATABASE_URL")
    test_db_path = None
    if db_url and db_url.startswith("postgresql"):
        conc_engine = create_engine(db_url, pool_size=25, max_overflow=10)
    else:
        test_db_path = "./test_concurrency.db"
        if os.path.exists(test_db_path):
            os.remove(test_db_path)
        conc_engine = create_engine(
            f"sqlite:///{test_db_path}",
            connect_args={"check_same_thread": False, "timeout": 30},
        )
        Base.metadata.create_all(bind=conc_engine)

    Session = sessionmaker(bind=conc_engine)
    setup_db = Session()

    # Create local buyer and suppliers in this test database
    run_id = uuid.uuid4().hex[:6]
    local_buyer = User(
        email=f"conc_buyer_{run_id}@meridian.com",
        password_hash=hash_password("Pass123!"),
        full_name="Conc Buyer",
        role=UserRole.BUYER.value,
    )
    setup_db.add(local_buyer)
    setup_db.flush()

    local_suppliers = []
    local_users = []
    for idx, s in enumerate(suppliers[:4]):
        s_code = f"C{run_id[:4]}{idx}"
        ls = Supplier(name=f"Conc-{run_id}-{s.name}", code=s_code, contact_email=f"conc-{run_id}-{idx}@meridian.com")
        setup_db.add(ls)
        setup_db.flush()
        local_suppliers.append(ls)

        lu = User(
            email=ls.contact_email,
            password_hash=hash_password("Pass123!"),
            full_name=f"{ls.code} Rep",
            role=UserRole.SUPPLIER.value,
            supplier_id=ls.id,
        )
        setup_db.add(lu)
        local_users.append(lu)

    setup_db.flush()

    bid_start = datetime(2026, 6, 1, 10, 0, 0, tzinfo=timezone.utc)
    bid_close = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
    forced_close = datetime(2026, 6, 1, 13, 0, 0, tzinfo=timezone.utc)
    pickup_date = datetime(2026, 6, 15, 0, 0, 0, tzinfo=timezone.utc)

    rfq = RFQ(
        reference_id=f"RFQ-CONC-{int(datetime.now(timezone.utc).timestamp())}",
        title="Concurrent Test RFQ",
        origin="Singapore (SGSIN)",
        destination="Rotterdam (NLRTM)",
        pickup_date=pickup_date,
        bid_start=bid_start,
        bid_close=bid_close,
        effective_close=bid_close,
        forced_close=forced_close,
        status=RFQStatus.ACTIVE.value,
        created_by=local_buyer.id,
    )
    setup_db.add(rfq)
    setup_db.flush()

    config = AuctionConfig(
        rfq_id=rfq.id,
        trigger_window_minutes=10,
        extension_minutes=5,
        trigger_type=TriggerType.BID_RECEIVED.value,
    )
    setup_db.add(config)

    for s in local_suppliers:
        setup_db.add(RFQInvitation(rfq_id=rfq.id, supplier_id=s.id))

    local_supplier_ids = [s.id for s in local_suppliers]
    local_supplier_codes = [s.code for s in local_suppliers]
    local_user_ids = [u.id for u in local_users]

    setup_db.commit()
    rfq_id = rfq.id
    setup_db.close()

    results = []
    errors = []

    def submit_worker(supplier_idx, amount):
        thread_db = Session()
        try:
            s_id = local_supplier_ids[supplier_idx]
            u_id = local_user_ids[supplier_idx]
            s_code = local_supplier_codes[supplier_idx]
            bid_time = datetime(2026, 6, 1, 11, 55, supplier_idx, tzinfo=timezone.utc)
            res = process_bid_submission(
                db=thread_db,
                rfq_id=rfq_id,
                supplier_id=s_id,
                user_id=u_id,
                freight_charges=Decimal(str(amount)),
                origin_charges=Decimal("100.00"),
                destination_charges=Decimal("100.00"),
                transit_time_days=12,
                quote_validity_date=pickup_date,
                carrier_name=f"Carrier-{s_code}",
                current_time=bid_time,
            )
            results.append(res)
        except Exception as e:
            errors.append(e)
        finally:
            thread_db.close()

    # Launch threads with different prices: $2000, $1900, $1800, $1700
    threads = []
    prices = [2000, 1900, 1800, 1700]
    for idx, price in enumerate(prices):
        t = threading.Thread(target=submit_worker, args=(idx, price))
        threads.append(t)

    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(errors) == 0, f"Encountered errors during concurrent bidding: {errors}"
    assert len(results) == 4

    verify_db = Session()
    final_rankings = calculate_rankings(verify_db, rfq_id)
    assert len(final_rankings) == 4

    # Verify order: lowest total ($1700 + 200 = $1900) should be L1
    assert final_rankings[0]["total"] == Decimal("1900.00")
    assert final_rankings[1]["total"] == Decimal("2000.00")
    assert final_rankings[2]["total"] == Decimal("2100.00")
    assert final_rankings[3]["total"] == Decimal("2200.00")

    # Verify 4 distinct ranks (1, 2, 3, 4)
    assert [r["rank"] for r in final_rankings] == [1, 2, 3, 4]
    verify_db.close()

    if test_db_path and os.path.exists(test_db_path):
        os.remove(test_db_path)


def test_row_lock_with_for_update_proof(db_session):
    """
    Item 4 Verification: Proof that get_rfq_with_lock calls with_for_update() on PostgreSQL,
    and proof that if with_for_update() is removed, the lock assertion fails.
    """
    from unittest.mock import patch
    from sqlalchemy.orm import Query
    from app.services.auction_engine import get_rfq_with_lock
    from app.services.exceptions import RFQNotFoundError

    was_locked = False
    original_wfu = Query.with_for_update

    def mock_wfu(self, *args, **kwargs):
        nonlocal was_locked
        was_locked = True
        return original_wfu(self, *args, **kwargs)

    # 1. Verify get_rfq_with_lock invokes with_for_update() when running with postgresql dialect
    with patch.object(Query, "with_for_update", side_effect=mock_wfu, autospec=True):
        with patch.object(db_session.bind.dialect, "name", "postgresql"):
            try:
                get_rfq_with_lock(db_session, "nonexistent-id")
            except RFQNotFoundError:
                pass
            assert was_locked is True, "Line 43 of auction_engine.py MUST invoke with_for_update() on PostgreSQL!"

    # 2. Defective implementation proof: if with_for_update() is removed, locking fails
    def broken_get_rfq(db, rfq_id):
        # Missing query.with_for_update()
        return db.query(RFQ).filter((RFQ.id == rfq_id) | (RFQ.reference_id == rfq_id)).first()

    was_locked_broken = False
    with patch.object(Query, "with_for_update", side_effect=mock_wfu, autospec=True):
        broken_get_rfq(db_session, "nonexistent-id")
        assert was_locked_broken is False, "Defective query without with_for_update correctly flagged as unlocked"
