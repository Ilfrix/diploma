import logging
import timm
import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

class ImageEncoder:
    """Класс для извлечения эмбеддингов изображений"""
    
    def __init__(self, model_path: str):
        self.model_path = model_path
        self.model = None
        self._load_model()
    
    def _load_model(self):
        """Загрузка модели энкодера"""
        try:
            self.model = timm.create_model(
                self.model_path,
                pretrained=True,
                num_classes=0  # Убираем голову, оставляем только features
            )
            self.model.eval()
            data_config = timm.data.resolve_model_data_config(self.model)
            self.transforms = timm.data.create_transform(**data_config, is_training=False)
            logger.info(f"Encoder model and transforms loaded from {self.model_path}")
        except Exception as e:
            logger.error(f"Failed to load encoder model: {e}")
            self.model = None

    
    def encode(self, image: np.ndarray) -> np.ndarray:
        """Извлечение эмбеддинга изображения"""
        if self.model is None:
            # Заглушка - возвращаем случайный вектор
            return np.random.rand(512)
        
        # Здесь должно быть реальное извлечение признаков
        # embedding = self.model.encode(image)
        
        image = Image.open(image_path).convert('RGB')
        
        # Применяем трансформации
        input_tensor = self.transform(cropped).unsqueeze(0)  # [1, 3, 384, 384]
        
        # Получаем эмбеддинг
        with torch.no_grad():
            features = self.model(input_tensor)  # [1, 1280]
        
        return features.squeeze().numpy()
    
    def is_loaded(self) -> bool:
        """Проверка загрузки модели"""
        return self.model is not None
