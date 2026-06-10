import io
import logging
import uuid
from typing import Any, Dict, List, Tuple

import numpy as np
from PIL import Image
from sqlalchemy.orm import Session

from app.minio_client import minio_client
from app.ml.detector import ImageDetector
from app.ml.encoder import ImageEncoder
from app.models import Crop, ImageModel, Vector
from app.utils import hash_image

# Глобальные экземпляры
detector = None
encoder = None

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def init_ml_models(detector_model_path: str, encoder_model_path: str):
    """Инициализация ML моделей"""
    global detector, encoder
    detector = ImageDetector(detector_model_path)
    encoder = ImageEncoder(encoder_model_path)
    return detector, encoder


def process_image_with_crops(
    image_bytes: bytes,
    db: Session,
    image_id: str = None,
    image_path: str = None,
    mime_type: str = "image/jpeg"
) -> Tuple[List[np.ndarray], Dict[str, Any], List[Dict[str, Any]]]:
    """
    Обработка изображения с сохранением кропов
    
    Returns:
        Tuple: (embeddings, detections, crops_data)
    """
    # Загрузка изображения
    image = Image.open(io.BytesIO(image_bytes))
    
    # Детекция объектов
    detections = detector.detect(np.array(image)) if detector else {}
    logger.info(detections)
    
    # Получаем кропы
    crops = []
    if detector and detections.get('boxes'):
        crops = detector.get_crops(image, detections.get('boxes', []))

    # Извлечение эмбеддингов для каждого кропа
    embeddings = []
    if encoder and crops:
        embeddings = encoder.encode(crops)
    
    if not embeddings:
        embeddings = [np.random.rand(1280) for _ in range(len(crops))]
    
    # Подготовка данных о кропах
    crops_data = []
    boxes = detections.get('boxes', [])
    classes = detections.get('classes', [])
    confidences = detections.get('confidences', [])
    
    for idx, (crop_image, bbox, class_name, confidence, embedding) in enumerate(
        zip(crops, boxes, classes, confidences, embeddings)
    ):
        crops_data.append({
            "index": idx,
            "image": crop_image,
            "bbox": bbox,
            "class_name": class_name,
            "confidence": confidence,
            "embedding": embedding
        })
    return embeddings, detections, crops_data


def save_crops_to_database(
    db: Session,
    image_id: str,
    crops_data: List[Dict[str, Any]],
    milvus_ids: List[str]
) -> List[Crop]:
    """Сохраняет кропы в базу данных"""
    saved_crops = []
    
    for crop_data, milvus_id in zip(crops_data, milvus_ids):
        # Сохраняем кроп в MinIO
        crop_path = f"crops/{image_id}/{crop_data['index']}.jpg"
        crop_bytes_io = io.BytesIO()
        crop_data['image'].save(crop_bytes_io, format='JPEG', quality=85)
        crop_bytes = crop_bytes_io.getvalue()
        
        minio_client.upload_file(
            file_data=crop_bytes,
            object_path=crop_path,
            content_type="image/jpeg"
        )
        
        # Создаем запись в таблице crops
        crop = Crop(
            id=str(uuid.uuid4()),
            image_id=image_id,
            crop_index=crop_data['index'],
            crop_path=crop_path,
            bbox_x1=float(crop_data['bbox'][0]),
            bbox_y1=float(crop_data['bbox'][1]),
            bbox_x2=float(crop_data['bbox'][2]),
            bbox_y2=float(crop_data['bbox'][3]),
            class_name=crop_data['class_name'],
            confidence=float(crop_data['confidence'])
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
    return saved_crops


def save_original_image_to_database(
    db: Session,
    image_bytes: bytes,
    image_path: str,
    mime_type: str,
    image_hash: str = None
) -> ImageModel:
    """Сохраняет оригинальное изображение в базу данных"""
    if not image_hash:
        image_hash = hash_image(image_bytes)
    
    # Проверяем, существует ли уже такое изображение
    existing_image = db.query(ImageModel).filter(
        ImageModel.image_hash == image_hash
    ).first()
    
    if existing_image:
        return existing_image
    
    # Создаем новое изображение
    image = ImageModel(
        id=str(uuid.uuid4()),
        image_path=image_path,
        image_hash=image_hash,
        mime_type=mime_type
    )
    
    db.add(image)
    db.commit()
    db.refresh(image)
    
    return image


def get_detector():
    global detector
    return detector


def get_encoder():
    global encoder
    return encoder