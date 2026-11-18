from typing import List, Optional
import time
from collections import defaultdict
from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.entities import Bid, User, RFQ
from app.models.enums import UserRole
from app.schemas.bid import BidCreate, BidOut, SupplierRankOut
from app.services.deps import get_current_user, require_supplier
from app.services.auction_engine import (
    process_bid_submission,
    calculate_rankings,
)
from app.services.websocket_manager import ws_manager

router = APIRouter(prefix="/rfqs/{rfq_id}/bids", tags=["Bids"])

# In-memory sliding window rate limiter: max 30 bids per second per supplier
_bid_timestamps = defaultdict(list)

def check_bid_rate_limit(supplier_id: str, max_requests: int = 30, window_seconds: float = 1.0):
    now = time.time()
    # Filter timestamps within window
    _bid_timestamps[supplier_id] = [t for t in _bid_timestamps[supplier_id] if now - t < window_seconds]
    if len(_bid_timestamps[supplier_id]) >= max_requests:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Maximum 30 quote submissions per second per carrier.",
            headers={"Retry-After": "1"}
        )
    _bid_timestamps[supplier_id].append(now)


@router.post("", response_model=BidOut, status_code=status.HTTP_201_CREATED)
def submit_bid(
    rfq_id: str,
    bid_in: BidCreate,
    response: Response,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_supplier),
):
    """
    Submits a new competitive quote in the British Auction.
    Protected by row-level locking, server-time enforcement, and idempotent replay guard.
    Broadcasts real-time events upon transaction commit.
    """
    # Rate limit check on active submissions
    check_bid_rate_limit(current_user.supplier_id)

    effective_idem_key = idempotency_key or bid_in.idempotency_key
    result = process_bid_submission(
        db=db,
        rfq_id=rfq_id,
        supplier_id=current_user.supplier_id,
        user_id=current_user.id,
        freight_charges=bid_in.freight_charges,
        origin_charges=bid_in.origin_charges,
        destination_charges=bid_in.destination_charges,
        transit_time_days=bid_in.transit_time_days,
        quote_validity_date=bid_in.quote_validity_date,
        carrier_name=bid_in.carrier_name,
        idempotency_key=effective_idem_key,
    )

    new_bid: Bid = result["bid"]
    rfq: RFQ = result.get("rfq")
    rankings = result["rankings"]
    supplier_rank = result["supplier_rank"]

    if result.get("is_replay"):
        response.status_code = status.HTTP_200_OK

    # If this wasn't an idempotent replay, broadcast real-time updates over WebSocket
    if not result.get("is_replay") and rfq:
        # Build broadcast payload
        broadcast_data = {
            "bid_id": new_bid.id,
            "rfq_id": rfq_id,
            "supplier_id": current_user.supplier_id,
            "supplier_name": current_user.supplier.name if current_user.supplier else "Supplier",
            "supplier_code": current_user.supplier.code if current_user.supplier else "",
            "total": float(new_bid.total),
            "freight_charges": float(new_bid.freight_charges),
            "origin_charges": float(new_bid.origin_charges),
            "destination_charges": float(new_bid.destination_charges),
            "transit_time_days": new_bid.transit_time_days,
            "carrier_name": new_bid.carrier_name,
            "rank": supplier_rank,
            "effective_close": rfq.effective_close.isoformat(),
            "forced_close": rfq.forced_close.isoformat(),
            "bid_visibility": getattr(rfq.config, "bid_visibility", "OPEN") if rfq.config else "OPEN",
            "extension_applied": result["extension_applied"],
            "extension_capped": result["extension_capped"],
            "rankings": [
                {
                    "rank": r["rank"],
                    "supplier_id": r["supplier_id"],
                    "supplier_name": r["supplier_name"],
                    "supplier_code": r["supplier_code"],
                    "total": float(r["total"]),
                }
                for r in rankings
            ],
        }

        if result["extension_applied"] and result.get("extension"):
            broadcast_data["extension_details"] = {
                "previous_close": result["extension"].previous_close.isoformat(),
                "new_close": result["extension"].new_close.isoformat(),
                "reason": result["extension"].reason,
                "is_clamped": result["extension"].is_clamped,
            }

        visibility = getattr(rfq.config, "bid_visibility", "OPEN") if rfq.config else "OPEN"
        for ev in result.get("events", []):
            ev_payload = dict(ev.payload)
            ev_payload["bid_visibility"] = visibility
            ws_manager.broadcast_to_rfq_sync(
                rfq_id=rfq_id,
                event_type=ev.event_type,
                data=ev_payload,
            )

        ws_manager.broadcast_to_rfq_sync(
            rfq_id=rfq_id,
            event_type="NEW_BID",
            data=broadcast_data,
        )

    out = BidOut.model_validate(new_bid)
    out.rank = supplier_rank
    if current_user.supplier:
        out.supplier_name = current_user.supplier.name
        out.supplier_code = current_user.supplier.code
    out.submitter_name = current_user.full_name
    return out


@router.get("", response_model=List[BidOut])
def list_bids_for_rfq(
    rfq_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rfq = db.query(RFQ).filter((RFQ.id == rfq_id) | (RFQ.reference_id == rfq_id)).first()
    if not rfq:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "RFQ_NOT_FOUND", "message": "RFQ not found"},
        )

    # If masked mode and user is supplier, only show their own bids
    if (
        current_user.role == UserRole.SUPPLIER.value
        and rfq.config
        and getattr(rfq.config, "bid_visibility", "OPEN") == "MASKED"
    ):
        bids_query = (
            db.query(Bid)
            .filter(Bid.rfq_id == rfq.id, Bid.supplier_id == current_user.supplier_id)
            .order_by(Bid.created_at.desc())
            .all()
        )
    else:
        bids_query = (
            db.query(Bid)
            .filter(Bid.rfq_id == rfq.id)
            .order_by(Bid.created_at.desc())
            .all()
        )

    rankings = calculate_rankings(db, rfq.id)
    rank_map = {r["supplier_id"]: r["rank"] for r in rankings}

    results = []
    for b in bids_query:
        bid_out = BidOut.model_validate(b)
        bid_out.rank = rank_map.get(b.supplier_id)
        if b.supplier:
            bid_out.supplier_name = b.supplier.name
            bid_out.supplier_code = b.supplier.code
        if b.submitter:
            bid_out.submitter_name = b.submitter.full_name
        results.append(bid_out)

    return results

