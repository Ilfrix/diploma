import asyncio
import base64
import time
import logging
import json
from typing import Dict, Any, List
from datetime import datetime
import uuid
from PIL import Image
import io
import numpy as np

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import Sample, SampleStatus, ImageModel, Crop, Vector
from app.utils import hash_image
from app.ml.processor import process_image_with_crops, save_crops_to_database, save_original_image_to_database, get_detector, get_encoder

from app.milvus_db import MilvusDatabase
from app.minio_client import minio_client
from app.config import config

logger = logging.getLogger(__name__)
detector = get_detector()
encoder = get_encoder()

class MLProcessingWorker:
    """Worker для асинхронной обработки изображений из Kafka"""
    
    def __init__(self, vector_db: MilvusDatabase):
        self.vector_db = vector_db
        self._running = False
    
    async def process_image_message(self, key: str, message: Dict[str, Any]):
        """Обработка сообщения с изображением"""
        sample_id = None
        image_id = None
        
        try:
            # Извлекаем данные из сообщения
            sample_id = message.get("image_id") or message.get("sample_id")
            image_data_b64 = message.get("image_data")
            metadata = message.get("metadata", {})
            timestamp = message.get("timestamp")
            
            if not sample_id:
                logger.error("No sample_id in message")
                return
            
            logger.info(f"Processing sample {sample_id}")
            
            # Декодирование изображения
            if image_data_b64:
                image_bytes = base64.b64decode(image_data_b64)
            else:
                # Если нет данных в сообщении, пробуем загрузить из MinIO
                image_path = metadata.get("image_path")
                if image_path:
                    image_bytes = minio_client.download_file(image_path)
                else:
                    raise ValueError("No image data or path provided")

            db = SessionLocal()
            
            try:
                # Получаем сэмпл из БД
                sample = db.query(Sample).filter(Sample.id == sample_id).first()
                if not sample:
                    logger.error(f"Sample {sample_id} not found in database")
                    await self._update_sample_status(db, sample_id, SampleStatus.FAILED, "Sample not found")
                    return
                
                # Сохраняем оригинальное изображение в БД (если еще не сохранено)
                image_path = metadata.get("image_path")
                if not sample.image_id and image_path:
                    # Создаем запись в таблице images
                    image_model = await self._save_image_to_database(
                        db=db,
                        image_bytes=image_bytes,
                        image_path=image_path,
                        mime_type=metadata.get("mime_type", "image/jpeg"),
                        image_hash=metadata.get("image_hash")
                    )
                    
                    # Связываем сэмпл с изображением
                    sample.image_id = image_model.id
                    db.commit()
                
                # Обновляем статус на PROCESSING
                sample.status = SampleStatus.PROCESSING
                db.commit()
                
                # ML обработка с сохранением кропов
                result = await self._process_and_save_crops(
                    db=db,
                    sample=sample,
                    image_bytes=image_bytes,
                    metadata=metadata
                )
                print('result')
                print(result)
                print(sample)
                
                # Обновляем статус сэмпла на PROCESSED
                sample.status = SampleStatus.PROCESSED
                sample.updated_at = datetime.now()
                db.commit()
                logger.info(f"Successfully processed sample {sample_id}: {len(result['crops'])} crops saved")
                
            finally:
                db.close()
            
        except Exception as e:
            logger.error(f"Error processing sample {sample_id}: {e}", exc_info=True)
            # Обновляем статус на FAILED
            db = SessionLocal()
            try:
                await self._update_sample_status(db, sample_id, SampleStatus.FAILED, str(e))
            finally:
                db.close()
    
    async def _save_image_to_database(
        self,
        db: Session,
        image_bytes: bytes,
        image_path: str,
        mime_type: str,
        image_hash: str = None
    ) -> ImageModel:
        """Сохраняет изображение в БД"""
        
        
        # Вычисляем хэш если не предоставлен
        if not image_hash:
            image_hash = hash_image(image_bytes)
        
        # Проверяем, существует ли уже такое изображение
        existing_image = db.query(ImageModel).filter(
            ImageModel.image_hash == image_hash
        ).first()
        
        if existing_image:
            return existing_image

        image_model = ImageModel(
            id=str(uuid.uuid4()),
            image_path=image_path,
            image_hash=image_hash,
            mime_type=mime_type
        )
        
        db.add(image_model)
        db.flush()
        
        return image_model
    
    async def _process_and_save_crops(
        self,
        db: Session,
        sample: Sample,
        image_bytes: bytes,
        metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Обрабатывает изображение и сохраняет кропы"""
        detector = get_detector()
        encoder = get_encoder()
        image = Image.open(io.BytesIO(image_bytes))
        
        # Детекция объектов
        detections = detector.detect(np.array(image)) if detector else {}
        print(detections)

        crops = []
        if detector and detections.get('boxes'):
            crops = detector.get_crops(image, detections.get('boxes', []))
        
        # Извлечение эмбеддингов для каждого кропа
        embeddings = []
        if encoder and crops:
            embeddings = encoder.encode(crops)
        
        if not embeddings:
            embeddings = [np.random.rand(1280) for _ in range(len(crops))]
        
        saved_crops = []
        milvus_ids = []
        
        boxes = detections.get('boxes', [])
        classes = detections.get('classes', [])
        confidences = detections.get('confidences', [])
        
        for idx, (crop_image, bbox, class_name, confidence, embedding) in enumerate(
            zip(crops, boxes, classes, confidences, embeddings)
        ):
            # Сохраняем кроп в MinIO
            crop_path = f"crops/{sample.image_id}/{idx}.jpg"
            crop_bytes_io = io.BytesIO()
            crop_image.save(crop_bytes_io, format='JPEG', quality=85)
            crop_bytes = crop_bytes_io.getvalue()
            
            minio_client.upload_file(
                file_data=crop_bytes,
                object_path=crop_path,
                content_type="image/jpeg"
            )
            
            milvus_id = f"crop_{sample.image_id}_{idx}"
            self.vector_db.add_vector(
                vector_id=milvus_id,
                vector=embedding.tolist() if hasattr(embedding, 'tolist') else embedding,
                metadata={
                    "sample_id": sample.id,
                    "user_id": sample.user_id,
                    "image_id": sample.image_id,
                    "crop_index": idx,
                    "class_name": class_name,
                    "confidence": float(confidence),
                    "bbox": json.dumps(bbox)
                }
            )
            print('-'*100)
            milvus_ids.append(milvus_id)
            
            # Создаем запись в таблице crops
            crop = Crop(
                id=str(uuid.uuid4()),
                image_id=sample.image_id,
                crop_index=idx,
                crop_path=crop_path,
                bbox_x1=float(bbox[0]),
                bbox_y1=float(bbox[1]),
                bbox_x2=float(bbox[2]),
                bbox_y2=float(bbox[3]),
                class_name=class_name,
                confidence=float(confidence)
            )
            db.add(crop)
            db.flush()
            
            # Создаем запись в таблице vectors
            vector = Vector(
                id=str(uuid.uuid4()),
                crop_id=crop.id,
                milvus_id=milvus_id
            )
            db.add(vector)
            
            saved_crops.append(crop)
        
        db.commit()
        
        return {
            "crops": saved_crops,
            "milvus_ids": milvus_ids,
            "detections": detections,
            "embeddings_count": len(embeddings)
        }
    
    async def _update_sample_status(
        self,
        db: Session,
        sample_id: str,
        status: SampleStatus,
        error: str = None
    ):
        """Обновление статуса сэмпла в БД"""
        try:
            sample = db.query(Sample).filter(Sample.id == sample_id).first()
            if sample:
                sample.status = status
                if error:
                    sample.error_message = error
                sample.updated_at = datetime.now()
                db.commit()
                logger.info(f"Updated sample {sample_id} status to {status.value}")
        except Exception as e:
            logger.error(f"Failed to update sample status: {e}")
    
    async def start(self):
        """Запуск worker"""
        self._running = True
        logger.info("ML Processing Worker started")
    
    async def stop(self):
        """Остановка worker"""
        self._running = False
        logger.info("ML Processing Worker stopped")
