import asyncio
import logging

import aio_pika
from aio_pika import ExchangeType
from aio_pika.abc import AbstractChannel, AbstractConnection, AbstractExchange

from mediride_common.events.constants import Exchanges

logger = logging.getLogger(__name__)


class RabbitMQBroker:
    def __init__(self, url: str):
        self.url = url
        self._connection: AbstractConnection | None = None
        self._channel: AbstractChannel | None = None
        self._exchanges: dict[str, AbstractExchange] = {}

    async def connect(self) -> None:
        """Establish connection to RabbitMQ with retry."""
        max_retries = 5
        for attempt in range(max_retries):
            try:
                self._connection = await aio_pika.connect_robust(self.url)
                self._channel = await self._connection.channel()
                await self._channel.set_qos(prefetch_count=10)
                await self._declare_exchanges()
                logger.info("Connected to RabbitMQ")
                return
            except Exception as e:
                if attempt < max_retries - 1:
                    wait_time = 2**attempt
                    logger.warning(
                        f"RabbitMQ connection attempt {attempt + 1} failed: {e}. "
                        f"Retrying in {wait_time}s..."
                    )
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"Failed to connect to RabbitMQ after {max_retries} attempts")
                    raise

    async def _declare_exchanges(self) -> None:
        """Declare all topic exchanges."""
        if not self._channel:
            raise RuntimeError("Channel not initialized")

        exchange_names = [
            Exchanges.AUTH,
            Exchanges.USERS,
            Exchanges.RIDES,
            Exchanges.PAYMENTS,
            Exchanges.TRACKING,
        ]

        for name in exchange_names:
            exchange = await self._channel.declare_exchange(
                name, ExchangeType.TOPIC, durable=True
            )
            self._exchanges[name] = exchange

        # Dead letter exchange (fanout)
        dlx = await self._channel.declare_exchange(
            Exchanges.DLX, ExchangeType.FANOUT, durable=True
        )
        self._exchanges[Exchanges.DLX] = dlx

    async def ensure_queue(
        self,
        queue_name: str,
        exchange_name: str,
        routing_keys: list[str],
    ) -> None:
        """Declare a durable queue and bind it to an exchange.

        Call this from producer services so that messages are persisted
        even when the consumer service has not started yet.
        """
        if not self._channel:
            raise RuntimeError("Channel not initialized")
        queue = await self._channel.declare_queue(
            queue_name,
            durable=True,
            arguments={"x-dead-letter-exchange": Exchanges.DLX},
        )
        exchange = self.get_exchange(exchange_name)
        for key in routing_keys:
            await queue.bind(exchange, routing_key=key)
        logger.info(
            "Ensured queue %s bound to %s with keys %s",
            queue_name, exchange_name, routing_keys,
        )

    def get_exchange(self, name: str) -> AbstractExchange:
        if name not in self._exchanges:
            raise RuntimeError(f"Exchange '{name}' not declared")
        return self._exchanges[name]

    @property
    def channel(self) -> AbstractChannel:
        if not self._channel:
            raise RuntimeError("Channel not initialized. Call connect() first.")
        return self._channel

    async def close(self) -> None:
        if self._connection:
            await self._connection.close()
            logger.info("RabbitMQ connection closed")
