.PHONY: dev backend frontend test lint up down

up:
	docker compose up --build

down:
	docker compose down

backend:
	cd backend && uvicorn app.main:app --reload

frontend:
	cd frontend && npm run dev

test:
	cd backend && pytest && cd ../frontend && npm test

lint:
	cd backend && ruff check . && cd ../frontend && npm run lint && npm run build

