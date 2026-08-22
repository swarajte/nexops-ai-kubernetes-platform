# NexOps commands (Stages 1–4)

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
| 4 | Same Helm install, with *intentional* payment-api failures |

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

## Stage 4 — Failure simulation (resume / interview notes)

We inject failures **on purpose** so later stages can detect OOMKilled, CrashLoopBackOff, etc.
Target is **payment-api** (the first planned incident in the project brief).

Two ways to trigger:

1. **Helm overlay** (Kubernetes-level, good for ImagePullBackOff / CrashLoop / OOM)
2. **HTTP** `POST /fail/...` (runtime, then `POST /fail/reset`)

Always recover with **`--reset-values`** (Helm 4 keeps the last `-f` overlay until you reset):

```bash
cd /storage/swarajt/nexops-ai-kubernetes-platform
helm upgrade nexops ./helm/nexops -n nexops --reset-values
```

Watch with:

```bash
kubectl -n nexops get pods -w
kubectl -n nexops describe pod -l app.kubernetes.io/component=payment-api
kubectl -n nexops get events --sort-by='.lastTimestamp'
```

Trigger HTTP from inside the cluster:

```bash
kubectl -n nexops exec deploy/orders-api -- python -c "import urllib.request; urllib.request.urlopen(urllib.request.Request('http://payment-api:8000/fail/oom', method='POST'))"
```

### 1) OOMKilled (do this first)

**What:** Linux / kubelet kills the container because it used more RAM than its **limit**.

**Why:** `resources.limits.memory` is a hard cap. The process did not "crash in Python"; it was SIGKILL'd. `restartCount` goes up. `lastState.terminated.reason` is `OOMKilled`.

**How:**
```bash
helm upgrade nexops ./helm/nexops -n nexops -f helm/nexops/failures/oom.yaml
kubectl -n nexops get pods -l app.kubernetes.io/component=payment-api
kubectl -n nexops describe pod -l app.kubernetes.io/component=payment-api | grep -A8 'Last State'
```

**Recover:**
```bash
helm upgrade nexops ./helm/nexops -n nexops --reset-values
```

### 2) CrashLoopBackOff

**What:** Container starts, exits non-zero, kubelet restarts it, backoff delay grows. Pod phase is Running or CrashLoopBackOff.

**Why:** `FAILURE_MODE=crash` calls `os._exit(1)` at process start. Not a probe failure — the process never stays up.

**How:**
```bash
helm upgrade nexops ./helm/nexops -n nexops -f helm/nexops/failures/crash.yaml
kubectl -n nexops get pods -l app.kubernetes.io/component=payment-api
```

**Recover:** `helm upgrade nexops ./helm/nexops -n nexops --reset-values`

### 3) ImagePullBackOff

**What:** kubelet cannot fetch the image. Pod never starts the app container.

**Why:** We pointed at `nexops/payment-api:does-not-exist`. This is a **Kubernetes/image** problem, not application code.

**How:**
```bash
helm upgrade nexops ./helm/nexops -n nexops -f helm/nexops/failures/imagepull.yaml
kubectl -n nexops describe pod -l app.kubernetes.io/component=payment-api | grep -i 'Failed to pull\|ImagePull'
```

**Recover:** `helm upgrade nexops ./helm/nexops -n nexops --reset-values`

### 4) Readiness failure

**What:** Pod is **Running** but **0/1 Ready**. Endpoints empty. Buy Now fails. Liveness `/health` still 200, so kubelet does **not** restart it.

**Why:** Readiness probe hits `/ready`. `FAILURE_MODE=ready` makes `/ready` return 503. This is how Kubernetes removes a pod from Service load-balancing without killing it.

**How:**
```bash
helm upgrade nexops ./helm/nexops -n nexops -f helm/nexops/failures/ready.yaml
kubectl -n nexops get pods -l app.kubernetes.io/component=payment-api
kubectl -n nexops get endpoints payment-api
```

Or HTTP (no Helm overlay): `POST http://payment-api:8000/fail/ready` with `{"fail": true}`  
Reset: `POST /fail/reset`

**Recover:** `helm upgrade ... --reset-values`, or `/fail/reset` if you used HTTP.

### 5) High CPU

**What:** A busy-loop thread burns CPU. Pod stays Ready (until you add throttling alerts in Stage 5).

**How:** overlay `failures/cpu.yaml` or `POST /fail/cpu`  
**Recover:** `--reset-values` or `/fail/reset`

### 6) High memory (not necessarily OOM)

**What:** Process holds extra heap (`FAILURE_MODE=memory` allocates ~40Mi). May or may not hit the 128Mi limit.

**How:** `failures/memory.yaml` or `POST /fail/memory`  
**Recover:** `--reset-values` or `/fail/reset` (restart the pod if memory was allocated in-process).

### 7) Slow application

**What:** `/pay` sleeps 5 seconds. Orders look stuck / may 502 if callers time out (orders-api timeout is 5s).

**How:** `failures/slow.yaml` or `POST /fail/slow`  
**Recover:** `--reset-values` or `/fail/reset`

### 8) High error rate

**What:** `/pay` returns HTTP 500 for most calls. Store shows order failed. Pod can still be Ready.

**How:** `failures/errors.yaml` or `POST /fail/errors` with `{"rate": 0.8}`  
**Recover:** `--reset-values` or `/fail/reset`

### Liveness vs readiness (say this in interviews)

| Probe | Path | Meaning |
|-------|------|---------|
| liveness | `/health` | Process should be restarted if this fails |
| readiness | `/ready` | Pod should receive traffic only if this succeeds |

---

## What is running now (after Stage 4)

Helm release `nexops` in namespace `nexops`, **payment-api image `nexops/payment-api:v2`** with failure endpoints.
Leave it healthy (`failureMode: none`) unless you are demonstrating a failure.
