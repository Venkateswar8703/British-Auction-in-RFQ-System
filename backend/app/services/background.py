import asyncio
import logging
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.entities import RFQ
from app.models.enums import RFQStatus
from app.services.auction_engine import check_and_update_rfq_status
from app.services.websocket_manager import ws_manager

logger = logging.getLogger(__name__)


async def auction_status_sweeper_task():
    """
    Background worker that runs every 5 seconds.
    Finds active and scheduled auctions, checks if their effective or forced close has passed,
    updates their status in the database, and emits real-time WebSocket events.
    """
    logger.info("Starting background auction status sweeper daemon...")
    while True:
        try:
            await asyncio.sleep(5)
            db: Session = SessionLocal()
            try:
                now = datetime.now(timezone.utc)
                # Query scheduled or active auctions
                candidates = (
                    db.query(RFQ)
                    .filter(RFQ.status.in_([RFQStatus.SCHEDULED.value, RFQStatus.ACTIVE.value]))
                    .all()
                )

                for rfq in candidates:
                    changed, event_type = check_and_update_rfq_status(db, rfq, now)
                    if changed:
                        db.commit()
                        logger.info("Auction %s transitioned to %s via background sweeper", rfq.reference_id, rfq.status)
                        # Broadcast status transition to WebSocket clients
                        await ws_manager.broadcast_to_rfq(
                            rfq_id=rfq.id,
                            event_type=event_type,
                            data={
                                "rfq_id": rfq.id,
                                "reference_id": rfq.reference_id,
                                "status": rfq.status,
                                "effective_close": rfq.effective_close.isoformat(),
                                "forced_close": rfq.forced_close.isoformat(),
                                "reason": "Auction reached effective or forced close time",
                            },
                        )
            except Exception as loop_err:
                logger.error("Error in status sweeper loop: %s", loop_err)
                db.rollback()
            finally:
                db.close()

        except asyncio.CancelledError:
            logger.info("Auction status sweeper cancelled.")
            break
        except Exception as e:
            logger.error("Unexpected error in auction sweeper task: %s", e)
            await asyncio.sleep(5)

