# notification-worker

Consumes `orders.created` events from NATS JetStream and sends order confirmation emails over SMTP. Python 3.14, nats-py, aiosmtplib, PostgreSQL.

It has no business API. Port 8001 serves only `/healthz`, `/readyz` and `/metrics`.

## Message handling

```
ORDERS stream (owned by order-service)
  durable pull consumer "notification-worker"   (explicit ack, ack_wait 30s)
    parse event
      malformed:  copy to DLQ stream, term            (poison: never retry)
    claim event_id in processed_events            (same DB transaction as the send)
      already processed:  ack                     (duplicate: no 2nd email)
    send email over SMTP
      ok:      commit claim, ack
      failure: roll back claim, nak(delay = 2^attempt s, max 60s)
               on the final attempt (MAX_DELIVER): copy to DLQ, term
```

- **Durable pull consumer.** JetStream stores the consumer's position, so restarts and deploys resume where they stopped. To scale out, add replicas: they all pull from the same consumer and share the messages.
- **Idempotent consumer ("inbox").** At-least-once delivery means duplicates *will* happen (redelivery after a crash, a re-sent outbox batch). The `processed_events` primary key makes each event send at most one email, even with several replicas.
- **Retries with backoff, then a dead-letter queue.** Transient failures are retried with increasing delays. A message that keeps failing, or can never succeed (poison), is moved to the `DLQ` stream (`dlq.notification-worker.orders.created`, with an error header) so it doesn't block or loop. Alert on `notification_events_processed_total{result="dead_lettered"}`.
- **Liveness checks the consume loop.** If the loop stops ticking for `LIVENESS_STALE_SECONDS`, `/healthz` fails and Kubernetes restarts the pod. Readiness requires NATS and Postgres.
- **Startup order doesn't matter.** If the stream doesn't exist yet, the worker reports not-ready and keeps retrying.

Inspect or replay dead letters with the NATS CLI:

```bash
nats stream view DLQ
nats stream get DLQ 1
```

## Configuration

| Variable | Default | Notes |
|---|---|---|
| `DATABASE_URL` | required | `postgres://user:pass@host:5432/notifications` |
| `NATS_URL` | `nats://nats:4222` | |
| `SMTP_HOST` / `SMTP_PORT` | unset / `1025` | Unset means dry-run (emails are only logged). Use Mailpit for dev |
| `MAIL_FROM` | `ShopLite <orders@shoplite.local>` | |
| `MAX_DELIVER` | `5` | Attempts before dead-lettering |
| `ACK_WAIT_SECONDS` | `30` | Redelivery timeout if the worker dies mid-message |
| `BATCH_SIZE` | `10` | Messages per fetch |
| `LIVENESS_STALE_SECONDS` | `60` | |
| `PORT` / `LOG_LEVEL` | `8001` / `INFO` | |

## Develop

```bash
uv sync
uv run ruff check . && uv run ruff format --check . && uv run pytest
DATABASE_URL=postgres://... uv run alembic upgrade head
DATABASE_URL=postgres://... SMTP_HOST=localhost uv run python -m notification_worker
```

## Container

```bash
docker build -t shoplite/notification:dev .
docker run --rm -e DATABASE_URL=... shoplite/notification:dev alembic upgrade head
docker run --rm -e DATABASE_URL=... -e NATS_URL=... -e SMTP_HOST=... shoplite/notification:dev
```
