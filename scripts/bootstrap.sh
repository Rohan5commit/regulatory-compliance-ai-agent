#!/usr/bin/env bash
set -euo pipefail

echo "[1/5] Starting infrastructure services"
docker-compose up -d postgres neo4j qdrant redis

echo "[2/5] Waiting for services"
sleep 10

echo "[3/5] Initializing graph + SQL schemas"
python scripts/init_neo4j.py
python -c "from src.models.database import Base, engine; Base.metadata.create_all(bind=engine)"

echo "[4/5] Seeding starter data"
python scripts/seed_data.py

echo "[5/5] Starting app + workers"
docker-compose up -d app celery_worker celery_beat

echo "Done. API docs: http://localhost:8000/docs"
