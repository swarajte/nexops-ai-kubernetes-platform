# NexOps

**NexOps — AI Kubernetes Incident Response & Self-Healing Platform**

## Current status
Stage 2 — Local Docker completed.

## Application flow
```
NexOps Store (frontend)
        ↓
    orders-api
        ↓
    payment-api
```

| Service | Path | Host port |
|---------|------|-----------|
| frontend | `frontend/` | 3000 |
| orders-api | `orders-api/` | 8001 |
| payment-api | `payment-api/` | 8000 |

## Run with Docker Compose (recommended)
```bash
docker compose up --build -d
```

Open http://localhost:3000 and click **Buy now**.

Useful commands:
```bash
docker compose ps
docker compose logs -f
docker compose down
```

## Local run without Docker
```bash
# terminal 1
cd payment-api
pip install -r requirements-dev.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000

# terminal 2
cd orders-api
pip install -r requirements-dev.txt
set PAYMENT_API_URL=http://localhost:8000   # PowerShell: $env:PAYMENT_API_URL=...
uvicorn app.main:app --host 0.0.0.0 --port 8001

# terminal 3
cd frontend
npm install
npm run dev
```

Open http://localhost:5173

## Tests
```bash
cd payment-api && pytest
cd orders-api && pytest
cd frontend && npm test
```

## Notes
- No secrets, proxy URLs, or corporate credentials belong in this repository.
- POC environments may need an external proxy for Docker image builds; that is environment-specific only.
