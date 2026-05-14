FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    POETRY_VERSION=1.8.4 \
    POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_CREATE=false

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir "poetry==${POETRY_VERSION}"

WORKDIR /app

COPY pyproject.toml poetry.lock* ./
RUN if [ ! -f poetry.lock ]; then poetry lock --no-update || poetry lock; fi \
 && poetry install --no-root --without dev

COPY . .

# Railway / Heroku-style PaaS provide $PORT; default to 8000 locally.
ENV PORT=8000
EXPOSE 8000

# Start command: run pending migrations, then boot Uvicorn.
# Use `sh -c` so $PORT is expanded at runtime, not at image build.
CMD sh -c "poetry run alembic upgrade head && poetry run uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"
