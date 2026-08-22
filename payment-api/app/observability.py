import logging
import time

from prometheus_fastapi_instrumentator import Instrumentator
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

SKIP_LOG_PATHS = {"/health", "/ready", "/metrics"}


def setup_logging(service: str) -> logging.Logger:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s level=%(levelname)s service=" + service + " %(message)s",
    )
    return logging.getLogger(service)


def setup_metrics(app) -> None:
    Instrumentator(
        should_group_status_codes=True,
        excluded_handlers=["/health", "/ready", "/metrics"],
    ).instrument(app).expose(app, include_in_schema=False)


class RequestLogMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, logger: logging.Logger):
        super().__init__(app)
        self.logger = logger

    async def dispatch(self, request: Request, call_next) -> Response:
        start = time.perf_counter()
        response = await call_next(request)
        if request.url.path not in SKIP_LOG_PATHS:
            duration_ms = (time.perf_counter() - start) * 1000
            self.logger.info(
                "request method=%s path=%s status=%s duration_ms=%.1f",
                request.method,
                request.url.path,
                response.status_code,
                duration_ms,
            )
        return response
