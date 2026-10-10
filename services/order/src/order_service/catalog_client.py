import asyncio
import logging
import uuid
from dataclasses import dataclass

import httpx

from .logging_setup import request_id_var

log = logging.getLogger(__name__)


class CatalogError(Exception):
    pass


class ProductNotFound(CatalogError):
    def __init__(self, product_id: uuid.UUID) -> None:
        super().__init__(f"product {product_id} not found")
        self.product_id = product_id


class InsufficientStock(CatalogError):
    def __init__(self, product_id: uuid.UUID) -> None:
        super().__init__(f"insufficient stock for product {product_id}")
        self.product_id = product_id


class CatalogUnavailable(CatalogError):
    pass


@dataclass(frozen=True)
class Product:
    id: uuid.UUID
    name: str
    price_cents: int


class CatalogClient:
    """HTTP client for catalog-service with timeouts and bounded retries.

    Retrying POSTs is only safe because reserve and release are idempotent per
    order id on the catalog side. Never retry a non-idempotent call blindly.
    """

    def __init__(
        self,
        base_url: str,
        *,
        timeout_seconds: float,
        retries: int,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._retries = retries
        self._http = httpx.AsyncClient(
            base_url=base_url, timeout=timeout_seconds, transport=transport
        )

    async def aclose(self) -> None:
        await self._http.aclose()

    async def _request(self, method: str, path: str, json: dict | None = None) -> httpx.Response:
        headers = {}
        if request_id := request_id_var.get():
            headers["x-request-id"] = request_id

        for attempt in range(self._retries + 1):
            try:
                response = await self._http.request(method, path, json=json, headers=headers)
                if response.status_code < 500:
                    return response
                reason = f"HTTP {response.status_code}"
            except httpx.TransportError as exc:  # connect errors and timeouts
                reason = f"{type(exc).__name__}: {exc}"

            log.warning(
                "catalog request failed",
                extra={"method": method, "path": path, "attempt": attempt + 1, "reason": reason},
            )
            if attempt < self._retries:
                await asyncio.sleep(0.1 * 2**attempt)  # exponential backoff

        raise CatalogUnavailable(f"catalog {method} {path} failed: {reason}")

    async def get_product(self, product_id: uuid.UUID) -> Product:
        response = await self._request("GET", f"/v1/products/{product_id}")
        if response.status_code == 404:
            raise ProductNotFound(product_id)
        response.raise_for_status()
        body = response.json()
        return Product(id=uuid.UUID(body["id"]), name=body["name"], price_cents=body["priceCents"])

    async def reserve(self, product_id: uuid.UUID, order_id: uuid.UUID, quantity: int) -> None:
        response = await self._request(
            "POST",
            f"/v1/products/{product_id}/reserve",
            json={"orderId": str(order_id), "quantity": quantity},
        )
        if response.status_code == 404:
            raise ProductNotFound(product_id)
        if response.status_code == 409:
            raise InsufficientStock(product_id)
        response.raise_for_status()

    async def release(self, product_id: uuid.UUID, order_id: uuid.UUID) -> None:
        response = await self._request(
            "POST", f"/v1/products/{product_id}/release", json={"orderId": str(order_id)}
        )
        if response.status_code != 404:
            response.raise_for_status()
