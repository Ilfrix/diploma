import logging
import numpy as np
from ultralytics import YOLO
from pathlib import Path
import cv2
import PIL
from typing import List

logger = logging.getLogger(__name__)


class ImageDetector:
    """Класс для детекции объектов на изображении"""
    
    def __init__(self, model_path: str = None, confidence: float = 0.25):
        self.model_path = Path(model_path)
        self.confidence = confidence
        self.model = None

        if not self.model_path.is_file():
            self.model_path = 'kesimeg/yolov8n-clothing-detection'

        self._load_model()
    
    def _load_model(self):
        """Загрузка модели детекции YOLOv8"""
        print('-'*100)
        try:
            # Загрузка модели YOLO
            self.model = YOLO(self.model_path)
            logger.info(f"YOLOv8 model loaded from {self.model_path}")
        except Exception as e:
            logger.error(f"Failed to load YOLO model: {e}")
            self.model = None
    
    def detect(self, image: np.ndarray) -> dict:
        """
        Детекция объектов на изображении
        
        Args:
            image: numpy array изображения (H, W, C) в формате BGR или RGB
            
        Returns:
            dict: {
                "objects": list of dict с информацией об объектах,
                "count": int количество объектов,
                "boxes": list of bounding boxes,
                "classes": list of class names,
                "confidences": list of confidence scores
            }
        """
        if self.model is None:
            logger.warning("Model not loaded, returning empty detection")
            return {
                "objects": [], 
                "count": 0,
                "boxes": [],
                "classes": [],
                "confidences": []
            }
        
        try:
            # Конвертация в RGB если изображение в BGR (OpenCV формат)
            # if len(image.shape) == 3 and image.shape[2] == 3:
            #     # Предполагаем, что изображение в BGR (как из cv2.imread)
            #     # YOLO ожидает RGB, но может работать и с BGR
            #     pass
            
            # Выполнение инференса
            results = self.model(image, conf=self.confidence, verbose=False)
            
            # Парсинг результатов
            detections = []
            boxes = []
            classes = []
            confidences = []
            
            if len(results) > 0:
                result = results[0]  # Берем первое изображение
                
                if result.boxes is not None:
                    # Получаем данные из результата
                    boxes_data = result.boxes.xyxy.cpu().numpy()  # [x1, y1, x2, y2]
                    confs_data = result.boxes.conf.cpu().numpy()
                    classes_data = result.boxes.cls.cpu().numpy().astype(int)
                    
                    for i, (box, conf, cls_id) in enumerate(zip(boxes_data, confs_data, classes_data)):
                        x1, y1, x2, y2 = box
                        class_name = self.model.names[cls_id]
                        
                        detection = {
                            "id": i,
                            "bbox": [float(x1), float(y1), float(x2), float(y2)],
                            "confidence": float(conf),
                            "class_id": int(cls_id),
                            "class_name": class_name,
                            # "area": float((x2 - x1) * (y2 - y1))
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
            logger.error(f"Detection failed: {e}")
            return {
                "objects": [], 
                "count": 0,
                "boxes": [],
                "classes": [],
                "confidences": []
            }

    
    def get_crops(self, image: PIL.Image, bboxes: List[List[float]]):
        crops = []
        for x1, y1, x2, y2 in bboxes:
            crop = image.crop((x1,y1,x2,y2))
            # crop.save(f'crop_{x1}.jpg')
            crops.append(crop)

        return crops


    def is_loaded(self) -> bool:
        """Проверка загрузки модели"""
        return self.model is not None
    
    def get_classes(self) -> list:
        """Получить список всех классов, которые умеет детектировать модель"""
        if self.model is None:
            return []
        return list(self.model.names.values())
