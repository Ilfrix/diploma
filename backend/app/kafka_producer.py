import base64
from datetime import datetime
import json
import logging
from typing import Any

from aiokafka import AIOKafkaProducer

from app.config import config


logger = logging.getLogger(__name__)

class KafkaProducerManager:
    """Менеджер Kafka продюсера"""
    
    def __init__(self, bootstrap_servers: str):
        self.bootstrap_servers = bootstrap_servers
        self.producer: AIOKafkaProducer = None
        self._running = False
    
    async def start(self):
        """Запуск продюсера"""
        self.producer = AIOKafkaProducer(
            bootstrap_servers=self.bootstrap_servers,
            value_serializer=lambda v: json.dumps(v, default=str).encode('utf-8')
        )
        await self.producer.start()
        self._running = True
        logger.info("Kafka producer started")
    
    async def stop(self):
        """Остановка продюсера"""
        if self.producer:
            await self.producer.stop()
            self._running = False
            logger.info("Kafka producer stopped")
    
    async def send_message(self, topic: str, key: str, value: dict[str, Any]):
        """Отправка сообщения в Kafka"""
        if not self._running:
            raise RuntimeError("Kafka producer is not running")
        
        try:
            await self.producer.send_and_wait(topic, key=key.encode(), value=value)
            logger.debug(f"Message sent to {topic}: key={key}")
        except Exception as e:
            logger.error(f"Failed to send message to Kafka: {e}")
            raise
    
    async def send_image_for_processing(self, image_id: str, image_bytes: bytes, 
                                       metadata: dict[str, Any]):
        """Отправка изображения на обработку"""
        
        message = {
            "image_id": image_id,
            "image_data": base64.b64encode(image_bytes).decode('utf-8'),
            "metadata": metadata,
            "timestamp": datetime.now()
        }
        
        await self.send_message(
            topic=config.KAFKA_IMAGE_TOPIC,
            key=image_id,
            value=message
        )
        logger.info(f"Image {image_id} sent for processing")

    async def send_search_request(
        self,
        request_id: str,
        image_bytes: bytes,
        metadata: dict[str, Any]
    ):
        """Отправка запроса на поиск"""
        
        message = {
            "request_id": request_id,
            "image_data": base64.b64encode(image_bytes).decode('utf-8'),
            "metadata": metadata,
            "timestamp": datetime.now().isoformat()
        }
        
        await self.send_message(
            topic=config.KAFKA_SEARCH_TOPIC,
            key=request_id,
            value=message
        )
        logger.info(f"Search request {request_id} sent for processing")

kafka_producer = KafkaProducerManager(config.KAFKA_BOOTSTRAP_SERVERS)
