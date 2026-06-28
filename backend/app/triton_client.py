import cv2
import numpy as np
import tritonclient.http as httpclient


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

        # Список классов YOLO (Все 80 изначальных классов)
        self.class_names = [
            "person",
            "bicycle",
            "car",
            "motorcycle",
            "airplane",
            "bus",
            "train",
            "truck",
            "boat",
            "traffic light",
            "fire hydrant",
            "stop sign",
            "parking meter",
            "bench",
            "bird",
            "cat",
            "dog",
            "horse",
            "sheep",
            "cow",
            "elephant",
            "bear",
            "zebra",
            "giraffe",
            "backpack",
            "umbrella",
            "handbag",
            "tie",
            "suitcase",
            "frisbee",
            "skis",
            "snowboard",
            "sports ball",
            "kite",
            "baseball bat",
            "baseball glove",
            "skateboard",
            "surfboard",
            "tennis racket",
            "bottle",
            "wine glass",
            "cup",
            "fork",
            "knife",
            "spoon",
            "bowl",
            "banana",
            "apple",
            "sandwich",
            "orange",
            "broccoli",
            "carrot",
            "hot dog",
            "pizza",
            "donut",
            "cake",
            "chair",
            "couch",
            "potted plant",
            "bed",
            "dining table",
            "toilet",
            "tv",
            "laptop",
            "mouse",
            "remote",
            "keyboard",
            "cell phone",
            "microwave",
            "oven",
            "toaster",
            "sink",
            "refrigerator",
            "book",
            "clock",
            "vase",
            "scissors",
            "teddy bear",
            "hair drier",
            "toothbrush",
        ]
        self.target_names = ["bench", "chair", "couch", "bed", "dinning table"]

    def preprocess(
        self, image: np.ndarray, target_size: tuple[int, int] = (1024, 1024)
    ) -> np.ndarray:
        """
        Подготовка изображения для Triton
        """
        # Ресайз
        resized = cv2.resize(image, target_size)
        # BGR -> RGB (если нужно)
        if len(image.shape) == 3 and image.shape[2] == 3:
            resized = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
        # Нормализация [0, 255] -> [0, 1]
        normalized = resized.astype(np.float32) / 255.0
        # [H, W, C] -> [C, H, W]
        transposed = np.transpose(normalized, (2, 0, 1))
        # Добавляем batch dimension
        batched = np.expand_dims(transposed, axis=0)
        return batched

    # def postprocess(
    #     self,
    #     output: np.ndarray,
    #     confidence_threshold: float = 0.25,
    #     iou_threshold: float = 0.45,
    # ) -> list[dict]:
    #     """
    #     Постобработка выхода YOLO

    #     Args:
    #         output: [1, 84, 8400] или [1, 8400, 84]
    #         confidence_threshold: порог уверенности
    #         iou_threshold: порог для NMS

    #     Returns:
    #         List[Dict]: детекции с ключами 'bbox', 'confidence', 'class_id', 'class_name'
    #     """
    #     # Проверяем размерность
    #     print('SHAPE '*100)
    #     print(output.shape)
    #     if len(output.shape) == 3 and output.shape[1] == 5:
    #         # Формат [batch, 8400, 84]
    #         output = output.transpose(0, 2, 1)  # -> [batch, 84, 8400]

    #     # Извлекаем данные
    #     cx = output[0, 0, :]
    #     cy = output[0, 1, :]
    #     w = output[0, 2, :]
    #     h = output[0, 3, :]

    #     # Конвертируем в [x1, y1, x2, y2]
    #     x1 = cx - w / 2
    #     y1 = cy - h / 2
    #     x2 = cx + w / 2
    #     y2 = cy + h / 2

    #     boxes = np.stack([x1, y1, x2, y2], axis=0)
    #     # boxes = output[0, 0:4, :]  # [4, 8400] - x1, y1, x2, y2 (в координатах 0-640)
    #     scores = output[0, 4:, :]  # [80, 8400] - confidence для каждого класса

    #     # Находим максимальные confidence для каждого анкера
    #     max_scores = np.max(scores, axis=0)  # [8400]
    #     class_ids = np.argmax(scores, axis=0)  # [8400]

    #     # Фильтрация по порогу
    #     mask = max_scores > confidence_threshold
    #     filtered_boxes = boxes[:, mask]
    #     filtered_scores = max_scores[mask]
    #     filtered_class_ids = class_ids[mask]

    #     if len(filtered_boxes) == 0:
    #         return []

    #     # NMS (Non-Maximum Suppression)
    #     keep_indices = self.nms(filtered_boxes, filtered_scores, iou_threshold)

    #     # Формируем результат
    #     detections = []
    #     for idx in keep_indices:
    #         x1, y1, x2, y2 = filtered_boxes[:, idx]
    #         class_id = filtered_class_ids[idx]
    #         class_name = (
    #             self.class_names[class_id]
    #             if class_id < len(self.class_names)
    #             else f"class_{class_id}"
    #         )
    #         if class_name not in self.target_names:
    #             continue

    #         detections.append(
    #             {
    #                 "bbox": [float(x1), float(y1), float(x2), float(y2)],
    #                 "confidence": float(filtered_scores[idx]),
    #                 "class_id": int(class_id),
    #                 "class_name": class_name,
    #             }
    #         )

    #     return detections

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
        # print(f"Output shape in postprocess: {output.shape}")
        # print(confidence_threshold)
        # print(iou_threshold)

        # Извлекаем данные
        cx = output[0, 0, :]  # center x
        cy = output[0, 1, :]  # center y
        w = output[0, 2, :]  # width
        h = output[0, 3, :]  # height
        objectness = output[0, 4, :]  # objectness score

        # print(f"Objectness range: [{objectness.min():.3f}, {objectness.max():.3f}]")
        # print(f"Coordinates range: cx=[{cx.min():.3f}, {cx.max():.3f}], cy=[{cy.min():.3f}, {cy.max():.3f}]")
        # print(f"Size range: w=[{w.min():.3f}, {w.max():.3f}], h=[{h.min():.3f}, {h.max():.3f}]")

        # Нормализация координат и размеров
        input_size = 1024

        # Если координаты уже в пикселях (как в вашем случае)
        if cx.max() > 1.0 or cy.max() > 1.0:
            # print("Coordinates in pixel space, normalizing...")
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

        # Конвертируем [cx, cy, w, h] в [x1, y1, x2, y2] (нормализованные)
        x1 = np.clip(cx_norm - w_norm / 2, 0, 1)
        y1 = np.clip(cy_norm - h_norm / 2, 0, 1)
        x2 = np.clip(cx_norm + w_norm / 2, 0, 1)
        y2 = np.clip(cy_norm + h_norm / 2, 0, 1)

        # Проверяем валидность боксов (ширина и высота > 0)
        valid_boxes = (x2 > x1) & (y2 > y1)
        # print(f"Valid boxes: {valid_boxes.sum()} out of {len(valid_boxes)}")

        boxes = np.stack([x1, y1, x2, y2], axis=0)  # [4, num_detections]
        scores = objectness

        # Фильтрация по порогу и валидности
        mask = (scores > confidence_threshold) & valid_boxes
        filtered_boxes = boxes[:, mask]
        filtered_scores = scores[mask]

        print(f"Detections before filtering: {len(scores)}")
        print(
            f"Detections after confidence threshold and validity check: {len(filtered_scores)}"
        )

        if len(filtered_boxes) == 0:
            return []

        # NMS
        keep_indices = self.nms(filtered_boxes, filtered_scores, iou_threshold)

        print(f"Detections after NMS: {len(keep_indices)}")

        # Формируем результат
        detections = []
        for idx in keep_indices:
            x1, y1, x2, y2 = filtered_boxes[:, idx]

            # Для модели с objectness, предполагаем что все детекции - это нужные объекты
            class_name = "bed"

            # Фильтрация по целевым классам (если есть)
            # if hasattr(self, 'target_names') and class_name not in self.target_names:
            #     continue

            detections.append(
                {
                    "bbox": [float(x1), float(y1), float(x2), float(y2)],
                    "confidence": float(filtered_scores[idx]),
                    "class_id": 0,
                    "class_name": class_name,
                }
            )

        print(f"Final detections: {len(detections)}")
        print(detections)
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

        # Получаем координаты
        x1 = boxes[0, :]
        y1 = boxes[1, :]
        x2 = boxes[2, :]
        y2 = boxes[3, :]

        # Вычисляем площади
        areas = (x2 - x1 + 1) * (y2 - y1 + 1)

        # Сортировка по уверенности
        order = scores.argsort()[::-1]

        keep = []
        while len(order) > 0:
            i = order[0]
            keep.append(i)

            # Вычисляем IoU с остальными
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
