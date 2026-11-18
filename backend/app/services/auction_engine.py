import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.entities import (
    RFQ,
    AuctionConfig,
    RFQInvitation,
    Bid,
    AuctionExtension,
    AuctionEvent,
    Supplier,
    utc_now,
)
from app.models.enums import (
    RFQStatus,
    TriggerType,
    InvitationStatus,
    AuctionEventType,
)
from app.services.exceptions import (
    AuctionNotStartedError,
    BidAfterCloseError,
    BidAfterForcedCloseError,
    AuctionClosedError,
    SupplierNotInvitedError,
    BidNotLowerError,
    InvalidValidityDateError,
    RFQNotFoundError,
)

logger = logging.getLogger(__name__)


def get_rfq_with_lock(db: Session, rfq_id: str) -> RFQ:
    """Acquires a pessimistic row lock on the RFQ if supported by the database dialect."""
    query = db.query(RFQ).filter((RFQ.id == rfq_id) | (RFQ.reference_id == rfq_id))
    dialect_name = db.bind.dialect.name if db.bind else ""
    if dialect_name.startswith("postgresql"):
        query = query.with_for_update()
    rfq = query.first()
    if not rfq:
        raise RFQNotFoundError(f"RFQ with ID {rfq_id} was not found")
    return rfq


def check_and_update_rfq_status(
    db: Session, rfq: RFQ, current_time: Optional[datetime] = None
) -> Tuple[bool, Optional[str]]:
    """
    Evaluates current server time against the RFQ timeline and transitions status:
    - If already CLOSED or FORCE_CLOSED, status is terminal and does not change.
    - If now >= effective_close:
        Transitions to FORCE_CLOSED ONLY if effective_close >= forced_close (extensions reached the ceiling).
        Otherwise transitions to CLOSED.
    - If now >= bid_start and old_status == SCHEDULED:
        Transitions to ACTIVE.
    Returns (status_changed: bool, event_type: Optional[str]).
    """
    # Concluded auctions are immutable in status
    if rfq.status in [RFQStatus.CLOSED.value, RFQStatus.FORCE_CLOSED.value]:
        return False, None

    now = current_time or utc_now()
    if rfq.effective_close.tzinfo is None:
        now_eval = now.replace(tzinfo=None)
    else:
        now_eval = now

    old_status = rfq.status

    # Check if auction has expired past its effective close
    if now_eval >= rfq.effective_close:
        # FORCE_CLOSED is only set when the final close time equals forced_close after extensions.
        if rfq.effective_close >= rfq.forced_close:
            new_status = RFQStatus.FORCE_CLOSED.value
            event_type = AuctionEventType.FORCED_CLOSE.value
            reason = "Auction reached final close time capped at forced close limit"
        else:
            new_status = RFQStatus.CLOSED.value
            event_type = AuctionEventType.AUCTION_CLOSED.value
            reason = "Auction reached effective close time"

        rfq.status = new_status
        event = AuctionEvent(
            rfq_id=rfq.id,
            event_type=event_type,
            payload={
                "previous_status": old_status,
                "new_status": new_status,
                "effective_close": rfq.effective_close.isoformat(),
                "forced_close": rfq.forced_close.isoformat(),
                "server_time": now.isoformat(),
                "reason": reason,
            },
            created_at=now,
        )
        db.add(event)
        return True, event_type

    # Check if scheduled auction should now become active
    elif now_eval >= rfq.bid_start and old_status == RFQStatus.SCHEDULED.value:
        new_status = RFQStatus.ACTIVE.value
        rfq.status = new_status
        event_type = AuctionEventType.AUCTION_STARTED.value
        event = AuctionEvent(
            rfq_id=rfq.id,
            event_type=event_type,
            payload={
                "previous_status": old_status,
                "new_status": new_status,
                "server_time": now.isoformat(),
                "reason": "Scheduled bid start time reached",
            },
            created_at=now,
        )
        db.add(event)
        return True, event_type

    return False, None


def calculate_rankings(db: Session, rfq_id: str) -> List[Dict[str, Any]]:
    """
    Computes ranking ladder for the RFQ.
    - Each participating supplier is ranked by their latest valid bid.
    - Ranking is by total ascending (L1 lowest).
    - Ties broken by earlier bid timestamp (created_at ASC).
    """
    # Fetch all bids for this RFQ ordered by created_at DESC to easily pick the latest per supplier
    all_bids = (
        db.query(Bid, Supplier)
        .join(Supplier, Bid.supplier_id == Supplier.id)
        .filter(Bid.rfq_id == rfq_id)
        .order_by(Bid.created_at.desc())
        .all()
    )

    latest_bids_by_supplier: Dict[str, Tuple[Bid, Supplier]] = {}
    for bid, supplier in all_bids:
        if bid.supplier_id not in latest_bids_by_supplier:
            latest_bids_by_supplier[bid.supplier_id] = (bid, supplier)

    # Sort suppliers by total ASC, then created_at ASC
    sorted_latest = sorted(
        latest_bids_by_supplier.values(),
        key=lambda item: (Decimal(str(item[0].total)), item[0].created_at),
    )

    rankings: List[Dict[str, Any]] = []
    for idx, (bid, supplier) in enumerate(sorted_latest, start=1):
        rankings.append({
            "rank": idx,
            "supplier_id": supplier.id,
            "supplier_name": supplier.name,
            "supplier_code": supplier.code,
            "total": Decimal(str(bid.total)),
            "freight_charges": Decimal(str(bid.freight_charges)),
            "origin_charges": Decimal(str(bid.origin_charges)),
            "destination_charges": Decimal(str(bid.destination_charges)),
            "transit_time_days": bid.transit_time_days,
            "quote_validity_date": bid.quote_validity_date,
            "carrier_name": bid.carrier_name,
            "bid_id": bid.id,
            "bid_created_at": bid.created_at,
        })

    return rankings


def is_inside_trigger_window(
    effective_close: datetime, trigger_window_minutes: int, bid_time: datetime
) -> bool:
    """
    A bid is inside the window if:
    effective_close - X minutes <= bid_time < effective_close
    """
    window_start = effective_close - timedelta(minutes=trigger_window_minutes)
    return window_start <= bid_time < effective_close


def evaluate_qualifying_event(
    trigger_type: str,
    prev_ranks: Dict[str, int],  # supplier_id -> rank
    new_ranks: Dict[str, int],   # supplier_id -> rank
    is_first_bid: bool,
    prev_l1_supplier_id: Optional[str],
    new_l1_supplier_id: Optional[str],
    bid_supplier_id: str,
) -> Tuple[bool, str]:
    """
    Qualifying events by trigger_type:
    1. BID_RECEIVED: any valid bid inside the trigger window qualifies.
    2. ANY_RANK_CHANGE: an existing supplier's position changed after re-ranking.
       The first bid and a new bottom entrant do not qualify.
    3. L1_CHANGE: qualifies only if the identity of the L1 supplier changed.
       The first bid counts as an L1 change.
    """
    if trigger_type == TriggerType.BID_RECEIVED.value:
        return True, "Valid bid submitted inside trigger window (BID_RECEIVED)"

    if trigger_type == TriggerType.L1_CHANGE.value:
        if is_first_bid or prev_l1_supplier_id is None:
            return True, "Initial L1 price established (first bid on auction)"
        if new_l1_supplier_id != prev_l1_supplier_id:
            return True, f"L1 supplier changed from {prev_l1_supplier_id} to {new_l1_supplier_id}"
        return False, "Bid did not change the L1 supplier identity"

    if trigger_type == TriggerType.ANY_RANK_CHANGE.value:
        # Definition: "an existing supplier's position changed after re-ranking"
        # The first bid and a new bottom entrant do not qualify.
        if is_first_bid or not prev_ranks:
            return False, "First bid on auction does not qualify for ANY_RANK_CHANGE (no existing supplier position changed)"

        # Check if ANY previously ranked existing supplier's position changed
        rank_changed = False
        changed_details = []
        for s_id, old_pos in prev_ranks.items():
            new_pos = new_ranks.get(s_id)
            if new_pos is not None and new_pos != old_pos:
                rank_changed = True
                changed_details.append(f"supplier {s_id}: rank {old_pos} -> {new_pos}")

        if rank_changed:
            return True, f"Existing supplier ranks shifted: {', '.join(changed_details)}"
        return False, "No existing supplier's position changed (new bottom entrant or no shift)"

    return False, "Unknown trigger type"


def process_bid_submission(
    db: Session,
    rfq_id: str,
    supplier_id: str,
    user_id: str,
    freight_charges: Decimal,
    origin_charges: Decimal,
    destination_charges: Decimal,
    transit_time_days: int,
    quote_validity_date: datetime,
    carrier_name: str,
    idempotency_key: Optional[str] = None,
    current_time: Optional[datetime] = None,
) -> Dict[str, Any]:
    """
    Authoritative Server-Side Transactional Bid Processor.
    Executes in a single database transaction with row-level lock.
    """
    now = current_time or utc_now()

    # 1. Check idempotency replay scoped strictly to (rfq_id, supplier_id, idempotency_key)
    if idempotency_key:
        existing_bid = (
            db.query(Bid)
            .filter(
                Bid.rfq_id == rfq_id,
                Bid.supplier_id == supplier_id,
                Bid.idempotency_key == idempotency_key,
            )
            .first()
        )
        if existing_bid:
            logger.info(
                "Idempotency key %s found for RFQ %s and Supplier %s; replaying existing bid %s",
                idempotency_key,
                rfq_id,
                supplier_id,
                existing_bid.id,
            )
            rankings = calculate_rankings(db, existing_bid.rfq_id)
            supplier_rank = next((r["rank"] for r in rankings if r["supplier_id"] == existing_bid.supplier_id), None)
            return {
                "bid": existing_bid,
                "rankings": rankings,
                "supplier_rank": supplier_rank,
                "is_replay": True,
                "extension_applied": False,
                "events": [],
            }

    # 2. Acquire RFQ Row Lock
    rfq = get_rfq_with_lock(db, rfq_id)
    config = rfq.config
    if not config:
        # Fallback default configuration if missing
        config = AuctionConfig(
            rfq_id=rfq.id,
            trigger_window_minutes=10,
            extension_minutes=5,
            trigger_type=TriggerType.L1_CHANGE.value,
        )
        db.add(config)
        db.flush()

    # 3. Lazy status evaluation before processing
    status_changed, status_event = check_and_update_rfq_status(db, rfq, now)

    # 4. Temporal & Status Validations
    now_eval = now if rfq.effective_close.tzinfo else now.replace(tzinfo=None)
    start_eval = rfq.bid_start if rfq.bid_start.tzinfo else rfq.bid_start.replace(tzinfo=None)
    close_eval = rfq.effective_close if rfq.effective_close.tzinfo else rfq.effective_close.replace(tzinfo=None)
    forced_eval = rfq.forced_close if rfq.forced_close.tzinfo else rfq.forced_close.replace(tzinfo=None)

    if now_eval < start_eval:
        raise AuctionNotStartedError(
            f"Auction has not started yet. Starts at {rfq.bid_start.isoformat()}"
        )
    if now_eval >= forced_eval:
        raise BidAfterForcedCloseError("Auction has reached forced close deadline")
    if now_eval >= close_eval:
        raise BidAfterCloseError("Auction is closed for bidding")
    if rfq.status in [RFQStatus.CLOSED.value, RFQStatus.FORCE_CLOSED.value]:
        raise AuctionClosedError(f"Auction is already {rfq.status}")

    # 5. Invitation Validation
    invitation = (
        db.query(RFQInvitation)
        .filter(RFQInvitation.rfq_id == rfq.id, RFQInvitation.supplier_id == supplier_id)
        .first()
    )
    if not invitation:
        raise SupplierNotInvitedError(f"Supplier {supplier_id} is not invited to RFQ {rfq.reference_id}")

    # 6. Validity Date Validation
    pickup_eval = rfq.pickup_date if rfq.pickup_date.tzinfo else rfq.pickup_date.replace(tzinfo=None)
    validity_eval = quote_validity_date if quote_validity_date.tzinfo else quote_validity_date.replace(tzinfo=None)
    if validity_eval < pickup_eval:
        raise InvalidValidityDateError(
            f"Quote validity date ({quote_validity_date.isoformat()}) must be on or after the pickup date ({rfq.pickup_date.isoformat()})"
        )

    # 7. Strictly Lower Than Previous Bid Rule
    total = freight_charges + origin_charges + destination_charges
    latest_supplier_bid = (
        db.query(Bid)
        .filter(Bid.rfq_id == rfq.id, Bid.supplier_id == supplier_id)
        .order_by(Bid.created_at.desc())
        .first()
    )
    if latest_supplier_bid is not None:
        if total >= latest_supplier_bid.total:
            raise BidNotLowerError(
                f"New bid total (${total:,.2f}) must be strictly lower than your previous bid (${latest_supplier_bid.total:,.2f})"
            )
        # Minimum bid decrement enforcement
        if config.min_decrement and config.min_decrement > 0:
            decrement = latest_supplier_bid.total - total
            if decrement < config.min_decrement:
                raise BidNotLowerError(
                    f"New bid total (${total:,.2f}) must decrement by at least ${config.min_decrement:,.2f} below your previous bid (${latest_supplier_bid.total:,.2f}). Current reduction: ${decrement:,.2f}"
                )

    # 8. Compute Pre-Bid Ranks and L1 State
    current_rankings = calculate_rankings(db, rfq.id)
    prev_ranks: Dict[str, int] = {r["supplier_id"]: r["rank"] for r in current_rankings}
    prev_l1_supplier_id = current_rankings[0]["supplier_id"] if current_rankings else None
    is_first_bid = len(current_rankings) == 0

    # 9. Insert the New Bid Record
    new_bid = Bid(
        rfq_id=rfq.id,
        supplier_id=supplier_id,
        submitted_by=user_id,
        freight_charges=freight_charges,
        origin_charges=origin_charges,
        destination_charges=destination_charges,
        total=total,
        transit_time_days=transit_time_days,
        quote_validity_date=quote_validity_date,
        carrier_name=carrier_name,
        idempotency_key=idempotency_key,
        created_at=now,
    )
    db.add(new_bid)
    db.flush()

    # 10. Recompute New Ranks
    new_rankings = calculate_rankings(db, rfq.id)
    new_ranks: Dict[str, int] = {r["supplier_id"]: r["rank"] for r in new_rankings}
    new_l1_supplier_id = new_rankings[0]["supplier_id"] if new_rankings else None

    # 11. Evaluate Trigger Window & Extensions
    inside_window = is_inside_trigger_window(
        rfq.effective_close, config.trigger_window_minutes, now
    )

    extension_applied = False
    extension_capped = False
    extension_record: Optional[AuctionExtension] = None
    events_created: List[AuctionEvent] = []

    if inside_window:
        is_qualified, qualify_reason = evaluate_qualifying_event(
            trigger_type=config.trigger_type,
            prev_ranks=prev_ranks,
            new_ranks=new_ranks,
            is_first_bid=is_first_bid,
            prev_l1_supplier_id=prev_l1_supplier_id,
            new_l1_supplier_id=new_l1_supplier_id,
            bid_supplier_id=supplier_id,
        )

        if is_qualified:
            old_close = rfq.effective_close

            # Authoritative Extension Formula: min(effective_close + Y, forced_close)
            target_close = old_close + timedelta(minutes=config.extension_minutes)

            if old_close >= rfq.forced_close:
                # Extension capped: already at forced_close
                extension_capped = True
                cap_event = AuctionEvent(
                    rfq_id=rfq.id,
                    bid_id=new_bid.id,
                    event_type=AuctionEventType.EXTENSION_CAPPED.value,
                    payload={
                        "bid_id": new_bid.id,
                        "effective_close": old_close.isoformat(),
                        "forced_close": rfq.forced_close.isoformat(),
                        "reason": f"Extension capped: effective close has reached forced close deadline ({qualify_reason})",
                        "server_time": now.isoformat(),
                    },
                    created_at=now,
                )
                db.add(cap_event)
                events_created.append(cap_event)
            else:
                # Apply extension
                extension_applied = True
                new_close = min(target_close, rfq.forced_close)
                is_clamped = target_close > rfq.forced_close or new_close == rfq.forced_close

                rfq.effective_close = new_close

                reason_text = (
                    f"Extended by {config.extension_minutes}m due to qualifying bid "
                    f"under {config.trigger_type} ({qualify_reason})"
                )
                if is_clamped:
                    reason_text += f" [Clamped at forced close {rfq.forced_close.isoformat()}]"

                extension_record = AuctionExtension(
                    rfq_id=rfq.id,
                    triggering_bid_id=new_bid.id,
                    previous_close=old_close,
                    new_close=new_close,
                    trigger_type=config.trigger_type,
                    reason=reason_text,
                    is_clamped=is_clamped,
                    created_at=now,
                )
                db.add(extension_record)

                ext_event = AuctionEvent(
                    rfq_id=rfq.id,
                    bid_id=new_bid.id,
                    event_type=AuctionEventType.EXTENSION_APPLIED.value,
                    payload={
                        "previous_close": old_close.isoformat(),
                        "new_close": new_close.isoformat(),
                        "forced_close": rfq.forced_close.isoformat(),
                        "trigger_type": config.trigger_type,
                        "extension_minutes": config.extension_minutes,
                        "is_clamped": is_clamped,
                        "reason": reason_text,
                        "triggering_bid_id": new_bid.id,
                        "server_time": now.isoformat(),
                    },
                    created_at=now,
                )
                db.add(ext_event)
                events_created.append(ext_event)

    # 12. Create BID_SUBMITTED Event
    bid_event = AuctionEvent(
        rfq_id=rfq.id,
        bid_id=new_bid.id,
        event_type=AuctionEventType.BID_SUBMITTED.value,
        payload={
            "bid_id": new_bid.id,
            "supplier_id": supplier_id,
            "freight_charges": float(freight_charges),
            "origin_charges": float(origin_charges),
            "destination_charges": float(destination_charges),
            "total": float(total),
            "transit_time_days": transit_time_days,
            "carrier_name": carrier_name,
            "rank": new_ranks.get(supplier_id),
            "server_time": now.isoformat(),
        },
        created_at=now,
    )
    db.add(bid_event)
    events_created.append(bid_event)

    # 13. Create L1_CHANGED or RANK_CHANGED Events
    if new_l1_supplier_id != prev_l1_supplier_id:
        l1_event = AuctionEvent(
            rfq_id=rfq.id,
            bid_id=new_bid.id,
            event_type=AuctionEventType.L1_CHANGED.value,
            payload={
                "previous_l1_supplier_id": prev_l1_supplier_id,
                "new_l1_supplier_id": new_l1_supplier_id,
                "new_l1_total": float(new_rankings[0]["total"]),
                "server_time": now.isoformat(),
            },
            created_at=now,
        )
        db.add(l1_event)
        events_created.append(l1_event)
    elif prev_ranks != new_ranks:
        rank_event = AuctionEvent(
            rfq_id=rfq.id,
            bid_id=new_bid.id,
            event_type=AuctionEventType.RANK_CHANGED.value,
            payload={
                "previous_ranks": prev_ranks,
                "new_ranks": new_ranks,
                "server_time": now.isoformat(),
            },
            created_at=now,
        )
        db.add(rank_event)
        events_created.append(rank_event)

    # 14. Commit the Transaction
    db.commit()
    db.refresh(new_bid)
    db.refresh(rfq)

    supplier_rank = new_ranks.get(supplier_id)

    return {
        "bid": new_bid,
        "rfq": rfq,
        "rankings": new_rankings,
        "supplier_rank": supplier_rank,
        "extension_applied": extension_applied,
        "extension_capped": extension_capped,
        "extension": extension_record,
        "events": events_created,
        "is_replay": False,
        "server_time": now,
    }
