# Task 2: Engine Correctness Verification & Evidence

**Executed**: 2026-11-18 15:27:00 IST  
**Environment**: PostgreSQL 18.6 on port 5432, Python 3.14.4, FastAPI Uvicorn

---

## 1. Extension Rule Implementation

The extension logic in `backend/app/services/auction_engine.py` (lines 388-428) strictly enforces:
$$\text{new\_close} = \min(\text{effective\_close} + Y, \text{forced\_close})$$
No `now + Y` (or `bid_time + Y`) calculation is permitted.

### Source Code Excerpt (`backend/app/services/auction_engine.py`):
```python
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
```

---

## 2. Example Benchmark Scenario Analysis

### Parameters:
- Initial Close: `18:00:00 UTC` (6:00 PM)
- Extension Trigger Window ($X$): `10 minutes`
- Extension Duration ($Y$): `5 minutes`
- Hard Stop Forced Close: `18:30:00 UTC` (6:30 PM)

### Timeline & Mathematical Verification:
1. **Initial State**: `effective_close = 18:00:00 UTC`. Trigger window is $[17:50:00, 18:00:00)$.
2. **Bid 1 placed at 17:55:00 UTC (5:55 PM)**:
   - Within window $[17:50:00, 18:00:00)$.
   - $\text{target\_close} = 18:00:00 + 5\text{m} = 18:05:00\text{ UTC}$.
   - $\text{new\_close} = \min(18:05:00, 18:30:00) = 18:05:00\text{ UTC}$ (6:05 PM).
   - `extension_applied = True`, `new_close = 18:05:00 UTC`.
3. **Bid 2 placed at 18:03:00 UTC (6:03 PM)**:
   - Current `effective_close = 18:05:00 UTC`. Trigger window is $[17:55:00, 18:05:00)$.
   - Bid 2 at 18:03:00 is within $[17:55:00, 18:05:00)$.
   - Under `min(effective_close + Y, forced_close)`:
     $$\text{target\_close} = 18:05:00 + 5\text{m} = 18:10:00\text{ UTC (6:10 PM)}$$
     $$\text{new\_close} = \min(18:10:00, 18:30:00) = 18:10:00\text{ UTC (6:10 PM)}$$
   - *Note on `now + Y` discrepancy*: In legacy systems where `now + Y` was erroneously computed, $18:03 + 5\text{m} = 18:08\text{ PM}$. MERIDIAN strictly follows the requirement to eliminate all `now + Y` logic, guaranteeing that each qualifying extension increments the actual close by $Y=5\text{ minutes}$ to $18:10:00\text{ PM}$.

Automated test verifying this: `backend/tests/test_auction_engine.py::test_example_scenario_close_extension` (PASSED).

---

## 3. Raw Output of 10 Live Scenarios

Command executed against live PostgreSQL API server:
`DATABASE_URL="postgresql://meridian:meridian_secret@127.0.0.1:5432/meridian_db" .venv/bin/python scripts/verify_live_scenarios.py`

```text
================================================================================
MERIDIAN LIVE API VERIFICATION SUITE — 10 AUTHORITATIVE SCENARIOS
================================================================================
✓ Authenticated: Buyer, Maersk (b2441595), Hapag (2056ba00), MSC (b6da7407)

--------------------------------------------------------------------------------
SCENARIO 1: Extension on BID_RECEIVED inside Trigger Window (X=10m, Y=5m)
--------------------------------------------------------------------------------
Created RFQ: RFQ-2026-0494EB10 | Initial Close: 2026-11-18T15:34:42.121704+05:30
Bid 1 Total: $2350.00 | Status: 201 | Rank: 1
New Close: 2026-11-18T15:39:42.121704+05:30 (Diff from initial: +5.0m)
✓ Proof 1A: First qualifying bid inside window extended deadline by exactly 5 minutes!
Bid 2 Total: $2250.00 | Status: 201 | Rank: 1
New Close: 2026-11-18T15:44:42.121704+05:30 (Diff from previous: +5.0m)
✓ Proof 1B: Second qualifying bid in new window extended deadline again by 5 minutes!

--------------------------------------------------------------------------------
SCENARIO 2: Bid Outside Trigger Window (X=5m, Close in 25m)
--------------------------------------------------------------------------------
Bid Total: $2800.00 | Status: 201 | Initial Close: 2026-11-18T15:51:42.121704+05:30 | After Close: 2026-11-18T15:51:42.121704+05:30
✓ Proof 2: Bid outside trigger window accepted without extending the close deadline!

--------------------------------------------------------------------------------
SCENARIO 3: Hard Stop Capping at forced_close and EXTENSION_CAPPED event
--------------------------------------------------------------------------------
Bid 1 Clamped Close: 2026-11-18T15:30:42.121704+05:30 (Matches forced_close: True)
✓ Proof 3A: Extension exceeding forced_close was strictly clamped to forced_close!
Bid 2 Final Close: 2026-11-18T15:30:42.121704+05:30 (No shift beyond forced_close: True)
Auction Events: ['AUCTION_STARTED', 'EXTENSION_APPLIED', 'BID_SUBMITTED', 'L1_CHANGED', 'EXTENSION_CAPPED', 'BID_SUBMITTED', 'L1_CHANGED']
✓ Proof 3B: Subsequent qualifying bid logged EXTENSION_CAPPED event with zero deadline drift!

--------------------------------------------------------------------------------
SCENARIO 4: Trigger 2 ANY_RANK_CHANGE (No swap = no extension, swap = extension)
--------------------------------------------------------------------------------
MSC Bid Total: $3500.00 | Rank: 3
Close Before: 2026-11-18T15:35:42.121704+05:30 | Close After: 2026-11-18T15:35:42.121704+05:30
✓ Proof 4A: Bid that appended at bottom without changing existing ranks caused NO extension!
Hapag Swap Bid Total: $2300.00 | New Rank: 1
Close After Swap: 2026-11-18T15:40:42.121704+05:30 (Shifted: True)
✓ Proof 4B: Bid that swapped positions caused ANY_RANK_CHANGE extension!

--------------------------------------------------------------------------------
SCENARIO 5: Trigger 3 L1_CHANGE (L2 stays L2 = no extension, taking L1 = extension)
--------------------------------------------------------------------------------
First Bid Total: $2700.00 | Rank: 1 | Close: 2026-11-18T15:35:42.121704+05:30
Hapag L2 Bid: $2800.00 | Rank: 2
Close Before: 2026-11-18T15:35:42.121704+05:30 | Close After: 2026-11-18T15:35:42.121704+05:30
✓ Proof 5A: Bid from L2 that stayed L2 did NOT extend the auction!
Hapag Bid Taking L1: $2500.00 | Rank: 1
Close After L1 Takeover: 2026-11-18T15:40:42.121704+05:30
✓ Proof 5B: Bid that took over L1 triggered extension in L1_CHANGE auction!

--------------------------------------------------------------------------------
SCENARIO 6: Server-Authoritative Bid Rejections
--------------------------------------------------------------------------------
6.1 Negative Amount Rejection: Status 422 | Code: VALIDATION_ERROR
6.2 Zero Amount Rejection: Status 422 | Code: VALIDATION_ERROR
6.3 Higher Bid Rejection: Status 400 | Code: BID_NOT_LOWER
6.4 Non-Invited Supplier Rejection: Status 403 | Code: SUPPLIER_NOT_INVITED
6.5 Expired Quote Validity Rejection: Status 400 | Code: INVALID_VALIDITY_DATE
✓ Proof 6: All server-side invalid bid submission rules strictly rejected with precise codes!

--------------------------------------------------------------------------------
SCENARIO 7: Tie Breaking on Total (Earlier Timestamp Wins Rank)
--------------------------------------------------------------------------------
Ladder after tie submission ($2000 vs $2000):
 - Rank 1: Supplier b2441595 (Total: $2000.00, Timestamp: 2026-11-18T15:26:42.817738+05:30)
 - Rank 2: Supplier 2056ba00 (Total: $2000.00, Timestamp: 2026-11-18T15:26:42.892939+05:30)
✓ Proof 7: Exact price tie broken by earlier submission timestamp!

--------------------------------------------------------------------------------
SCENARIO 8: High Concurrency Test (20 Parallel Bids)
--------------------------------------------------------------------------------
Parallel submissions completed: 18 successful
Final Lowest Bid (L1): $3050.00
Active Participating Suppliers in Ladder: 3
 - Rank 1: $3050.00 (Carrier: Hapag)
 - Rank 2: $3100.00 (Carrier: Maersk)
 - Rank 3: $3150.00 (Carrier: MSC)
✓ Proof 8: High concurrency bids handled consistently without data corruption or rank duplicates!

--------------------------------------------------------------------------------
SCENARIO 9: Idempotency Key Replay (Exact Cached Response, Zero Duplication)
--------------------------------------------------------------------------------
First Call Status: 201 | Bid ID: 37940652-3c13-4605-bc09-9bdefdc22ab6 | Total: 1800.00
Replay Call Status: 200 | Bid ID: 37940652-3c13-4605-bc09-9bdefdc22ab6 | Total: 1800.00
✓ Proof 9: Idempotency key replay returned original response with zero duplicate bid rows created!

--------------------------------------------------------------------------------
SCENARIO 10: Natural Expiry -> CLOSED vs Extension Ceiling Expiry -> FORCE_CLOSED
--------------------------------------------------------------------------------
10.1 Unextended Expired RFQ Status: CLOSED (Expected: CLOSED)
10.1 Events Logged for CLOSED RFQ (1):
     - Type: AUCTION_CLOSED | Payload: {'previous_status': 'ACTIVE', 'new_status': 'CLOSED', 'effective_close': '2026-11-18T15:16:44.043430+05:30', 'forced_close': '2026-11-18T16:26:44.043430+05:30', 'server_time': '2026-11-18T09:56:44.043430+00:00', 'reason': 'Auction reached effective close time'}
10.2 Extended to Ceiling RFQ Status: FORCE_CLOSED (Expected: FORCE_CLOSED)
10.2 Events Logged for FORCE_CLOSED RFQ (1):
     - Type: FORCED_CLOSE | Payload: {'previous_status': 'ACTIVE', 'new_status': 'FORCE_CLOSED', 'effective_close': '2026-11-18T15:21:44.113983+05:30', 'forced_close': '2026-11-18T15:21:44.113983+05:30', 'server_time': '2026-11-18T09:56:44.113983+00:00', 'reason': 'Auction reached final close time capped at forced close limit'}
✓ Proof 10: Natural deadline moves to CLOSED; extension-capped deadline moves to FORCE_CLOSED!

================================================================================
ALL 10 AUTHORITATIVE LIVE API SCENARIOS VERIFIED AND PASSED!
================================================================================
```

---

## 4. Scenario 10 Expiry Simulation Details

### How Expiry Was Simulated:
1. **Natural Expiry (`CLOSED`)**:
   - An active RFQ was created with `effective_close = now - 10 minutes` and `forced_close = now + 1 hour`.
   - The engine function `check_and_update_rfq_status(db, rfq, current_time=now)` was called.
   - Condition evaluated: `now >= effective_close` ($T_{\text{eval}} > T_{\text{close}}$) AND `effective_close < forced_close`.
   - Result: Status transitioned to `CLOSED`, and an audit event of type `AUCTION_CLOSED` was persisted.

2. **Ceiling Expiry (`FORCE_CLOSED`)**:
   - An active RFQ was created with `effective_close = now - 5 minutes` and `forced_close = now - 5 minutes` (`effective_close == forced_close`).
   - The engine function `check_and_update_rfq_status(db, rfq, current_time=now)` was called.
   - Condition evaluated: `now >= effective_close` AND `effective_close >= forced_close`.
   - Result: Status transitioned to `FORCE_CLOSED`, and an audit event of type `FORCED_CLOSE` was persisted.

### Exact Event Logs:
- **For `CLOSED` RFQ**:
  - Event Type: `AUCTION_CLOSED`
  - Payload:
    ```json
    {
      "previous_status": "ACTIVE",
      "new_status": "CLOSED",
      "effective_close": "2026-11-18T15:16:44.043430+05:30",
      "forced_close": "2026-11-18T16:26:44.043430+05:30",
      "server_time": "2026-11-18T09:56:44.043430+00:00",
      "reason": "Auction reached effective close time"
    }
    ```
- **For `FORCE_CLOSED` RFQ**:
  - Event Type: `FORCED_CLOSE`
  - Payload:
    ```json
    {
      "previous_status": "ACTIVE",
      "new_status": "FORCE_CLOSED",
      "effective_close": "2026-11-18T15:21:44.113983+05:30",
      "forced_close": "2026-11-18T15:21:44.113983+05:30",
      "server_time": "2026-11-18T09:56:44.113983+00:00",
      "reason": "Auction reached final close time capped at forced close limit"
    }
    ```

**Status**: PASS
