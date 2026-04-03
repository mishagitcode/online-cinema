# Online Cinema API

---

## Contents

1. [Project Overview](#project-overview)
2. [Features](#features)
3. [Project Structure](#project-structure)
4. [API Endpoints](#api-endpoints)
5. [Run with Docker](#run-with-docker)
6. [Run Locally](#run-locally)
7. [Testing](#testing)
8. [Technologies](#technologies)

---

## Project Overview

Online Cinema API is a FastAPI backend for an online movie platform. It covers user account
lifecycle, movie catalogue management, shopping cart and ordering flows, payment processing,
notifications, and protected API documentation.

The project includes:

- JWT authentication with access and refresh tokens
- Account activation and password reset flows
- Movie catalogue search, filtering, sorting, favorites, ratings, and comments
- Cart, order, payment, refund, and purchased-library flows
- Celery and Celery Beat for background token cleanup
- Swagger, ReDoc, and OpenAPI schema protected with HTTP Basic auth
- Docker Compose support for local development

---

## Features

- User registration with activation email and resend activation flow
- Login, logout, token refresh, password change, and password reset endpoints
- Role-based access with `USER`, `MODERATOR`, and `ADMIN`
- Movie CRUD for moderators and admins
- Genre, star, director, and certification management
- Search, pagination, filtering, and sorting for movies and favorites
- Movie likes, dislikes, ratings, comments, replies, and notifications
- Shopping cart with duplicate and already-purchased validation
- Order creation from cart items with pending/paid/canceled statuses
- Payment flow with `fake` mode for local use and Stripe-ready webhook handling
- Admin visibility into users, carts, orders, and payments

---

## Project Structure

```text
online-cinema/
|-- .github/
|   `-- workflows/                 # CI and CD workflows
|-- docs/
|   `-- custom-endpoints.md        # Notes for custom business endpoints
|-- src/
|   `-- online_cinema/
|       |-- api/
|       |   |-- dependencies/      # Auth and role dependencies
|       |   |-- routes/            # Auth, users, movies, commerce, health routes
|       |   |-- docs.py            # Protected Swagger/ReDoc/OpenAPI endpoints
|       |   `-- router.py          # Main API router
|       |-- core/
|       |   |-- celery_app.py      # Celery and beat configuration
|       |   |-- config.py          # Environment settings
|       |   `-- security.py        # JWT, password hashing, password rules
|       |-- db/
|       |   |-- models/            # Auth, movies, and commerce models
|       |   |-- base.py            # SQLAlchemy declarative base
|       |   |-- init_db.py         # Initial seeding and bootstrap admin
|       |   `-- session.py         # Async DB engine and session
|       |-- schemas/               # Pydantic request and response schemas
|       |-- services/              # Business logic for auth, movies, commerce
|       |-- tasks/                 # Celery tasks
|       `-- main.py                # FastAPI app entrypoint
|-- tests/                         # Integration and API tests
|-- .env.example
|-- docker-compose.yml
|-- Dockerfile
|-- pyproject.toml
|-- poetry.lock
`-- README.md
```

---

## API Endpoints

Base URL: `http://127.0.0.1:8000/api/v1/`

Main route groups:

- `/auth/*`
- `/users/*`
- `/movies`
- `/favorites`
- `/genres`
- `/stars`
- `/directors`
- `/certifications`
- `/cart`
- `/orders`
- `/payments`
- `/purchased`
- `/admin/*`

Documentation routes:

- `/docs`
- `/redoc`
- `/openapi.json`

Example login request:

```http
POST /api/v1/auth/login
Content-Type: application/json

{
  "email": "admin@example.com",
  "password": "Admin123!"
}
```

Use the access token in authenticated requests:

```text
Authorization: Bearer <access_token>
```

Additional custom endpoint notes:

- [docs/custom-endpoints.md](docs/custom-endpoints.md)

---

## Run with Docker

### Prerequisites

- Docker Desktop
- Docker Compose

### Start the app

1. Clone the repository and move into the project directory:

```bash
git clone https://github.com/mishagitcode/online-cinema
cd online-cinema
```

2. Create the environment file:

```bash
cp .env.example .env
```

Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

3. Build and start all services:

```bash
docker compose up --build
```

The stack starts:

- FastAPI on port `8000`
- PostgreSQL on port `5432`
- Redis on port `6379`
- Mailpit on ports `1025` and `8025`
- MinIO on ports `9000` and `9001`

Open:

- `http://127.0.0.1:8000/api/v1/health`
- `http://127.0.0.1:8000/docs`
- `http://127.0.0.1:8025` for Mailpit
- `http://127.0.0.1:9001` for MinIO Console

Documentation credentials from the default `.env`:

- username: `admin`
- password: `admin`

### Optional Docker commands

Show container status:

```bash
docker compose ps
```

Show API logs:

```bash
docker compose logs api --tail=100
```

Stop the app:

```bash
docker compose down
```

---

## Run Locally

### Prerequisites

- Python 3.12+
- Poetry
- PostgreSQL
- Redis

### Setup

1. Clone the repository:

```bash
git clone https://github.com/mishagitcode/online-cinema
cd online-cinema
```

2. Install dependencies:

```bash
python -m poetry install
```

3. Create the environment file:

```bash
cp .env.example .env
```

Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

4. Adjust `.env` for local services:

- change `DATABASE_URL` from `db` host to your local PostgreSQL host
- change `REDIS_URL`, `CELERY_BROKER_URL`, and `CELERY_RESULT_BACKEND` if needed
- optionally keep `PAYMENT_PROVIDER=fake` for local development

5. Start the API:

```bash
python -m poetry run uvicorn online_cinema.main:app --reload
```

6. Optionally start Celery worker:

```bash
python -m poetry run celery -A online_cinema.core.celery_app.celery_app worker --loglevel=info
```

7. Optionally start Celery Beat:

```bash
python -m poetry run celery -A online_cinema.core.celery_app.celery_app beat --loglevel=info
```

---

## Testing

Run the full test suite:

```bash
python -m poetry run pytest
```

Run linting:

```bash
python -m poetry run ruff check .
```

Run type checks:

```bash
python -m poetry run mypy src
```

---

## Technologies

- Python 3.12
- FastAPI
- SQLAlchemy 2
- Pydantic Settings
- PostgreSQL
- Redis
- Celery and Celery Beat
- Poetry
- Pytest
- Ruff
- MyPy
- Docker and Docker Compose
- MinIO
- Mailpit
- Stripe SDK

---

Developed by [mishagitcode](https://github.com/mishagitcode)
