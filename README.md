# MERIDIAN — British Auction RFQ Procurement Exchange

[![MERIDIAN CI Verification Suite](https://github.com/Venkateswar8703/British-Auction-in-RFQ-System/actions/workflows/ci.yml/badge.svg)](https://github.com/Venkateswar8703/British-Auction-in-RFQ-System/actions/workflows/ci.yml)

> **Industrial-grade British Auction RFQ procurement system for ocean and air freight logistics.**
> Built with strict server-side state enforcement, ACID row-level concurrency locking, real-time WebSocket state broadcasting with sub-second drift compensation, and a high-density financial terminal aesthetic.

---

## Table of Contents
1. [Overview & British Auction Mechanics](#overview--british-auction-mechanics)
2. [Deliverables Checklist](#deliverables-checklist)
3. [Architecture & System Design](#architecture--system-design)
4. [One-Command Quick Start](#one-command-quick-start)
5. [Demo User Credentials & Fast Persona Switcher](#demo-user-credentials--fast-persona-switcher)
6. [Interactive Walkthrough Script](#interactive-walkthrough-script)
7. [Authoritative Auction Engine Rules](#authoritative-auction-engine-rules)
8. [Testing & Quality Assurance](#testing--quality-assurance)
9. [Tech Stack](#tech-stack)

---

## Overview & British Auction Mechanics

In global freight procurement, standard static sealed bids or fixed-deadline reverse auctions suffer from **bid sniping** (suppliers holding competitive rates until the final seconds to deny competitors a chance to counter) or premature market clearing.

**MERIDIAN** implements the **British Auction** (Dynamic Soft-Close Extension) model:
- **Strict Downward Bidding**: Each supplier may submit multiple bids, but each successive bid must have a **strictly lower total price** than their own previous best quote.
- **Dynamic Extension ($Y$ minutes)**: If qualifying bidding activity occurs within a defined **Trigger Window ($X$ minutes)** before the deadline, the auction automatically extends.
- **Forced Close Hard Cap**: To preserve logistics scheduling and port cut-offs, the auction can never extend past `forced_close`. If an extension would exceed this deadline, it is clamped to `forced_close`, and subsequent qualifying bids log an `EXTENSION_CAPPED` event without shifting the deadline.
- **Ties Broken by Timestamp**: If two carriers submit the exact same price, the carrier who submitted first holds the superior rank.
- **Server-Authoritative**: The frontend client never decides auction timing, ranking, or validity. A periodic background daemon runs every 5 seconds, paired with lazy deadline checks on every read and write.

---

## Deliverables Checklist

| Deliverable | Location | Description |
| :--- | :--- | :--- |
| **High-Level Design (HLD)** | [`docs/HLD.md`](docs/HLD.md) | Architectural diagram (Mermaid), ACID transaction lifecycle, drift sync, RBAC matrix |
| **Database Schema & ERD** | [`docs/SCHEMA.md`](docs/SCHEMA.md) | Entity Relationship Diagram (Mermaid), 8 relational tables, CHECK constraints, composite indexes |
| **Alembic Migrations** | `backend/alembic/versions/` | Production-ready SQL schema migrations |
| **Backend Engine & APIs** | `backend/app/` | FastAPI, SQLAlchemy 2.x, Pydantic v2, WebSockets, background daemon |
| **Frontend Application** | `frontend/` | React 18, TypeScript, Tailwind CSS, Framer Motion, IBM Plex Mono typography |
| **Automated Test Suites** | `backend/tests/` & `frontend/src/tests/` | 21 backend pytest tests (93% engine coverage) + 21 frontend Vitest tests (All Passing) |
| **Live Verification Suite** | `scripts/verify_live_scenarios.py` | 10 authoritative live API scenarios verified against running server |
| **Docker Infrastructure** | `docker-compose.yml`, `Dockerfile.*` | Multi-container setup (PostgreSQL 16, FastAPI backend, Nginx frontend) |
| **Makefile Automation** | `Makefile` | One-command targets (`make dev`, `make test`, `make seed`, `make demo`, `make verify`) |
| **Reseed & Simulation Scripts** | `scripts/` | `reseed.py` (CLI database seeder) and `simulate_bidders.py` (live rival bidder) |

---

## Architecture & System Design

```mermaid
graph TD
    subgraph Clients["Frontend Clients (React 18 + TypeScript)"]
        BuyerClient["Buyer Command Center & Live Room"]
        CarrierA["Carrier: Maersk Line"]
        CarrierB["Carrier: Hapag-Lloyd"]
    end

    subgraph Edge["Reverse Proxy & Gateway"]
        Nginx["Nginx (Port 80 / 5173)"]
    end

    subgraph Backend["FastAPI Backend (Port 8000)"]
        AuthRouter["Auth & RBAC (JWT)"]
        RFQRouter["RFQ & Live Engine Router"]
        Engine["Authoritative Auction Engine"]
        WSManager["WebSocket Connection Manager"]
        BackgroundSweeper["Background Status Sweeper (Every 5s)"]
    end

    subgraph Storage["Persistence & Transactions"]
        DB[("PostgreSQL 16 / SQLite Fallback<br/>Row-Level Lock: SELECT FOR UPDATE")]
    end

    BuyerClient -->|"REST & WS"| Nginx
    CarrierA -->|"REST & WS"| Nginx
    CarrierB -->|"REST & WS"| Nginx
    Nginx -->|"/api/*"| RFQRouter
    Nginx -->|"/api/auth/*"| AuthRouter
    Nginx -->|"/ws/*"| WSManager

    RFQRouter -->|"Transaction"| Engine
    Engine -->|"Lock Auction Row"| DB
    BackgroundSweeper -->|"Status Check & Sweep"| DB
    Engine -->|"Broadcast Mutation"| WSManager
    WSManager -->|"Live Sync: Bids, Extensions, Ladder"| BuyerClient
    WSManager -->|"Live Sync: Bids, Extensions, Ladder"| CarrierA
    WSManager -->|"Live Sync: Bids, Extensions, Ladder"| CarrierB
```

<details>
<summary><b>View Static Architecture Diagram (PNG Fallback)</b></summary>

![MERIDIAN Architecture](docs/architecture.png)

</details>

For full sequence diagrams and transaction flows, see [`docs/HLD.md`](docs/HLD.md).

---

## One-Command Quick Start

> [!IMPORTANT]
> **Deployment Architecture**: The British Auction engine requires continuous bidirectional WebSockets and transactional row locking (`SELECT ... FOR UPDATE` on PostgreSQL 16). The authoritative full stack runs via Docker Compose (`docker compose up --build`) or local services. Static frontend hosts (such as Vercel) without persistent backend WebSockets and database connectivity are not suitable for the live auction engine.

### Option A: Makefile (Instant Local Development with PostgreSQL)
A complete `Makefile` is provided at the repository root for one-command operations. `make dev` uses PostgreSQL 16 by default:

```bash
# 1. Start PostgreSQL 16 container (or run local Postgres service on port 5432)
docker compose up -d db

# 2. Set DATABASE_URL in .env (if not already set)
cp .env.example .env
# DATABASE_URL=postgresql://meridian:meridian_secret@127.0.0.1:5432/meridian_db

# 3. Apply Alembic migrations and seed data
PYTHONPATH=backend .venv/bin/alembic -c backend/alembic.ini upgrade head
PYTHONPATH=backend .venv/bin/python3 scripts/reseed.py

# 4. Start local development stack (Backend on port 8000, Frontend on port 5173)
make dev

# 5. Verify connected database via health check
curl http://localhost:8000/health
# Returns: {"status":"healthy","service":"MERIDIAN Auction Engine","database":"postgresql",...}
```

Additional make targets:
```bash
make test     # Runs full backend pytest (93% engine coverage) and frontend Vitest suites
make seed     # Reseeds database relative to now() with Scheduled, Active, Closed & Force Closed RFQs
make demo     # Resets the signature live demo auction into its trigger window
make verify   # Executes the 10 authoritative live API verification scenarios
make build    # Builds frontend production bundle and verifies TypeScript types
make docker-up # Boots full PostgreSQL 16 + FastAPI + Nginx stack in containers
make docker-down # Stops all Docker containers
```

---

### Option B: Full Stack Docker Compose (PostgreSQL 16 + Backend + Frontend)

Ensure Docker and Docker Compose are installed, then run:

```bash
docker compose up --build -d
```

- **Frontend**: [http://localhost:5173](http://localhost:5173) (or [http://localhost](http://localhost))
- **Backend Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Database**: PostgreSQL on port 5432
- **Health Check**: `curl http://localhost:8000/health` (`"database":"postgresql"`)

*(Migrations and seed data are automatically applied on container startup).*

---

### Option C: Local Development with SQLite Fallback (No PostgreSQL Needed)

MERIDIAN supports a zero-configuration local fallback mode using SQLite when PostgreSQL is unavailable.
> [!WARNING]
> Running with SQLite triggers an explicit warning on startup:
> ```
> ⚠️  [DATABASE WARNING] Running on SQLite fallback (sqlite:///./meridian.db).
> Row-level locking (SELECT ... FOR UPDATE) is NOT enforced by SQLite.
> For production-grade ACID concurrency and row-level locking, use PostgreSQL 16 via DATABASE_URL.
> ```
> SQLite serializes writes at the file level and does not support true row-level locking (`SELECT ... FOR UPDATE`). PostgreSQL 16 is the authoritative, production-supported database engine required for concurrent bidding.

To run with SQLite fallback:
```bash
export DATABASE_URL="sqlite:///./meridian.db"
PYTHONPATH=backend .venv/bin/alembic -c backend/alembic.ini upgrade head
PYTHONPATH=backend .venv/bin/python3 scripts/reseed.py
make dev
```

Open [http://localhost:5173](http://localhost:5173) in your browser.

---

## Demo User Credentials & Fast Persona Switcher

The application features a **One-Click Fast Persona Switcher** on the Login page and in the top navigation bar. You can switch between buyer and rival suppliers with a single click without typing passwords.

### Pre-Configured Personas

| Role | Organization | Email | Password | Details |
| :--- | :--- | :--- | :--- | :--- |
| **Buyer** | Meridian Global Logistics | `buyer@meridian.com` | `MeridianBuyer2026!` | VP Procurement (Full RFQ management, Command Center) |
| **Buyer** | Meridian Global Logistics | `alex.chen@meridian.com` | `MeridianBuyer2026!` | Procurement Lead (Read/Write access) |
| **Supplier** | A.P. Moller - Maersk | `bids@maersk.com` | `SupplierPass2026!` | Global Tier-1 Ocean Carrier |
| **Supplier** | Hapag-Lloyd Ocean | `quotes@hapag-lloyd.com` | `SupplierPass2026!` | Leading Container Carrier |
| **Supplier** | MSC Mediterranean Shipping | `rfq@msc.com` | `SupplierPass2026!` | Container Shipping Line |
| **Supplier** | CMA CGM Logistics | `ocean@cma-cgm.com` | `SupplierPass2026!` | Ocean Freight & Logistics |
| **Supplier** | Evergreen Marine Corp | `pricing@evergreen.com` | `SupplierPass2026!` | Global Liner Service |
| **Supplier** | COSCO Shipping | `commercial@cosco.com` | `SupplierPass2026!` | Global Shipping Operator |
| **Supplier** | ONE Ocean Network Express | `rates@one-line.com` | `SupplierPass2026!` | Container Carrier |
| **Supplier** | Kuehne+Nagel Intermodal | `freight@kuehne-nagel.com` | `SupplierPass2026!` | Freight Forwarder |

---

## Application Screens & Portals

MERIDIAN delivers an enterprise editorial procurement product with dedicated interfaces for both buyers and suppliers:

1. **Buyer Command Center** (`/dashboard` or `/`):
   - Aggregated KPIs: total RFQs, active, scheduled, closed, and forced-closed counts.
   - Live price yield & performance charts tracking savings across concluded freight corridors.
   - Active auctions radar showing real-time countdown badges and quick-access control links.
2. **Auction Listing Console** (`/auctions`):
   - Full tabular view of all RFQs with status filters, search by title/port/carrier, and route UN/LOCODEs (`SGSIN → AUMEL`).
   - Live closing countdowns, sticky headers, and action buttons for viewing or managing auctions.
3. **Create & Edit RFQ Console** (`/auctions/new`, `/auctions/:rfqId/edit`):
   - Definition of origin, destination, pickup dates, and strictly validated timelines (`bid_start < bid_close < forced_close < pickup`).
   - Dynamic extension configuration: trigger window ($X$), extension duration ($Y$), trigger event type (`BID_RECEIVED`, `ANY_RANK_CHANGE`, `L1_CHANGE`).
   - Bid visibility selector: **`OPEN`** (transparent ladder) vs **`MASKED`** (blind bidding, rival quotes redacted).
   - Supplier invitation whitelist manager (locked once auction is active).
4. **Live Auction Control Room** (`/auctions/:rfqId`):
   - Signature 3-zone layout:
     - **Zone 1 (Left)**: Shipment specifications, container details, pickup dates, and submitted quote overview.
     - **Zone 2 (Center)**: Dark focal instrument panels featuring millisecond-synchronized live countdown hero, current L1 lowest bid, effective and forced close timestamps, and real-time bid submission console with preset underbid shortcuts.
     - **Zone 3 (Right)**: Live rank ladder (L1 → Ln) with rank-shift animations, masked rival handling, and chronological activity feed.
5. **Supplier Portal** (`/supplier`):
   - Dedicated dashboard for carrier commercial representatives.
   - Live participation metrics: invited auctions count, active bids placed, leading contracts (L1), and RFQ deadlines.
   - Direct bid submission actions and status tracking for invited routes.
6. **Auction Details & History / Audit Console** (`/auctions/:rfqId/details`):
   - Comprehensive chronological audit log and post-auction inspection console.
   - Interactive replay scrubber and historical event timeline (`BID_SUBMITTED`, `RANK_CHANGED`, `L1_CHANGED`, `EXTENSION_APPLIED`, `EXTENSION_CAPPED`, `AUCTION_CLOSED`).
   - Detailed quote breakdowns, participant bidding logs, tamper-proof event integrity badges, and authoritative CSV export.

---

## Interactive Walkthrough Script

Follow these steps to demonstrate every requirement and dynamic mechanic of the British Auction:

### Scenario 1: The Live British Auction Soft-Close & Extension (Signature Flow)
1. **Reset the Demo State**:
   - Run `python scripts/reseed.py --live-demo-only` (or click **"Reseed Live Demo RFQ"** in the Live Room).
   - This sets up RFQ **`RFQ-2026-LIVE-DEMO`** (Transpacific Shanghai → Long Beach) with:
     - `bid_close` = Current time + 2 minutes 30 seconds
     - `trigger_window_minutes` ($X$) = 5 minutes (meaning the auction is *already inside the trigger window*)
     - `extension_minutes` ($Y$) = 3 minutes
     - `forced_close` = Current time + 15 minutes
2. **Open the Live Auction Room**:
   - Log in as **Maersk Line** (click Maersk in the persona switcher).
   - In the Supplier Portal or navigation, open `RFQ-2026-LIVE-DEMO`.
   - Observe the **Live Millisecond Countdown**, the active **Rank Ladder**, and the **Live Activity Feed**.
3. **Submit a Competitive Underbid**:
   - In the Bid Submission panel, click the preset **`-$50 Underbid`** button.
   - Click **`Submit Authoritative Bid`**.
4. **Observe Real-Time Dynamic Extension**:
   - A burnt-orange notification banner instantly animates into the center console:
     > *"TRIGGER EXTENSION APPLIED: Dynamic extension (+3m) triggered inside 5m window. New close: [HH:MM:SS]."*
   - The countdown timer **adds exactly 3 minutes in real time** without refreshing the page!
   - In the right-hand panel, **Maersk immediately takes Rank L1**, and the activity feed broadcasts the new bid and extension to all connected users.

### Scenario 2: Multi-Bidder Concurrency Simulation
1. Keep the Live Auction Room open in your browser.
2. In your terminal, run the automated bidder simulation:
   ```bash
   python scripts/simulate_bidders.py
   ```
3. Watch the Live Room as rival carriers (Hapag-Lloyd, MSC, CMA CGM) place bids at 3-second intervals:
   - Rank L1 continuously shifts between carriers.
   - The auction extends further, approaching `forced_close`.
   - The chronological timeline logs every extension reason.

### Scenario 3: British Auction Rejection Rules
1. Try submitting a bid that is higher or equal to your own previous quote:
   - The client warns: *"Bid total must be strictly lower than your previous quote"*.
   - If forced past the client, the server returns an **HTTP 400 `BID_NOT_LOWER`** error.
2. Try submitting zero or negative amounts:
   - The server validates all line items with **HTTP 422 `VALIDATION_ERROR`** (`Field greater than 0 required`).
3. An uninvited carrier attempting to view or bid on the RFQ receives **HTTP 403 `SUPPLIER_NOT_INVITED`**.
4. Bids submitted with a validity date before pickup receive **HTTP 400 `INVALID_VALIDITY_DATE`**.

### Scenario 4: Forced Close Clamping
1. Let the auction receive bids until the effective close reaches the `forced_close` boundary.
2. When a qualifying bid arrives inside the trigger window:
   - `new_close = min(effective_close + Y, forced_close)`
   - The engine caps the extension at `forced_close`.
   - An `EXTENSION_CAPPED` event is emitted: *"Dynamic extension capped by forced close limit"*.
   - No further time extensions are granted. Once the forced close passes, the status becomes `FORCE_CLOSED`.

### Scenario 5: Buyer Command Center & Analytics
1. Switch personas to **Buyer (Meridian Admin)**.
2. Navigate to **Command Center**:
   - View aggregate metrics: Total RFQs (14), Active (4), Closed (4), Force-Closed (3), Scheduled (3).
   - View the **Procurement Yield & Performance Chart**: Average price reduction from first quote to L1 across all finished auctions.
   - Inspect **Active Auctions Radar** with live countdown badges.
3. Click on any completed RFQ to view the **Audit Timeline**:
   - Complete chronological audit log with distinct markers for `BID_SUBMITTED`, `EXTENSION_APPLIED`, `RANK_CHANGED`, and `AUCTION_CLOSED`.

---

## Authoritative Auction Engine Rules

The engine in `backend/app/services/auction_engine.py` implements the exact mathematical specification:

```python
# Effective close moves dynamically:
effective_close = rfq.effective_close

# Inside trigger window check:
is_in_window = (effective_close - timedelta(minutes=X)) <= bid_time < effective_close

# Qualifying event evaluation:
if trigger_type == TriggerType.BID_RECEIVED:
    qualifies = is_in_window
elif trigger_type == TriggerType.ANY_RANK_CHANGE:
    qualifies = is_in_window and any_existing_supplier_rank_changed
elif trigger_type == TriggerType.L1_CHANGE:
    qualifies = is_in_window and (new_l1_supplier_id != old_l1_supplier_id)

# Dynamic extension calculation (strictly bounded by forced_close):
if qualifies:
    new_close = min(effective_close + timedelta(minutes=Y), rfq.forced_close)
```

### Concurrency & Data Integrity
- Every bid submission is executed in an isolated database transaction with row-level locking (`SELECT ... FOR UPDATE` on PostgreSQL; transactional mutex on SQLite).
- `Idempotency-Key` headers are verified against past bids; duplicate submissions immediately return the original transaction without re-evaluating or extending.
- WebSockets broadcast events **only after the database commit succeeds**.

---

## Value-Add Improvements Implemented

1. **Interactive Scrubbable Historical Auction Replay (`AuctionDetails.tsx`)**:
   - Buyers and carriers can scrub an interactive chronological timeline slider to inspect past ladder positions, bid values, and lead changes at any discrete timestamp in the auction's history.
2. **Post-Auction Official Award Workflow (`POST /api/v1/rfqs/{id}/award`)**:
   - Buyers can officially award the concluded freight contract to the winning carrier (defaulting to L1 lowest bidder) with contractual comments, logging an immutable `AWARD_CONFIRMED` event and broadcasting across WebSockets.
3. **Streaming CSV Audit Log Export (`GET /api/v1/rfqs/{id}/export-csv`)**:
   - One-click export of complete chronological bids with carrier names, rate breakdowns (freight, origin, destination, total), transit days, validity dates, and UTC timestamps.
4. **Pre-Bid Confirmation Guardrail Modal (`BidSubmissionPanel.tsx`)**:
   - High-contrast guardrail modal displaying complete rate breakdown, reduction delta vs supplier's prior quote, projected ladder rank impact, and a checkbox to remember confirmation preference.
5. **In-App Live Notification Center (`Navbar.tsx`)**:
   - Activity dropdown alerting participants in real time when auctions extend, when L1 leadership changes hands, or when contracts are awarded.

---

## Testing & Quality Assurance

Both the backend and frontend have comprehensive automated test suites:

### Backend pytest Suite (21 Tests — 93% Engine Coverage)
Run from root:
```bash
.venv/bin/pytest backend/tests/ -v
```
- `test_auth_and_profile_flow`: JWT issuance, profile retrieval, buyer & supplier RBAC.
- `test_rfq_creation_and_role_access`: Timing validation (`forced_close > bid_close > bid_start`), carrier access restrictions.
- `test_endpoints_rfq_patch_invitations_and_suppliers`: `PATCH/PUT /rfqs/{id}` (locked once started), `POST/DELETE /rfqs/{id}/invitations`, `GET /suppliers`.
- `test_bid_visibility_masked_payloads`: Redaction of rival supplier names and quotes in `MASKED` mode; unmasked for buyers.
- `test_ws_ticket_and_first_message_auth`: Short-lived tickets (`POST /api/v1/auth/ws-ticket`, 60s) and first-message WebSocket auth.
- `test_rate_limiting_returns_429`: Sliding window rate limiter returning HTTP 429 `RATE_LIMIT_EXCEEDED` on rapid bursts.
- `test_cors_headers_and_jwt_expiry`: CORS allow-origin response and 401 on expired tokens.
- `test_example_scenario_close_extension`: The PDF benchmark scenario (6:00 PM close, X=10, Y=5, 6:30 PM forced close, bid at 5:55 -> 6:05 PM, bid at 6:03 -> 6:08 PM).
- `test_trigger_type_l1_change`: Verifies that non-L1 bids do not extend when trigger is `L1_CHANGE`.
- `test_trigger_type_any_rank_change`: Verifies rank change criteria (bottom entrants do not trigger; swapping L2/L3 triggers).
- `test_first_bid_on_any_rank_change_does_not_extend`: Verifies first bid on auction does not trigger `ANY_RANK_CHANGE` extension.
- `test_extension_clamped_and_capped`: Clamping to `forced_close` and emission of `EXTENSION_CAPPED`.
- `test_bid_validation_rejections`: Tests `BID_NOT_LOWER`, negative charges, zero ancillaries, past deadlines, and uninvited carriers.
- `test_ranking_and_tie_breaking`: Ties broken by earlier timestamp.
- `test_idempotency_key_replay`: Deduplication via `Idempotency-Key`.
- `test_status_transitions`: Transitions to `CLOSED` vs `FORCE_CLOSED`.
- `test_schema_forced_close_validation`: Database CHECK constraints prevent invalid auction durations.
- `test_concurrent_bids_consistency`: Concurrent threads firing simultaneous bids to verify zero lost updates.
- `test_row_lock_with_for_update_proof`: Proof of `with_for_update()` row-level pessimistic locking.
- `test_configurable_min_decrement_enforcement`: Rejection of bids failing to meet `min_decrement`.
- `test_auction_events_tamper_proof_trigger`: Trigger blocking UPDATE/DELETE on `auction_events`.

### Frontend Vitest Suite (21 Tests)
Run from `frontend/`:
```bash
cd frontend && npm test
```
- `calculateBidTotal`: Precision summation of freight, origin, and destination charges.
- `validateBidSubmission`: Strict downward price verification against supplier's previous quote, allowing zero origin/destination ancillaries.
- `isInsideTriggerWindow`: Boundary testing for $[effective\_close - X, effective\_close)$.
- `calculateClockDrift` & `formatTimeRemaining`: Millisecond countdown formatting, urgency flags (<5m), and network drift compensation using $\text{offset} = t_{\text{server}} + \frac{RTT}{2} - t_{\text{client\_receive}}$ (verified with simulated 200ms RTT).
- `rankBids`: L1 ascending sort, latest quote filtering, and timestamp tie-breaking.
- `extractLocode` & `formatDateDisplay`: UN/LOCODE parsing and UTC formatting.

---

## Tech Stack

| Layer | Technology | Rationale |
| :--- | :--- | :--- |
| **Backend Framework** | FastAPI (Python 3.12+) | High performance asynchronous REST & native WebSocket support |
| **ORM & Database** | SQLAlchemy 2.x + Alembic | Declarative data modeling, ACID transactions, migrations |
| **Databases** | PostgreSQL 16 (Prod & Concurrency) / SQLite (Dev) | PostgreSQL enforces true row-level locks (`SELECT ... FOR UPDATE`); SQLite serializes at file level |
| **Security & Auth** | JWT (`python-jose`) + `bcrypt` | Role-based access control (`buyer`, `supplier`) |
| **Real-Time** | Starlette WebSockets | Real-time state synchronization across buyers and carriers (measured localhost: avg 54.17ms, min 29.43ms, max 85.72ms, sample size 5) |
| **Frontend Framework** | React 18 + TypeScript + Vite | Rapid client-rendered UI with strong typing |
| **Styling & Design** | Tailwind CSS | MERIDIAN industrial palette (`#171A19`, `#C5F36B`, `#E4774D`) |
| **Typography** | Space Grotesk, Inter, IBM Plex Mono | Financial terminal density with tabular figures |
| **Animations** | Framer Motion | Smooth ladder rank transitions, extension alerts |
| **Icons** | Lucide React | Crisp, low-weight iconography |

