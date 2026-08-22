# NexOps

**NexOps — AI Kubernetes Incident Response & Self-Healing Platform**

## Current status
Stage 6 — Incident detector completed.

**How everything works in simple words:** [docs/SIMPLE_GUIDE.md](docs/SIMPLE_GUIDE.md)  
Start/stop commands: **[docs/COMMANDS.md](docs/COMMANDS.md)**

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

```bash
helm install nexops ./helm/nexops -n nexops --create-namespace
helm upgrade nexops ./helm/nexops -n nexops --reset-values
```

## Failure simulation (Stage 4)

```bash
helm upgrade nexops ./helm/nexops -n nexops -f helm/nexops/failures/oom.yaml
helm upgrade nexops ./helm/nexops -n nexops --reset-values
```

## Monitoring (Stage 5)

Reuse cluster Prometheus/Grafana. Loki is `nexops-loki`. Grafana UI: `http://10.245.101.134:3300` (not port 2400).

## Incident detector (Stage 6)

```bash
docker build -t nexops/incident-detector:v1 ./incident-detector
docker save nexops/incident-detector:v1 | ctr -n k8s.io images import -
helm upgrade nexops ./helm/nexops -n nexops --reset-values
kubectl -n nexops exec deploy/incident-detector -- python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8080/incidents').read().decode())"
```

## Tests
```bash
cd incident-detector && pytest
```

## Notes
- No secrets, proxy URLs, or corporate credentials belong in this repository.
