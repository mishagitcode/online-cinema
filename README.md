# Online Cinema

Backend service for an online cinema platform built with FastAPI, Poetry, Celery, PostgreSQL,
Redis, MinIO, Docker Compose, and Stripe-compatible payments.

## Quick start

1. Copy `.env.example` to `.env`.
2. Run `docker compose up --build`.
3. Open `http://localhost:8000/api/v1/health`.

## Tooling

- Install locally with `python -m poetry install`.
- Run the API with `python -m poetry run uvicorn online_cinema.main:app --reload`.
- Run tests with coverage via `python -m poetry run pytest`.
- Run lint/type checks via `python -m poetry run ruff check .` and `python -m poetry run mypy src`.

## Documentation

- Swagger UI is available at `/docs`.
- ReDoc is available at `/redoc`.
- Both documentation routes and `/openapi.json` are protected with HTTP Basic credentials from
  `DOCS_USERNAME` and `DOCS_PASSWORD`.
- Additional endpoint notes live in [docs/custom-endpoints.md](docs/custom-endpoints.md).

## Payment Modes

- `PAYMENT_PROVIDER=fake`: payments complete immediately and are suitable for local development and tests.
- `PAYMENT_PROVIDER=stripe`: creates Stripe Checkout sessions and finalizes orders from the webhook endpoint.

## Task Branches

- `task/bootstrap-infra`
- `task/auth-accounts`
- `task/movies-catalog`
- `task/cart-orders-payments`
- `task/docs-polish`
