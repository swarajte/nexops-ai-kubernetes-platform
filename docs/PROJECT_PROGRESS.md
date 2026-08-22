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

Docker Compose (Stage 2) runs the same flow as three containers on one Docker network.

Stage 3 runs the same flow on Kubernetes in namespace `nexops`:
1. Raw YAML in `k8s/` (kept for learning)
2. Helm chart in `helm/nexops` (current install on POC)

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
**Stage 3 — Kubernetes + Helm (COMPLETED)**  
Next: Stage 4 — Failure Simulation (not started)

## Important decisions
- GitHub repository `nexops-ai-kubernetes-platform` is the permanent source of truth.
- Stage 1/2 services stay simple: no database, no Redis/Kafka.
- Frontend nginx proxies `/api` to `orders-api`; `orders-api` reaches `payment-api` via cluster DNS (`PAYMENT_API_URL=http://payment-api:8000`).
- POC/corporate proxy remains environment-specific and is not hardcoded into Compose, Kubernetes, or Helm.
- Stage 3: raw Kubernetes YAML first, verified, then replaced with `helm install` in namespace `nexops`. Raw YAML remains in `k8s/`.
- ClusterIP services only; access via `kubectl port-forward`.
- Images built on POC and imported into containerd (`imagePullPolicy: IfNotPresent`). No registry yet.
- No Kubernetes Secrets in Stage 3 (nothing secret to store).

## Known issues
- Local Windows workstation does not have Git installed; Git commit/push is done from the POC environment.
- POC Docker/GitHub access may need an environment-specific proxy (not committed).
- Images are local to the POC node until a registry (ECR) is added later.

## Last updated
2026-08-22
