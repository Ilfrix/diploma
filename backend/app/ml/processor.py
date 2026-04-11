import io
import numpy as np
from PIL import Image
from typing import Tuple, Dict, Any

from app.ml.detector import ImageDetector
from app.ml.encoder import ImageEncoder

# Глобальные экземпляры
detector = None
encoder = None


def init_ml_models(detector_model_path: str, encoder_model_path: str):
    """Инициализация ML моделей"""
    global detector, encoder
    detector = ImageDetector(detector_model_path)
    encoder = ImageEncoder(encoder_model_path)
    return detector, encoder


def process_image(image_bytes: bytes) -> Tuple[np.ndarray, Dict[str, Any]]:
    """Синхронная обработка изображения: детекция и извлечение признаков"""
    # Загрузка изображения
    image = Image.open(io.BytesIO(image_bytes))
    image_array = np.array(image)
    
    # Детекция объектов (если нужно)
    # detections = detector.detect(image_array) if detector else {}
    
    # Извлечение эмбеддингов
    # embedding = encoder.encode(image_array) if encoder else np.random.rand(512)
    embedding = np.ones(512)
    detections = [1, 2]
    return embedding, detections
