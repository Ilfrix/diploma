import asyncio
import base64
import logging
import json
from typing import Dict, Any
from datetime import datetime

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import Sample, SampleStatus
from app.ml.processor import process_image
from app.milvus_db import MilvusDatabase
from app.config import config

logger = logging.getLogger(__name__)

class MLProcessingWorker:
    """Worker для асинхронной обработки изображений из Kafka"""
    
    def __init__(self, vector_db: MilvusDatabase):
        self.vector_db = vector_db
        self._running = False
    
    async def process_image_message(self, key: str, message: Dict[str, Any]):
        """Обработка сообщения с изображением"""
        vector_ids = []
        try:
            image_id = message.get("image_id")
            image_data_b64 = message.get("image_data")
            metadata = message.get("metadata", {})
            timestamp = message.get("timestamp")
            
            logger.info(f"Processing image {image_id}")
            
            # Декодирование изображения
            image_bytes = base64.b64decode(image_data_b64)
            
            # ML обработка
            embeddings, detections = process_image(image_bytes)
            
                        # Получаем списки боксов и классов из детекций
            boxes = detections.get('boxes', [])
            classes = detections.get('classes', [])
            confidences = detections.get('confidences', [])
            
            # Сохраняем каждый кроп как отдельный вектор в Milvus
            vectors_data = []
            for i, (embedding, bbox) in enumerate(zip(embeddings, boxes)):
                crop_id = f"crop_{image_id}_{i}"
                vector_ids.append(crop_id)
                
                # Подготовка метаданных для кропа
                crop_metadata = {
                    "sample_id": image_id,           # Связь с оригинальным изображением
                    "user_id": metadata.get("user_id", ""),
                    "original_id": metadata.get("original_id", ""),
                    "crop_index": i,
                    "bbox": json.dumps(bbox),         # Координаты bbox
                    "class_id": classes[i] if i < len(classes) else -1,
                    "confidence": confidences[i] if i < len(confidences) else 0.0,
                    "file_name": metadata.get("file_name", ""),
                    "mime_type": metadata.get("mime_type", ""),
                    "processed_at": datetime.now().isoformat()
                }
                
                vectors_data.append({
                    "vector_id": crop_id,
                    "vector": embedding,
                    "metadata": crop_metadata
                })
            
            # Пакетная вставка в Milvus
            if vectors_data:
                self.vector_db.add_vectors_batch(vectors_data)
                logger.info(f"Added {len(vectors_data)} crop vectors to Milvus")

            # await self._update_sample_with_crops(
            #     image_id, 
            #     vector_ids, 
            #     boxes, 
            #     classes, 
            #     confidences,
            #     metadata
            # )
            # Обновление статуса в PostgreSQL
            # await self._update_sample_status(image_id, vector_id, SampleStatus.PROCESSED)
            await self._update_sample_status(image_id, crop_id, SampleStatus.PROCESSED)
            
            logger.info(f"Successfully processed image {image_id}")

        except Exception as e:
            logger.error(f"Error processing image {image_id}: {e}")
            # await self._update_sample_status(image_id, vector_id, SampleStatus.FAILED, str(e))
            await self._update_sample_status(image_id, crop_id, SampleStatus.FAILED, str(e))
    

    # async def _update_sample_with_crops(
    #     self, 
    #     sample_id: str, 
    #     crop_ids: list,
    #     boxes: list,
    #     classes: list,
    #     confidences: list,
    #     metadata: dict
    # ):
    #     """Обновление статуса семпла и сохранение связей с кропами"""
    #     db = SessionLocal()
    #     try:
    #         # Обновляем основной семпл
    #         sample = db.query(Sample).filter(Sample.id == sample_id).first()
    #         if sample:
    #             sample.status = SampleStatus.PROCESSED
    #             sample.processed_at = datetime.now()
    #             sample.crops_count = len(crop_ids)  # Добавьте поле в модель Sample
    #             db.commit()
    #             logger.info(f"Updated sample {sample_id} status to PROCESSED")
                
    #             # Сохраняем каждый кроп как отдельную запись
    #             for i, crop_id in enumerate(crop_ids):
    #                 crop = SampleCrop(
    #                     id=crop_id,
    #                     sample_id=sample_id,
    #                     crop_index=i,
    #                     bbox=json.dumps(boxes[i]) if i < len(boxes) else None,
    #                     class_id=classes[i] if i < len(classes) else -1,
    #                     confidence=confidences[i] if i < len(confidences) else 0.0,
    #                     vector_id=crop_id,  # Ссылка на вектор в Milvus
    #                     created_at=datetime.now()
    #                 )
    #                 db.add(crop)
                
    #             db.commit()
    #             logger.info(f"Saved {len(crop_ids)} crops for sample {sample_id}")
    #         else:
    #             logger.warning(f"Sample {sample_id} not found in database")
                
    #     except Exception as e:
    #         logger.error(f"Failed to update sample with crops: {e}")
    #         db.rollback()
    #     finally:
    #         db.close()

    
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
