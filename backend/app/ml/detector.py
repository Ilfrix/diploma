import logging

import numpy as np
from PIL import Image

from app.triton_client import TritonYOLODetector


logger = logging.getLogger(__name__)

class ImageDetector:
    """Адаптер для Triton клиента"""
    
    def __init__(self, triton_url: str = "triton:8010", confidence: float = 0.25):
        self.confidence = confidence
        self.triton_client = None
        self._connect_to_triton(triton_url)
    
    def _connect_to_triton(self, url: str):
        """Подключение к Triton серверу"""
        try:
            
            self.triton_client = TritonYOLODetector(url=url)
            logger.info(f"Connected to Triton at {url}")
        except Exception as e:
            logger.error(f"Failed to connect to Triton: {e}")
            self.triton_client = None
    
    def detect(self, image: np.ndarray) -> dict:
        """Детекция через Triton"""
        if self.triton_client is None:
            return {"objects": [], "count": 0, "boxes": [], "classes": [], "confidences": []}
        
        try:
            results = self.triton_client.detect(image, confidence_threshold=self.confidence)
            print(results)
            # results = self.model(image, conf=self.confidence, verbose=False)
            
            # Парсинг результатов
            detections = []
            boxes = []
            classes = []
            confidences = []
            
            # if len(results) > 0:
            result = results  # Берем первое изображение
            
            if len(result) > 0:
                # Получаем данные из результата
                boxes_data = result['boxes']  # [x1, y1, x2, y2]
                confs_data = result['confidences']
                classes_data = result['classes']
                class_ids = [elem['class_id'] for elem in results['objects']]
                
                for i, (box, conf, class_name, cls_id) in enumerate(
                    zip(boxes_data, confs_data,classes_data, class_ids, strict=True)
                ):
                    x1, y1, x2, y2 = box
                    
                    detection = {
                        "id": i,
                        "bbox": [float(x1), float(y1), float(x2), float(y2)],
                        "confidence": float(conf),
                        "class_id": cls_id,
                        "class_name": class_name,
                    }
                    
                    detections.append(detection)
                    boxes.append([float(x1), float(y1), float(x2), float(y2)])
                    classes.append(class_name)
                    confidences.append(float(conf))
            
            logger.debug(f"Detected {len(detections)} objects")
            
            return {
                "objects": detections,
                "count": len(detections),
                "boxes": boxes,
                "classes": classes,
                "confidences": confidences
            }
                
        except Exception as e:
            logger.error(f"Triton inference failed: {e}")
            return {"objects": [], "count": 0, "boxes": [], "classes": [], "confidences": []}
        
    def get_crops(self, image: Image.Image, bboxes: list[list[float]], original_size: tuple[int, int]):
        """
        Вырезание кропов с учетом масштабирования
        
        Args:
            image: Оригинальное изображение (PIL Image)
            bboxes: Координаты из модели [x1, y1, x2, y2] в системе 640x640
            original_size: (width, height) оригинального изображения (если None - берем из image)
        """
        crops = []
        
        # Получаем оригинальный размер
        if original_size is None:
            orig_w, orig_h = image.size  # PIL: (width, height)
        else:
            orig_w, orig_h = original_size
        
        # Коэффициенты масштабирования
        scale_x = orig_w / 640.0
        scale_y = orig_h / 640.0
        
        for x1, y1, x2, y2 in bboxes:
            print(f"Original bbox (640x640): ({x1:.2f}, {y1:.2f}, {x2:.2f}, {y2:.2f})")
            
            # Масштабируем координаты к оригинальному размеру
            x1_orig = x1 * scale_x
            y1_orig = y1 * scale_y
            x2_orig = x2 * scale_x
            y2_orig = y2 * scale_y
            
            # Преобразуем в целые числа для PIL
            x1_orig = int(x1_orig)
            y1_orig = int(y1_orig)
            x2_orig = int(x2_orig)
            y2_orig = int(y2_orig)
            
            # Корректируем порядок (на случай если x1 > x2 или y1 > y2)
            if x2_orig < x1_orig:
                x1_orig, x2_orig = x2_orig, x1_orig
            if y2_orig < y1_orig:
                y1_orig, y2_orig = y2_orig, y1_orig
            
            # Ограничиваем границами изображения
            x1_orig = max(0, x1_orig)
            y1_orig = max(0, y1_orig)
            x2_orig = min(orig_w, x2_orig)
            y2_orig = min(orig_h, y2_orig)
            
            print(f"Scaled bbox ({orig_w}x{orig_h}): ({x1_orig}, {y1_orig}, {x2_orig}, {y2_orig})")
            
            # Проверяем, что bbox валидный
            if x2_orig <= x1_orig or y2_orig <= y1_orig:
                print("Warning: Invalid bbox after scaling, skipping")
                continue
            
            # Вырезаем кроп из ОРИГИНАЛЬНОГО изображения (без resize!)
            crop = image.crop((x1_orig, y1_orig, x2_orig, y2_orig))
            crops.append(crop)
        
        return crops