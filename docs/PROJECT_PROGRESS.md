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
| 9 | Remediation | COMPLETED |
| 10 | Kubernetes Security | COMPLETED |
| 11 | CI (clean Docker images) | NOT STARTED |
| 12 | AWS + ECR + EKS + Helm (IAC + CD) | NOT STARTED |
| 13 | Production Improvements | NOT STARTED |
| 14 | Final Demo | NOT STARTED |
| 15 | Reverse Engineering | NOT STARTED |

## Current stage
**Stage 10 — Kubernetes security (COMPLETED)**
Chart `0.7.0`: store pods use tokenless ServiceAccounts; detector is read-only;
analyzer is read-only; remediation may get/patch only `deployment/payment-api`.
Python workloads run as uid 10001 with dropped capabilities.
Next (planned, not started): Stage 11 CI, then Stage 12 AWS + ECR + EKS + Helm.

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
- Stage 8 is `/ops` in the existing React frontend. Nginx proxies platform APIs and the UI joins by `incident_id`.
- Stage 9 persists decisions and applies only four server-side allowlisted actions to `payment-api`; success requires rollout, app health, and detector resolution.
- Stage 10 gives every workload its own ServiceAccount. Store pods do not mount an API token. Analyzer/detector Roles are get/list (watch on detector). Remediation Role is get/patch on `deployment/payment-api` only.
- Stage 11 is **CI only**: GitHub Actions runs existing tests and `docker build` on GitHub-hosted runners with **no proxy args**, producing clean production images. No ECR push, no Helm deploy, no change to POC pods.
- Stage 12 is **IAC + CD**: Terraform (or equivalent) for AWS (VPC, EKS, ECR), push those images to ECR, and Helm-deploy NexOps onto EKS so it runs outside the corporate POC. Old “standalone EKS stage” is part of Stage 12.

## Known issues
- Local Windows workstation does not have Git; push is from POC.
- Images are local to the POC node (`nexops/frontend:v3`, `nexops/remediation:v1`, `nexops/payment-api:v3`, `nexops/orders-api:v2`, `nexops/incident-detector:v2`, `nexops/ai-analyzer:v2`). Stage 11 CI builds do not replace those POC images. Stage 12 is when EKS pulls from ECR.
- After manual failure tests use `--reset-values`; after a Stage 9 direct patch use `--reset-values --force-conflicts` so Helm 4 reclaims changed fields.
- The POC has a pre-existing operator ClusterRoleBinding (`postgres-operator-prerequisities-due-to-ocp-limitations`) that still grants **all** service accounts Deployment create/delete/patch. Kubernetes RBAC is additive, so NexOps Roles cannot hide that. Stage 10 removes the **token** from store pods so they cannot use it, and keeps analyzer/detector/remediation on least-privilege Roles. Do not delete that ClusterRoleBinding on this shared cluster. A clean EKS cluster will not have it.

## Last updated
2026-08-27
