from prometheus_client import Counter, Gauge, Histogram

HTTP_DURATION = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "route", "status_code"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5),
)

ORDERS_CREATED = Counter("orders_created_total", "Orders successfully placed")

EVENTS_PUBLISHED = Counter("outbox_events_published_total", "Outbox events published to NATS")

# Alert if this keeps growing: events are being stored but not delivered.
OUTBOX_PENDING = Gauge("outbox_pending_events", "Outbox events not yet published")
