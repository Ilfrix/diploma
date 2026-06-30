import hashlib
import math

import cv2
import numpy as np


color_map = {
    "red": (180, 40, 40),
    "green": (40, 160, 40),
    "blue": (40, 40, 160),
    "black": (0, 0, 0),
    "white": (240, 240, 240),
    "gray": (120, 120, 120),
}

COLOR_NAMES = {
    "red": "Красный",
    "green": "Зеленый",
    "blue": "Синий",
    "black": "Черный",
    "white": "Белый",
    "gray": "Серый",
}


def hash_image(image_bytes: bytes) -> str:
    """Вычисление хэша изображения для проверки дубликатов"""
    return hashlib.sha256(image_bytes).hexdigest()


class ColorExtractor:
    """Извлечение и сравнение цветов изображений"""

    @staticmethod
    def color_to_name(color: tuple[int, int, int]):
        min_distance = 1_000
        for col, val in color_map.items():
            d = ColorExtractor.color_distance_weighted(color, val)
            if d < min_distance:
                min_distance = d
                name = col
        return name

    @staticmethod
    def name_to_russian(color: str):
        return COLOR_NAMES.get(color, "Нет цвета в словаре")

    @staticmethod
    def debug_color_extraction(image_bytes: bytes):
        """Отладочная функция для проверки определения цвета"""
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

        h, w = img_rgb.shape[:2]
        center = img_rgb[h // 4 : 3 * h // 4, w // 4 : 3 * w // 4]

        center_float = center.astype(np.float64)
        median_center = np.median(center_float.reshape(-1, 3), axis=0)
        print(f"Медиана центра: {median_center}")

        return tuple(map(int, median_center))

    @staticmethod
    def color_distance_weighted(rgb1, rgb2):
        # Больше вес на разницу насыщенности/тона, меньше на яркость
        w = np.array([0.33, 0.33, 0.33])
        return np.sqrt(np.sum(w * (np.array(rgb1) - np.array(rgb2)) ** 2)) / 255.0

    @staticmethod
    def color_distance(rgb1: tuple[int, int, int], rgb2: tuple[int, int, int]) -> float:
        """
        Евклидово расстояние в RGB пространстве, нормализованное от 0 до 1

        0 - идентичные цвета, 1 - максимально разные
        """
        distance = math.sqrt(
            sum((c1 - c2) ** 2 for c1, c2 in zip(rgb1, rgb2, strict=True))
        )
        max_distance = math.sqrt(3 * 255**2)  # ~441.67
        return distance / max_distance

    @staticmethod
    def color_name_to_rgb(color_name: str) -> tuple[int, int, int]:
        """Преобразует название цвета в RGB"""
        return color_map.get(color_name.lower(), (128, 128, 128))

    @staticmethod
    def matches_color(
        image_color: tuple[int, int, int],
        target_color: tuple[int, int, int],
        tolerance: float = 0.3,
    ) -> bool:
        """Проверяет, соответствует ли цвет изображения целевому"""
        distance = ColorExtractor.color_distance(image_color, target_color)
        return distance <= tolerance
