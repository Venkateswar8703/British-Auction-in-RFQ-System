# Task 1: PostgreSQL Proof & Verification Evidence

**Task Status**: **PASS**  
**Database**: PostgreSQL 18.6 (x86_64 Ubuntu Linux)  
**Host & Port**: `127.0.0.1:5432`  
**Database Name**: `meridian_db`  
**User**: `meridian`  
**DATABASE_URL**: `postgresql://meridian:meridian_secret@127.0.0.1:5432/meridian_db`

---

## 1. Engine & Database Connection Proof

### 1.1 `SELECT version();` Raw Output
Command:
```bash
PGPASSWORD=meridian_secret psql -U meridian -h 127.0.0.1 -d meridian_db -c "SELECT version();"
```
Output:
```
                                                             version                                                             
---------------------------------------------------------------------------------------------------------------------------------
 PostgreSQL 18.6 (Ubuntu 18.6-0ubuntu0.26.04.1) on x86_64-pc-linux-gnu, compiled by gcc (Ubuntu 15.2.0-16ubuntu1) 15.2.0, 64-bit
(1 row)
```

### 1.2 `DATABASE_URL` and Clean Startup Log
Backend initialization logs confirming connection to PostgreSQL and absence of SQLite warning:
```
INFO:     Started server process [142498]
INFO:     Waiting for application startup.
2026-11-18 15:20:14,004 [INFO] app.seeds.seed_data: Reset Live Demo Auction RFQ-2026-LIVE-DEMO to close at 2026-11-18T15:22:43.942995+05:30
2026-11-18 15:20:14,005 [INFO] meridian: Live demo auction primed and active on startup.
2026-11-18 15:20:14,005 [INFO] meridian: MERIDIAN British Auction Engine online.
2026-11-18 15:20:14,005 [INFO] app.services.background: Starting background auction status sweeper daemon...
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

Endpoint Health check verification:
```bash
curl -s http://localhost:8000/health
```
Output:
```json
{"status":"healthy","service":"MERIDIAN Auction Engine","database":"postgresql","timestamp":"2026-11-18T09:43:25.874555+00:00"}
```

---

## 2. Reversible Alembic Migrations

Command:
```bash
DATABASE_URL="postgresql://meridian:meridian_secret@127.0.0.1:5432/meridian_db" \
  alembic downgrade base && alembic upgrade head
```
Output:
```
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
INFO  [alembic.runtime.migration] Running downgrade b225e45624e2 -> , Initial schema migration
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
INFO  [alembic.runtime.migration] Running upgrade  -> b225e45624e2, Initial schema migration
```

---

## 3. PostgreSQL Schema Inspection (`\d+` & `\di`)

### 3.1 `rfqs` Table
```
                                                        Table "public.rfqs"
     Column      |           Type           | Collation | Nullable | Default | Storage  | Compression | Stats target | Description 
-----------------+--------------------------+-----------+----------+---------+----------+-------------+--------------+-------------
 id              | character varying(36)    |           | not null |         | extended |             |              | 
 reference_id    | character varying(64)    |           | not null |         | extended |             |              | 
 title           | character varying(255)   |           | not null |         | extended |             |              | 
 description     | text                     |           |          |         | extended |             |              | 
 origin          | character varying(255)   |           | not null |         | extended |             |              | 
 destination     | character varying(255)   |           | not null |         | extended |             |              | 
 pickup_date     | timestamp with time zone |           | not null |         | plain    |             |              | 
 bid_start       | timestamp with time zone |           | not null |         | plain    |             |              | 
 bid_close       | timestamp with time zone |           | not null |         | plain    |             |              | 
 effective_close | timestamp with time zone |           | not null |         | plain    |             |              | 
 forced_close    | timestamp with time zone |           | not null |         | plain    |             |              | 
 status          | character varying(20)    |           | not null |         | extended |             |              | 
 created_by      | character varying(36)    |           | not null |         | extended |             |              | 
 created_at      | timestamp with time zone |           | not null |         | plain    |             |              | 
 updated_at      | timestamp with time zone |           | not null |         | plain    |             |              | 
Indexes:
    "rfqs_pkey" PRIMARY KEY, btree (id)
    "idx_rfqs_status_effective" btree (status, effective_close)
    "ix_rfqs_reference_id" UNIQUE, btree (reference_id)
Check constraints:
    "chk_bid_close_gt_bid_start" CHECK (bid_close > bid_start)
    "chk_forced_close_gt_bid_close" CHECK (forced_close > bid_close)
    "chk_pickup_date_gt_bid_close" CHECK (pickup_date > bid_close)
Foreign-key constraints:
    "rfqs_created_by_fkey" FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE RESTRICT
Referenced by:
    TABLE "auction_configs" CONSTRAINT "auction_configs_rfq_id_fkey" FOREIGN KEY (rfq_id) REFERENCES rfqs(id) ON DELETE CASCADE
    TABLE "auction_events" CONSTRAINT "auction_events_rfq_id_fkey" FOREIGN KEY (rfq_id) REFERENCES rfqs(id) ON DELETE CASCADE
    TABLE "auction_extensions" CONSTRAINT "auction_extensions_rfq_id_fkey" FOREIGN KEY (rfq_id) REFERENCES rfqs(id) ON DELETE CASCADE
    TABLE "bids" CONSTRAINT "bids_rfq_id_fkey" FOREIGN KEY (rfq_id) REFERENCES rfqs(id) ON DELETE CASCADE
    TABLE "rfq_invitations" CONSTRAINT "rfq_invitations_rfq_id_fkey" FOREIGN KEY (rfq_id) REFERENCES rfqs(id) ON DELETE CASCADE
```

### 3.2 `bids` Table
```
                                                          Table "public.bids"
       Column        |           Type           | Collation | Nullable | Default | Storage  | Compression | Stats target | Description 
---------------------+--------------------------+-----------+----------+---------+----------+-------------+--------------+-------------
 id                  | character varying(36)    |           | not null |         | extended |             |              | 
 rfq_id              | character varying(36)    |           | not null |         | extended |             |              | 
 supplier_id         | character varying(36)    |           | not null |         | extended |             |              | 
 submitted_by        | character varying(36)    |           | not null |         | extended |             |              | 
 freight_charges     | numeric(12,2)            |           | not null |         | main     |             |              | 
 origin_charges      | numeric(12,2)            |           | not null |         | main     |             |              | 
 destination_charges | numeric(12,2)            |           | not null |         | main     |             |              | 
 total               | numeric(12,2)            |           | not null |         | main     |             |              | 
 transit_time_days   | integer                  |           | not null |         | plain    |             |              | 
 quote_validity_date | timestamp with time zone |           | not null |         | plain    |             |              | 
 carrier_name        | character varying(255)   |           | not null |         | extended |             |              | 
 idempotency_key     | character varying(128)   |           |          |         | extended |             |              | 
 created_at          | timestamp with time zone |           | not null |         | plain    |             |              | 
Indexes:
    "bids_pkey" PRIMARY KEY, btree (id)
    "idx_bids_rfq_created" btree (rfq_id, created_at)
    "idx_bids_rfq_total" btree (rfq_id, total)
    "idx_bids_supplier_rfq" btree (supplier_id, rfq_id, created_at DESC)
    "ix_bids_idempotency_key" UNIQUE, btree (idempotency_key)
Check constraints:
    "chk_bids_destination_positive" CHECK (destination_charges > 0::numeric)
    "chk_bids_freight_positive" CHECK (freight_charges > 0::numeric)
    "chk_bids_origin_positive" CHECK (origin_charges > 0::numeric)
    "chk_bids_total_positive" CHECK (total > 0::numeric)
    "chk_bids_transit_positive" CHECK (transit_time_days > 0)
Foreign-key constraints:
    "bids_rfq_id_fkey" FOREIGN KEY (rfq_id) REFERENCES rfqs(id) ON DELETE CASCADE
    "bids_submitted_by_fkey" FOREIGN KEY (submitted_by) REFERENCES users(id) ON DELETE RESTRICT
    "bids_supplier_id_fkey" FOREIGN KEY (supplier_id) REFERENCES suppliers(id) ON DELETE RESTRICT
```

### 3.3 `auction_events` Table
```
                                                     Table "public.auction_events"
   Column   |           Type           | Collation | Nullable | Default | Storage  | Compression | Stats target | Description 
------------+--------------------------+-----------+----------+---------+----------+-------------+--------------+-------------
 id         | character varying(36)    |           | not null |         | extended |             |              | 
 rfq_id     | character varying(36)    |           | not null |         | extended |             |              | 
 bid_id     | character varying(36)    |           |          |         | extended |             |              | 
 event_type | character varying(50)    |           | not null |         | extended |             |              | 
 payload    | jsonb                    |           | not null |         | extended |             |              | 
 created_at | timestamp with time zone |           | not null |         | plain    |             |              | 
Indexes:
    "auction_events_pkey" PRIMARY KEY, btree (id)
    "idx_auction_events_rfq_created" btree (rfq_id, created_at)
Foreign-key constraints:
    "auction_events_bid_id_fkey" FOREIGN KEY (bid_id) REFERENCES bids(id) ON DELETE SET NULL
    "auction_events_rfq_id_fkey" FOREIGN KEY (rfq_id) REFERENCES rfqs(id) ON DELETE CASCADE
```

### 3.4 `auction_extensions` Table
```
                                                  Table "public.auction_extensions"
      Column       |           Type           | Collation | Nullable | Default | Storage  | Compression | Stats target | Description 
-------------------+--------------------------+-----------+----------+---------+----------+-------------+--------------+-------------
 id                | character varying(36)    |           | not null |         | extended |             |              | 
 rfq_id            | character varying(36)    |           | not null |         | extended |             |              | 
 triggering_bid_id | character varying(36)    |           |          |         | extended |             |              | 
 previous_close    | timestamp with time zone |           | not null |         | plain    |             |              | 
 new_close         | timestamp with time zone |           | not null |         | plain    |             |              | 
 trigger_type      | character varying(30)    |           | not null |         | extended |             |              | 
 reason            | text                     |           | not null |         | extended |             |              | 
 is_clamped        | boolean                  |           | not null |         | plain    |             |              | 
 created_at        | timestamp with time zone |           | not null |         | plain    |             |              | 
Indexes:
    "auction_extensions_pkey" PRIMARY KEY, btree (id)
    "idx_extensions_rfq" btree (rfq_id, created_at)
Foreign-key constraints:
    "auction_extensions_rfq_id_fkey" FOREIGN KEY (rfq_id) REFERENCES rfqs(id) ON DELETE CASCADE
    "auction_extensions_triggering_bid_id_fkey" FOREIGN KEY (triggering_bid_id) REFERENCES bids(id) ON DELETE SET NULL
```

### 3.5 Complete Index List (`\di`)
```
                                 List of indexes
 Schema |              Name              | Type  |  Owner   |       Table        
--------+--------------------------------+-------+----------+--------------------
 public | alembic_version_pkc            | index | meridian | alembic_version
 public | auction_configs_pkey           | index | meridian | auction_configs
 public | auction_configs_rfq_id_key     | index | meridian | auction_configs
 public | auction_events_pkey            | index | meridian | auction_events
 public | auction_extensions_pkey        | index | meridian | auction_extensions
 public | bids_pkey                      | index | meridian | bids
 public | idx_auction_events_rfq_created | index | meridian | auction_events
 public | idx_bids_rfq_created           | index | meridian | bids
 public | idx_bids_rfq_total             | index | meridian | bids
 public | idx_bids_supplier_rfq          | index | meridian | bids
 public | idx_extensions_rfq             | index | meridian | auction_extensions
 public | idx_invitations_rfq            | index | meridian | rfq_invitations
 public | idx_invitations_supplier       | index | meridian | rfq_invitations
 public | idx_rfqs_status_effective      | index | meridian | rfqs
 public | ix_bids_idempotency_key        | index | meridian | bids
 public | ix_rfqs_reference_id           | index | meridian | rfqs
 public | ix_suppliers_code              | index | meridian | suppliers
 public | ix_users_email                 | index | meridian | users
 public | rfq_invitations_pkey           | index | meridian | rfq_invitations
 public | rfqs_pkey                      | index | meridian | rfqs
 public | suppliers_name_key             | index | meridian | suppliers
 public | suppliers_pkey                 | index | meridian | suppliers
 public | uq_rfq_supplier_invitation     | index | meridian | rfq_invitations
 public | users_pkey                     | index | meridian | users
(24 rows)
```

---

## 4. Pytest & Concurrency Execution on PostgreSQL

Command:
```bash
DATABASE_URL="postgresql://meridian:meridian_secret@127.0.0.1:5432/meridian_db" \
  pytest --cov=app.services.auction_engine --cov-report=term-missing backend/tests
```
Output:
```
============================= test session starts ==============================
platform linux -- Python 3.14.4, pytest-9.2.0, pluggy-1.7.0
rootdir: /home/venkateswar_8703/Desktop/GoComet
plugins: asyncio-1.5.0, cov-7.1.0, anyio-4.16.0
asyncio: mode=Mode.STRICT, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
collecting ... collected 13 items                                                             

backend/tests/test_api.py ..                                             [ 15%]
backend/tests/test_auction_engine.py ........                            [ 76%]
backend/tests/test_concurrency.py ...                                    [100%]

================================ tests coverage ================================
Name                                     Stmts   Miss  Cover   Missing
----------------------------------------------------------------------
backend/app/services/auction_engine.py     177     14    92%   69, 106-121, 214, 229, 277-284, 300, 304
----------------------------------------------------------------------
TOTAL                                      177     14    92%
======================== 13 passed, 1 warning in 38.20s ========================
```

---

## 5. Persistence Across Backend Restart

### Step 1: Submit Bid Before Restart
```
=== BEFORE BACKEND RESTART ===
Bid ID: 5ecbe875-4e98-427e-a484-cd598cc4b90f
Carrier: Maersk Line
Total: $1950.00
Rank: L1
Current L1: $1950.00
Leader Carrier: Maersk Line
```

### Step 2: Restart Server Process
```bash
pkill -9 -f uvicorn
PYTHONPATH=backend DATABASE_URL="postgresql://meridian:meridian_secret@127.0.0.1:5432/meridian_db" \
  uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Step 3: Query After Restart
```
=== AFTER BACKEND RESTART ===
RFQ Reference: RFQ-2026-LIVE-DEMO
Current L1 Total: $1950.00
Ladder Rankings Count: 3
Leader Carrier: Maersk Line
Leader Price: $1950.00
Total Bids In Ledger: 4
Confirmed Surviving Bid: ID=5ecbe875-4e98-427e-a484-cd598cc4b90f, Total=$1950.00, Carrier=Maersk Line
SUCCESS: Full persistence verified across backend restart on PostgreSQL!
```

---

## 6. Row-Level Lock Proof (`with_for_update()`)

### 6.1 Source Code Implementation
In `backend/app/services/auction_engine.py` (lines 38-47):
```python
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
```

### 6.2 Lock Verification Test
In `backend/tests/test_concurrency.py` (`test_row_lock_with_for_update_proof`):
Verifies that:
1. `get_rfq_with_lock` unconditionally applies `query.with_for_update()` under PostgreSQL dialect.
2. If `with_for_update()` is removed from the query, the locking assertion fails (`was_locked is False`).
Test Result: **PASS** (`backend/tests/test_concurrency.py::test_row_lock_with_for_update_proof PASSED`).

