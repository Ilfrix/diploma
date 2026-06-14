import logging
from typing import Any, cast

import numpy as np
from pymilvus import (
    Collection,
    CollectionSchema,
    DataType,
    FieldSchema,
    connections,
    utility,
)


logger = logging.getLogger(__name__)


class MilvusDatabase:
    """Векторная база данных на основе Milvus (стандартный API)"""

    def __init__(
        self,
        host: str = "localhost",
        port: str = "19530",
        collection_name: str = "embeddings",
        dim: int = 1280,
    ):
        self.host = host
        self.port = port
        self.collection_name = collection_name
        self.dim = dim
        self.collection: Collection | None = None

        self._connect()
        self._init_collection_with_schema()

    def _connect(self):
        """Подключение к Milvus"""
        try:
            connections.connect(alias="default", host=self.host, port=self.port)
            logger.info(f"Connected to Milvus at {self.host}:{self.port}")
        except Exception as e:
            logger.error(f"Failed to connect to Milvus: {e}")
            raise

    def _init_collection_with_schema(self):
        """Инициализация коллекции с явной схемой"""
        try:
            if utility.has_collection(self.collection_name):
                self.collection = Collection(self.collection_name)
                logger.info(f"Loaded existing collection: {self.collection_name}")
            else:
                fields = [
                    # Primary key
                    FieldSchema(
                        name="id",
                        dtype=DataType.VARCHAR,
                        max_length=255,
                        is_primary=True,
                    ),
                    # Векторное поле
                    FieldSchema(
                        name="vector", dtype=DataType.FLOAT_VECTOR, dim=self.dim
                    ),
                    # Связь с оригинальным изображением
                    FieldSchema(
                        name="sample_id", dtype=DataType.VARCHAR, max_length=255
                    ),
                    FieldSchema(name="crop_index", dtype=DataType.INT32),
                    # Информация о пользователе
                    FieldSchema(name="user_id", dtype=DataType.VARCHAR, max_length=255),
                    FieldSchema(
                        name="original_id", dtype=DataType.VARCHAR, max_length=255
                    ),
                    # Информация о детекции
                    FieldSchema(name="bbox", dtype=DataType.VARCHAR, max_length=500),
                    FieldSchema(
                        name="class_name", dtype=DataType.VARCHAR, max_length=100
                    ),
                    FieldSchema(name="confidence", dtype=DataType.FLOAT),
                    # Метаданные
                    FieldSchema(
                        name="file_name", dtype=DataType.VARCHAR, max_length=500
                    ),
                    FieldSchema(
                        name="mime_type", dtype=DataType.VARCHAR, max_length=100
                    ),
                    FieldSchema(
                        name="processed_at", dtype=DataType.VARCHAR, max_length=100
                    ),
                ]

                # Создаем схему
                schema = CollectionSchema(
                    fields, description="Image crop vectors for duplicate detection"
                )
                # Создаем коллекцию
                self.collection = Collection(self.collection_name, schema)

                # Создаем индекс для векторов
                index_params = {
                    "metric_type": "COSINE",
                    "index_type": "IVF_FLAT",
                    "params": {"nlist": 128},
                }
                self.collection.create_index("vector", index_params)
                logger.info(
                    f"Created new collection with explicit schema: {self.collection_name}"
                )

            # Загружаем коллекцию в память
            self.collection.load()
            logger.info(
                f"Collection {self.collection_name} loaded, contains {self.collection.num_entities} entities"
            )

        except Exception as e:
            logger.error(f"Error initializing collection: {e}")
            raise

    def _prepare_vector(self, vector: np.ndarray) -> list[float]:
        """Подготовка вектора для Milvus"""
        if isinstance(vector, np.ndarray):
            vector = vector.astype(np.float32)
            return cast(list[float], vector.tolist())
        return list(vector) if vector else []

    def add_vectors_batch(self, vectors_data: list[dict[str, Any]]):
        """
        Пакетное добавление векторов

        Args:
            vectors_data: [{"vector_id": str, "vector": np.ndarray, "metadata": dict}, ...]
        """
        if not vectors_data:
            return

        try:
            if self.collection is None:
                raise RuntimeError("Milvus collection not initialized")

            insert_data = []
            for v_data in vectors_data:
                vector_list = self._prepare_vector(v_data["vector"])
                metadata = v_data["metadata"]

                # Проверка размерности
                if len(vector_list) != self.dim:
                    logger.warning(
                        f"Vector dimension mismatch: expected {self.dim}, got {len(vector_list)}"
                    )
                    if len(vector_list) > self.dim:
                        vector_list = vector_list[: self.dim]
                    else:
                        vector_list.extend([0.0] * (self.dim - len(vector_list)))

                # Формируем запись по схеме
                record = {
                    "id": v_data["vector_id"],
                    "vector": vector_list,
                    "sample_id": metadata.get("sample_id", ""),
                    "crop_index": metadata.get("crop_index", 0),
                    "user_id": metadata.get("user_id", ""),
                    "original_id": metadata.get("original_id", ""),
                    "bbox": metadata.get("bbox", "[]"),
                    "class_name": metadata.get("class_name", "-1"),
                    "confidence": metadata.get("confidence", 0.0),
                    "file_name": metadata.get("file_name", ""),
                    "mime_type": metadata.get("mime_type", ""),
                    "processed_at": metadata.get("processed_at", ""),
                }
                insert_data.append(record)

            # Вставка в коллекцию
            self.collection.insert(insert_data)
            self.collection.flush()
            logger.info(f"Batch added {len(insert_data)} vectors to Milvus")

        except Exception as e:
            logger.error(f"Error in batch add: {e}", exc_info=True)
            raise

    def add_vector(self, vector_id: str, vector: np.ndarray, metadata: dict[str, Any]):
        """Добавление одного вектора"""
        self.add_vectors_batch(
            [{"vector_id": vector_id, "vector": vector, "metadata": metadata}]
        )

    def get_vector(self, vector_id: str) -> np.ndarray | None:
        """Получение вектора по ID"""
        try:
            if self.collection is None:
                raise RuntimeError("Milvus collection not initialized")

            results = self.collection.query(
                expr=f'id == "{vector_id}"', output_fields=["vector"]
            )
            if results:
                return np.array(results[0]["vector"], dtype=np.float32)
            return None
        except Exception as e:
            logger.error(f"Error getting vector {vector_id}: {e}")
            return None

    def delete_vector(self, vector_id: str):
        """Удаление вектора"""
        try:
            if self.collection is None:
                raise RuntimeError("Milvus collection not initialized")
            self.collection.delete(f'id == "{vector_id}"')
            self.collection.flush()
            logger.debug(f"Deleted vector {vector_id}")
        except Exception as e:
            logger.error(f"Error deleting vector {vector_id}: {e}")

    def delete_by_sample_id(self, sample_id: str):
        """Удаление всех векторов, связанных с изображением"""
        try:
            if self.collection is None:
                raise RuntimeError("Milvus collection not initialized")
            expr = f'sample_id == "{sample_id}"'
            self.collection.delete(expr)
            self.collection.flush()
            logger.info(f"Deleted vectors for sample {sample_id}")
        except Exception as e:
            logger.error(f"Error deleting by sample_id: {e}")

    def get_metadata(self, vector_id: str) -> dict[str, Any]:
        """Получение метаданных"""
        try:
            if self.collection is None:
                raise RuntimeError("Milvus collection not initialized")
            results = self.collection.query(
                expr=f'id == "{vector_id}"',
                output_fields=[
                    "sample_id",
                    "crop_index",
                    "user_id",
                    "original_id",
                    "bbox",
                    "class_name",
                    "confidence",
                    "file_name",
                    "processed_at",
                ],
            )
            if results:
                result = results[0]
                return {k: v for k, v in result.items() if k != "id"}
            return {}
        except Exception as e:
            logger.error(f"Error getting metadata for {vector_id}: {e}")
            return {}

    def search_similar(
        self,
        query_vector: np.ndarray,
        k: int = 10,
        threshold: float = 0.7,
        user_id: str = "",
    ) -> list[tuple[str, float, dict]]:
        """Поиск похожих векторов"""
        try:
            if self.collection is None:
                raise RuntimeError("Milvus collection not initialized")
            query_list = self._prepare_vector(query_vector)

            # Параметры поиска
            search_params = {"metric_type": "COSINE", "params": {"nprobe": 10}}

            # Поиск
            results = self.collection.search(
                data=[query_list],
                anns_field="vector",
                param=search_params,
                limit=k,
                output_fields=[
                    "sample_id",
                    "crop_index",
                    "user_id",
                    "bbox",
                    "class_name",
                    "confidence",
                    "file_name",
                ],
            )

            formatted_results = []
            for hits in results:
                for hit in hits:
                    if hit.score >= threshold:
                        metadata = {
                            "sample_id": hit.entity.get("sample_id"),
                            "crop_index": hit.entity.get("crop_index"),
                            "user_id": hit.entity.get("user_id"),
                            "bbox": hit.entity.get("bbox"),
                            "class_name": hit.entity.get("class_name"),
                            "confidence": hit.entity.get("confidence"),
                            "file_name": hit.entity.get("file_name"),
                        }
                        formatted_results.append((hit.id, hit.score, metadata))

            return formatted_results

        except Exception as e:
            logger.error(f"Error searching similar vectors: {e}", exc_info=True)
            return []

    def health_check(self) -> str:
        """Проверка состояния"""
        try:
            if self.collection is None:
                raise RuntimeError("Milvus collection not initialized")
            num_entities = self.collection.num_entities
            return f"Milvus DB healthy with {num_entities} vectors"
        except Exception as e:
            return f"Milvus DB error: {e!s}"

    def count(self) -> int:
        """Количество векторов в БД"""
        try:
            if self.collection is None:
                raise RuntimeError("Milvus collection not initialized")
            return int(self.collection.num_entities)
        except Exception:
            return 0

    def close(self):
        """Закрытие соединения"""
        try:
            connections.disconnect("default")
            logger.info("Disconnected from Milvus")
        except Exception as e:
            logger.error(f"Error closing connection: {e}")
