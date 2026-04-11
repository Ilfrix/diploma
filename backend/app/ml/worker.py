import asyncio
import base64
import logging
from typing import Dict, Any
from datetime import datetime

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import Sample, SampleStatus
from app.ml.processor import process_image
from app.vector_db import VectorDatabase
from app.config import config

logger = logging.getLogger(__name__)

class MLProcessingWorker:
    """Worker для асинхронной обработки изображений из Kafka"""
    
    def __init__(self, vector_db: VectorDatabase):
        self.vector_db = vector_db
        self._running = False
    
    async def process_image_message(self, key: str, message: Dict[str, Any]):
        """Обработка сообщения с изображением"""
        try:
            image_id = message.get("image_id")
            image_data_b64 = message.get("image_data")
            metadata = message.get("metadata", {})
            timestamp = message.get("timestamp")
            
            logger.info(f"Processing image {image_id}")
            
            # Декодирование изображения
            image_bytes = base64.b64decode(image_data_b64)
            
            # ML обработка
            embedding, detections = process_image(image_bytes)
            
            # Сохранение в векторную БД
            vector_id = f"sample_{image_id}"
            self.vector_db.add_vector(vector_id, embedding, {
                "sample_id": image_id,
                "user_id": metadata.get("user_id"),
                "name": metadata.get("name"),
                "detections": detections,
                "processed_at": datetime.now().isoformat()
            })
            
            # Обновление статуса в PostgreSQL
            await self._update_sample_status(image_id, vector_id, SampleStatus.PROCESSED)
            
            logger.info(f"Successfully processed image {image_id}")
            
            # Здесь можно отправить результат в другой топик при необходимости
            # await self._send_result_to_kafka(image_id, embedding, detections)
            
        except Exception as e:
            logger.error(f"Error processing image {image_id}: {e}")
            await self._update_sample_status(image_id, vector_id, SampleStatus.FAILED, str(e))
    
    async def _update_sample_status(self, sample_id: str, vector_id: str, 
                                   status: str, error: str = None):
        """Обновление статуса семпла в БД"""
        db = SessionLocal()
        try:
            sample = db.query(Sample).filter(Sample.id == sample_id).first()
            if sample:
                print(status)
                if status == SampleStatus.PROCESSED:
                    sample.vector_id = vector_id
                    sample.status = SampleStatus.PROCESSED
                elif status == SampleStatus.FAILED:
                    sample.status = SampleStatus.FAILED
                    sample.error_message = error
                db.commit()
                logger.info(f"Updated sample {sample_id} status to {status}")
        except Exception as e:
            logger.error(f"Failed to update sample status: {e}")
        finally:
            db.close()
    
    async def start(self):
        """Запуск worker"""
        self._running = True
        logger.info("ML Processing Worker started")
    
    async def stop(self):
        """Остановка worker"""
        self._running = False
        logger.info("ML Processing Worker stopped")
