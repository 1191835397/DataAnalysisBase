.PHONY: dev-api dev-web test-backend lint-backend

dev-api:
	cd backend && uvicorn dataanalysisbase.api.main:app --reload --port 8000

dev-web:
	cd frontend && npm run dev

test-backend:
	cd backend && pytest

lint-backend:
	cd backend && ruff check . && ruff format --check . && mypy src
