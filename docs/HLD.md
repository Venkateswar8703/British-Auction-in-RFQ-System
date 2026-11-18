# MERIDIAN: British Auction RFQ Procurement Exchange
## High-Level Design (HLD) Architecture

---

### 1. Purpose & Domain Overview
**MERIDIAN** is an enterprise-grade British Auction RFQ (Request for Quotation) procurement platform engineered specifically for ocean container shipping and air freight logistics. In freight procurement, freight forwarders and shippers require competitive pricing while eliminating predatory bidding practices.

Unlike standard English forward auctions (ascending price) or Dutch auctions (clock-driven descending price), a **British Auction RFQ** operates as a reverse auction where invited carriers submit descending price quotes against an authoritative server deadline. 

Key operational imperatives addressed by MERIDIAN include:
1. **Anti-Sniping Dynamic Extension ("Soft Close")**: Opportunistic bots submit bids milliseconds before deadline to deny rivals reaction time. When a qualifying bid is submitted within the last $X$ minutes (trigger window), the auction dynamically extends by $Y$ minutes.
2. **Deterministic Hard Ceiling ("Forced Close")**: To prevent indefinite extensions and guarantee business closure, an absolute inviolable deadline (`forced_close`) caps all extensions:
   $$\text{new\_close} = \min(\text{effective\_close} + Y, \text{forced\_close})$$
3. **Multi-Tenant Privacy Modes**: Configurable per-RFQ visibility (`OPEN` transparent pricing vs. `MASKED` blind pricing where rival carriers only see their own rank and L1 price).
4. **Tamper-Proof Audit Trail**: Immutable append-only audit trail enforced by database-level triggers to guarantee compliance with commercial procurement regulations.

All ranking algorithms, validation rules, timer calculations, and concurrency controls execute strictly within the server-side transactional boundary.

---

### 2. High-Level System Architecture

The MERIDIAN platform is structured across four tiers: Client Application, Reverse Proxy Edge, Application Services (FastAPI), and Relational Persistence (PostgreSQL 16).

![MERIDIAN Architecture](architecture.png)

```mermaid
flowchart TB
    subgraph Client ["Client Tier (Browser)"]
        UI_Buyer["Buyer Web App (React 18 + Vite)<br/>- Command Center & Live Room<br/>- RFQ Builder & Supplier Invites<br/>- Contract Awarding & CSV Audit"]
        UI_Supplier["Supplier Web App (React 18 + Vite)<br/>- Carrier Portal & Invited RFQs<br/>- High-Precision Bidding Console<br/>- Drift-Compensated Countdown"]
    end

    subgraph ReverseProxy ["Edge Reverse Proxy"]
        Nginx["Nginx Reverse Proxy / Web Server<br/>- Port 80 (HTTP) / 443 (HTTPS)<br/>- Static SPA Asset Serving<br/>- Reverse Proxy /api/v1 -> Backend<br/>- WebSocket Upgrade /ws -> Backend"]
    end

    subgraph BackendApp ["FastAPI Application Services (Port 8000)"]
        subgraph Routers ["REST API Routers"]
            AuthRouter["Auth Router<br/>/api/v1/auth (JWT, ws-ticket)"]
            RFQRouter["RFQ Router<br/>/api/v1/rfqs (CRUD, invites, award)"]
            BidRouter["Bid Router<br/>/api/v1/rfqs/{id}/bids (Idempotency)"]
            SupplierRouter["Suppliers Router<br/>/api/v1/suppliers (Buyer-only)"]
            AnalyticsRouter["Analytics Router<br/>/api/v1/analytics"]
        end

        subgraph CoreServices ["Core Domain & Engine"]
            AuctionEngine["Auction Engine (auction_engine.py)<br/>- Pessimistic Row Lock (FOR UPDATE)<br/>- Server-Side Validations & Decr.<br/>- Dynamic Extension Formula<br/>- Dynamic Multi-Tenant Ranking"]
            WSManager["WebSocket Manager (ws_manager.py)<br/>- Single-Use Ticket Auth<br/>- Room-Based Topic Hub<br/>- Masked vs Open Payload Filter"]
            Sweeper["Background Sweeper (sweeper.py)<br/>- Periodic Async Daemon (5s tick)<br/>- Lazy Status Lifecycle Transitions"]
        end
    end

    subgraph DatabaseTier ["Persistence Tier (PostgreSQL 16)"]
        Postgres[("PostgreSQL 16 Database<br/>- ACID Read Committed Isolation<br/>- Row-Level Locking (FOR UPDATE)<br/>- Check Constraints (Total, Charges)<br/>- Scoped Partial Unique Indexes<br/>- Tamper-Proof Audit Trigger (auction_events)")]
    end

    UI_Buyer -->|"HTTP / REST"| Nginx
    UI_Buyer <-->|"WSS (WebSocket)"| Nginx
    UI_Supplier -->|"HTTP / REST"| Nginx
    UI_Supplier <-->|"WSS (WebSocket)"| Nginx

    Nginx -->|"/api/v1 requests"| Routers
    Nginx <-->|"/ws and /api/v1/ws"| WSManager

    BidRouter -->|"Acquire Row Lock & Process"| AuctionEngine
    RFQRouter -->|"State & Invitations"| AuctionEngine
    AuctionEngine -->|"SELECT FOR UPDATE & INSERT/UPDATE"| Postgres
    AuctionEngine -.->|"Post-Commit Broadcast Event"| WSManager
    WSManager -.->|"Push Real-Time Events"| Nginx
    Sweeper -->|"Sweep Status Transitions"| Postgres
    Sweeper -.->|"Broadcast AUCTION_CLOSED / FORCED_CLOSE"| WSManager
```

---

### 3. British Auction Domain Rules

#### 3.1 Initial Auction Configuration
Every British Auction RFQ contains explicit timing parameters:
- `bid_start`: Earliest moment bids are accepted.
- `bid_close`: Initial scheduled auction close deadline.
- `effective_close`: Dynamic current close deadline (initialized to `bid_close`).
- `forced_close`: Inviolable hard ceiling beyond which no extensions can push the auction.
- `trigger_window_minutes` ($X$): Time window before `effective_close` during which qualifying bids trigger an extension.
- `extension_minutes` ($Y$): Duration added to the close time upon a qualifying bid.
- `trigger_type`: Event condition required to trigger an extension.
- `min_decrement`: Minimum downward step required below carrier's prior quote (default: \$0.01).
- `bid_visibility`: Carrier privacy setting (`OPEN` vs. `MASKED`).

#### 3.2 Dynamic Extension Formula
When a qualifying bid is submitted inside the trigger window $[ \text{effective\_close} - X, \text{effective\_close} )$, the engine computes:
$$\text{new\_close} = \min(\text{effective\_close} + Y, \text{forced\_close})$$
**Strict Implementation Rule**: The formula strictly anchors to $\text{effective\_close} + Y$ (never $\text{now} + Y$). If $\text{effective\_close} + Y > \text{forced\_close}$, the extension is clamped to `forced_close`, and an `EXTENSION_CAPPED` event is emitted. Once $\text{effective\_close} == \text{forced\_close}$, no further extensions can occur.

#### 3.3 Qualifying Trigger Types
1. **`BID_RECEIVED`**: Any valid bid inside the trigger window qualifies and triggers an extension.
2. **`L1_CHANGE`**: Qualifies only if the identity of the lowest total bidder (L1) changes. The first bid on an auction qualifies as it establishes the initial L1.
3. **`ANY_RANK_CHANGE`**: Strictly defined as **an existing supplier's position changed after re-ranking**. The very first bid on an auction and a new bottom entrant who takes the lowest rank without disturbing any previously ranked supplier's position do **not** qualify.

#### 3.4 Monotonic Price Improvement & Component Charges
- A carrier's subsequent bid must improve upon their own previous best bid by at least `min_decrement`:
  $$\text{new\_total} \le \text{previous\_best\_total} - \text{min\_decrement}$$
- Component constraints enforced at database and application level:
  $$\text{freight\_charges} > 0, \quad \text{origin\_charges} \ge 0, \quad \text{destination\_charges} \ge 0$$
  $$\text{total} = \text{freight\_charges} + \text{origin\_charges} + \text{destination\_charges}$$
- Quote validity date must satisfy: $\text{quote\_validity\_date} \ge \text{rfq.pickup\_date}$.

#### 3.5 Auction Status Lifecycle

```mermaid
stateDiagram-v2
    [*] --> DRAFT : Buyer creates RFQ
    DRAFT --> ACTIVE : current_time >= bid_start
    ACTIVE --> ACTIVE : Qualifying bid in trigger window<br/>new_close = min(effective_close + Y, forced_close)
    ACTIVE --> CLOSED : current_time >= effective_close AND effective_close < forced_close
    ACTIVE --> FORCE_CLOSED : current_time >= forced_close (Hard Ceiling reached)
    CLOSED --> AWARDED : Buyer awards winning quote
    FORCE_CLOSED --> AWARDED : Buyer awards winning quote
    AWARDED --> [*]
```

- **`DRAFT`**: Configured by buyer; invitations managed; parameters editable via `PATCH /rfqs/{id}`.
- **`ACTIVE`**: Auction is open for bidding. Modifications to dates, origin, destination, or pricing parameters are strictly rejected.
- **`CLOSED`**: Concluded normally when $\text{current\_time} \ge \text{effective\_close}$ and $\text{effective\_close} < \text{forced\_close}$.
- **`FORCE_CLOSED`**: Concluded because the auction reached its inviolable `forced_close` ceiling.
- **`AWARDED`**: Contract finalized and awarded to the selected supplier via `POST /rfqs/{id}/award`.

---

### 4. Bid Transaction & Concurrency Architecture

#### 4.1 Pessimistic Concurrency & Transaction Isolation
To prevent race conditions during simultaneous last-second bids (e.g. 20 concurrent carrier submissions), MERIDIAN employs **Pessimistic Row-Level Locking** on the target RFQ row:
1. Transaction runs at PostgreSQL default isolation level: **`READ COMMITTED`**.
2. Lock is acquired at `app/services/auction_engine.py:43` via:
   ```python
   query = db.query(RFQ).filter(RFQ.id == rfq_id).with_for_update()
   rfq = query.first()
   ```
   This generates:
   ```sql
   SELECT ... FROM rfqs WHERE id = :rfq_id FOR UPDATE;
   ```
3. PostgreSQL serializes all competing transactions on that specific RFQ row. The first transaction executes ranking, checks the trigger window, updates `effective_close`, records events, and releases the lock on `db.commit()`. The second transaction then reads the freshly committed `effective_close` and re-evaluates ranking.

#### 4.2 Sequence Diagram: End-to-End Bid Submission

```mermaid
sequenceDiagram
    autonumber
    actor Supplier as Supplier Client
    participant Proxy as Nginx / API Gateway
    participant Router as Bid Router (bids.py)
    participant RateLimit as Rate Limiter (30 req/s)
    participant Engine as Auction Engine (auction_engine.py)
    participant DB as PostgreSQL 16 (meridian_db)
    participant WS as WebSocket Hub (ws_manager.py)
    actor Buyer as Buyer Observer

    Supplier->>Proxy: POST /api/v1/rfqs/{id}/bids (Idempotency-Key, payload)
    Proxy->>Router: Forward Request with JWT
    Router->>RateLimit: Check burst submission (per-carrier)
    alt Rate Limit Exceeded
        RateLimit-->>Supplier: 429 Too Many Requests (Retry-After: 1)
    end
    Router->>Engine: process_bid_submission()
    alt Idempotency Key Matched (rfq_id, supplier_id, idempotency_key)
        Engine->>DB: Query existing bid by (rfq, supplier, key)
        DB-->>Engine: Cached Bid
        Engine-->>Router: is_replay = True, cached bid
        Router-->>Supplier: 200 OK (Replayed Bid Result)
    else New Bid Submission
        Engine->>DB: SELECT * FROM rfqs WHERE id = :id FOR UPDATE
        Note over Engine,DB: Pessimistic Row Lock acquired on RFQ row
        Engine->>Engine: Validate server time, active status, invited supplier, component charges, validity date
        alt Validation Failure
            Engine->>DB: Rollback Transaction
            Engine-->>Router: Raise Domain Error (e.g. BID_NOT_LOWER, INVALID_VALIDITY_DATE)
            Router-->>Supplier: 400/422 Error Response
        else Validation Success
            Engine->>DB: INSERT INTO bids (charges, total, validity, timestamp)
            Engine->>Engine: Recompute Ranks (Total ASC, created_at ASC)
            Engine->>Engine: Evaluate Trigger Condition inside [effective_close - X, effective_close)
            alt Qualifying Event Triggered (BID_RECEIVED / L1_CHANGE / ANY_RANK_CHANGE)
                Engine->>Engine: Calculate new_close = min(effective_close + Y, forced_close)
                Engine->>DB: UPDATE rfqs SET effective_close = new_close
                Engine->>DB: INSERT INTO auction_extensions (triggering_bid_id, new_close)
                Engine->>DB: INSERT INTO auction_events (EXTENSION_APPLIED)
            end
            Engine->>DB: INSERT INTO auction_events (BID_SUBMITTED, RANK_CHANGED, L1_CHANGED)
            Engine->>DB: COMMIT Transaction (Releases Row Lock)
            Engine-->>Router: Result (Bid, Rankings, Extension Status)
            Router->>WS: broadcast_rfq(rfq_id, broadcast_data)
            WS-->>Supplier: Sync Event (Masked/Open as per config)
            WS-->>Buyer: Full Sync Event (All carrier amounts & ranks)
            Router-->>Supplier: 201 Created (Bid Confirmation)
        end
    end
```

---

### 5. Access Control & Security Model

1. **Authentication**:
   - Stateless JWT tokens signed with HMAC-SHA256 containing `sub` (User ID), `email`, and `role`.
   - Passwords securely hashed with `bcrypt`.
2. **Role-Based Access Control (RBAC)**:
   - **`buyer`**: Can create and patch RFQs, invite suppliers, inspect all carrier bids, view global analytics, export CSV audit files, and award contracts.
   - **`supplier`**: Can only view RFQs they are invited to via `rfq_invitations`. Submissions are verified against `current_user.supplier_id`. Calling buyer-only routes (e.g. `GET /api/v1/suppliers`) returns `403 Forbidden`.
3. **Bid Visibility Privacy (`OPEN` vs. `MASKED`)**:
   - In `OPEN` auctions: All invited carriers receive transparent ladders with carrier names, ranks, and bid amounts.
   - In `MASKED` auctions: The server filters all REST and WebSocket payloads for suppliers. Invited carriers receive their own bid details, their own rank, and the current L1 price. Rival carrier names, breakdowns, and amounts are completely redacted server-side.
4. **WebSocket Single-Use Ticket Authentication**:
   - Browsers obtain an ephemeral single-use ticket via `POST /api/v1/auth/ws-ticket` using their Bearer JWT.
   - The ticket expires in 60 seconds and is consumed immediately on the initial WebSocket handshake frame `{"type": "auth", "ticket": "..."}`. Query parameter tokens are completely disabled.
5. **Rate Limiting**:
   - Per-carrier sliding window: Maximum 30 quote submissions per second per supplier (`429 Too Many Requests`).
   - Per-client general rate limiter: 120 requests per minute on standard REST browsing routes.

---

### 6. API Route Catalog

All routes are mounted under the `/api/v1` namespace (with top-level `/health` aliases).

| Method | Endpoint | Access Role | Description | Response Codes |
|---|---|---|---|---|
| `GET` | `/health` / `/api/v1/health` | Public | Database connectivity & dialect health check | `200` |
| `POST` | `/api/v1/auth/register` | Public | Register new user account | `201`, `400` |
| `POST` | `/api/v1/auth/login` | Public | Authenticate and obtain JWT access token | `200`, `401` |
| `GET` | `/api/v1/auth/me` | Authenticated | Retrieve current user profile and supplier info | `200`, `401` |
| `POST` | `/api/v1/auth/ws-ticket` | Authenticated | Generate single-use 60s WebSocket ticket | `200`, `401` |
| `GET` | `/api/v1/suppliers` | Buyer Only | List all registered freight suppliers | `200`, `403` |
| `GET` | `/api/v1/rfqs` | Authenticated | List RFQs (filtered to invited RFQs for suppliers) | `200` |
| `POST` | `/api/v1/rfqs` | Buyer Only | Create new RFQ with British auction configuration | `201`, `422` |
| `GET` | `/api/v1/rfqs/{id}` | Invited / Buyer | Get RFQ details (payload masked if MASKED mode) | `200`, `403`, `404` |
| `PATCH` | `/api/v1/rfqs/{id}` | Buyer Only | Update draft RFQ (rejected in ACTIVE/CLOSED) | `200`, `400`, `404` |
| `POST` | `/api/v1/rfqs/{id}/invitations` | Buyer Only | Invite supplier to RFQ | `201`, `400`, `404` |
| `DELETE` | `/api/v1/rfqs/{id}/invitations/{s_id}` | Buyer Only | Revoke supplier invitation | `204`, `400`, `404` |
| `POST` | `/api/v1/rfqs/{id}/award` | Buyer Only | Award RFQ to winning supplier quote | `200`, `400`, `404` |
| `GET` | `/api/v1/rfqs/{id}/export-csv` | Buyer Only | Export RFC 4180 audit trail CSV of bids | `200`, `403`, `404` |
| `POST` | `/api/v1/rfqs/{id}/reseed-demo` | Public / Dev | Reset demo RFQ to active state with 30m window | `200` |
| `POST` | `/api/v1/rfqs/{id}/bids` | Invited Supplier | Submit quote (with Idempotency-Key support) | `200`, `201`, `400`, `403`, `422`, `429` |
| `GET` | `/api/v1/rfqs/{id}/bids` | Invited / Buyer | List bids for RFQ (masked for rival suppliers) | `200`, `403`, `404` |
| `GET` | `/api/v1/rfqs/{id}/events` | Invited / Buyer | List audit events for RFQ | `200`, `403`, `404` |
| `GET` | `/api/v1/analytics/command-center` | Buyer Only | Aggregated KPIs for buyer dashboard | `200`, `403` |
| `GET` | `/api/v1/analytics/supplier-portal`| Supplier Only | Performance KPIs for carrier portal | `200`, `403` |
| `WS` | `/ws/rfqs/{id}` | Authenticated | Real-time auction room event stream | `1000`, `4003` |

---

### 7. Deployment Architecture

#### 7.1 Docker Compose Deployment
The standard production stack is orchestrated via `docker-compose.yml`:
- **`db`**: PostgreSQL 16 container (`postgres:16-alpine`), internal port 5432, exposed on `${POSTGRES_PORT:-5432}:5432`. Data persisted in `postgres_data` volume. Healthcheck: `pg_isready -U meridian -d meridian_db`.
- **`backend`**: FastAPI application running on Uvicorn (`app.main:app`), internal port 8000, exposed on `8000:8000`. Depends on healthy `db`.
- **`frontend`**: React Vite SPA served via Nginx on port 80 (or development dev server on 5173). Reverse proxies `/api` and `/ws` to the backend container.

#### 7.2 Native Development & Makefile
- Native virtual environment: `.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload`
- Make targets:
  - `make dev`: Launches background backend and frontend Vite dev servers.
  - `make test-backend`: Executes Pytest suite against PostgreSQL test database.
  - `make test-frontend`: Executes Vitest client validation suite.
  - `make seed`: Seeds baseline buyers, suppliers, and sample RFQs.
  - `make demo`: Seeds authoritative live demonstration RFQs.
  - `make verify`: Executes comprehensive end-to-end verification (Pytest, Vitest, 20-parallel concurrent bids, tamper-proof trigger test).

---

### 8. Known Limitations & Architecture Decisions

1. **In-Process WebSocket Pub/Sub**:
   - `ConnectionManager` stores active WebSockets in an in-memory dictionary.
   - *Limitation*: For horizontal scaling across multiple backend worker nodes, a Redis Pub/Sub adapter would be required to synchronize broadcasts across instances.
2. **In-Memory Rate Limiting**:
   - Sliding-window rate limiters store timestamps in memory per process.
   - *Limitation*: Rate limits apply per Uvicorn worker process. In distributed multi-worker deployments, a Redis-backed sliding window counter is recommended.
3. **In-Process State Sweeper**:
   - An asynchronous background task runs every 5 seconds inside the FastAPI process to sweep expired auctions.
   - *Architecture Guarantee*: Lazy evaluation on every read and write request ensures that even if the background sweeper experiences jitter, bids submitted past `effective_close` are rejected with zero tolerance. In large-scale deployments, Celery Beat or `pg_cron` can be utilized.
4. **Transaction Isolation Level**:
   - MERIDIAN deliberately operates on PostgreSQL `READ COMMITTED` paired with explicit `SELECT ... FOR UPDATE` pessimistic locks. This avoids `SERIALIZABLE` retry transaction aborts while guaranteeing strict serial execution on a per-auction basis.
