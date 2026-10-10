import logging
import time
import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import JSONResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from .catalog_client import CatalogUnavailable, InsufficientStock, ProductNotFound
from .logging_setup import request_id_var
from .metrics import HTTP_DURATION
from .service import OrderLine, OrderService

log = logging.getLogger("order_service.access")


class ApiModel(BaseModel):
    """camelCase on the wire, snake_case in Python."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, from_attributes=True)


class OrderLineIn(ApiModel):
    product_id: uuid.UUID
    quantity: int = Field(ge=1, le=1000)


class CreateOrderIn(ApiModel):
    customer_email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", max_length=254)
    items: list[OrderLineIn] = Field(min_length=1, max_length=50)


class OrderItemOut(ApiModel):
    product_id: uuid.UUID
    product_name: str
    unit_price_cents: int
    quantity: int


class OrderOut(ApiModel):
    id: uuid.UUID
    customer_email: str
    status: str
    total_cents: int
    created_at: datetime
    items: list[OrderItemOut]


class OrderListOut(ApiModel):
    items: list[OrderOut]


def _service(request: Request) -> OrderService:
    return request.app.state.order_service


orders = APIRouter(prefix="/v1/orders", tags=["orders"])


@orders.post("", status_code=201, response_model=OrderOut)
async def create_order(body: CreateOrderIn, request: Request, response: Response):
    order = await _service(request).place_order(
        body.customer_email,
        [OrderLine(product_id=i.product_id, quantity=i.quantity) for i in body.items],
    )
    response.headers["location"] = f"/v1/orders/{order.id}"
    return order


@orders.get("/{order_id}", response_model=OrderOut)
async def get_order(order_id: uuid.UUID, request: Request):
    order = await request.app.state.repo.get(order_id)
    if order is None:
        raise HTTPException(404, f"order {order_id} not found")
    return order


@orders.get("", response_model=OrderListOut)
async def list_orders(
    request: Request,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    return {"items": await request.app.state.repo.list(limit, offset)}


ops = APIRouter(include_in_schema=False)


@ops.get("/healthz")
async def healthz():
    # Liveness: never check dependencies here.
    return {"status": "ok"}


@ops.get("/readyz")
async def readyz(request: Request):
    if request.app.state.shutting_down:
        return JSONResponse({"status": "shutting_down"}, status_code=503)
    try:
        await request.app.state.repo.ping()
    except Exception:
        log.warning("readiness check failed", exc_info=True)
        return JSONResponse({"status": "database_unavailable"}, status_code=503)
    # NATS is deliberately not checked: the outbox keeps orders working without it.
    return {"status": "ready"}


@ops.get("/metrics")
async def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


QUIET_PATHS = {"/healthz", "/readyz", "/metrics"}


def build_app(lifespan=None) -> FastAPI:
    """Builds the HTTP app. Dependencies (repo, order_service) live on app.state,
    set by the production lifespan or directly by tests."""
    app = FastAPI(title="ShopLite order-service", version="0.1.0", lifespan=lifespan)
    app.state.shutting_down = False
    app.include_router(orders)
    app.include_router(ops)

    @app.middleware("http")
    async def observe(request: Request, call_next):
        request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
        token = request_id_var.set(request_id)
        start = time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            response.headers["x-request-id"] = request_id
            return response
        finally:
            elapsed = time.perf_counter() - start
            # Route template, not raw path, to keep metric cardinality bounded.
            route = getattr(request.scope.get("route"), "path", "unmatched")
            if route != "/metrics":
                HTTP_DURATION.labels(request.method, route, str(status)).observe(elapsed)
            if request.url.path not in QUIET_PATHS:
                log.info(
                    "request completed",
                    extra={
                        "method": request.method,
                        "path": request.url.path,
                        "status": status,
                        "duration_ms": round(elapsed * 1000, 1),
                    },
                )
            request_id_var.reset(token)

    @app.exception_handler(ProductNotFound)
    async def _not_found(request: Request, exc: ProductNotFound):
        return JSONResponse({"detail": str(exc)}, status_code=422)

    @app.exception_handler(InsufficientStock)
    async def _no_stock(request: Request, exc: InsufficientStock):
        return JSONResponse({"detail": str(exc)}, status_code=409)

    @app.exception_handler(CatalogUnavailable)
    async def _unavailable(request: Request, exc: CatalogUnavailable):
        return JSONResponse(
            {"detail": "catalog temporarily unavailable"},
            status_code=503,
            headers={"retry-after": "2"},
        )

    return app
