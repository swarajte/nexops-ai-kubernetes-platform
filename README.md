# NexOps

**NexOps — AI Kubernetes Incident Response & Self-Healing Platform**

## Current status
Stage 3 — Kubernetes + Helm completed.

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

Access the store:

```bash
kubectl -n nexops port-forward svc/frontend 3000:80
```

Open http://localhost:3000

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
