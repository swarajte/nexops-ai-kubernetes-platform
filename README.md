# NexOps

**NexOps — AI Kubernetes Incident Response & Self-Healing Platform**

## Current status
Stage 4 — Failure simulation completed.

Start/stop and failure-demo commands: **[docs/COMMANDS.md](docs/COMMANDS.md)**

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
cd frontend && npm test
```

## Notes
- No secrets, proxy URLs, or corporate credentials belong in this repository.
- POC environments may need an external proxy for Docker image builds; that is environment-specific only.
