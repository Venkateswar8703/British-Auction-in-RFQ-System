.PHONY: help dev test test-backend test-frontend seed demo verify build docker-up docker-down

help:
	@echo "MERIDIAN British Auction RFQ Procurement Exchange"
	@echo "------------------------------------------------"
	@echo "make dev           - Start full-stack local development services"
	@echo "make test          - Run full backend & frontend test suites"
	@echo "make test-backend  - Run backend pytest suite with engine coverage"
	@echo "make test-frontend - Run frontend Vitest suite"
	@echo "make seed          - Reseed full database with Scheduled, Active & Closed auctions"
	@echo "make demo          - Reset live demo auction into its trigger window"
	@echo "make verify        - Run authoritative 10-scenario live API verification"
	@echo "make build         - Build frontend production distribution and check types"
	@echo "make docker-up     - Start PostgreSQL 16, backend, and frontend via Docker Compose"
	@echo "make docker-down   - Stop all Docker containers"

dev:
	@echo "Starting MERIDIAN backend (port 8000) and frontend (port 5173)..."
	@(PYTHONPATH=backend DATABASE_URL="$${DATABASE_URL:-postgresql://meridian:meridian_secret@127.0.0.1:5432/meridian_db}" .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload & cd frontend && npm run dev)

test: test-backend test-frontend

test-backend:
	PYTHONPATH=backend DATABASE_URL="$${DATABASE_URL:-postgresql://meridian:meridian_secret@127.0.0.1:5432/meridian_test_db}" .venv/bin/pytest --cov=app.services.auction_engine --cov-report=term-missing backend/tests

test-frontend:
	cd frontend && npm test

seed:
	PYTHONPATH=backend .venv/bin/python3 scripts/reseed.py

demo:
	PYTHONPATH=backend .venv/bin/python3 scripts/reseed.py --live-demo-only

verify:
	PYTHONPATH=backend .venv/bin/python3 scripts/verify_live_scenarios.py

build:
	cd frontend && npm run build

docker-up:
	docker compose up -d --build

docker-down:
	docker compose down -v

