import os
import pickle
import logging
from typing import List, Tuple, Dict, Any
import numpy as np

logger = logging.getLogger(__name__)

class VectorDatabase:
    """Простая векторная база данных на основе pickle"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.vectors_file = os.path.join(db_path, "vectors.pkl")
        self.metadata_file = os.path.join(db_path, "metadata.pkl")
        self.vectors = {}
        self.metadata = {}
        self._load()
    
    def _load(self):
        """Загрузка данных из файлов"""
        if os.path.exists(self.vectors_file):
            with open(self.vectors_file, 'rb') as f:
                self.vectors = pickle.load(f)
        
        if os.path.exists(self.metadata_file):
            with open(self.metadata_file, 'rb') as f:
                self.metadata = pickle.load(f)
        
        logger.info(f"Loaded {len(self.vectors)} vectors from database")
    
    def _save(self):
        """Сохранение данных в файлы"""
        with open(self.vectors_file, 'wb') as f:
            pickle.dump(self.vectors, f)
        
        with open(self.metadata_file, 'wb') as f:
            pickle.dump(self.metadata, f)
    
    def add_vector(self, vector_id: str, vector: np.ndarray, metadata: Dict[str, Any]):
        """Добавление вектора в БД"""
        self.vectors[vector_id] = vector
        self.metadata[vector_id] = metadata
        self._save()
    
    def get_vector(self, vector_id: str) -> np.ndarray:
        """Получение вектора по ID"""
        return self.vectors.get(vector_id)
    
    def delete_vector(self, vector_id: str):
        """Удаление вектора из БД"""
        if vector_id in self.vectors:
            del self.vectors[vector_id]
        if vector_id in self.metadata:
            del self.metadata[vector_id]
        self._save()
    
    def update_metadata(self, vector_id: str, metadata: Dict[str, Any]):
        """Обновление метаданных вектора"""
        if vector_id in self.metadata:
            self.metadata[vector_id].update(metadata)
            self._save()
    
    def search_similar(self, query_vector: np.ndarray, k: int = 10, threshold: float = 0.7) -> List[Tuple[str, float, Dict]]:
        """Поиск похожих векторов"""
        if not self.vectors:
            return []
        
        results = []
        for vec_id, vector in self.vectors.items():
            # Косинусное сходство
            similarity = self._cosine_similarity(query_vector, vector)
            
            if similarity >= threshold:
                results.append((vec_id, similarity, self.metadata.get(vec_id, {})))
        
        # Сортировка по убыванию сходства
        results.sort(key=lambda x: x[1], reverse=True)
        
        return results[:k]
    
    def _cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        """Вычисление косинусного сходства"""
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        
        if norm_a == 0 or norm_b == 0:
            return 0.0
        
        return float(np.dot(a, b) / (norm_a * norm_b))
    
    def health_check(self) -> str:
        """Проверка состояния БД"""
        return f"Vector DB healthy with {len(self.vectors)} vectors"