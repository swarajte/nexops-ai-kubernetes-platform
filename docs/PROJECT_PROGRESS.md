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

Stage 4 adds **controlled failure injection on payment-api** so we can create real Kubernetes symptoms without touching other apps.

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
| Containers | Docker + Docker Compose |
| Orchestration | Kubernetes + Helm |
| Future | Prometheus, Grafana, Loki, Terraform, AWS EKS, GitHub Actions, LLM API |

## Build stages

| Stage | Name | Status |
|-------|------|--------|
| 1 | Applications (frontend, orders-api, payment-api) | COMPLETED |
| 2 | Local Docker | COMPLETED |
| 3 | Kubernetes + Helm | COMPLETED |
| 4 | Failure Simulation | COMPLETED |
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
**Stage 4 — Failure Simulation (COMPLETED)**  
Next: Stage 5 — Monitoring (not started)

## Important decisions
- GitHub repository `nexops-ai-kubernetes-platform` is the permanent source of truth.
- Failures are **intentional and reversible** (Helm overlays under `helm/nexops/failures/` plus HTTP `/fail/*` on payment-api).
- First failure is **OOMKilled** on payment-api (matches the project brief).
- Liveness = `/health`, readiness = `/ready` so a pod can be unready without being restarted.
- ImagePullBackOff is a **bad image tag**, not application code.
- CrashLoopBackOff is `FAILURE_MODE=crash` (`os._exit(1)` at startup).
- Live cluster stays on Helm in namespace `nexops`. Raw YAML in `k8s/` is updated to match probes but is not the live install.
- Commands for interviews: `docs/COMMANDS.md`.
- Helm 4 keeps last `-f` overlay on upgrade unless you pass `--reset-values`.

## Known issues
- Local Windows workstation does not have Git; push is from POC.
- Images are local to the POC node (`nexops/payment-api:v2` after Stage 4).
- After a failure demo, always `helm upgrade ... --reset-values` so overlays do not stick (Helm 4).

## Last updated
2026-08-22
