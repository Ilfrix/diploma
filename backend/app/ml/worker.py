import base64
from datetime import datetime
import io
import json
import logging
from typing import Any
import uuid

import numpy as np
from PIL import Image
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.milvus_db import MilvusDatabase
from app.minio_client import minio_client
from app.ml.detector import ImageDetector
from app.ml.encoder import ImageEncoder
from app.models import Crop, ImageModel, ProcessStatus, Sample, Vector
from app.utils import ColorExtractor, hash_image


logger = logging.getLogger(__name__)


class MLProcessingWorker:
    """Worker для асинхронной обработки изображений из Kafka"""

    def __init__(
        self, vector_db: MilvusDatabase, detector: ImageDetector, encoder: ImageEncoder
    ):
        self.vector_db = vector_db
        self.detector = detector
        self.encoder = encoder
        self._running = False

    async def process_image_message(self, key: str, message: dict[str, Any]):
        """Обработка сообщения с изображением"""
        sample_id = None

        try:
            # Извлечение данных из сообщения
            sample_id = message.get("image_id") or message.get("sample_id")
            image_data_b64 = message.get("image_data")
            metadata = message.get("metadata", {})

            if not sample_id:
                logger.error("No sample_id in message")
                return

            logger.info(f"Processing sample {sample_id}")

            # Декодирование изображения
            if image_data_b64:
                image_bytes = base64.b64decode(image_data_b64)
            else:
                # Если нет данных в сообщении, загрузка из MinIO
                image_path = metadata.get("image_path")
                if image_path:
                    image_bytes = minio_client.download_file(image_path)
                else:
                    raise ValueError("No image data or path provided")

            db = SessionLocal()

            try:
                # Получение сэмпла из БД
                sample = db.query(Sample).filter(Sample.id == sample_id).first()
                if not sample:
                    logger.error(f"Sample {sample_id} not found in database")
                    await self._update_sample_status(
                        db, sample_id, ProcessStatus.FAILED, "Sample not found"
                    )
                    return

                # Сохранение оригинального изображение в БД (если еще не сохранено)
                image_path = metadata.get("image_path")
                if not sample.image_id and image_path:
                    # Создание записи в таблице images
                    image_model = await self._save_image_to_database(
                        db=db,
                        image_bytes=image_bytes,
                        image_path=image_path,
                        mime_type=metadata.get("mime_type", "image/jpeg"),
                        image_hash=metadata.get("image_hash"),
                    )

                    # Связь сэмпла с изображением
                    sample.image_id = image_model.id
                    db.commit()

                # Обновеление статуса на PROCESSING
                sample.status = ProcessStatus.PROCESSING
                db.commit()

                # ML обработка с сохранением кропов
                result = await self._process_and_save_crops(
                    db=db, sample=sample, image_bytes=image_bytes, metadata=metadata
                )
                logger.info(f"Результат обработки с сохранением {result}")

                # Обновление статуса сэмпла на PROCESSED
                sample.status = ProcessStatus.PROCESSED
                sample.updated_at = datetime.now()
                db.commit()
                logger.info(
                    f"Успешно обработан {sample_id}: {len(result['crops'])} кроп сохранен"
                )

            finally:
                db.close()

        except Exception as e:
            logger.error(f"Ошибка обработка сэмпла {sample_id}: {e}", exc_info=True)
            # Обновление статус на FAILED
            db = SessionLocal()
            try:
                sample_id = str(sample_id) if sample_id else ""
                await self._update_sample_status(
                    db, sample_id, ProcessStatus.FAILED, str(e)
                )
            finally:
                db.close()

    async def _save_image_to_database(
        self,
        db: Session,
        image_bytes: bytes,
        image_path: str,
        mime_type: str,
        image_hash: str,
    ) -> ImageModel:
        """Сохраняет изображение в БД"""

        # Вычисление хэша если не предоставлен
        if not image_hash:
            image_hash = hash_image(image_bytes)

        # Проверка существует ли уже такое изображение
        existing_image = (
            db.query(ImageModel).filter(ImageModel.image_hash == image_hash).first()
        )

        if existing_image:
            return existing_image

        image_model = ImageModel(
            id=str(uuid.uuid4()),
            image_path=image_path,
            image_hash=image_hash,
            mime_type=mime_type,
        )

        db.add(image_model)
        db.flush()

        return image_model

    async def _process_and_save_crops(
        self, db: Session, sample: Sample, image_bytes: bytes, metadata: dict[str, Any]
    ) -> dict[str, Any]:
        """Обрабатывает изображение и сохраняет кропы"""
        detector = self.detector
        encoder = self.encoder
        image = Image.open(io.BytesIO(image_bytes))

        # Детекция объектов
        detections = detector.detect(np.array(image)) if detector else {}

        crops = []
        logger.info(f"Ббоксы {detections.get('boxes')}")

        if detector and detections.get("boxes"):
            crops, orig = detector.get_crops(image, detections.get("boxes", []))
        logger.info(f"Кропы {crops}")

        # Извлечение эмбеддингов для каждого кропа
        embeddings: np.ndarray = np.array([])

        if encoder and crops:
            embeddings = encoder.encode(crops)
        logger.info(f"Размерность эмбеддинга {embeddings.shape}")

        if embeddings.size == 0:
            embeddings = np.array([np.random.rand(1280) for _ in range(len(crops))])

        saved_crops = []
        milvus_ids = []

        boxes = [orig]
        classes = detections.get("classes", [])
        confidences = detections.get("confidences", [])

        for idx, (crop_image, bbox, class_name, confidence, embedding) in enumerate(
            zip(crops, boxes, classes, confidences, embeddings, strict=True)
        ):
            # Сохранение кропа в MinIO
            crop_path = f"crops/{sample.image_id}/{idx}.jpg"
            crop_bytes_io = io.BytesIO()
            crop_image.save(crop_bytes_io, format="JPEG", quality=95)
            crop_bytes = crop_bytes_io.getvalue()

            minio_client.upload_file(
                file_data=crop_bytes, object_path=crop_path, content_type="image/jpeg"
            )

            milvus_id = f"crop_{sample.image_id}_{idx}"
            self.vector_db.add_vector(
                vector_id=milvus_id,
                vector=embedding.tolist()
                if hasattr(embedding, "tolist")
                else embedding,
                metadata={
                    "sample_id": sample.id,
                    "user_id": sample.user_id,
                    "image_id": sample.image_id,
                    "crop_index": idx,
                    "class_name": class_name,
                    "confidence": float(confidence),
                    "bbox": json.dumps(bbox),
                },
            )
            milvus_ids.append(milvus_id)
            color_val = ColorExtractor.debug_color_extraction(crop_bytes)
            color_name = ColorExtractor.color_to_name(color_val)
            russian_color_name = ColorExtractor.name_to_russian(color_name)

            # Создание записи в таблице crops
            logger.info(f"Создание записи в Crop. {bbox}")
            crop = Crop(
                id=str(uuid.uuid4()),
                image_id=sample.image_id,
                crop_index=idx,
                color_name=russian_color_name,
                crop_path=crop_path,
                bbox_x1=float(bbox[0]),
                bbox_y1=float(bbox[1]),
                bbox_x2=float(bbox[2]),
                bbox_y2=float(bbox[3]),
                class_name=class_name,
                confidence=float(confidence),
            )
            db.add(crop)
            db.flush()

            # Создание записи в таблице vectors
            vector = Vector(id=str(uuid.uuid4()), crop_id=crop.id, milvus_id=milvus_id)
            db.add(vector)

            saved_crops.append(crop)

        db.commit()

        return {
            "crops": saved_crops,
            "milvus_ids": milvus_ids,
            "detections": detections,
            "embeddings_count": len(embeddings),
        }

    async def _update_sample_status(
        self, db: Session, sample_id: str, status: ProcessStatus, error: str
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
                logger.info(f"Обновление статуса сэмпла {sample_id} до {status.value}")
        except Exception as e:
            logger.error(f"Ошибка обновления статуса сэмпла: {e}")

    async def start(self):
        """Запуск worker"""
        self._running = True
        logger.info("MLProcessingWorker начал работу")

    async def stop(self):
        """Остановка worker"""
        self._running = False
        logger.info("MLProcessingWorker остановлен")
