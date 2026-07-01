import asyncio
from collections.abc import Awaitable, Callable
import json
import logging

from aiokafka import AIOKafkaConsumer

from app.config import config


logger = logging.getLogger(__name__)


class KafkaConsumerManager:
    """Менеджер Kafka консюмера"""

    def __init__(self, bootstrap_servers: str, group_id: str, topics: list):
        logger.info(f"KafkaConsumer {bootstrap_servers}")
        self.bootstrap_servers = bootstrap_servers
        self.group_id = group_id
        self.topics = topics
        self.consumer: AIOKafkaConsumer = None
        self._running = False
        self._message_handler: Callable | None = None

    async def start(self, message_handler: Callable[[str, dict], Awaitable[None]]):
        """Запуск консюмера с обработчиком сообщений"""
        self._message_handler = message_handler

        self.consumer = AIOKafkaConsumer(
            *self.topics,
            bootstrap_servers=self.bootstrap_servers,
            group_id=self.group_id,
            value_deserializer=lambda v: json.loads(v.decode("utf-8")),
            auto_offset_reset="earliest",
            enable_auto_commit=True,
        )

        await self.consumer.start()
        self._running = True
        logger.info(f"Kafka consumer запущен для топика: {self.topics}")

        # Запуск цикла обработки сообщений
        self._task = asyncio.create_task(self._consume_loop())

    async def stop(self):
        """Остановка консюмера"""
        self._running = False
        if self.consumer:
            await self.consumer.stop()
            logger.info("Kafka consumer остановлен")

    async def _consume_loop(self):
        """Основной цикл потребления сообщений"""
        try:
            async for msg in self.consumer:
                if not self._running:
                    break

                try:
                    if self._message_handler:
                        await self._message_handler(msg.key.decode(), msg.value)
                except Exception as e:
                    logger.error(f"Ошибка обработки сообщения: {e}")
        except Exception as e:
            logger.error(f"Ошибка цикла консьюмера: {e}")
            if self._running:
                # Перезапуск консюмера при ошибке
                await asyncio.sleep(5)
                self._task = asyncio.create_task(self._consume_loop())


kafka_consumer = KafkaConsumerManager(
    config.KAFKA_BOOTSTRAP_SERVERS,
    config.KAFKA_CONSUMER_GROUP,
    [config.KAFKA_IMAGE_TOPIC],
)

kafka_search_consumer = KafkaConsumerManager(
    config.KAFKA_BOOTSTRAP_SERVERS,
    config.KAFKA_SEARCH_CONSUMER_GROUP,
    [config.KAFKA_SEARCH_TOPIC],
)
