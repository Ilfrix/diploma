import hashlib
import cv2
import numpy as np
from typing import Tuple, List
from sklearn.cluster import KMeans
from collections import Counter


color_map = {
    "red": (255, 0, 0),
    "green": (0, 255, 0),
    "blue": (0, 0, 255),
    "yellow": (255, 255, 0),
    "purple": (128, 0, 128),
    "orange": (255, 165, 0),
    "pink": (255, 192, 203),
    "brown": (139, 69, 19),
    "black": (0, 0, 0),
    "white": (255, 255, 255),
    "gray": (128, 128, 128),
    "silver": (192, 192, 192),
    "beige": (245, 245, 220),        # бежевый (классика для мебели)
    "cream": (255, 255, 204),        # кремовый
    "ivory": (255, 255, 240),        # слоновая кость
    "wenge": (50, 40, 35),           # венге (очень популярен)
    "oak": (160, 120, 80),           # дуб
    "walnut": (119, 85, 61),         # орех
    "cherry": (138, 54, 15),         # вишня
    "beech": (196, 160, 116),        # бук
    "ash": (138, 129, 111),          # ясень
    "pine": (227, 194, 140),         # сосна
    "mahogany": (76, 38, 24),        # красное дерево
    "gold": (255, 215, 0),           # золотистый
    "bronze": (205, 127, 50),        # бронзовый
    "copper": (184, 115, 51),        # медный
    "taupe": (72, 60, 50),           # серо-коричневый
    "mint": (152, 255, 152),         # мятный
    "lavender": (230, 230, 250),     # лавандовый
    "turquoise": (64, 224, 208),     # бирюзовый
    "coral": (255, 127, 80),         # коралловый
    "burgundy": (128, 0, 32),        # бордовый
    "olive": (128, 128, 0),          # оливковый
    "khaki": (195, 176, 145),        # хаки
    "charcoal": (54, 69, 79),        # темно-серый
}


def hash_image(image_bytes: bytes) -> str:
    """Вычисление хэша изображения для проверки дубликатов"""
    return hashlib.sha256(image_bytes).hexdigest()


class ColorExtractor:
    """Извлечение и сравнение цветов изображений"""
    
    @staticmethod
    def get_dominant_color(image_bytes: bytes, n_colors: int = 3) -> Tuple[int, int, int]:
        """
        Находит доминирующий цвет с помощью K-means кластеризации
        
        Args:
            image_bytes: Байты изображения
            n_colors: Количество цветов для кластеризации
            
        Returns:
            RGB кортеж доминирующего цвета
        """
        # Загружаем изображение
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        
        img = cv2.resize(img, (200, 200))
        
        # Преобразуем в массив пикселей
        pixels = img.reshape(-1, 3)
        
        # K-means кластеризация
        kmeans = KMeans(
            n_clusters=min(n_colors, len(pixels)),
            n_init=5,
            max_iter=100,
            random_state=42
        )
        kmeans.fit(pixels)
        
        # Получаем частоту каждого кластера
        labels = kmeans.labels_
        label_counts = Counter(labels)
        
        # Берем самый частый кластер
        dominant_label = max(label_counts, key=label_counts.get)
        print('dominant')
        print(dominant_label)
        dominant_color = kmeans.cluster_centers_[dominant_label]
        print(dominant_color)
        
        return tuple(map(int, dominant_color))
    
    @staticmethod
    def color_to_name(color: tuple[int, int,int]):
        min_distance = 1_000
        for col, val in color_map.items():
            d = ColorExtractor.color_distance(color, val)
            if d < min_distance:
                min_distance = d
                name = col
        return name
    
    @staticmethod
    def color_distance(rgb1: Tuple[int, int, int], rgb2: Tuple[int, int, int]) -> float:
        """
        Евклидово расстояние в RGB пространстве, нормализованное от 0 до 1
        
        0 - идентичные цвета, 1 - максимально разные
        """
        distance = np.sqrt(sum((c1 - c2) ** 2 for c1, c2 in zip(rgb1, rgb2)))
        max_distance = np.sqrt(3 * 255 ** 2)  # ~441.67
        return distance / max_distance
    
    @staticmethod
    def color_name_to_rgb(color_name: str) -> Tuple[int, int, int]:
        """Преобразует название цвета в RGB"""
        return color_map.get(color_name.lower(), (128, 128, 128))
    
    @staticmethod
    def matches_color(
        image_color: Tuple[int, int, int], 
        target_color: Tuple[int, int, int],
        tolerance: float = 0.3
    ) -> bool:
        """Проверяет, соответствует ли цвет изображения целевому"""
        distance = ColorExtractor.color_distance(image_color, target_color)
        return distance <= tolerance