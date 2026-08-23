from app.app_signals import classify_fail_status


def test_errors_mode():
    found = classify_fail_status({"failure_mode_env": "errors", "error_rate": 0.8, "ready": True})
    assert found is not None
    assert found.problem == "HighErrorRate"
    assert found.service == "payment-api"


def test_cpu_flag():
    found = classify_fail_status({"failure_mode_env": "none", "cpu": True})
    assert found is not None
    assert found.problem == "HighCpu"


def test_healthy():
    assert (
        classify_fail_status(
            {
                "failure_mode_env": "none",
                "ready": True,
                "slow_seconds": 0,
                "error_rate": 0,
                "cpu": False,
                "memory_blocks": 0,
            }
        )
        is None
    )
