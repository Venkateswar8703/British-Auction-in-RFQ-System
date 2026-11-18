import pytest
import uuid
from datetime import datetime, timezone, timedelta
from sqlalchemy import text
from app.models.entities import RFQ, AuctionEvent

def test_auction_events_tamper_proof_trigger(db_session, buyer_user):
    # Create an RFQ for foreign key requirement
    now = datetime.now(timezone.utc)
    rfq = RFQ(
        reference_id=f"TEST-AUDIT-{uuid.uuid4().hex[:6].upper()}",
        title="Audit Trigger RFQ",
        origin="SGSIN",
        destination="NLRTM",
        pickup_date=now + timedelta(days=10),
        bid_start=now - timedelta(hours=1),
        bid_close=now + timedelta(hours=1),
        effective_close=now + timedelta(hours=1),
        forced_close=now + timedelta(hours=2),
        status="ACTIVE",
        created_by=buyer_user.id
    )
    db_session.add(rfq)
    db_session.commit()

    # Ensure trigger is installed
    db_session.execute(text("""
        CREATE OR REPLACE FUNCTION prevent_audit_tampering()
        RETURNS TRIGGER AS $$
        BEGIN
            RAISE EXCEPTION 'MERIDIAN AUDIT VIOLATION: auction_events is append-only and tamper-proof. UPDATE and DELETE operations are strictly forbidden.';
        END;
        $$ LANGUAGE plpgsql;

        DROP TRIGGER IF EXISTS trg_prevent_audit_tampering ON auction_events;
        CREATE TRIGGER trg_prevent_audit_tampering
        BEFORE UPDATE OR DELETE ON auction_events
        FOR EACH ROW EXECUTE FUNCTION prevent_audit_tampering();
    """))
    db_session.commit()

    try:
        # 1. INSERT is allowed
        ev = AuctionEvent(
            rfq_id=rfq.id,
            event_type="TEST_AUDIT_LOG",
            payload={"message": "Immutable audit record"},
            created_at=now
        )
        db_session.add(ev)
        db_session.commit()
        db_session.refresh(ev)
        assert ev.id is not None

        # 2. UPDATE is blocked by trigger
        with pytest.raises(Exception) as exc_update:
            db_session.execute(text(f"UPDATE auction_events SET event_type = 'TAMPERED' WHERE id = '{ev.id}'"))
            db_session.commit()
        assert "MERIDIAN AUDIT VIOLATION" in str(exc_update.value)
        db_session.rollback()

        # 3. DELETE is blocked by trigger
        with pytest.raises(Exception) as exc_delete:
            db_session.execute(text(f"DELETE FROM auction_events WHERE id = '{ev.id}'"))
            db_session.commit()
        assert "MERIDIAN AUDIT VIOLATION" in str(exc_delete.value)
        db_session.rollback()
    finally:
        # Clean up trigger so subsequent test teardown can delete rows
        db_session.execute(text("DROP TRIGGER IF EXISTS trg_prevent_audit_tampering ON auction_events;"))
        db_session.commit()
