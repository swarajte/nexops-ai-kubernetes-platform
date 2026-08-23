from app.classify import classify_pod, fingerprint


def _pod(**kwargs):
    return {
        "metadata": {
            "name": kwargs.get("name", "payment-api-abc"),
            "labels": {"app.kubernetes.io/component": kwargs.get("service", "payment-api")},
            "deletionTimestamp": kwargs.get("deletionTimestamp"),
        },
        "status": {
            "phase": kwargs.get("phase", "Running"),
            "containerStatuses": kwargs.get("containerStatuses", []),
        },
    }


def test_oom():
    pod = _pod(
        containerStatuses=[
            {
                "ready": False,
                "state": {"waiting": {"reason": "CrashLoopBackOff"}},
                "lastState": {"terminated": {"reason": "OOMKilled"}},
            }
        ]
    )
    found = classify_pod(pod)
    assert found is not None
    assert found.problem == "OOMKilled"
    assert found.service == "payment-api"
    assert fingerprint(found) == "payment-api:OOMKilled"


def test_crashloop_without_oom():
    pod = _pod(
        containerStatuses=[
            {
                "ready": False,
                "state": {"waiting": {"reason": "CrashLoopBackOff"}},
                "lastState": {"terminated": {"reason": "Error", "exitCode": 1}},
            }
        ]
    )
    found = classify_pod(pod)
    assert found is not None
    assert found.problem == "CrashLoopBackOff"


def test_image_pull():
    pod = _pod(
        phase="Pending",
        containerStatuses=[{"ready": False, "state": {"waiting": {"reason": "ImagePullBackOff"}}}],
    )
    found = classify_pod(pod)
    assert found is not None
    assert found.problem == "ImagePullBackOff"


def test_not_ready():
    pod = _pod(
        containerStatuses=[
            {"ready": False, "state": {"running": {"startedAt": "2026-01-01T00:00:00Z"}}}
        ]
    )
    found = classify_pod(pod)
    assert found is not None
    assert found.problem == "NotReady"


def test_healthy_none():
    pod = _pod(
        containerStatuses=[
            {"ready": True, "state": {"running": {"startedAt": "2026-01-01T00:00:00Z"}}}
        ]
    )
    assert classify_pod(pod) is None


def test_skip_deleting():
    pod = _pod(
        deletionTimestamp="2026-01-01T00:00:00Z",
        containerStatuses=[{"ready": False, "state": {"waiting": {"reason": "CrashLoopBackOff"}}}],
    )
    assert classify_pod(pod) is None


def test_crash_error_before_backoff():
    pod = _pod(
        containerStatuses=[
            {
                "ready": False,
                "restartCount": 2,
                "state": {"terminated": {"reason": "Error", "exitCode": 1}},
            }
        ]
    )
    found = classify_pod(pod)
    assert found is not None
    assert found.problem == "CrashLoopBackOff"
