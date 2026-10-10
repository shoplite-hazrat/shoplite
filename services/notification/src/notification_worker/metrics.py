from prometheus_client import Counter, Histogram

# result: sent | duplicate | retry | poison | dead_lettered
EVENTS_PROCESSED = Counter(
    "notification_events_processed_total", "Order events handled, by outcome", ["result"]
)

PROCESSING_DURATION = Histogram(
    "notification_event_processing_seconds",
    "Time to handle one event, including sending the email",
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
)
