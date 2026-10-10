import pytest
from conftest import MAX_DELIVER, FakeMsg, order_created_event

pytestmark = pytest.mark.anyio


async def test_sends_confirmation_and_acks(handler, mailer, store):
    msg = FakeMsg(order_created_event())
    await handler.handle(msg)

    assert msg.outcome == "ack"
    [(to, subject, body)] = mailer.sent
    assert to == "ada@example.com"
    assert "is confirmed" in subject
    assert "2 x Mug @ $9.99" in body
    assert "Total: $44.97" in body
    assert len(store.processed) == 1


async def test_duplicate_event_is_acked_without_second_email(handler, mailer):
    data = order_created_event("11111111-1111-1111-1111-111111111111")
    first, redelivered = FakeMsg(data), FakeMsg(data, attempt=2)

    await handler.handle(first)
    await handler.handle(redelivered)

    assert redelivered.outcome == "ack"
    assert len(mailer.sent) == 1


async def test_transient_failure_naks_with_backoff_and_does_not_record(handler, mailer, store):
    mailer.failing = True
    msg = FakeMsg(order_created_event(), attempt=2)
    await handler.handle(msg)

    assert msg.outcome == "nak"
    assert msg.nak_delay == 4  # 2 ** attempt
    assert store.processed == set()  # claim rolled back, so a retry can send


async def test_retry_succeeds_after_transient_failure(handler, mailer):
    data = order_created_event()
    mailer.failing = True
    await handler.handle(FakeMsg(data, attempt=1))
    mailer.failing = False
    retry = FakeMsg(data, attempt=2)
    await handler.handle(retry)

    assert retry.outcome == "ack"
    assert len(mailer.sent) == 1


async def test_final_attempt_goes_to_dead_letter_queue(handler, mailer, dead_letters):
    mailer.failing = True
    msg = FakeMsg(order_created_event(), attempt=MAX_DELIVER)
    await handler.handle(msg)

    assert msg.outcome == "term"
    [(dead, reason)] = dead_letters.messages
    assert dead is msg
    assert "smtp down" in reason


@pytest.mark.parametrize(
    "data",
    [b"not json", b'{"id": "x"}', b'{"id": "x", "data": {"orderId": "y", "items": "nope"}}'],
)
async def test_poison_message_is_dead_lettered_immediately(handler, mailer, dead_letters, data):
    msg = FakeMsg(data, attempt=1)
    await handler.handle(msg)

    assert msg.outcome == "term"
    assert mailer.sent == []
    assert len(dead_letters.messages) == 1


async def test_backoff_is_capped(handler, mailer):
    mailer.failing = True
    handler._max_deliver = 100
    msg = FakeMsg(order_created_event(), attempt=10)
    await handler.handle(msg)
    assert msg.nak_delay == 60
