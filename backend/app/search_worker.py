import base64
from datetime import datetime
import io
import logging
from typing import Any

import numpy as np
from PIL import Image
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.milvus_db import MilvusDatabase
from app.ml.detector import ImageDetector
from app.ml.encoder import ImageEncoder
from app.models import Crop, ProcessStatus, Sample, SearchRequest
from app.utils import COLOR_NAMES


logger = logging.getLogger(__name__)


class SearchWorker:
    """Worker для асинхронной обработки поисковых запросов из Kafka"""
    
    def __init__(self, vector_db: MilvusDatabase, detector: ImageDetector, encoder: ImageEncoder):
        self.vector_db = vector_db
        self.detector = detector
        self.encoder = encoder
    
    async def process_search_message(self, key: str, message: dict[str, Any]):
        """Обработка поискового запроса - вызывается из kafka_search_consumer"""
        request_id = message.get("request_id")
        image_data_b64 = message.get("image_data")
        metadata = message.get("metadata", {})
        
        db = SessionLocal()
        
        try:
            logger.info(f"Processing search request {request_id}")
            
            # Обновляем статус на PROCESSING
            self._update_request_status(db, request_id, ProcessStatus.PROCESSING)
            
            # Декодируем изображение
            image_bytes = base64.b64decode(image_data_b64)

            result = self._perform_search(
                image_bytes=image_bytes,
                metadata=metadata,
                db=db
            )
            
            # Сохраняем результат
            self._update_request_result(db, request_id, result, ProcessStatus.PROCESSED)
            
            logger.info(f"Search request {request_id} processed with {len(result.get('similar_images', []))} results")
            
        except Exception as e:
            logger.error(f"Error processing search request {request_id}: {e}", exc_info=True)
            self._update_request_result(db, request_id, None, ProcessStatus.FAILED, error=str(e))
        
        finally:
            db.close()
    
    def _perform_search(
        self,
        image_bytes: bytes,
        metadata: dict[str, Any],
        db: Session
    ) -> dict[str, Any]:
        """Выполняет поиск похожих изображений (синхронный метод)"""
        detector = self.detector
        encoder = self.encoder
        
        if detector is None or encoder is None:
            raise RuntimeError("ML models not initialized")
        
        # Обработка изображения
        image = Image.open(io.BytesIO(image_bytes))
        detections = detector.detect(np.array(image))
        
        # Получаем кропы
        crops = []
        if detections.get('boxes'):
            crops = detector.get_crops(image, detections.get('boxes', []))
        
        # Извлекаем эмбеддинги
        embeddings = []
        if crops:
            embeddings = encoder.encode(crops)
        
        if not embeddings:
            return {"similar_images": [], "message": "No features extracted"}
        
        # Параметры поиска
        color_filter = metadata.get("color")
        limit = metadata.get("limit", 10)
        threshold = metadata.get("threshold", 0.7)
        
        # Поиск в Milvus
        search_limit = limit * 3 if color_filter else limit
        similar_vectors = self.vector_db.search_similar(
            embeddings[0], k=search_limit, threshold=threshold
        )
        
        # Формируем результат
        return self._format_results(similar_vectors, color_filter, limit, db)
    
    def _format_results(
        self,
        similar_vectors: list,
        color_filter: str | None,
        limit: int,
        db: Session
    ) -> dict[str, Any]:
        """Форматирует результаты поиска"""
        similar_images = []
        
        # Конвертируем английский цвет в русский для сравнения
        russian_color = None
        if color_filter:
            color_lower = color_filter.lower()
            for eng_name, rus_name in COLOR_NAMES.items():
                if eng_name.lower() == color_lower:
                    russian_color = rus_name
                    break
            if not russian_color:
                russian_color = color_filter
        
        for _vec_id, score, metadata in similar_vectors:
            sample_id = metadata.get("sample_id")
            if not sample_id:
                continue
            
            sample = db.query(Sample).filter(Sample.id == sample_id).first()
            if not sample or not sample.image:
                continue
            
            # Фильтрация по цвету
            if russian_color:
                crop_with_color = db.query(Crop).filter(
                    Crop.image_id == sample.image_id,
                    Crop.color_name == russian_color
                ).first()
                if not crop_with_color:
                    continue
            
            similar_images.append({
                "sample_id": sample.id,
                "name": sample.name,
                "description": sample.description,
                "similarity_score": float(score),
                "image_id": sample.image_id
            })
            
            if len(similar_images) >= limit:
                break
        
        return {"similar_images": similar_images, "count": len(similar_images)}
    
    def _update_request_status(
        self,
        db: Session,
        request_id: str,
        status: ProcessStatus
    ):
        """Обновляет статус запроса"""
        db.query(SearchRequest).filter(
            SearchRequest.id == request_id
        ).update({
            "status": status.value,
            "updated_at": datetime.now()
        })
        db.commit()
    
    def _update_request_result(
        self,
        db: Session,
        request_id: str,
        result: dict | None,
        status: ProcessStatus,
        error: str = ''
    ):
        """Обновляет результат запроса"""
        update_data = {
            "status": status.value,
            "updated_at": datetime.now()
        }
        if result is not None:
            update_data["result"] = result
            update_data["completed_at"] = datetime.now()
        if error:
            update_data["error_message"] = error
        
        db.query(SearchRequest).filter(
            SearchRequest.id == request_id
        ).update(update_data)
        db.commit()