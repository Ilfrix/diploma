import io
import logging
from typing import Any

import numpy as np
from PIL import Image

from app.ml.detector import ImageDetector
from app.ml.encoder import ImageEncoder


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def init_ml_models(detector_model_path: str, encoder_model_path: str):
    """Инициализация ML моделей"""
    detector = ImageDetector(detector_model_path)
    encoder = ImageEncoder(encoder_model_path)
    return detector, encoder


def process_image_with_crops(
    image_bytes: bytes,
    detector: ImageDetector,
    encoder: ImageEncoder,
    mime_type: str = "image/jpeg",
) -> tuple[np.ndarray, dict[str, Any], list[dict[str, Any]]]:
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
    if detector and detections.get("boxes"):
        crops = detector.get_crops(image, detections.get("boxes", []))

    # Извлечение эмбеддингов для каждого кропа
    embeddings: np.ndarray = np.array([])
    if encoder and crops:
        embeddings = encoder.encode(crops)

    if not embeddings:
        embeddings = np.array([np.random.rand(1280) for _ in range(len(crops))])

    # Подготовка данных о кропах
    crops_data = []
    boxes = detections.get("boxes", [])
    classes = detections.get("classes", [])
    confidences = detections.get("confidences", [])

    for idx, (crop_image, bbox, class_name, confidence, embedding) in enumerate(
        zip(crops, boxes, classes, confidences, embeddings, strict=True)
    ):
        crops_data.append(
            {
                "index": idx,
                "image": crop_image,
                "bbox": bbox,
                "class_name": class_name,
                "confidence": confidence,
                "embedding": embedding,
            }
        )
    return embeddings, detections, crops_data
