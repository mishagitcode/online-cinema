FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    POETRY_VERSION=1.8.4

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential curl libpq-dev \
    && pip install --no-cache-dir "poetry==$POETRY_VERSION" \
    && poetry config virtualenvs.create false \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md /app/
RUN poetry install --no-interaction --no-ansi --without dev

COPY src /app/src
COPY tests /app/tests

CMD ["uvicorn", "online_cinema.main:app", "--host", "0.0.0.0", "--port", "8000"]

