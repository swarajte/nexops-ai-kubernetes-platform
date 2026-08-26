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

Later platform flow:

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
| Monitoring | Prometheus + Grafana (reused) + Loki |
| Platform | incident-detector, ai-analyzer (Python) |

## Build stages

| Stage | Name | Status |
|-------|------|--------|
| 1 | Applications (frontend, orders-api, payment-api) | COMPLETED |
| 2 | Local Docker | COMPLETED |
| 3 | Kubernetes + Helm | COMPLETED |
| 4 | Failure Simulation | COMPLETED |
| 5 | Monitoring | COMPLETED |
| 6 | Incident Detector | COMPLETED |
| 7 | AI Analyzer | COMPLETED |
| 8 | NexOps Control Center | COMPLETED |
| 9 | Remediation | NOT STARTED |
| 10 | Kubernetes Security | NOT STARTED |
| 11 | CI/CD | NOT STARTED |
| 12 | Infrastructure (Terraform) | NOT STARTED |
| 13 | AWS / EKS | NOT STARTED |
| 14 | Production Improvements | NOT STARTED |
| 15 | Final Demo | NOT STARTED |
| 16 | Reverse Engineering | NOT STARTED |

## Current stage
**Stage 8 — NexOps Control Center (COMPLETED)**  
Frontend `v2` is live on POC. Same-origin detector/analyzer proxies and HighErrorRate correlation were verified. Next: Stage 9 remediation.

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
- Stage 5 reuses existing Prometheus/Grafana in `monitoring`; Loki is a new Helm release `nexops-loki` in `nexops-monitoring`.
- ServiceMonitors must have label `release: prometheus` or the existing operator ignores them.
- Stage 6 incident-detector only watches namespace `nexops` (Role, not ClusterRole). One OPEN incident per `service:problem`. Healthy again → RESOLVED.
- Stage 7 ai-analyzer is read-only (pods, logs, events). Default analysis is a rule engine; LLM is optional via Secret and is not required on this POC.
- Detector + analyzer share one mapping table: OOMKilled→increase_memory, CrashLoopBackOff→restart_deployment, ImagePullBackOff→fix_image_tag, NotReady and injected Ready-pod modes→reset_failure_mode. App modes come from payment-api `/fail/status`.
- Stage 8 is `/ops` in the existing React frontend. Nginx proxies detector/analyzer APIs, the UI joins by `incident_id`, and approval is UI-only until Stage 9.
- Plain-language walkthrough: `docs/SIMPLE_GUIDE.md`.

## Known issues
- Local Windows workstation does not have Git; push is from POC.
- Images are local to the POC node (`nexops/frontend:v2`, `nexops/payment-api:v3`, `nexops/orders-api:v2`, `nexops/incident-detector:v2`, `nexops/ai-analyzer:v2`).
- After a failure demo, always `helm upgrade ... --reset-values` so overlays do not stick (Helm 4).

## Last updated
2026-08-26
