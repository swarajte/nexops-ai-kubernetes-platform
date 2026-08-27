# NexOps commands (Stages 1–7)

Use this while preparing interviews / reverse-engineering.
**Simple English for every piece:** [SIMPLE_GUIDE.md](SIMPLE_GUIDE.md).
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
| 5 | Same pods, plus Prometheus scrape, Grafana dashboards, Loki logs |
| 6 | Same cluster, plus incident-detector watching pods and storing OPEN/RESOLVED incidents |

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

## Stage 5 — Monitoring

POC already had **kube-prometheus-stack** in namespace `monitoring` (Prometheus, Grafana, kube-state-metrics, node-exporter). We did **not** install a second full stack.

| Signal | Where it comes from |
|--------|---------------------|
| CPU / memory | cAdvisor metrics already scraped by cluster Prometheus |
| Pod restarts / phase / OOMKilled reason | kube-state-metrics (`kube_pod_*`) |
| Kubernetes events | `kubectl get events -n nexops` (and restart/OOM metrics on the dashboard) |
| Request rate, latency, HTTP errors | `/metrics` on orders-api and payment-api + ServiceMonitor |
| Application logs | Loki + Promtail (only namespace `nexops`) |

Grafana sidecar watches **all namespaces** for ConfigMaps labeled `grafana_dashboard=1` / `grafana_datasource=1`, so NexOps dashboards live in namespace `nexops`.

### Start / apply (from POC project path)

```bash
cd /storage/swarajt/nexops-ai-kubernetes-platform

# 1) Rebuild APIs (new /metrics endpoint). Tags must bump because imagePullPolicy is IfNotPresent.
docker build -t nexops/payment-api:v3 ./payment-api
docker build -t nexops/orders-api:v2 ./orders-api
docker save nexops/payment-api:v3 nexops/orders-api:v2 | ctr -n k8s.io images import -

# 2) Loki + Promtail (Grafana/Prometheus already exist in monitoring)
helm upgrade --install nexops-loki grafana/loki-stack \
  -n nexops-monitoring --create-namespace \
  -f helm/nexops-monitoring/loki-stack-values.yaml

# 3) ServiceMonitors + Grafana dashboard + Loki datasource + new image tags
helm upgrade nexops ./helm/nexops -n nexops --reset-values
```

`--reset-values` clears any leftover Stage 4 failure overlay.

### Stop / uninstall monitoring only (leave the store running)

```bash
helm uninstall nexops-loki -n nexops-monitoring
kubectl delete ns nexops-monitoring
```

Then disable NexOps scrape/dashboards if you want a store-only cluster:

```bash
helm upgrade nexops ./helm/nexops -n nexops --reset-values \
  --set monitoring.serviceMonitor.enabled=false \
  --set monitoring.grafana.dashboard.enabled=false \
  --set monitoring.grafana.lokiDatasource.enabled=false
```

### Open Grafana (from Windows)

`http://10.245.101.134:2400` **will not work**. There is a NodePort Service named `prometheus-grafana-ext` on 2400, but it points at **port 9090 on the Grafana pod**. Grafana's UI listens on **3000**. The node iptables rule for 2400 therefore hits a closed port → Chrome `ERR_CONNECTION_REFUSED` (same error even if you curl on the POC). Do **not** "fix" that Service; it belongs to the cluster monitoring Helm release, not NexOps.

Use a **port-forward**, same idea as the store (this one is already running on POC as `0.0.0.0:3300`):

On POC:
```bash
kubectl -n monitoring port-forward --address 0.0.0.0 svc/prometheus-grafana 3300:80
```

On Windows Chrome: **http://10.245.101.134:3300**  
(not 2400, not `localhost` unless you also SSH-tunnel)

SSH tunnel instead (then http://localhost:3300 on Windows):
```bash
ssh -L 3300:127.0.0.1:3300 root@10.245.101.134
```
Keep the POC port-forward running. On POC you can bind localhost only:
```bash
kubectl -n monitoring port-forward svc/prometheus-grafana 3300:80
```

Folder **NexOps**, dashboard **NexOps Store**.

Admin user/password are in the cluster secret (do not commit them):

```bash
kubectl -n monitoring get secret prometheus-grafana \
  -o jsonpath='{.data.admin-user}' | base64 -d; echo
kubectl -n monitoring get secret prometheus-grafana \
  -o jsonpath='{.data.admin-password}' | base64 -d; echo
```

Prometheus UI (cluster-internal, port-forward on POC):

```bash
kubectl -n monitoring port-forward --address 0.0.0.0 svc/prometheus-kube-prometheus-prometheus 9090:9090
```

Then `http://10.245.101.134:9090` → Status → Targets, look for `nexops/payment-api` and `nexops/orders-api`.

### What / why / how / recover

**Prometheus (reused)**  
**What:** Time-series DB that scrapes HTTP `/metrics`.  
**Why:** CPU, memory, restarts, and request counters need a scraper + TSDB.  
**How:** Existing operator watches ServiceMonitors with label `release: prometheus` in any namespace. NexOps chart creates those.  
**Recover:** `kubectl -n nexops get servicemonitor`; if targets are down, check `/metrics` on the pod and that the label is exactly `release: prometheus`.

**Grafana (reused)**  
**What:** Dashboards over Prometheus + Loki.  
**Why:** One place to see a failure (OOM, 5xx, logs) during demos.  
**How:** ConfigMaps `nexops-grafana-dashboard` and `nexops-grafana-loki-datasource`. Sidecar imports them.  
**Recover:** Delete/recreate the ConfigMaps via `helm upgrade`; wait ~30s for sidecar. If the dashboard is missing, confirm labels `grafana_dashboard=1`.

**Loki + Promtail (we installed)**  
**What:** Loki stores logs; Promtail DaemonSet tails container logs and pushes them.  
**Why:** Prometheus does not store log lines; Stage 5 brief asks for application logs.  
**How:** Helm release `nexops-loki` in `nexops-monitoring`. Promtail `keep`s only `namespace=nexops`.  
**Recover:** `kubectl -n nexops-monitoring get pods`; `kubectl logs -n nexops-monitoring -l app=loki`. If Loki is Ready but Grafana shows no logs, Promtail may have started first: `kubectl -n nexops-monitoring rollout restart daemonset/nexops-loki-promtail`. Uninstall with `helm uninstall nexops-loki -n nexops-monitoring`.

**App `/metrics`**  
**What:** Prometheus text format from `prometheus-fastapi-instrumentator`.  
**Why:** Request count, latency histogram, HTTP status (errors) are application-level, not in cAdvisor.  
**How:** `GET /metrics` on payment-api:8000 and orders-api:8001.  
**Recover:** If `/metrics` 404, you are on an old image (v1/v2 payment without instrumentator). Rebuild `v3` / orders `v2` and import to containerd.

### Demo: see a failure on the dashboard

```bash
helm upgrade nexops ./helm/nexops -n nexops --reset-values -f helm/nexops/failures/oom.yaml
# Grafana: restarts + last terminated reason OOMKilled; Loki: container restart
helm upgrade nexops ./helm/nexops -n nexops --reset-values
```

HTTP errors (no pod restart):

```bash
kubectl -n nexops exec deploy/orders-api -- python -c "import urllib.request; urllib.request.urlopen(urllib.request.Request('http://payment-api:8000/fail/errors', method='POST', data=b'{\"rate\":1}', headers={'Content-Type':'application/json'}))"
# generate traffic via the store, then Grafana 5xx ratio
kubectl -n nexops exec deploy/orders-api -- python -c "import urllib.request; urllib.request.urlopen(urllib.request.Request('http://payment-api:8000/fail/reset', method='POST'))"
```

### Events

```bash
kubectl -n nexops get events --sort-by='.lastTimestamp'
```

---

## What is running now (after Stage 5)

- Helm `nexops` in `nexops`: frontend `v1`, orders-api `v2`, payment-api `v3`, ServiceMonitors, Grafana dashboard ConfigMaps.
- Helm `nexops-loki` in `nexops-monitoring`: Loki + Promtail.
- Cluster Grafana: `http://10.245.101.134:2400` dashboard **NexOps Store**.
Leave payment-api healthy (`failureMode: none`) unless you are demonstrating a failure.

## Stage 6 — Incident detector

Simple explanation: [SIMPLE_GUIDE.md](SIMPLE_GUIDE.md) sections 8 and 11.

**What:** A Python pod that lists pods in `nexops` every 10 seconds. If a pod looks wrong, it **opens an incident**. If the problem is gone, it marks that incident **RESOLVED**.

```bash
kubectl -n nexops exec deploy/incident-detector -- python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8080/incidents').read().decode())"
```

Demo: overlay oom, wait ~30s, read OPEN incidents, then `helm upgrade ... --reset-values`.

---
## Stage 7 — AI analyzer

Simple explanation: [SIMPLE_GUIDE.md](SIMPLE_GUIDE.md) sections 8 and 12.

**What:** A Python pod that reads OPEN incidents from `incident-detector`, gathers **read-only** Kubernetes facts (pod resources, events, log tail), and stores a structured analysis. Default brain is a **rule engine**. An LLM is optional and off on this POC.

**Why:** Stage 6 only names the symptom (`OOMKilled`, `NotReady`, …). Stage 7 turns that into English + a `suggested_action` object Stage 9 can allowlist later (`increase_memory`, `restart_deployment`, …).

**What it must never do:** patch/delete objects, exec into pods, or run shell as “the fix.” Role verbs are `get`/`list` only.

**Where stored:** SQLite on `emptyDir` (cleared if the analyzer pod is deleted).

**Ports:** detector **8080**, analyzer **8081**.

### Verify it yourself (from POC)

Workdir: `/storage/swarajt/nexops-ai-kubernetes-platform`

**Step 1 — is the analyzer pod up?**

```bash
kubectl -n nexops get deploy,pod,svc -l app.kubernetes.io/component=ai-analyzer
kubectl -n nexops rollout status deploy/ai-analyzer
```

Expect: `1/1` Ready, Service `ai-analyzer` on port **8081**.

**Step 2 — does its HTTP API answer?**

```bash
kubectl -n nexops exec deploy/ai-analyzer -- python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8081/health').read().decode())"
kubectl -n nexops exec deploy/ai-analyzer -- python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8081/analyses').read().decode())"
```

Expect: `{\"status\":\"healthy\",\"service\":\"ai-analyzer\"}`.  
`analyses` may already have rows (for example a short `NotReady` on the analyzer itself while it was starting).

**Step 3 — open it in Windows Chrome (optional)**

On POC (leave this running):

```bash
kubectl -n nexops port-forward --address 0.0.0.0 svc/ai-analyzer 8081:8081
```

On Windows Chrome (not `localhost` unless you also SSH-tunnel):

- http://10.245.101.134:8081/health
- http://10.245.101.134:8081/analyses

Same rule as Grafana and the detector: port-forward on POC is **not** your laptop’s localhost.

**Step 4 — prove it explains a failure**

```bash
helm upgrade nexops ./helm/nexops -n nexops --reset-values -f helm/nexops/failures/oom.yaml
sleep 45
kubectl -n nexops exec deploy/incident-detector -- python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8080/incidents?status=OPEN').read().decode())"
kubectl -n nexops exec deploy/ai-analyzer -- python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8081/analyses').read().decode())"
```

Expect JSON with `\"service\":\"payment-api\"`, `\"source\":\"rules\"`, and a `\"suggested_action\"` (often `\"type\":\"increase_memory\"`).
If `analyses` has no payment-api row yet but an OPEN incident exists, POST `/analyze` with that incident id.

`problem` on the incident may be **`NotReady`** first; the analyzer still treats NotReady + restarts/OOM events as a memory issue.

**Step 5 — recover the cluster**

```bash
helm upgrade nexops ./helm/nexops -n nexops --reset-values
kubectl -n nexops rollout status deploy/payment-api
```

Leave payment-api healthy. Analyses stay in SQLite until the analyzer pod is deleted.

**Step 6 — if it looks dead**

```bash
kubectl -n nexops logs deploy/ai-analyzer --tail=80
kubectl -n nexops describe rolebinding ai-analyzer
```

- `Forbidden` → Role is missing `pods`, `pods/log`, or `events`.
- cannot list OPEN incidents → detector URL should be `http://incident-detector:8080`.
- Empty analyses while OPEN exists → wait 20s, or POST `/analyze` yourself.
- Analyses vanish after you delete the analyzer pod → SQLite lives on `emptyDir` (expected).

### Stop analyzer only

```bash
kubectl -n nexops scale deploy/ai-analyzer --replicas=0
```

Bring it back: `kubectl -n nexops scale deploy/ai-analyzer --replicas=1`

---

## Stage 8 — NexOps Control Center

**What:** The existing React frontend now has `/store` and `/ops`. The control center polls detector and analyzer through nginx, correlates rows by `incident_id`, and shows health, incidents, evidence, analysis, suggested action, confidence, decisions and recovery.

**Safety boundary:** Approve/Reject is UI state only. It does **not** modify Kubernetes. Stage 9 adds the allowlisted remediation API.

### Build and deploy

```bash
cd /storage/swarajt/nexops-ai-kubernetes-platform
docker build -t nexops/frontend:v2 ./frontend
docker save nexops/frontend:v2 | ctr -n k8s.io images import -
helm upgrade nexops ./helm/nexops -n nexops --reset-values
kubectl -n nexops rollout status deploy/frontend
kubectl -n nexops port-forward --address 0.0.0.0 svc/frontend 3000:80
```

Windows Chrome:

- Store: `http://10.245.101.134:3000/store`
- Control Center: `http://10.245.101.134:3000/ops`

### Acceptance test

```bash
# Healthy: /ops shows all three services healthy.

# Pod-level failure:
helm upgrade nexops ./helm/nexops -n nexops --reset-values \
  -f helm/nexops/failures/oom.yaml
# Wait 30-45s: /ops shows OOMKilled then increase_memory.

# Recover and wait for OPEN to clear:
helm upgrade nexops ./helm/nexops -n nexops --reset-values
kubectl -n nexops rollout status deploy/payment-api

# Ready-but-failing application mode:
helm upgrade nexops ./helm/nexops -n nexops --reset-values \
  -f helm/nexops/failures/errors.yaml
# payment-api remains 1/1 but /ops must show HighErrorRate then reset_failure_mode.

# Leave healthy:
helm upgrade nexops ./helm/nexops -n nexops --reset-values
```

### Troubleshooting

```bash
kubectl -n nexops exec deploy/frontend -- wget -qO- http://127.0.0.1/ops-api/detector/incidents
kubectl -n nexops exec deploy/frontend -- wget -qO- http://127.0.0.1/ops-api/analyzer/analyses
kubectl -n nexops logs deploy/frontend --tail=80
```

---

## Stage 9 — Allowlisted remediation

**What:** `/ops` now persists Approve/Reject decisions through the remediation service. Approved actions are revalidated against the current OPEN incident and matching analysis before any Kubernetes write.

Allowlisted actions: `increase_memory`, `restart_deployment`, `fix_image_tag`, and `reset_failure_mode`. The only target is `payment-api`; memory is capped at 512Mi. Unknown actions, targets, resolved incidents, and stale analyses fail closed. Recovery succeeds only after the Deployment is ready, `/fail/status` is healthy, and the detector marks the incident RESOLVED.

```bash
docker build -t nexops/remediation:v1 ./remediation
docker build -t nexops/frontend:v3 ./frontend
docker save nexops/remediation:v1 nexops/frontend:v3 | ctr -n k8s.io images import -
helm upgrade nexops ./helm/nexops -n nexops --reset-values

kubectl -n nexops rollout status deploy/remediation
kubectl -n nexops exec deploy/frontend -- wget -qO- http://127.0.0.1/ops-api/remediation/health
kubectl -n nexops exec deploy/frontend -- wget -qO- http://127.0.0.1/ops-api/remediation/remediations
```

Acceptance verified on 2026-08-27: `HighErrorRate → reset_failure_mode`, decision `approved`, status `succeeded`, incident `RESOLVED`, and `failure_mode_env=none`.

Important: direct remediation fixes the workload but does not rewrite Helm's stored failure-overlay values. Helm 4 server-side apply also sees the direct patch as another field owner. After a remediation demo, reconcile with:

```bash
helm upgrade nexops ./helm/nexops -n nexops --reset-values --force-conflicts
```

Security note: this chart creates a Role limited to get/patch `deployment/payment-api`. The POC also has a pre-existing operator ClusterRoleBinding that grants all service accounts broader Deployment rights. RBAC is additive, so the chart Role cannot hide that extra access. Stage 10 turns off API tokens on store pods and keeps NexOps Roles least-privilege. Do not delete the operator ClusterRoleBinding on this shared POC.

---

## Stage 10 — Kubernetes security

**What:** Dedicated ServiceAccounts, namespace Roles, and pod security for every NexOps workload. Analyzer stays read-only. Remediation stays named `payment-api` get/patch only.

```bash
cd /storage/swarajt/nexops-ai-kubernetes-platform
helm upgrade nexops ./helm/nexops -n nexops --reset-values --force-conflicts
kubectl -n nexops get role,rolebinding,sa
kubectl -n nexops exec deploy/payment-api -- ls /var/run/secrets/kubernetes.io/serviceaccount 2>&1 || true
```

Store pods must not mount a serviceaccount token. Analyzer Role is get/list only. Remediation Role is get/patch on deployment/payment-api. Frontend nginx still runs as root on port 80; Python apps are uid 10001.

---

## What is running now (after Stage 10)

- Helm `nexops` chart `0.7.0`: frontend `v3`, incident-detector `v2`, ai-analyzer `v2`, remediation `v1`, tokenless store ServiceAccounts.
- Helm `nexops-loki` in `nexops-monitoring`.
- Grafana: **http://10.245.101.134:3300** (not NodePort 2400).
Leave payment-api healthy unless you are demonstrating a failure.
