from datetime import datetime, timezone
from typing import Dict, Any, List
from decimal import Decimal
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from app.database import get_db
from app.models.entities import (
    RFQ,
    Bid,
    Supplier,
    AuctionEvent,
    RFQInvitation,
    User,
    utc_now,
)
from app.models.enums import RFQStatus, UserRole
from app.services.deps import get_current_user, require_buyer, require_supplier
from app.services.auction_engine import calculate_rankings

router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.get("/command-center")
def get_command_center_metrics(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_buyer),
) -> Dict[str, Any]:
    now = utc_now()

    # RFQ Counts
    total_rfqs = db.query(RFQ).count()
    active_count = db.query(RFQ).filter(RFQ.status == RFQStatus.ACTIVE.value).count()
    closed_count = db.query(RFQ).filter(RFQ.status == RFQStatus.CLOSED.value).count()
    force_closed_count = db.query(RFQ).filter(RFQ.status == RFQStatus.FORCE_CLOSED.value).count()
    scheduled_count = db.query(RFQ).filter(RFQ.status == RFQStatus.SCHEDULED.value).count()

    # Total participating suppliers
    participating_suppliers = db.query(func.count(func.distinct(Bid.supplier_id))).scalar() or 0
    total_bids = db.query(Bid).count()

    # Upcoming Deadlines (Active RFQs sorted by effective_close ASC)
    active_rfqs = (
        db.query(RFQ)
        .filter(RFQ.status == RFQStatus.ACTIVE.value)
        .order_by(RFQ.effective_close.asc())
        .limit(6)
        .all()
    )
    deadlines = []
    for r in active_rfqs:
        rankings = calculate_rankings(db, r.id)
        lowest = rankings[0]["total"] if rankings else None
        deadlines.append({
            "id": r.id,
            "reference_id": r.reference_id,
            "title": r.title,
            "effective_close": r.effective_close.isoformat(),
            "forced_close": r.forced_close.isoformat(),
            "lowest_bid": float(lowest) if lowest else None,
            "bids_count": db.query(Bid).filter(Bid.rfq_id == r.id).count(),
        })

    # Recent Activity Feed (Global across all auctions)
    recent_events = (
        db.query(AuctionEvent, RFQ)
        .join(RFQ, AuctionEvent.rfq_id == RFQ.id)
        .order_by(AuctionEvent.created_at.desc())
        .limit(10)
        .all()
    )
    activities = []
    for ev, r in recent_events:
        activities.append({
            "id": ev.id,
            "rfq_id": r.id,
            "rfq_ref": r.reference_id,
            "rfq_title": r.title,
            "event_type": ev.event_type,
            "payload": ev.payload,
            "created_at": ev.created_at.isoformat(),
        })

    # Performance Analytics: price reduction from initial bid to current L1
    all_rfqs_with_bids = db.query(RFQ).all()
    performance_records = []
    total_savings_pct_sum = 0.0
    rfqs_with_savings_count = 0

    for rfq in all_rfqs_with_bids:
        bids = db.query(Bid).filter(Bid.rfq_id == rfq.id).order_by(Bid.created_at.asc()).all()
        if len(bids) >= 1:
            first_bid_total = float(bids[0].total)
            rankings = calculate_rankings(db, rfq.id)
            current_l1 = float(rankings[0]["total"]) if rankings else first_bid_total
            reduction_pct = 0.0
            if first_bid_total > 0 and current_l1 <= first_bid_total:
                reduction_pct = round(((first_bid_total - current_l1) / first_bid_total) * 100, 1)
                total_savings_pct_sum += reduction_pct
                rfqs_with_savings_count += 1

            performance_records.append({
                "rfq_ref": rfq.reference_id,
                "title": rfq.title,
                "first_bid": first_bid_total,
                "current_l1": current_l1,
                "reduction_pct": reduction_pct,
                "bids_count": len(bids),
            })

    avg_savings_pct = round(total_savings_pct_sum / max(rfqs_with_savings_count, 1), 1)

    from app.models.entities import AuctionExtension
    total_extensions = db.query(AuctionExtension).count()
    completed_rfqs = closed_count + force_closed_count
    avg_extensions = round(total_extensions / max(completed_rfqs, 1), 2)

    return {
        "summary": {
            "total_rfqs": total_rfqs,
            "active_count": active_count,
            "closed_count": closed_count,
            "force_closed_count": force_closed_count,
            "scheduled_count": scheduled_count,
            "total_bids": total_bids,
            "participating_suppliers": participating_suppliers,
            "avg_price_reduction_pct": avg_savings_pct,
            "avg_extensions_per_auction": avg_extensions,
            "total_extensions_triggered": total_extensions,
        },
        "upcoming_deadlines": deadlines,
        "recent_activity": activities,
        "performance": performance_records[:8],
        "server_time": now.isoformat(),
    }


@router.get("/supplier-portal")
def get_supplier_portal_metrics(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_supplier),
) -> Dict[str, Any]:
    supplier_id = current_user.supplier_id
    now = utc_now()

    # Total invitations
    invited_rfq_ids = [
        inv.rfq_id
        for inv in db.query(RFQInvitation).filter(RFQInvitation.supplier_id == supplier_id).all()
    ]

    total_invited = len(invited_rfq_ids)

    # Active auctions supplier is invited to
    active_invited = (
        db.query(RFQ)
        .filter(RFQ.id.in_(invited_rfq_ids), RFQ.status == RFQStatus.ACTIVE.value)
        .order_by(RFQ.effective_close.asc())
        .all()
    )

    my_bids_count = db.query(Bid).filter(Bid.supplier_id == supplier_id).count()

    # Calculate current standing across invited auctions
    l1_wins = 0
    outbid_count = 0
    active_auctions_data = []

    for rfq in active_invited:
        rankings = calculate_rankings(db, rfq.id)
        supplier_rank = next((r["rank"] for r in rankings if r["supplier_id"] == supplier_id), None)
        supplier_bid = next((r["total"] for r in rankings if r["supplier_id"] == supplier_id), None)
        lowest_bid = rankings[0]["total"] if rankings else None

        if supplier_rank == 1:
            l1_wins += 1
        elif supplier_rank is not None and supplier_rank > 1:
            outbid_count += 1

        active_auctions_data.append({
            "id": rfq.id,
            "reference_id": rfq.reference_id,
            "title": rfq.title,
            "origin": rfq.origin,
            "destination": rfq.destination,
            "effective_close": rfq.effective_close.isoformat(),
            "forced_close": rfq.forced_close.isoformat(),
            "my_rank": supplier_rank,
            "my_bid": float(supplier_bid) if supplier_bid else None,
            "lowest_bid": float(lowest_bid) if lowest_bid else None,
            "total_bids": db.query(Bid).filter(Bid.rfq_id == rfq.id).count(),
        })

    # Recent personal bids
    recent_my_bids = (
        db.query(Bid, RFQ)
        .join(RFQ, Bid.rfq_id == RFQ.id)
        .filter(Bid.supplier_id == supplier_id)
        .order_by(Bid.created_at.desc())
        .limit(8)
        .all()
    )

    my_bids_list = []
    for b, r in recent_my_bids:
        my_bids_list.append({
            "bid_id": b.id,
            "rfq_id": r.id,
            "rfq_ref": r.reference_id,
            "rfq_title": r.title,
            "total": float(b.total),
            "transit_time_days": b.transit_time_days,
            "carrier_name": b.carrier_name,
            "created_at": b.created_at.isoformat(),
        })

    return {
        "summary": {
            "total_invited": total_invited,
            "active_auctions_count": len(active_invited),
            "my_total_bids": my_bids_count,
            "l1_count": l1_wins,
            "outbid_count": outbid_count,
        },
        "active_auctions": active_auctions_data,
        "recent_bids": my_bids_list,
        "server_time": now.isoformat(),
    }

