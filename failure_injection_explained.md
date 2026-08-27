# NexOps Failure Injection

## Overview

NexOps uses **controlled failure injection** to deliberately break the `payment-api` and test the complete incident lifecycle:

```text
Inject Failure
      ↓
Observe Symptoms
      ↓
Detect Incident
      ↓
Analyze Root Cause
      ↓
Remediate
```

These failures are intentional test scenarios, not real production failures.

---

## Failure Injection Architecture

There are two main ways failures are injected:

```text
                    Failure Injection
                           │
              ┌────────────┴────────────┐
              │                         │
       Kubernetes-level           Application-level
          injection                  injection
              │                         │
     ┌────────┴────────┐        FAILURE_MODE variable
     │                 │                 │
   OOMKilled       ImagePullBackOff       │
                                         │
                              ┌──────────┼──────────┐
                              │          │          │
                           crash       cpu        memory
                           ready       slow       errors
```

---

## 1. Failure Overlays

Failure scenarios are defined under:

```text
helm/nexops/failures/
```

Current scenarios:

```text
oom.yaml
imagepull.yaml
crash.yaml
ready.yaml
cpu.yaml
memory.yaml
slow.yaml
errors.yaml
```

A failure is injected using Helm:

```bash
helm upgrade nexops ./helm/nexops \
  -n nexops \
  --reset-values \
  -f helm/nexops/failures/<failure>.yaml
```

Example:

```bash
helm upgrade nexops ./helm/nexops \
  -n nexops \
  --reset-values \
  -f helm/nexops/failures/oom.yaml
```

To return to the normal configuration:

```bash
helm upgrade nexops ./helm/nexops \
  -n nexops \
  --reset-values
```

---

# 2. How Helm Injects the Failure

The important Helm template is:

```text
helm/nexops/templates/payment-api.yaml
```

The template consumes values from the failure overlay.

For example:

```yaml
env:
  - name: FAILURE_MODE
    value: {{ .Values.paymentApi.failureMode | quote }}
```

If the failure overlay contains:

```yaml
paymentApi:
  failureMode: cpu
```

Helm renders:

```yaml
env:
  - name: FAILURE_MODE
    value: "cpu"
```

The resulting environment variable is available inside the `payment-api` container:

```text
FAILURE_MODE=cpu
```

The application then reads this value and deliberately performs the corresponding failure behavior.

### Important

Helm does **not** directly create most of the application failures.

Helm mainly acts as the configuration layer:

```text
Failure YAML
     ↓
Helm Values
     ↓
Helm Template
     ↓
Kubernetes Deployment
     ↓
FAILURE_MODE environment variable
     ↓
payment-api
     ↓
Intentional failure
```

---

# 3. Kubernetes-Level Failure Injection

## OOMKilled

The OOM overlay contains:

```yaml
paymentApi:
  failureMode: oom
  resources:
    requests:
      cpu: 25m
      memory: 32Mi
    limits:
      cpu: 200m
      memory: 32Mi
```

Two things happen:

1. `FAILURE_MODE=oom` tells the application to keep allocating memory.
2. Kubernetes gives the container a very small memory limit of `32Mi`.

The result:

```text
payment-api allocates memory
        ↓
Memory usage exceeds 32Mi
        ↓
Kubernetes kills container
        ↓
OOMKilled
        ↓
Container restarts
```

This combines **application behavior + Kubernetes resource configuration**.

---

## ImagePullBackOff

The overlay changes the image tag:

```yaml
paymentApi:
  image:
    repository: nexops/payment-api
    tag: does-not-exist
    pullPolicy: Always
```

The Helm template produces an image such as:

```text
nexops/payment-api:does-not-exist
```

Kubernetes attempts to pull it:

```text
Image does not exist
        ↓
ErrImagePull
        ↓
ImagePullBackOff
```

The application never starts because the container image cannot be pulled.

---

# 4. Application-Level Failure Injection

For the remaining scenarios, the Helm overlay only changes:

```yaml
failureMode: <mode>
```

This becomes:

```text
FAILURE_MODE=<mode>
```

inside the container.

The actual failure behavior is implemented in:

```text
payment-api/app/fail.py
```

---

## CrashLoopBackOff

```yaml
failureMode: crash
```

The application immediately exits.

```text
Application starts
      ↓
FAILURE_MODE=crash
      ↓
Application exits
      ↓
Kubernetes restarts container
      ↓
Application exits again
      ↓
CrashLoopBackOff
```

---

## Readiness Failure

```yaml
failureMode: ready
```

The application deliberately marks itself as not ready.

The Deployment has a readiness probe:

```yaml
readinessProbe:
  httpGet:
    path: /ready
    port: http
```

Therefore:

```text
FAILURE_MODE=ready
      ↓
/ready fails
      ↓
Readiness probe fails
      ↓
Pod becomes NotReady
```

The container can still be running.

---

## High CPU

```yaml
failureMode: cpu
```

The application starts a CPU-burning background loop.

```text
FAILURE_MODE=cpu
      ↓
CPU-intensive loop
      ↓
CPU usage increases
```

The Pod can still remain:

```text
Running
Ready
```

because high CPU usage does not necessarily make Kubernetes mark the Pod unhealthy.

---

## High Memory

```yaml
failureMode: memory
```

The application deliberately allocates additional memory.

```text
FAILURE_MODE=memory
      ↓
Allocate extra memory
      ↓
Memory usage increases
```

Unlike the OOM scenario, the intention is to increase memory usage without necessarily exceeding the container's memory limit.

---

## Slow API

```yaml
failureMode: slow
```

The application deliberately delays `/pay` responses.

```text
Request
  ↓
/pay
  ↓
Artificial delay
  ↓
Response
```

This creates an application latency problem while the Pod may remain healthy from Kubernetes' perspective.

---

## High Error Rate

```yaml
failureMode: errors
```

The application sets a high payment error rate.

The current implementation uses approximately:

```text
80% error rate
```

Conceptually:

```text
Payment request
      ↓
Random decision
      ↓
~80% → error
~20% → success
```

This creates an application-level HTTP error problem without necessarily making the Kubernetes Pod unhealthy.

---

# 5. Complete Failure Matrix

| Failure           | What We Change                          | Who Creates the Failure?      | Typical Symptom            |
| ----------------- | --------------------------------------- | ----------------------------- | -------------------------- |
| OOMKilled         | `failureMode=oom` + memory limit `32Mi` | Application + Kubernetes      | `OOMKilled`                |
| ImagePullBackOff  | Invalid image tag                       | Kubernetes                    | `ImagePullBackOff`         |
| CrashLoopBackOff  | `failureMode=crash`                     | Application                   | `CrashLoopBackOff`         |
| Readiness failure | `failureMode=ready`                     | Application + readiness probe | `NotReady`                 |
| High CPU          | `failureMode=cpu`                       | Application                   | High CPU                   |
| High memory       | `failureMode=memory`                    | Application                   | High memory                |
| Slow API          | `failureMode=slow`                      | Application                   | High latency               |
| High errors       | `failureMode=errors`                    | Application                   | HTTP 500 / high error rate |

---

# 6. Important Kubernetes Concepts

The failure injection also demonstrates an important distinction:

```text
Running ≠ Ready
```

A Pod can be:

```text
Running
but
NotReady
```

For example:

```text
failureMode=ready
       ↓
 /ready returns failure
       ↓
readinessProbe fails
       ↓
Pod remains Running
       ↓
Pod becomes NotReady
```

Similarly, a Pod can be:

```text
Running
Ready
```

while the application is still experiencing:

* High CPU
* High memory
* High latency
* HTTP 500 errors

This is why NexOps eventually needs information from more than just Kubernetes Pod status.

---

# 7. Observability Perspective

The injected failures produce different types of evidence.

### Kubernetes state

Useful for:

```text
OOMKilled
CrashLoopBackOff
ImagePullBackOff
NotReady
```

### Prometheus metrics

Useful for:

```text
High CPU
High memory
High latency
Request/error rates
```

### Loki/application logs

Useful for:

```text
Application errors
Crash information
Request failures
Other application-level symptoms
```

The goal of NexOps is to bring these signals together:

```text
             Failure
                ↓
       ┌────────┼────────┐
       ↓        ↓        ↓
   Kubernetes Prometheus Loki
       │        │        │
       └────────┼────────┘
                ↓
        NexOps Detector
                ↓
        Incident Analysis
                ↓
          Remediation
```

---

# 8. Key Mental Model

The most important thing to remember:

> **Failure overlays configure the failure; the application or Kubernetes actually produces the failure.**

For application failures:

```text
failureMode
    ↓
Helm
    ↓
FAILURE_MODE
    ↓
payment-api
    ↓
intentional bad behavior
```

For Kubernetes failures:

```text
Helm
    ↓
Kubernetes configuration
    ↓
Kubernetes produces the failure
```

---

## One-Line Interview Explanation

> **NexOps uses Helm-based failure overlays to deliberately introduce controlled Kubernetes and application failures. Kubernetes-level failures are created through configuration changes such as memory limits or invalid images, while application failures are triggered through the `FAILURE_MODE` environment variable, allowing us to test NexOps's detection, analysis, and remediation pipeline.**

