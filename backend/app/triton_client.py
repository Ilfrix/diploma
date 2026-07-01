import logging

import cv2
import numpy as np
import tritonclient.http as httpclient


logger = logging.getLogger(__name__)


class TritonYOLODetector:
    def __init__(self, url: str = "triton:8010"):  # Ваш порт 8010
        print(url)
        print("=" * 100)
        self.client = httpclient.InferenceServerClient(url=url)
        self.model_name = "yolo_detector"

        # Проверка доступности модели
        assert self.client.is_model_ready(self.model_name), (
            f"Model {self.model_name} not ready"
        )

        # Получение метаданных
        model_metadata = self.client.get_model_metadata(self.model_name)
        self.input_name = model_metadata["inputs"][0]["name"]
        self.output_name = model_metadata["outputs"][0]["name"]

    def preprocess(
        self, image: np.ndarray, target_size: tuple[int, int] = (1024, 1024)
    ) -> np.ndarray:
        """
        Подготовка изображения для Triton
        """
        resized = cv2.resize(image, target_size)
        if len(image.shape) == 3 and image.shape[2] == 3:
            resized = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
        # Нормализация [0, 255] -> [0, 1]
        normalized = resized.astype(np.float32) / 255.0
        # [H, W, C] -> [C, H, W]
        transposed = np.transpose(normalized, (2, 0, 1))
        # Добавление batch dimension
        batched = np.expand_dims(transposed, axis=0)
        return batched

    def postprocess(
        self,
        output: np.ndarray,
        confidence_threshold: float = 0.25,
        iou_threshold: float = 0.45,
    ) -> list[dict]:
        """
        Постобработка для формата [batch, 5, num_detections]
        где 5 = [cx, cy, w, h, objectness]
        """

        # Извлекаем данные
        cx = output[0, 0, :]  # center x
        cy = output[0, 1, :]  # center y
        w = output[0, 2, :]  # width
        h = output[0, 3, :]  # height
        objectness = output[0, 4, :]  # objectness score

        # Нормализация координат и размеров
        input_size = 1024

        # Если координаты в пикселях
        if cx.max() > 1.0 or cy.max() > 1.0:
            cx_norm = np.clip(cx / input_size, 0, 1)
            cy_norm = np.clip(cy / input_size, 0, 1)
            w_norm = np.clip(w / input_size, 0, 1)
            h_norm = np.clip(h / input_size, 0, 1)
        else:
            # Координаты уже нормализованы
            cx_norm = np.clip(cx, 0, 1)
            cy_norm = np.clip(cy, 0, 1)
            w_norm = np.clip(w, 0, 1)
            h_norm = np.clip(h, 0, 1)

        # Конвертация [cx, cy, w, h] в [x1, y1, x2, y2] (нормализованные)
        x1 = np.clip(cx_norm - w_norm / 2, 0, 1)
        y1 = np.clip(cy_norm - h_norm / 2, 0, 1)
        x2 = np.clip(cx_norm + w_norm / 2, 0, 1)
        y2 = np.clip(cy_norm + h_norm / 2, 0, 1)

        # Проверка валидности боксов (ширина и высота > 0)
        valid_boxes = (x2 > x1) & (y2 > y1)

        boxes = np.stack([x1, y1, x2, y2], axis=0)  # [4, num_detections]
        scores = objectness

        # Фильтрация по порогу и валидности
        mask = (scores > confidence_threshold) & valid_boxes
        filtered_boxes = boxes[:, mask]
        filtered_scores = scores[mask]

        logger.info(f"Детекция до фильтрации: {len(scores)}")
        logger.info(f"Детекция после порога и валидации {len(filtered_scores)}")

        if len(filtered_boxes) == 0:
            return []

        # NMS
        keep_indices = self.nms(filtered_boxes, filtered_scores, iou_threshold)

        logger.info(f"Детекция после NMS: {len(keep_indices)}")

        # Формирование результата
        detections = []
        for idx in keep_indices:
            x1, y1, x2, y2 = filtered_boxes[:, idx]
            class_name = "bed"

            detections.append(
                {
                    "bbox": [float(x1), float(y1), float(x2), float(y2)],
                    "confidence": float(filtered_scores[idx]),
                    "class_id": 0,
                    "class_name": class_name,
                }
            )

        logger.info(f"Результирующие детекции: {detections}")
        return detections

    def nms(
        self, boxes: np.ndarray, scores: np.ndarray, iou_threshold: float = 0.45
    ) -> list[int]:
        """
        Non-Maximum Suppression

        Args:
            boxes: [N, 4] массив боксов (x1, y1, x2, y2)
            scores: [N] массив уверенностей
            iou_threshold: порог IoU

        Returns:
            List[int]: индексы боксов для сохранения
        """
        if len(boxes) == 0:
            return []

        x1 = boxes[0, :]
        y1 = boxes[1, :]
        x2 = boxes[2, :]
        y2 = boxes[3, :]

        areas = (x2 - x1 + 1) * (y2 - y1 + 1)
        order = scores.argsort()[::-1]

        keep = []
        while len(order) > 0:
            i = order[0]
            keep.append(i)

            # Вычисление IoU с остальными
            xx1 = np.maximum(x1[i], x1[order[1:]])
            yy1 = np.maximum(y1[i], y1[order[1:]])
            xx2 = np.minimum(x2[i], x2[order[1:]])
            yy2 = np.minimum(y2[i], y2[order[1:]])

            w = np.maximum(0.0, xx2 - xx1 + 1)
            h = np.maximum(0.0, yy2 - yy1 + 1)
            inter = w * h

            iou = inter / (areas[i] + areas[order[1:]] - inter)

            # Те, у которых IoU < порога
            inds = np.where(iou <= iou_threshold)[0]
            order = order[inds + 1]

        return keep

    def detect(self, image: np.ndarray, confidence_threshold: float = 0.25) -> dict:
        """
        Детекция объектов на изображении

        Args:
            image: numpy array изображения (H, W, C)
            confidence_threshold: порог уверенности

        Returns:
            dict: {
                "objects": list of dict с информацией об объектах,
                "count": int,
                "boxes": list of bboxes,
                "classes": list of class names,
                "confidences": list of confidence scores
            }
        """
        # Предобработка
        input_data = self.preprocess(image)

        # Инференс через Triton
        inputs = [httpclient.InferInput(self.input_name, input_data.shape, "FP32")]
        inputs[0].set_data_from_numpy(input_data)

        outputs = [httpclient.InferRequestedOutput(self.output_name)]

        response = self.client.infer(
            model_name=self.model_name, inputs=inputs, outputs=outputs
        )
        # Получение результата
        output_data = response.as_numpy(self.output_name)

        # Постобработка
        detections = self.postprocess(
            output_data, confidence_threshold=confidence_threshold
        )

        return {
            "objects": detections,
            "count": len(detections),
            "boxes": [d["bbox"] for d in detections],
            "classes": [d["class_name"] for d in detections],
            "confidences": [d["confidence"] for d in detections],
        }
