import json
import logging

from aio_pika import Message, DeliveryMode
from aio_pika.abc import AbstractIncomingMessage

from mediride_common.events.broker import RabbitMQBroker
from mediride_common.events.constants import Exchanges
from mediride_common.events.schemas import EventEnvelope
from mediride_common.exceptions import RetryableError

logger = logging.getLogger(__name__)


class BaseEventConsumer:
    """Base consumer with retry and dead letter queue support."""

    MAX_RETRIES = 3
    QUEUE_NAME: str = ""

    def __init__(self, broker: RabbitMQBroker):
        self.broker = broker

    async def setup_queue(
        self,
        queue_name: str,
        exchange_name: str,
        routing_keys: list[str],
    ) -> None:
        """Declare queue and bind to exchange with routing keys."""
        dlx_exchange = self.broker.get_exchange(Exchanges.DLX)

        queue = await self.broker.channel.declare_queue(
            queue_name,
            durable=True,
            arguments={
                "x-dead-letter-exchange": Exchanges.DLX,
            },
        )

        exchange = self.broker.get_exchange(exchange_name)
        for key in routing_keys:
            await queue.bind(exchange, routing_key=key)

        await queue.consume(self.process_message)
        logger.info(
            f"Consumer setup: queue={queue_name}, "
            f"exchange={exchange_name}, keys={routing_keys}"
        )

    async def process_message(self, message: AbstractIncomingMessage) -> None:
        retry_count = int(message.headers.get("x-retry-count", 0))

        try:
            envelope = EventEnvelope.model_validate_json(message.body)
            logger.info(
                f"Processing event: {envelope.event_type}",
                extra={
                    "event_id": str(envelope.event_id),
                    "event_type": envelope.event_type,
                    "retry_count": retry_count,
                },
            )
            await self.handle(envelope)
            await message.ack()

        except RetryableError as e:
            if retry_count < self.MAX_RETRIES:
                logger.warning(
                    f"Retryable error (attempt {retry_count + 1}): {e}",
                )
                await self._republish_with_retry(message, retry_count + 1)
                await message.ack()
            else:
                logger.error(f"Max retries exceeded: {e}")
                await self._send_to_dlq(message, str(e))
                await message.ack()

        except Exception as e:
            logger.error(f"Non-retryable error: {e}", exc_info=True)
            await self._send_to_dlq(message, str(e))
            await message.ack()

    async def _republish_with_retry(
        self, original: AbstractIncomingMessage, retry_count: int
    ) -> None:
        """Republish message with incremented retry count."""
        headers = dict(original.headers or {})
        headers["x-retry-count"] = retry_count

        new_message = Message(
            body=original.body,
            content_type=original.content_type,
            delivery_mode=DeliveryMode.PERSISTENT,
            correlation_id=original.correlation_id,
            headers=headers,
        )

        # Republish to same exchange with same routing key
        exchange_name = original.exchange
        if exchange_name:
            exchange = self.broker.get_exchange(exchange_name)
            await exchange.publish(
                new_message, routing_key=original.routing_key or ""
            )

    async def _send_to_dlq(
        self, original: AbstractIncomingMessage, error: str
    ) -> None:
        """Send failed message to dead letter queue."""
        headers = dict(original.headers or {})
        headers["x-error"] = error
        headers["x-original-exchange"] = original.exchange or ""
        headers["x-original-routing-key"] = original.routing_key or ""

        dlq_message = Message(
            body=original.body,
            content_type=original.content_type,
            delivery_mode=DeliveryMode.PERSISTENT,
            headers=headers,
        )

        dlx = self.broker.get_exchange(Exchanges.DLX)
        await dlx.publish(dlq_message, routing_key="")

    async def handle(self, envelope: EventEnvelope) -> None:
        """Override in subclass to handle specific event types."""
        raise NotImplementedError
