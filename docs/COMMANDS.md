# NexOps commands (Stages 1–3)

Use this while preparing interviews / reverse-engineering.
GitHub is the source of truth: `nexops-ai-kubernetes-platform`.

POC project path:
`/storage/swarajt/nexops-ai-kubernetes-platform`

---

## How the request actually flows

```
Browser
  → frontend (NexOps Store, nginx)
       /api/*  →  orders-api:8001
                     POST /orders
                       →  payment-api:8000  POST /pay
                     ← payment success
       ← Order confirmed
```

Same flow in every stage. Only the *runtime* changes:

| Stage | Where it runs |
|-------|----------------|
| 1 | Processes on a machine (`uvicorn` + `npm run dev`) |
| 2 | Three Docker containers (`docker compose`) |
| 3 | Three Kubernetes pods (raw YAML first, then Helm) |

---

## Why `localhost:3000` failed in Chrome on Windows

`kubectl port-forward` binds to **localhost of the machine where you ran kubectl**.

You ran it **on POC**. That opens `127.0.0.1:3000` **on the POC server**, not on your laptop.

Your Windows Chrome talks to **your PC's** `localhost:3000` → nothing is listening → `ERR_CONNECTION_REFUSED`.

**Fix (pick one):**

1. **SSH tunnel from Windows** (best match for “port-forward”):
   ```bash
   ssh -L 3000:127.0.0.1:3000 root@10.245.101.134
   ```
   Keep that SSH session open. On POC, in another session:
   ```bash
   kubectl -n nexops port-forward svc/frontend 3000:80
   ```
   Then on Windows Chrome: http://localhost:3000

2. **Listen on the POC node IP** (from POC):
   ```bash
   kubectl -n nexops port-forward --address 0.0.0.0 svc/frontend 3000:80
   ```
   Then on Windows Chrome: `http://10.245.101.134:3000`
   (not `localhost`)

3. **kubectl on Windows** pointed at the POC cluster, then:
   ```bash
   kubectl -n nexops port-forward svc/frontend 3000:80
   ```
   Then http://localhost:3000 on Windows is correct.

Stop port-forward: `Ctrl+C` in that terminal.

---

## Stage 1 — apps as processes

Workdir: project root.

### Start
```bash
# terminal 1 — payment-api
cd payment-api
pip install -r requirements-dev.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000

# terminal 2 — orders-api
cd orders-api
pip install -r requirements-dev.txt
# PowerShell: $env:PAYMENT_API_URL="http://127.0.0.1:8000"
export PAYMENT_API_URL=http://127.0.0.1:8000
uvicorn app.main:app --host 0.0.0.0 --port 8001

# terminal 3 — store (dev)
cd frontend
npm install
npm run dev
```

Open http://localhost:5173

### Stop
`Ctrl+C` in each of the three terminals.

### Test
```bash
cd payment-api && pytest
cd orders-api && pytest
cd frontend && npm test

curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8001/health
curl -X POST http://127.0.0.1:8001/orders \
  -H "Content-Type: application/json" \
  -d '{"product_id":"nx-mug","product_name":"On-Call Mug","quantity":1,"unit_price":14.0}'
```

---

## Stage 2 — Docker Compose

Workdir: project root (where `docker-compose.yml` is).

### Start
```bash
docker compose up --build -d
docker compose ps
```

Open http://localhost:3000 (on the **same machine** that runs Compose).

### Logs / stop
```bash
docker compose logs -f
docker compose stop
docker compose down          # stop and remove containers
docker compose down --rmi local   # also remove built images (optional)
```

### Test
```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8001/health
curl http://127.0.0.1:3000/api/health
curl -X POST http://127.0.0.1:3000/api/orders \
  -H "Content-Type: application/json" \
  -d '{"product_id":"nx-mug","product_name":"On-Call Mug","quantity":1,"unit_price":14.0}'
```

---

## Stage 3 — Kubernetes, then Helm

We did **two steps on purpose**:

1. **Raw YAML** (`k8s/`) — you can read Deployments, Services, probes, limits with no Helm magic.
2. After that worked, we **replaced** it with Helm (`helm/nexops`) so install/upgrade is one command. Raw YAML stays in git so Kubernetes is not hidden.

Do **not** `kubectl apply -f k8s/` and `helm install` at the same time.

POC cluster uses **containerd**. Docker-built images must be imported or kubelet cannot see them.

### Images (POC)
```bash
cd /storage/swarajt/nexops-ai-kubernetes-platform

docker build -t nexops/payment-api:v1 ./payment-api
docker build -t nexops/orders-api:v1 ./orders-api
docker build -t nexops/frontend:v1 ./frontend

docker save nexops/payment-api:v1 nexops/orders-api:v1 nexops/frontend:v1 \
  | ctr -n k8s.io images import -
```

(POC may need a **proxy in the shell only** for `docker build`. Do not put proxy URLs in git.)

### Part A — raw Kubernetes (learning path)
```bash
kubectl apply -f k8s/
kubectl -n nexops get pods,svc
kubectl -n nexops rollout status deploy/frontend
```

Stop / remove raw install:
```bash
kubectl delete -f k8s/
# or
kubectl delete namespace nexops
```

### Part B — Helm (current install on POC)
```bash
helm lint ./helm/nexops
helm install nexops ./helm/nexops -n nexops --create-namespace
helm upgrade nexops ./helm/nexops -n nexops
helm list -n nexops
helm status nexops -n nexops
```

Useful inspect commands:
```bash
kubectl -n nexops get pods,svc,deploy,cm
kubectl -n nexops describe pod -l app.kubernetes.io/component=frontend
kubectl -n nexops logs deploy/orders-api
kubectl -n nexops logs deploy/payment-api
kubectl -n nexops logs deploy/frontend
```

Port-forward (run where you will open the browser, or use SSH tunnel — see top):
```bash
kubectl -n nexops port-forward svc/frontend 3000:80
```

Stop Helm release:
```bash
helm uninstall nexops -n nexops
kubectl delete namespace nexops
```

### In-cluster test (no browser)
```bash
kubectl -n nexops exec deploy/frontend -- wget -qO- http://127.0.0.1/api/health
kubectl -n nexops exec deploy/frontend -- wget -qO- \
  --header='Content-Type: application/json' \
  --post-data='{"product_id":"nx-mug","product_name":"On-Call Mug","quantity":1,"unit_price":14.0}' \
  http://127.0.0.1/api/orders
```

---

## What is running now (after Stage 3)

Helm release `nexops` in namespace `nexops` (not Docker Compose, not Stage 1 processes).
