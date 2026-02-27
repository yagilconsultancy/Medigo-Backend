import json
import logging

from aio_pika import Message, DeliveryMode

from mediride_common.events.broker import RabbitMQBroker
from mediride_common.events.schemas import EventEnvelope
from mediride_common.utils import generate_uuid, utc_now

logger = logging.getLogger(__name__)


class EventPublisher:
    def __init__(self, broker: RabbitMQBroker, source_service: str):
        self.broker = broker
        self.source_service = source_service

    async def publish(
        self,
        exchange_name: str,
        routing_key: str,
        payload: dict,
        correlation_id: str = "",
    ) -> None:
        envelope = EventEnvelope(
            event_id=generate_uuid(),
            event_type=routing_key,
            timestamp=utc_now(),
            correlation_id=correlation_id,
            source_service=self.source_service,
            payload=payload,
        )

        exchange = self.broker.get_exchange(exchange_name)
        message = Message(
            body=envelope.model_dump_json().encode(),
            content_type="application/json",
            delivery_mode=DeliveryMode.PERSISTENT,
            correlation_id=correlation_id,
            headers={"x-retry-count": 0},
        )

        await exchange.publish(message, routing_key=routing_key)
        logger.info(
            f"Published event {routing_key} to {exchange_name}",
            extra={
                "event_id": str(envelope.event_id),
                "routing_key": routing_key,
                "exchange": exchange_name,
            },
        )
