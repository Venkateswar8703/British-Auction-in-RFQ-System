# Task 8: Continuous Integration (CI) Verification & Evidence

**Executed**: 2026-11-18 15:53:00 IST  
**Environment**: GitHub Actions CI workflow, local Linux execution parity

---

## 1. CI Workflow Configuration (`.github/workflows/ci.yml`)

The CI workflow is configured to automatically test pull requests and pushes across both tiers:
- **Backend Job**: Spins up a containerized `postgres:16-alpine` service, executes Alembic migrations on an empty database, and runs Pytest with coverage reporting.
- **Frontend Job**: Sets up Node.js 20, verifies Vitest client auction engine test suite, and confirms TypeScript typecheck and production bundle build.

```yaml
name: MERIDIAN CI Verification Suite

on:
  push:
    branches: [ master, main ]
  pull_request:
    branches: [ master, main ]

jobs:
  backend-verification:
    name: Backend Pytest & PostgreSQL Engine
    runs-on: ubuntu-latest

    services:
      postgres:
        image: postgres:16-alpine
        env:
          POSTGRES_DB: meridian_test_db
          POSTGRES_USER: meridian
          POSTGRES_PASSWORD: meridian_secret
        ports:
          - 5432:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    steps:
      - name: Checkout Source Code
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: "pip"

      - name: Install Dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r backend/requirements.txt
          pip install pytest pytest-asyncio pytest-cov psycopg[binary]

      - name: Run Database Migrations
        env:
          DATABASE_URL: postgresql://meridian:meridian_secret@127.0.0.1:5432/meridian_test_db
        run: |
          cd backend
          alembic upgrade head

      - name: Execute Authoritative Pytest Suite & Coverage
        env:
          TESTING: "1"
          DATABASE_URL: postgresql://meridian:meridian_secret@127.0.0.1:5432/meridian_test_db
        run: |
          PYTHONPATH=backend pytest backend/tests -v --cov=backend/app --cov-report=term-missing

  frontend-verification:
    name: Frontend Vitest & Production Build
    runs-on: ubuntu-latest

    steps:
      - name: Checkout Source Code
        uses: actions/checkout@v4

      - name: Set up Node.js
        uses: actions/setup-node@v4
        with:
          node-version: 20
          cache: "npm"
          cache-dependency-path: frontend/package-lock.json

      - name: Install Frontend Dependencies
        run: |
          cd frontend
          npm ci

      - name: Run Frontend Vitest Unit Tests
        run: |
          cd frontend
          npm test -- --run

      - name: Verify TypeScript & Production Build
        run: |
          cd frontend
          npm run build
```

---

## 2. Local Execution Proofs

### A. Backend Pytest & PostgreSQL Coverage
Command: `PYTHONPATH=backend TESTING=1 DATABASE_URL="postgresql://meridian:meridian_secret@127.0.0.1:5432/meridian_test_db" .venv/bin/pytest backend/tests -v --cov=backend/app --cov-report=term-missing`

```text
============================= test session starts ==============================
platform linux -- Python 3.14.4, pytest-9.2.0, pluggy-1.7.0 -- /home/venkateswar_8703/Desktop/GoComet/.venv/bin/python3
cachedir: .pytest_cache
rootdir: /home/venkateswar_8703/Desktop/GoComet
plugins: asyncio-1.5.0, cov-7.1.0, anyio-4.16.0
asyncio: mode=Mode.STRICT, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
collecting ... collected 13 items                                                             

backend/tests/test_api.py::test_auth_and_profile_flow PASSED             [  7%]
backend/tests/test_api.py::test_rfq_creation_and_role_access PASSED      [ 15%]
backend/tests/test_auction_engine.py::test_example_scenario_close_extension PASSED [ 23%]
backend/tests/test_auction_engine.py::test_trigger_type_l1_change PASSED [ 30%]
backend/tests/test_auction_engine.py::test_trigger_type_any_rank_change PASSED [ 38%]
backend/tests/test_auction_engine.py::test_extension_clamped_and_capped PASSED [ 46%]
backend/tests/test_auction_engine.py::test_bid_validation_rejections PASSED [ 53%]
backend/tests/test_auction_engine.py::test_ranking_and_tie_breaking PASSED [ 61%]
backend/tests/test_auction_engine.py::test_idempotency_key_replay PASSED [ 69%]
backend/tests/test_auction_engine.py::test_status_transitions PASSED     [ 76%]
backend/tests/test_concurrency.py::test_schema_forced_close_validation PASSED [ 84%]
backend/tests/test_concurrency.py::test_concurrent_bids_consistency PASSED [ 92%]
backend/tests/test_concurrency.py::test_row_lock_with_for_update_proof PASSED [100%]

================================ tests coverage ================================
Name                                        Stmts   Miss  Cover   Missing
-------------------------------------------------------------------------
backend/app/config.py                          12      0   100%
backend/app/database.py                        26     11    58%   10-16, 30-34, 42-46
backend/app/main.py                            81     21    74%   27-32, 42-43, 57, 87-89, 117-119, 133-137, 150
backend/app/models/__init__.py                  3      0   100%
backend/app/models/entities.py                141      2    99%   31, 38
backend/app/models/enums.py                    26      0   100%
backend/app/routers/analytics.py               80     64    20%   30-119, 144-218
backend/app/routers/auth.py                    33      3    91%   19, 39, 45
backend/app/routers/bids.py                    62     20    68%   28, 74, 109, 137-165
backend/app/routers/rfqs.py                   224    141    37%   59, 71-92, 114-149, 162, 235-299, 314-383, 392-405, 420-464, 488-538, 558-591
backend/app/routers/suppliers.py               12      2    83%   18-19
backend/app/routers/ws.py                      62     47    24%   26-110
backend/app/schemas/__init__.py                 7      0   100%
backend/app/schemas/bid.py                     22      0   100%
backend/app/schemas/common.py                   8      0   100%
backend/app/schemas/event.py                    8      0   100%
backend/app/schemas/rfq.py                     66      1    98%   67
backend/app/schemas/supplier.py                12      0   100%
backend/app/schemas/user.py                    16      0   100%
backend/app/services/auction_engine.py        177     14    92%   69, 106-121, 214, 229, 277-284, 300, 304
backend/app/services/auth.py                   30      5    83%   20-21, 27, 39-40
backend/app/services/background.py             35     17    51%   25-57, 62-64
backend/app/services/deps.py                   44     16    64%   18-27, 40, 43, 46, 49, 64, 69
backend/app/services/exceptions.py             35      3    91%   25, 30, 55
backend/app/services/websocket_manager.py      57     36    37%   11-13, 22-30, 41-45, 48-51, 55-76, 83-86
-------------------------------------------------------------------------
TOTAL                                        1279    403    68%
======================== 13 passed, 1 warning in 38.43s ========================
```

### B. Frontend Vitest Client Logic Tests
Command: `cd frontend && npm test -- --run`

```text
 RUN  v1.6.1 /home/venkateswar_8703/Desktop/GoComet/frontend

 ✓ src/tests/auction.test.ts (19)
   ✓ MERIDIAN Client Auction Logic (19)
     ✓ calculateBidTotal (2)
     ✓ validateBidSubmission (5)
     ✓ isInsideTriggerWindow (3)
     ✓ calculateClockDrift and formatTimeRemaining (4)
     ✓ rankBids (3)
     ✓ extractLocode and formatDateDisplay (2)

 Test Files  1 passed (1)
      Tests  19 passed (19)
   Start at  15:47:06
   Duration  1.49s
```

### C. Frontend Production Build
Command: `cd frontend && npm run build`

```text
> meridian-frontend@1.0.0 build
> tsc && vite build

vite v5.4.21 building for production...
✓ 2181 modules transformed.
dist/index.html                   1.16 kB │ gzip:   0.62 kB
dist/assets/index-DyIHj-W0.css   29.90 kB │ gzip:   6.15 kB
dist/assets/index-BwjVd06h.js   454.11 kB │ gzip: 129.62 kB
✓ built in 6.66s
```

**Status**: PASS

