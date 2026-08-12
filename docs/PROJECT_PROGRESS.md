# NexOps — Project Progress

## Project name
**NexOps** — AI Kubernetes Incident Response & Self-Healing Platform

## Project goal
Build a production-style DevOps platform that monitors applications on Kubernetes, detects problems, uses AI to diagnose them, suggests safe fixes, requires human approval, applies approved remediations, and verifies recovery.

## Architecture summary
Monitored application flow:

```
User → NexOps Store (frontend) → orders-api → payment-api
```

Later platform flow (not started yet):

```
Failure → Monitoring → Incident Detector → AI Analyzer
  → NexOps Control Center → Human approval → Remediation → Health verification
```

## Technology stack
| Area | Choice |
|------|--------|
| Frontend | React + TypeScript (Vite) |
| Backend | Python + FastAPI |
| Containers | Docker |
| Future | Kubernetes, Prometheus, Grafana, Loki, Terraform, AWS EKS, GitHub Actions, LLM API |

## Build stages

| Stage | Name | Status |
|-------|------|--------|
| 1 | Applications (frontend, orders-api, payment-api) | COMPLETED |
| 2 | Local Docker | NOT STARTED |
| 3 | Local Kubernetes | NOT STARTED |
| 4 | Failure Simulation | NOT STARTED |
| 5 | Monitoring | NOT STARTED |
| 6 | Incident Detector | NOT STARTED |
| 7 | AI Analyzer | NOT STARTED |
| 8 | NexOps Control Center | NOT STARTED |
| 9 | Remediation | NOT STARTED |
| 10 | Kubernetes Security | NOT STARTED |
| 11 | CI/CD | NOT STARTED |
| 12 | Infrastructure (Terraform) | NOT STARTED |
| 13 | AWS / EKS | NOT STARTED |
| 14 | Production Improvements | NOT STARTED |
| 15 | Final Demo | NOT STARTED |
| 16 | Reverse Engineering | NOT STARTED |

## Current stage
**Stage 1 — Applications (COMPLETED)**  
Next: Stage 2 — Local Docker (not started)

## Important decisions
- GitHub repository `nexops-ai-kubernetes-platform` is the permanent source of truth.
- Stage 1 services stay simple: no database, no Redis/Kafka.
- POC Docker builds may need an environment-specific proxy; that proxy is **not** part of NexOps production architecture and is not hardcoded into application code.
- Existing `payment-api` was reviewed and extended (typed `/pay` payload, tests, non-root Dockerfile) instead of rewritten.
- Frontend talks to `orders-api`; `orders-api` calls `payment-api` via `PAYMENT_API_URL`.

## Known issues
- Local Windows workstation does not have Git installed; Git commit/push is done from the POC environment which already has authenticated GitHub credentials.
- POC network access to GitHub/Docker Hub may require an environment-specific proxy at runtime (not committed to the repo).

## Last updated
2026-08-12
