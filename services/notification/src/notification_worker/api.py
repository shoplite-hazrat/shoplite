import logging
import time

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

log = logging.getLogger(__name__)


def build_app(lifespan=None, *, liveness_stale_seconds: int = 60) -> FastAPI:
    """Ops endpoints only. app.state.consumer / app.state.store are set by the
    production lifespan or directly by tests."""
    app = FastAPI(title="ShopLite notification-worker", lifespan=lifespan, docs_url=None)
    app.state.shutting_down = False

    @app.get("/healthz")
    async def healthz(request: Request):
        # A worker has no requests to fail, so liveness checks the loop itself:
        # if it stopped ticking it is hung, and a restart is the right fix.
        age = time.monotonic() - request.app.state.consumer.last_tick
        if age > liveness_stale_seconds:
            return JSONResponse({"status": "stuck", "last_tick_s": round(age)}, status_code=503)
        return {"status": "ok"}

    @app.get("/readyz")
    async def readyz(request: Request):
        if request.app.state.shutting_down:
            return JSONResponse({"status": "shutting_down"}, status_code=503)
        if not request.app.state.consumer.ready:
            return JSONResponse({"status": "nats_unavailable"}, status_code=503)
        try:
            await request.app.state.store.ping()
        except Exception:
            log.warning("readiness check failed", exc_info=True)
            return JSONResponse({"status": "database_unavailable"}, status_code=503)
        return {"status": "ready"}

    @app.get("/metrics")
    async def metrics():
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    return app
