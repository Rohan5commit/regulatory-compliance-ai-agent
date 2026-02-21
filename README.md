# Regulatory Compliance AI Agent Framework

Autonomous AI system for monitoring financial regulations, extracting compliance obligations, mapping them to internal controls, and generating audit-ready outputs.

## What This Repository Includes

- Regulatory horizon scanning (SEC implemented, FINRA/MAS/FCA/ECB templates included)
- NLP obligation extraction with rule-based + model-assisted logic
- Policy mapping agent with NVIDIA NIM support (default), plus OpenAI/Anthropic and free heuristic fallback
- Hybrid retrieval foundation (vector store via Qdrant + graph via Neo4j)
- Compliance gap discovery and dashboard-friendly API
- Celery orchestration for recurring scanning/processing jobs

## Quick Start

### 1) Clone and Configure

```bash
git clone https://github.com/Rohan5commit/regulatory-compliance-ai-agent.git
cd regulatory-compliance-ai-agent
cp .env.example .env
```

You can leave API keys blank to run in free heuristic mode.

### 2) Start Infrastructure

```bash
docker-compose up -d postgres neo4j qdrant redis
```

### 3) Initialize Schemas

```bash
python scripts/init_neo4j.py
python -c "from src.models.database import Base, engine; Base.metadata.create_all(bind=engine)"
```

### 4) Seed Starter Data

```bash
python scripts/seed_data.py
```

### 5) Start Services

```bash
docker-compose up -d app celery_worker celery_beat
```

API docs: http://localhost:8000/docs

## API Keys (Optional)

- NVIDIA NIM (recommended free starting point): https://build.nvidia.com/
- OpenAI: https://platform.openai.com/api-keys
- Anthropic: https://console.anthropic.com/settings/keys

Default mapping provider is `nvidia_nim` with model `meta/llama-3.1-8b-instruct`.

## Mapping Provider Options

Set these in `.env`:

```bash
MAPPING_PROVIDER=nvidia_nim   # options: nvidia_nim | openai | anthropic
MAPPING_MODEL=meta/llama-3.1-8b-instruct
NIM_API_KEY=...
NIM_BASE_URL=https://integrate.api.nvidia.com/v1
```

If no API key is present for the selected provider, policy mapping automatically falls back to heuristic scoring.

## Core Endpoints

- `GET /health`
- `POST /api/v1/admin/trigger-scan`
- `POST /api/v1/admin/trigger-processing`
- `GET /api/v1/regulations`
- `GET /api/v1/obligations/unmapped`
- `POST /api/v1/search/regulations`
- `POST /api/v1/mapping/run`
- `GET /api/v1/dashboard/stats`

## Notes on Production Hardening

- Add immutable audit-log persistence policy (WORM storage or append-only event bus)
- Add human-review workflow before applying AI mapping decisions
- Add row-level tenancy + data masking for sensitive controls
- Add regulator-specific scraper parsers and quality scoring
- Add CI tests for scraper drift and model output regressions
