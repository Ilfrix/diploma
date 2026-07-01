import logging

import numpy as np
from PIL import Image

from app.triton_client import TritonYOLODetector


logger = logging.getLogger(__name__)


class ImageDetector:
    """Адаптер для Triton клиента"""

    def __init__(self, triton_url: str = "triton:8010", confidence: float = 0.25):
        self.confidence = confidence
        self.triton_client: TritonYOLODetector | None
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
            return {
                "objects": [],
                "count": 0,
                "boxes": [],
                "classes": [],
                "confidences": [],
            }

        try:
            results = self.triton_client.detect(
                image, confidence_threshold=self.confidence
            )

            detections = []
            boxes = []
            classes = []
            confidences = []

            result = results

            if len(result) > 0:
                boxes_data = result["boxes"]  # [x1, y1, x2, y2]
                confs_data = result["confidences"]
                classes_data = result["classes"]
                class_ids = [elem["class_id"] for elem in results["objects"]]

                for i, (box, conf, class_name, cls_id) in enumerate(
                    zip(boxes_data, confs_data, classes_data, class_ids, strict=True)
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
                "confidences": confidences,
            }

        except Exception as e:
            logger.error(f"Triton inference failed: {e}")
            return {
                "objects": [],
                "count": 0,
                "boxes": [],
                "classes": [],
                "confidences": [],
            }

    def get_crops(self, image: Image.Image, bboxes: list[list[float]]):
        """
        Вырезание кропов из нормализованных координат

        Args:
            image: Оригинальное изображение (PIL Image)
            bboxes: Координаты в формате [x1, y1, x2, y2] НОРМАЛИЗОВАННЫЕ (0-1)
        """
        crops = []

        # Получаем оригинальный размер
        orig_w, orig_h = image.size

        for box in bboxes:
            # Распаковываем bbox
            if len(box) == 4:
                x1, y1, x2, y2 = box
            else:
                logger.info(f"⚠️ Неправильный формат bbox: {box}")
                continue

            # Проверяем, нормализованные ли координаты
            is_normalized = all(0 <= v <= 1 for v in box)

            if is_normalized:
                # Координаты уже нормализованы (0-1) - просто масштабируем
                logger.info(
                    f"Нормализованные значения: ({x1:.4f}, {y1:.4f}, {x2:.4f}, {y2:.4f})"
                )

                x1_orig = int(x1 * orig_w)
                y1_orig = int(y1 * orig_h)
                x2_orig = int(x2 * orig_w)
                y2_orig = int(y2 * orig_h)

            else:
                logger.info(
                    f"Пиксельные bbox: ({x1:.2f}, {y1:.2f}, {x2:.2f}, {y2:.2f})"
                )

                input_size = 1024
                scale_x = orig_w / input_size
                scale_y = orig_h / input_size

                x1_orig = int(x1 * scale_x)
                y1_orig = int(y1 * scale_y)
                x2_orig = int(x2 * scale_x)
                y2_orig = int(y2 * scale_y)

            # Корректировка порядка координат
            if x2_orig < x1_orig:
                x1_orig, x2_orig = x2_orig, x1_orig
            if y2_orig < y1_orig:
                y1_orig, y2_orig = y2_orig, y1_orig

            # Ограничиваем границами изображения
            x1_orig = max(0, min(x1_orig, orig_w - 1))
            y1_orig = max(0, min(y1_orig, orig_h - 1))
            x2_orig = max(x1_orig + 1, min(x2_orig, orig_w))
            y2_orig = max(y1_orig + 1, min(y2_orig, orig_h))

            # Проверяем, что bbox валидный
            if x2_orig <= x1_orig or y2_orig <= y1_orig:
                logger.warning("Невалидный bbox")
                continue

            # Вырезаем кроп
            crop = image.crop((x1_orig, y1_orig, x2_orig, y2_orig))
            crops.append(crop)

        logger.info(f"Количество кропов: {len(crops)}")
        logger.info(f"Кропы: {crops}")
        return crops, (x1_orig, y1_orig, x2_orig, y2_orig)
