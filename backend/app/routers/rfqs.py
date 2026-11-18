import uuid
import csv
import io
from datetime import datetime, timezone, timedelta
from typing import List, Optional
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import or_, desc, asc

from app.database import get_db
from app.models.entities import (
    RFQ,
    AuctionConfig,
    RFQInvitation,
    Bid,
    AuctionExtension,
    AuctionEvent,
    Supplier,
    User,
    utc_now,
)
from app.models.enums import (
    UserRole,
    RFQStatus,
    TriggerType,
    InvitationStatus,
    AuctionEventType,
)
from app.schemas.rfq import (
    RFQCreate,
    RFQUpdate,
    RFQOut,
    RFQDetailOut,
    AuctionConfigOut,
    AuctionExtensionOut,
)
from app.schemas.bid import SupplierRankOut, BidOut
from app.schemas.event import AuctionEventOut
from app.services.deps import get_current_user, require_buyer
from app.services.auction_engine import (
    check_and_update_rfq_status,
    calculate_rankings,
)
from app.services.websocket_manager import ws_manager
from app.services.exceptions import RFQLockedError, RFQNotFoundError

router = APIRouter(prefix="/rfqs", tags=["RFQs"])


def build_rfq_out(db: Session, rfq: RFQ, current_user: User) -> RFQOut:
    """Helper to populate computed statistics on RFQ."""
    # Lazy status check
    now = utc_now()
    changed, ev = check_and_update_rfq_status(db, rfq, now)
    if changed:
        db.commit()

    rankings = calculate_rankings(db, rfq.id)
    lowest_bid_total = rankings[0]["total"] if rankings else None
    participating_suppliers_count = len(rankings)
    total_bids_count = db.query(Bid).filter(Bid.rfq_id == rfq.id).count()

    is_invited = False
    my_latest_bid = None
    my_rank = None

    if current_user.role == UserRole.SUPPLIER.value and current_user.supplier_id:
        inv = (
            db.query(RFQInvitation)
            .filter(RFQInvitation.rfq_id == rfq.id, RFQInvitation.supplier_id == current_user.supplier_id)
            .first()
        )
        is_invited = inv is not None

        # Find user's supplier's rank
        for r in rankings:
            if r["supplier_id"] == current_user.supplier_id:
                my_rank = r["rank"]
                break

        latest_b = (
            db.query(Bid)
            .filter(Bid.rfq_id == rfq.id, Bid.supplier_id == current_user.supplier_id)
            .order_by(Bid.created_at.desc())
            .first()
        )
        if latest_b:
            my_latest_bid = BidOut.model_validate(latest_b)
            my_latest_bid.rank = my_rank

    rfq_out = RFQOut.model_validate(rfq)
    rfq_out.lowest_bid_total = lowest_bid_total
    rfq_out.total_bids_count = total_bids_count
    rfq_out.participating_suppliers_count = participating_suppliers_count
    rfq_out.is_invited = is_invited
    rfq_out.my_latest_bid = my_latest_bid
    rfq_out.my_rank = my_rank
    rfq_out.server_time = now
    return rfq_out


@router.get("", response_model=List[RFQOut])
def list_rfqs(
    search: Optional[str] = Query(None, description="Search by title, reference ID, origin, destination"),
    status: Optional[str] = Query(None, description="Filter by status: SCHEDULED, ACTIVE, CLOSED, FORCE_CLOSED"),
    sort_by: str = Query("created_at", description="Sort field: created_at, effective_close, reference_id, title"),
    order: str = Query("desc", description="Sort direction: asc or desc"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(RFQ)

    # Role-based scoping: suppliers only see invited RFQs
    if current_user.role == UserRole.SUPPLIER.value:
        if not current_user.supplier_id:
            return []
        query = query.join(RFQInvitation, RFQ.id == RFQInvitation.rfq_id).filter(
            RFQInvitation.supplier_id == current_user.supplier_id
        )

    # Status filter
    if status:
        query = query.filter(RFQ.status == status.upper())

    # Text search
    if search:
        s = f"%{search.strip()}%"
        query = query.filter(
            or_(
                RFQ.reference_id.ilike(s),
                RFQ.title.ilike(s),
                RFQ.origin.ilike(s),
                RFQ.destination.ilike(s),
            )
        )

    # Sorting
    sort_column = getattr(RFQ, sort_by, RFQ.created_at)
    if order.lower() == "asc":
        query = query.order_by(asc(sort_column))
    else:
        query = query.order_by(desc(sort_column))

    rfqs = query.all()
    results = [build_rfq_out(db, rfq, current_user) for rfq in rfqs]
    return results


@router.post("", response_model=RFQDetailOut, status_code=status.HTTP_201_CREATED)
def create_rfq(
    rfq_in: RFQCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_buyer),
):
    now = utc_now()
    ref_id = rfq_in.reference_id.strip() if rfq_in.reference_id else f"RFQ-{now.year}-{uuid.uuid4().hex[:8].upper()}"
    existing = db.query(RFQ).filter(RFQ.reference_id == ref_id).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "RFQ_REFERENCE_EXISTS", "message": f"RFQ with reference ID '{ref_id}' already exists"},
        )

    initial_status = RFQStatus.ACTIVE.value if now >= rfq_in.bid_start else RFQStatus.SCHEDULED.value

    new_rfq = RFQ(
        reference_id=ref_id,
        title=rfq_in.title.strip(),
        description=rfq_in.description,
        origin=rfq_in.origin.strip(),
        destination=rfq_in.destination.strip(),
        pickup_date=rfq_in.pickup_date,
        bid_start=rfq_in.bid_start,
        bid_close=rfq_in.bid_close,
        effective_close=rfq_in.bid_close,
        forced_close=rfq_in.forced_close,
        status=initial_status,
        created_by=current_user.id,
    )
    db.add(new_rfq)
    db.flush()

    config = AuctionConfig(
        rfq_id=new_rfq.id,
        trigger_window_minutes=rfq_in.trigger_window_minutes,
        extension_minutes=rfq_in.extension_minutes,
        trigger_type=rfq_in.trigger_type.value,
    )
    db.add(config)

    # Attach invited suppliers
    for s_id in rfq_in.invited_supplier_ids:
        supplier_exists = db.query(Supplier).filter(Supplier.id == s_id).first()
        if supplier_exists:
            inv = RFQInvitation(rfq_id=new_rfq.id, supplier_id=s_id)
            db.add(inv)

    # Log creation event
    ev = AuctionEvent(
        rfq_id=new_rfq.id,
        event_type=AuctionEventType.AUCTION_STARTED.value if initial_status == RFQStatus.ACTIVE.value else "RFQ_CREATED",
        payload={
            "created_by": current_user.email,
            "reference_id": new_rfq.reference_id,
            "trigger_window_minutes": rfq_in.trigger_window_minutes,
            "extension_minutes": rfq_in.extension_minutes,
            "trigger_type": rfq_in.trigger_type.value,
            "server_time": now.isoformat(),
        },
        created_at=now,
    )
    db.add(ev)

    db.commit()
    db.refresh(new_rfq)

    rfq_base = build_rfq_out(db, new_rfq, current_user)
    return RFQDetailOut(
        **rfq_base.model_dump(),
        rankings=[],
        recent_extensions=[],
        my_bid_history=[],
    )


@router.get("/{rfq_id}", response_model=RFQDetailOut)
def get_rfq(
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

    # Access check for suppliers
    if current_user.role == UserRole.SUPPLIER.value:
        inv = (
            db.query(RFQInvitation)
            .filter(RFQInvitation.rfq_id == rfq.id, RFQInvitation.supplier_id == current_user.supplier_id)
            .first()
        )
        if not inv:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": "SUPPLIER_NOT_INVITED", "message": "You are not invited to participate in this RFQ"},
            )

    rfq_base = build_rfq_out(db, rfq, current_user)
    raw_rankings = calculate_rankings(db, rfq.id)

    rankings_out = []
    for r in raw_rankings:
        rankings_out.append(
            SupplierRankOut(
                rank=r["rank"],
                supplier_id=r["supplier_id"],
                supplier_name=r["supplier_name"],
                supplier_code=r["supplier_code"],
                total=r["total"],
                freight_charges=r["freight_charges"],
                origin_charges=r["origin_charges"],
                destination_charges=r["destination_charges"],
                transit_time_days=r["transit_time_days"],
                quote_validity_date=r["quote_validity_date"],
                carrier_name=r["carrier_name"],
                bid_id=r["bid_id"],
                bid_created_at=r["bid_created_at"],
                is_current_user_supplier=(current_user.supplier_id == r["supplier_id"]),
            )
        )

    # Extensions
    extensions = (
        db.query(AuctionExtension)
        .filter(AuctionExtension.rfq_id == rfq.id)
        .order_by(AuctionExtension.created_at.desc())
        .limit(20)
        .all()
    )

    # Supplier's own bid history
    my_bids = []
    if current_user.role == UserRole.SUPPLIER.value and current_user.supplier_id:
        bids_q = (
            db.query(Bid)
            .filter(Bid.rfq_id == rfq.id, Bid.supplier_id == current_user.supplier_id)
            .order_by(Bid.created_at.desc())
            .all()
        )
        my_bids = [BidOut.model_validate(b) for b in bids_q]

    return RFQDetailOut(
        **rfq_base.model_dump(),
        rankings=rankings_out,
        recent_extensions=[AuctionExtensionOut.model_validate(ext) for ext in extensions],
        my_bid_history=my_bids,
    )


@router.put("/{rfq_id}", response_model=RFQDetailOut)
def update_rfq(
    rfq_id: str,
    rfq_update: RFQUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_buyer),
):
    rfq = db.query(RFQ).filter((RFQ.id == rfq_id) | (RFQ.reference_id == rfq_id)).first()
    if not rfq:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "RFQ_NOT_FOUND", "message": "RFQ not found"},
        )

    now = utc_now()
    # Check if locked: cannot edit if auction is ACTIVE, CLOSED, or FORCE_CLOSED, or if now >= bid_start
    if rfq.status != RFQStatus.SCHEDULED.value or now >= rfq.bid_start:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "RFQ_LOCKED", "message": "Auction cannot be modified once bidding has started or concluded"},
        )

    # Apply updates
    if rfq_update.title is not None:
        rfq.title = rfq_update.title.strip()
    if rfq_update.description is not None:
        rfq.description = rfq_update.description
    if rfq_update.origin is not None:
        rfq.origin = rfq_update.origin.strip()
    if rfq_update.destination is not None:
        rfq.destination = rfq_update.destination.strip()
    if rfq_update.pickup_date is not None:
        rfq.pickup_date = rfq_update.pickup_date
    if rfq_update.bid_start is not None:
        rfq.bid_start = rfq_update.bid_start
    if rfq_update.bid_close is not None:
        rfq.bid_close = rfq_update.bid_close
        rfq.effective_close = rfq_update.bid_close
    if rfq_update.forced_close is not None:
        rfq.forced_close = rfq_update.forced_close

    # Validate timing constraints
    if rfq.bid_close <= rfq.bid_start:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_TIMING", "message": "bid_close must be strictly after bid_start"},
        )
    if rfq.forced_close <= rfq.bid_close:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_TIMING", "message": "forced_close must be strictly after bid_close"},
        )
    if rfq.pickup_date <= rfq.bid_close:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_TIMING", "message": "pickup_date must be strictly after bid_close"},
        )

    # Update config
    if rfq.config:
        if rfq_update.trigger_window_minutes is not None:
            rfq.config.trigger_window_minutes = rfq_update.trigger_window_minutes
        if rfq_update.extension_minutes is not None:
            rfq.config.extension_minutes = rfq_update.extension_minutes
        if rfq_update.trigger_type is not None:
            rfq.config.trigger_type = rfq_update.trigger_type.value

    # Update invitations if supplied
    if rfq_update.invited_supplier_ids is not None:
        db.query(RFQInvitation).filter(RFQInvitation.rfq_id == rfq.id).delete()
        for s_id in rfq_update.invited_supplier_ids:
            db.add(RFQInvitation(rfq_id=rfq.id, supplier_id=s_id))

    db.commit()
    db.refresh(rfq)

    return get_rfq(rfq.id, db, current_user)


@router.get("/{rfq_id}/events", response_model=List[AuctionEventOut])
def get_rfq_events(
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

    events = (
        db.query(AuctionEvent)
        .filter(AuctionEvent.rfq_id == rfq_id)
        .order_by(AuctionEvent.created_at.asc())
        .all()
    )
    return [AuctionEventOut.model_validate(ev) for ev in events]


@router.post("/reseed-live-demo")
@router.post("/{rfq_id}/reseed-demo")
async def reseed_demo_rfq(
    rfq_id: str = "RFQ-2026-LIVE-DEMO",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Resets the RFQ timer into its trigger window (~2.5 minutes remaining)
    and broadcasts the reset event via WebSocket.
    Supports either UUID or reference_id (defaults to RFQ-2026-LIVE-DEMO).
    """
    rfq = db.query(RFQ).filter((RFQ.id == rfq_id) | (RFQ.reference_id == rfq_id)).first()
    if not rfq:
        # Fallback to RFQ-2026-LIVE-DEMO if rfq_id was empty or not found
        rfq = db.query(RFQ).filter(RFQ.reference_id == "RFQ-2026-LIVE-DEMO").first()
    if not rfq:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "RFQ_NOT_FOUND", "message": "RFQ not found"},
        )

    now = utc_now()
    rfq.bid_start = now - timedelta(minutes=45)
    rfq.bid_close = now + timedelta(minutes=2, seconds=30)
    rfq.effective_close = now + timedelta(minutes=2, seconds=30)
    rfq.forced_close = now + timedelta(minutes=15)
    rfq.status = RFQStatus.ACTIVE.value

    # Log reset event
    ev = AuctionEvent(
        rfq_id=rfq.id,
        event_type="DEMO_RESEEDED",
        payload={
            "effective_close": rfq.effective_close.isoformat(),
            "forced_close": rfq.forced_close.isoformat(),
            "server_time": now.isoformat(),
            "reason": "Live demo timeline reset into active trigger window (~2.5m remaining)",
        },
        created_at=now,
    )
    db.add(ev)
    db.commit()

    # Broadcast reset to live WebSocket listeners
    await ws_manager.broadcast_to_rfq(
        rfq_id=rfq.id,
        event_type="DEMO_RESEEDED",
        data={
            "effective_close": rfq.effective_close.isoformat(),
            "forced_close": rfq.forced_close.isoformat(),
            "status": rfq.status,
            "message": "Demo auction timeline reset into trigger window",
        },
    )

    return {
        "success": True,
        "message": "Live demo auction reset to ~2.5m before effective close",
        "effective_close": rfq.effective_close.isoformat(),
        "forced_close": rfq.forced_close.isoformat(),
    }


class AwardRequest(BaseModel):
    winning_bid_id: str
    award_reason: str
    notes: Optional[str] = None


@router.post("/{rfq_id}/award")
async def award_rfq(
    rfq_id: str,
    payload: AwardRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_buyer),
):
    """
    Awards a concluded RFQ to the selected supplier bid with full audit trail logging.
    """
    rfq = db.query(RFQ).filter((RFQ.id == rfq_id) | (RFQ.reference_id == rfq_id)).first()
    if not rfq:
        raise HTTPException(status_code=404, detail={"code": "RFQ_NOT_FOUND", "message": "RFQ not found"})

    if rfq.status not in (RFQStatus.CLOSED.value, RFQStatus.FORCE_CLOSED.value):
        raise HTTPException(
            status_code=400,
            detail={"code": "AUCTION_NOT_CONCLUDED", "message": "RFQ must be concluded before an award can be made"},
        )

    winning_bid = db.query(Bid).filter(Bid.id == payload.winning_bid_id, Bid.rfq_id == rfq.id).first()
    if not winning_bid:
        raise HTTPException(
            status_code=404,
            detail={"code": "BID_NOT_FOUND", "message": "Selected bid not found on this RFQ"},
        )

    now = utc_now()
    award_event = AuctionEvent(
        rfq_id=rfq.id,
        bid_id=winning_bid.id,
        event_type="AUCTION_AWARDED",
        payload={
            "winning_bid_id": winning_bid.id,
            "carrier_name": winning_bid.carrier_name,
            "supplier_id": winning_bid.supplier_id,
            "total": float(winning_bid.total),
            "award_reason": payload.award_reason,
            "notes": payload.notes,
            "awarded_by": current_user.email,
            "awarded_at": now.isoformat(),
        },
        created_at=now,
    )
    db.add(award_event)
    db.commit()

    # Broadcast real-time award announcement to all listening clients
    await ws_manager.broadcast_to_rfq(
        rfq_id=rfq.id,
        event_type="AUCTION_AWARDED",
        data={
            "winning_bid_id": winning_bid.id,
            "carrier_name": winning_bid.carrier_name,
            "total": float(winning_bid.total),
            "award_reason": payload.award_reason,
            "awarded_by": current_user.full_name,
        },
    )

    return {
        "success": True,
        "message": f"RFQ awarded to {winning_bid.carrier_name} for ${winning_bid.total:,.2f}",
        "awarded_bid_id": winning_bid.id,
        "carrier_name": winning_bid.carrier_name,
        "total": float(winning_bid.total),
        "award_reason": payload.award_reason,
        "awarded_at": now.isoformat(),
    }


@router.get("/{rfq_id}/export-csv")
def export_rfq_csv(
    rfq_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Generates an official audit-ready CSV export containing all bids, rates, and timing records.
    """
    rfq = db.query(RFQ).filter((RFQ.id == rfq_id) | (RFQ.reference_id == rfq_id)).first()
    if not rfq:
        raise HTTPException(status_code=404, detail={"code": "RFQ_NOT_FOUND", "message": "RFQ not found"})

    if current_user.role == UserRole.SUPPLIER.value:
        inv = db.query(RFQInvitation).filter(RFQInvitation.rfq_id == rfq.id, RFQInvitation.supplier_id == current_user.supplier_id).first()
        if not inv:
            raise HTTPException(status_code=403, detail={"code": "ACCESS_DENIED", "message": "Not invited"})

    bids = db.query(Bid).filter(Bid.rfq_id == rfq.id).order_by(Bid.created_at.asc()).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Bid ID", "Timestamp (UTC)", "Carrier Name", "Freight Charges (USD)",
        "Origin Charges (USD)", "Destination Charges (USD)", "Total Price (USD)",
        "Transit Time (Days)", "Quote Validity Date"
    ])
    for b in bids:
        writer.writerow([
            b.id,
            b.created_at.isoformat(),
            b.carrier_name,
            f"{b.freight_charges:.2f}",
            f"{b.origin_charges:.2f}",
            f"{b.destination_charges:.2f}",
            f"{b.total:.2f}",
            b.transit_time_days,
            b.quote_validity_date.isoformat(),
        ])

    output.seek(0)
    filename = f"meridian_{rfq.reference_id}_audit_export.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
