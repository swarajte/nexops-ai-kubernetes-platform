# NexOps

**NexOps — AI Kubernetes Incident Response & Self-Healing Platform**

## Current status
Stage 10 — Kubernetes least-privilege RBAC completed and verified on the POC.

**Next (planned, not started):** Stage 11 CI (GitHub Actions tests + proxy-free image builds). Stage 12 AWS + ECR + EKS + Helm (IAC + CD).

**How everything works in simple words:** [docs/SIMPLE_GUIDE.md](docs/SIMPLE_GUIDE.md)  
Start/stop commands: **[docs/COMMANDS.md](docs/COMMANDS.md)**  
One-failure-at-a-time experiments: **[docs/FAILURE_EXPERIMENTS.md](docs/FAILURE_EXPERIMENTS.md)**

## Application flow
```
NexOps Store (frontend)
        ↓
    orders-api
        ↓
    payment-api
```

## Kubernetes + Helm (Stage 3)

Raw manifests (for learning) live in `k8s/`.  
The Helm chart is `helm/nexops`.

Build images on the Kubernetes node, then import them into containerd so kubelet can use them:

```bash
docker build -t nexops/payment-api:v1 ./payment-api
docker build -t nexops/orders-api:v1 ./orders-api
docker build -t nexops/frontend:v1 ./frontend
docker save nexops/payment-api:v1 nexops/orders-api:v1 nexops/frontend:v1 | ctr -n k8s.io images import -
```

Install with Helm (current method):

```bash
helm install nexops ./helm/nexops -n nexops --create-namespace
helm upgrade nexops ./helm/nexops -n nexops
```

## Failure simulation (Stage 4)

Intentional payment-api failures (OOMKilled first, then crash, image pull, readiness, CPU, memory, slowness, errors).

```bash
# example: OOMKilled
helm upgrade nexops ./helm/nexops -n nexops -f helm/nexops/failures/oom.yaml

# recover to healthy (Helm 4: must reset overlays)
helm upgrade nexops ./helm/nexops -n nexops --reset-values
```

What each failure looks like, why it happens, and how to recover: **[docs/COMMANDS.md](docs/COMMANDS.md)** (Stage 4).

## Monitoring (Stage 5)

This POC already runs **kube-prometheus-stack** in namespace `monitoring`. NexOps reuses that Prometheus and Grafana. We add:

- `/metrics` on orders-api and payment-api
- ServiceMonitors (`release: prometheus`)
- Grafana dashboard **NexOps Store** (folder NexOps)
- Loki + Promtail via `helm/nexops-monitoring/loki-stack-values.yaml`

```bash
helm upgrade --install nexops-loki grafana/loki-stack \
  -n nexops-monitoring --create-namespace \
  -f helm/nexops-monitoring/loki-stack-values.yaml
helm upgrade nexops ./helm/nexops -n nexops --reset-values
```

Grafana (port-forward on POC, same pattern as the store): `http://10.245.101.134:3300`  
Do not use `:2400` — that NodePort targets the wrong container port. See **[docs/COMMANDS.md](docs/COMMANDS.md)** (Stage 5).

## Incident detector (Stage 6)

Python service in namespace `nexops`. It watches pods and stores OPEN/RESOLVED incidents (no AI, no auto-fix).

```bash
docker build -t nexops/incident-detector:v1 ./incident-detector
docker save nexops/incident-detector:v1 | ctr -n k8s.io images import -
helm upgrade nexops ./helm/nexops -n nexops --reset-values
kubectl -n nexops exec deploy/incident-detector -- python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8080/incidents').read().decode())"
```

Verify it yourself (pod up, `/health`, then OOM overlay → `OPEN`, recover → `RESOLVED`): **[docs/COMMANDS.md](docs/COMMANDS.md)** Stage 6.

## AI analyzer (Stage 7)

Python service in namespace `nexops`. It reads OPEN incidents, gathers read-only Kubernetes evidence, and stores structured JSON (rules by default; LLM optional, not required).

```bash
docker build -t nexops/ai-analyzer:v1 ./ai-analyzer
docker save nexops/ai-analyzer:v1 | ctr -n k8s.io images import -
helm upgrade nexops ./helm/nexops -n nexops --reset-values
kubectl -n nexops exec deploy/ai-analyzer -- python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8081/health').read().decode())"
```

Verify it yourself (pod up, `/health`, OOM overlay → analysis JSON, recover): **[docs/COMMANDS.md](docs/COMMANDS.md)** Stage 7.

## NexOps Control Center (Stage 8)

The React frontend now serves both the monitored store and a production-style SRE dashboard:

- `/store` — store application
- `/ops` — overall health, OPEN/RESOLVED incidents, evidence, AI analysis, confidence and suggested action
- approval/rejection is persisted and approved actions run through the Stage 9 allowlist
- analyses are correlated using `incident_id`, never by assuming the newest historical analysis is current

Nginx provides same-origin proxies for detector, analyzer, and remediation APIs.

```bash
docker build -t nexops/frontend:v3 ./frontend
docker save nexops/frontend:v3 | ctr -n k8s.io images import -
helm upgrade nexops ./helm/nexops -n nexops --reset-values
kubectl -n nexops port-forward --address 0.0.0.0 svc/frontend 3000:80
```

Open `http://10.245.101.134:3000/ops`.

## Allowlisted remediation (Stage 9)

The `remediation/` service persists Approve/Reject decisions, revalidates the live incident and matching analysis, then patches only an allowlisted target. Supported actions are `increase_memory`, `restart_deployment`, `fix_image_tag`, and `reset_failure_mode`. Unknown targets/actions and stale analyses are rejected. The UI polls `queued → validating → applying → verifying → succeeded/failed`.

Stage 9 was accepted on the POC with a `HighErrorRate` incident: `reset_failure_mode` was approved, the `payment-api` Deployment was patched, the detector resolved the incident, and `/fail/status` returned healthy.
The OOM path was also verified: `increase_memory` applied 32Mi→64Mi while clearing the infinite OOM injector, then the incident resolved. Reconcile Helm 4 after direct remediation with `--reset-values --force-conflicts`.

## Kubernetes security (Stage 10)

Every NexOps pod has its own ServiceAccount.

- `frontend`, `orders-api`, `payment-api` do **not** mount an API token
- `incident-detector` may `get/list/watch` pods and events in `nexops` only
- `ai-analyzer` may `get/list` pods, pod logs, and events (no patch/delete)
- `remediation` may `get/patch` **only** `deployment/payment-api`
- Python containers run as uid `10001` with `allowPrivilegeEscalation: false` and all capabilities dropped


Access the store (port-forward listens on the machine where you run kubectl):

```bash
kubectl -n nexops port-forward svc/frontend 3000:80
```

If kubectl runs **on POC**, `http://localhost:3000` works **on POC**, not on your laptop Chrome.
From Windows, use an SSH tunnel or `--address 0.0.0.0` and the POC IP. See [docs/COMMANDS.md](docs/COMMANDS.md).

Optional: apply the raw YAML instead of Helm (do not mix both):

```bash
kubectl apply -f k8s/
```

## Docker Compose (Stage 2)
```bash
docker compose up --build -d
```

Open http://localhost:3000

## Tests
```bash
cd payment-api && pytest
cd orders-api && pytest
cd incident-detector && pytest
cd ai-analyzer && pytest
cd frontend && npm test
```

## Notes
- No secrets, proxy URLs, or corporate credentials belong in this repository.
- POC environments may need an external proxy for Docker image builds; that is environment-specific only.
- Stage 11 (not started): GitHub Actions tests + `docker build` without proxy args. Builds do not start long-running containers and do not update the POC.
- Stage 12 (not started): AWS infrastructure, push images to ECR, Helm deploy to EKS.
