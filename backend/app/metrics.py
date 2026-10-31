import time

from prometheus_client import Counter, Histogram, Gauge
from starlette.middleware.base import BaseHTTPMiddleware

HTTP_REQ = Counter("redalimenta_http_requests_total", "Solicitudes HTTP", ["method", "route", "status"])
HTTP_LAT = Histogram("redalimenta_http_request_duration_seconds", "Duración de solicitudes", ["method", "route"],
                     buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5))
DEP_UP = Gauge("redalimenta_dependency_up", "Salud de dependencias vista por la app", ["dependency"])
OUTBOX_PEND = Gauge("redalimenta_outbox_pendientes", "Eventos outbox sin publicar")
OUTBOX_PUB = Counter("redalimenta_outbox_publicados_total", "Eventos publicados en MongoDB")
OUTBOX_ERR = Counter("redalimenta_outbox_errores_total", "Errores al publicar en MongoDB")


class MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        t0 = time.perf_counter()
        status = 500
        try:
            resp = await call_next(request)
            status = resp.status_code
            return resp
        finally:
            route = request.scope.get("route")
            path = getattr(route, "path", "sin_ruta")
            HTTP_REQ.labels(request.method, path, str(status)).inc()
            HTTP_LAT.labels(request.method, path).observe(time.perf_counter() - t0)
