# NexOps in simple words

Read this before Stage 6. Commands to start/stop things live in [COMMANDS.md](COMMANDS.md). This file is **what the pieces are and why they exist**.

GitHub is the source of truth: `nexops-ai-kubernetes-platform`.
POC folder: `/storage/swarajt/nexops-ai-kubernetes-platform`.

---

## 1. What are we building?

**NexOps** is not only a shop website. It is two layers:

1. **The store** (what customers use): a tiny shop with three programs.
2. **The platform** (what operators use later): watch Kubernetes, notice when something is wrong, explain it, suggest a fix, wait for a human, then apply the fix.

We build the store first so we have a **real app** that can break. Then we build the platform around it.

The big picture:

```
Customer uses the store
        ↓
Something breaks (we can also break it on purpose)
        ↓
Monitoring sees numbers and logs  (Stage 5)
        ↓
Incident detector says this is an incident  (Stage 6)
        ↓
Later: AI explains it, a dashboard asks you to approve, a fixer talks to Kubernetes
```

---

## 2. The store (always the same three programs)

Think of a checkout line.

| Program | Everyday name | What it does |
|---------|----------------|--------------|
| **frontend** | The shop website | Shows products. Buy talks to orders-api. |
| **orders-api** | The cashier | Creates an order, then asks payment-api to take money. |
| **payment-api** | The card machine | Says yes or no. **This is the one we break on purpose.** |

```
Browser → frontend → orders-api:8001 POST /orders → payment-api:8000 POST /pay
```

- payment-api `/health` = process alive (**liveness**)
- payment-api `/ready` = may take traffic (**readiness**)
- both APIs `/metrics` = numbers for Prometheus

---

## 3. Stage 1 — programs on a machine

**What:** uvicorn + npm, no Docker. **Why:** prove the three programs talk. **How:** ports 8000, 8001, 5173.

---

## 4. Stage 2 — Docker Compose

**What:** same apps in containers. **Why:** same package later used in Kubernetes. Frontend on port **3000**.

---

## 5. Stage 3 — Kubernetes then Helm

Namespace **nexops**. **Pod** = running app. **Deployment** = keep it running. **Service** = stable name like `payment-api:8000`. **Limits.memory** too small → **OOMKilled**.

Raw YAML in `k8s/` for learning. Live install is Helm `helm/nexops`. Helm 4: recover failures with `--reset-values`.

Build with Docker, import: `docker save IMAGE | ctr -n k8s.io images import -`.
Bump image tags because `IfNotPresent` ignores a rebuilt same tag.

`kubectl port-forward` on POC is **POC localhost**, not Windows. From Windows use `http://10.245.101.134:PORT` or an SSH tunnel.

---

## 6. Stage 4 — break payment-api on purpose

Helm overlay or `POST /fail/...`. Recover: `helm upgrade nexops ./helm/nexops -n nexops --reset-values`.

| Failure | Simple meaning |
|---------|----------------|
| OOMKilled | Used more RAM than the limit; kernel killed it |
| CrashLoopBackOff | Process keeps exiting |
| ImagePullBackOff | Bad image tag; not app code |
| NotReady | `/ready` fails; `/health` can still pass |

Liveness = restart me. Readiness = stop sending me traffic.

---

## 7. Stage 5 — monitoring

| Tool | Job |
|------|-----|
| Prometheus | Scrapes numbers (CPU, memory, restarts, `/metrics`) |
| Grafana | Draws graphs (dashboard **NexOps Store** at **http://10.245.101.134:3300**, not :2400) |
| Loki | Stores log lines; Promtail ships logs from namespace nexops |

We reused cluster Prometheus/Grafana in `monitoring`. We added ServiceMonitors with label `release: prometheus`, plus Loki in `nexops-monitoring`.

---

## 8. How information travels

OOM → Kubernetes records it → Prometheus/Loki show it → **incident detector opens OPEN** → later AI, dashboard, approve, fix.

Stage 6 does **not** fix or call AI.

---

## 9. Stage 6 — incident detector (built)

Every 10 seconds it lists pods. Problems (first match): ImagePullBackOff, OOMKilled, CrashLoopBackOff, NotReady. One OPEN row per service+problem. Healthy again → RESOLVED.

`GET /incidents` on port 8080. ServiceAccount may only **list** pods/events in `nexops`.

Commands: [COMMANDS.md](COMMANDS.md).
