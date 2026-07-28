FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY pyproject.toml requirements.lock ./
COPY alembic.ini ./
COPY alembic ./alembic
COPY app ./app
RUN pip install --upgrade pip \
    && pip install -r requirements.lock \
    && pip install --no-build-isolation --no-deps .

EXPOSE 3000

CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-3000}"]
