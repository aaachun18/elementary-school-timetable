# Build context MUST be the repo root (see docker-compose.yml): the backend
# imports the sibling scheduling_engine/ package via a sys.path bootstrap
# (backend/app/services/scheduler.py), and alembic.ini lives at the root.
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# /app mirrors the repo root layout: /app/alembic.ini, /app/backend/,
# /app/scheduling_engine/.
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY alembic.ini .
COPY backend/ backend/
COPY scheduling_engine/ scheduling_engine/

EXPOSE 8000

# alembic must run from the repo root (alembic.ini's script_location is
# relative to it); uvicorn must run from backend/ (app.main is relative to
# it) -- same two constraints as the local dev flow in README.
CMD ["sh", "-c", "alembic upgrade head && cd backend && exec python -m uvicorn app.main:app --host 0.0.0.0 --port 8000"]
