# Failure experiments (one at a time)

**You run these. Do not apply two overlays at once.** After each experiment, recover to healthy before the next one.

Workdir on POC:

```bash
cd /storage/swarajt/nexops-ai-kubernetes-platform
```

GitHub: `nexops-ai-kubernetes-platform`.  
Helm 4: always include `--reset-values` when you apply a `-f` overlay, or the previous failure sticks.

---

## What we are observing

```
You apply one failure (Helm)
        ↓
Kubernetes shows a pod symptom (or the app stays Ready but misbehaves)
        ↓
Incident detector (every ~10s) opens an incident JSON
        ↓
AI analyzer (every ~20s) writes an analysis JSON (rules, not ChatGPT)
        ↓
You recover (--reset-values)
        ↓
Detector should mark that incident RESOLVED (pod/app healthy again)
```

Detector: `http://incident-detector:8080` (port **8080**).  
Analyzer: `http://ai-analyzer:8081` (port **8081**).  
Both only **read**. They do not fix the cluster.

### What you should see (mapping)

| # | Overlay file | Expected detector `problem` | Expected analyzer `suggested_action.type` |
|---|--------------|-----------------------------|-------------------------------------------|
| 1 | `oom.yaml` | `OOMKilled` (sometimes `NotReady` first) | `increase_memory` if OOM; `reset_failure_mode` if only NotReady |
| 2 | `crash.yaml` | `CrashLoopBackOff` | `restart_deployment` |
| 3 | `imagepull.yaml` | `ImagePullBackOff` | `fix_image_tag` |
| 4 | `ready.yaml` | `NotReady` | `reset_failure_mode` |
| 5 | `cpu.yaml` | `HighCpu` (pod often 1/1 Ready) | `reset_failure_mode` |
| 6 | `memory.yaml` | `HighMemory` (pod often 1/1 Ready) | `reset_failure_mode` |
| 7 | `slow.yaml` | `SlowRequests` | `reset_failure_mode` |
| 8 | `errors.yaml` | `HighErrorRate` | `reset_failure_mode` |

Wait **30–45 seconds** after each overlay (detector 10s, analyzer 20s, OOM/crash can take longer).

---

## One-time: are the platform pods up?

```bash
kubectl -n nexops get pods
kubectl -n nexops rollout status deploy/incident-detector
kubectl -n nexops rollout status deploy/ai-analyzer
```

Expect store + `incident-detector` + `ai-analyzer` all `1/1`.

Optional Windows Chrome (run on **POC**, leave running):

```bash
kubectl -n nexops port-forward --address 0.0.0.0 svc/incident-detector 8080:8080
kubectl -n nexops port-forward --address 0.0.0.0 svc/ai-analyzer 8081:8081
```

Then: http://10.245.101.134:8080/incidents?status=OPEN  
and http://10.245.101.134:8081/analyses  

Not `localhost` on your laptop unless you also SSH-tunnel.

---

## Commands you reuse every experiment

**A — apply one failure** (example uses oom; change the file for 2–8):

```bash
helm upgrade nexops ./helm/nexops -n nexops --reset-values -f helm/nexops/failures/oom.yaml
```

**B — look at the pod**

```bash
kubectl -n nexops get pods -l app.kubernetes.io/component=payment-api
kubectl -n nexops get events --sort-by='.lastTimestamp' | tail -20
```

**C — wait, then incident detector**

```bash
sleep 35
kubectl -n nexops exec deploy/incident-detector -- python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8080/incidents?status=OPEN').read().decode())"
```

**D — AI analyzer**

```bash
kubectl -n nexops exec deploy/ai-analyzer -- python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8081/analyses').read().decode())"
```

If OPEN exists but analyses has no row for that `id`, wait another 20s, or POST (replace `INCIDENT_ID`):

```bash
kubectl -n nexops exec deploy/ai-analyzer -- python -c "import json,urllib.request; req=urllib.request.Request('http://127.0.0.1:8081/analyze', data=json.dumps({'incident_id':'INCIDENT_ID'}).encode(), headers={'Content-Type':'application/json'}, method='POST'); print(urllib.request.urlopen(req).read().decode())"
```

**E — recover (always)**

```bash
helm upgrade nexops ./helm/nexops -n nexops --reset-values
kubectl -n nexops rollout status deploy/payment-api
sleep 15
kubectl -n nexops exec deploy/incident-detector -- python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8080/incidents?status=OPEN').read().decode())"
```

Expect OPEN list empty (or no payment-api row). Then start the next overlay.

---

## The eight experiments (run in order)

### 1) OOMKilled — `helm/nexops/failures/oom.yaml`

Apply with **A** using `-f helm/nexops/failures/oom.yaml`.  
Watch: restart count, `OOMKilled` in describe.  
Detector: `OOMKilled`. Analyzer: `increase_memory`.

### 2) Crash — `helm/nexops/failures/crash.yaml`

Apply **A** with `crash.yaml`. Recover **E**.  
Detector: `CrashLoopBackOff`. Analyzer: `restart_deployment`.

### 3) Image pull — `helm/nexops/failures/imagepull.yaml`

Apply **A** with `imagepull.yaml`. Recover **E**.  
Detector: `ImagePullBackOff`. Analyzer: `fix_image_tag`.

### 4) Not ready — `helm/nexops/failures/ready.yaml`

Apply **A** with `ready.yaml`. Recover **E**.  
Pod often `0/1 Running` (alive, not taking traffic).  
Detector: `NotReady`. Analyzer: `reset_failure_mode`.

### 5) CPU — `helm/nexops/failures/cpu.yaml`

Apply **A** with `cpu.yaml`. Recover **E**.  
Pod may stay `1/1 Ready`. Detector: `HighCpu` (from `/fail/status`). Analyzer: `reset_failure_mode`.

### 6) Extra memory (not OOM) — `helm/nexops/failures/memory.yaml`

Apply **A** with `memory.yaml`. Recover **E**.  
Detector: `HighMemory`. Analyzer: `reset_failure_mode`.

### 7) Slow — `helm/nexops/failures/slow.yaml`

Apply **A** with `slow.yaml`. Recover **E**.  
Detector: `SlowRequests`. Analyzer: `reset_failure_mode`.

### 8) HTTP errors — `helm/nexops/failures/errors.yaml`

Apply **A** with `errors.yaml`. Recover **E**.  
Detector: `HighErrorRate`. Analyzer: `reset_failure_mode`.

---

## Observation log (POC, 2026-08-26)

All eight overlays run **one at a time** from a healthy cluster (`helm get values` null, OPEN empty). Recover after each: `helm upgrade nexops ./helm/nexops -n nexops --reset-values`. Cluster left **healthy** (revision 65, payment-api 1/1, OPEN `[]`).

| # | Overlay | Pod when captured | Detector `problem` | Analyzer `suggested_action.type` | Match |
|---|---------|-------------------|--------------------|----------------------------------|-------|
| 1 | oom | restarting / OOM | `OOMKilled` | `increase_memory` | yes |
| 2 | crash | CrashLoop | `CrashLoopBackOff` | `restart_deployment` | yes |
| 3 | imagepull | ImagePullBackOff (old replica can stay 1/1) | `ImagePullBackOff` | `fix_image_tag` | yes |
| 4 | ready | `0/1 Running` | `NotReady` | `reset_failure_mode` | yes |
| 5 | cpu | `1/1 Running` | `HighCpu` | `reset_failure_mode` | yes |
| 6 | memory | `1/1 Running` | `HighMemory` | `reset_failure_mode` | yes |
| 7 | slow | `1/1 Running` | `SlowRequests` | `reset_failure_mode` | yes |
| 8 | errors | `1/1 Running` | `HighErrorRate` | `reset_failure_mode` | yes |

**7 slow (15:21 UTC+3 / 12:22 UTC):** pod `payment-api-6b75d845b7-8bswz` 1/1, `/fail/status` `failure_mode_env=slow`. OPEN id `879b9090-23f6-4155-910a-2c02bc318682`. Analyzer matched that id: `reset_failure_mode`, confidence 85, source `rules`. OPEN empty after recover.

**8 errors (15:24 UTC+3 / 12:24 UTC):** pod `payment-api-dd884777c-m62br` 1/1, `/fail/status` `error_rate=0.8`. OPEN id `2e6cb3aa-926c-4b2f-9b1a-f733f09469ae`. Analyzer matched that id: `reset_failure_mode`, confidence 85, source `rules`. OPEN empty after recover.

### Timing / race notes (Stage 8 must handle these)

- Empty OPEN on a **healthy** cluster is correct. Query only after an overlay + 30–45s.
- Helm rollout can show **two payment-api pods**. Detector attaches to the **broken** replica; UI should list replicas and highlight the failing one.
- Analyzer SQLite is history: **latest analysis ≠ current OPEN**. Match on `incident_id`.
- Analyzer poll ~20s. If OPEN exists with no matching analysis, wait or `POST /analyze`.
- App-level modes (cpu/memory/slow/errors) stay **Ready**. Control center must show detector `problem`, not assume CrashLoop/OOM from kubectl Ready.
- Wait until OPEN is empty after `--reset-values` before the next overlay, or fingerprints linger.
- OOM can briefly look like CrashLoop until `OOMKilled` is recorded.

### Stage 8 control-center implications

Show **incident then analysis** (not pod status alone). Primary row: service, problem, status, pod, suggested_action. Secondary: evidence, confidence, source. Recover is always `--reset-values` until Stage 9 applies remediations.

---

## If something looks wrong

```bash
kubectl -n nexops logs deploy/incident-detector --tail=40
kubectl -n nexops logs deploy/ai-analyzer --tail=40
```

- Empty OPEN while the pod is clearly broken → wait 10–20s more.  
- OPEN but no analysis → wait 20s or POST `/analyze`.  
- Overlay “still on” after a new helm upgrade → you forgot `--reset-values`.
