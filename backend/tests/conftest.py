import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from unittest.mock import MagicMock, patch
import numpy as np
import asyncio

# ВАЖНО: Импортируем app ДО определения фикстур
from main import app
from app.database import get_db, Base
from app.models import User
from app.auth import create_access_token, get_current_user


# Тестовая БД SQLite
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db?cache=shared"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="session")
def db_engine():
    """Создание тестовой БД"""
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session(db_engine):
    """Фикстура сессии БД"""
    connection = db_engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)
    
    yield session
    
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def test_user(db_session):
    """Тестовый пользователь"""
    from app.auth import hash_password
    
    user = User(
        username="testuser",
        email="test@example.com",
        password_hash=hash_password("testpassword123")
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def test_user2(db_session):
    """Второй тестовый пользователь"""
    from app.auth import hash_password
    
    user = User(
        username="testuser2",
        email="test2@example.com",
        password_hash=hash_password("testpassword456")
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def auth_headers(test_user):
    """Заголовки с токеном авторизации"""
    token = create_access_token(data={"sub": test_user.id, "username": test_user.username})
    return {"Authorization": f"Bearer {token}"}


# Мок для MilvusDatabase
class MockMilvusDatabase:
    """Мок для векторной БД Milvus"""
    
    def __init__(self):
        self.vectors = {}
        self.next_id = 1
    
    def add_vector(self, vector_id: str, vector: np.ndarray, metadata: dict):
        self.vectors[vector_id] = {
            "vector": vector.tolist() if isinstance(vector, np.ndarray) else vector,
            "metadata": metadata
        }
    
    def get_vector(self, vector_id: str):
        if vector_id in self.vectors:
            return np.array(self.vectors[vector_id]["vector"], dtype=np.float32)
        return None
    
    def delete_vector(self, vector_id: str):
        if vector_id in self.vectors:
            del self.vectors[vector_id]
    
    def delete_by_sample_id(self, sample_id: str):
        to_delete = [vid for vid, data in self.vectors.items() 
                    if data["metadata"].get("sample_id") == sample_id]
        for vid in to_delete:
            del self.vectors[vid]
    
    def search_similar(self, query_vector: np.ndarray, k: int = 10, 
                      threshold: float = 0.7, user_id: str = None):
        query = query_vector.tolist() if isinstance(query_vector, np.ndarray) else query_vector
        results = []
        
        for vec_id, data in self.vectors.items():
            if user_id and data["metadata"].get("user_id") != user_id:
                continue
            
            similarity = self._compute_similarity(query, data["vector"])
            
            if similarity >= threshold:
                results.append((vec_id, similarity, data["metadata"]))
        
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:k]
    
    def _compute_similarity(self, emb1, emb2):
        """Вычисление косинусного сходства"""
        emb1 = np.array(emb1)
        emb2 = np.array(emb2)
        
        if len(emb1) != len(emb2):
            min_len = min(len(emb1), len(emb2))
            emb1 = emb1[:min_len]
            emb2 = emb2[:min_len]
        
        norm1 = np.linalg.norm(emb1)
        norm2 = np.linalg.norm(emb2)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return float(np.dot(emb1, emb2) / (norm1 * norm2))
    
    def count(self) -> int:
        return len(self.vectors)
    
    def health_check(self) -> str:
        return "Mock Milvus DB healthy"


@pytest.fixture
def mock_milvus():
    """Мок для MilvusDatabase"""
    mock = MockMilvusDatabase()
    
    with patch('app.milvus_db.MilvusDatabase', return_value=mock):
        yield mock


# Мок Kafka
class MockKafkaProducer:
    """Полноценный мок Kafka продюсера"""
    def __init__(self):
        self.producer = MagicMock()
        self.running = True
        self.start_called = False
        self.stop_called = False
    
    async def start(self):
        self.start_called = True
        self.running = True
        print("Mock Kafka started")
    
    async def stop(self):
        self.stop_called = True
        self.running = False
        print("Mock Kafka stopped")
    
    async def send_image_for_processing(self, image_id: str, image_bytes: bytes, metadata: dict):
        print(f"Mock Kafka: sending image {image_id}")
        return None
    
    async def send_message(self, topic: str, message: dict):
        print(f"Mock Kafka: sending to {topic}")
        return None


@pytest.fixture(autouse=True)
def mock_kafka():
    """Мок Kafka продюсера - подменяет во всех местах"""
    mock_instance = MockKafkaProducer()
    
    # Важно: подменяем во всех модулях, где импортируется kafka_producer
    patches = [
        patch('app.kafka_producer.kafka_producer', mock_instance),
        patch('app.routers.samples.kafka_producer', mock_instance),
    ]
    
    # Запускаем все патчи
    for p in patches:
        p.start()
    
    # Запускаем мок
    loop = asyncio.get_event_loop()
    loop.run_until_complete(mock_instance.start())
    
    yield mock_instance
    
    # Останавливаем мок
    loop.run_until_complete(mock_instance.stop())
    
    # Останавливаем все патчи
    for p in patches:
        p.stop()


@pytest.fixture(autouse=True)
def mock_minio():
    """Мок MinIO клиента"""
    with patch('app.minio_client.minio_client') as mock_client:
        mock_client.upload_file = MagicMock(return_value=True)
        mock_client.file_exists = MagicMock(return_value=True)
        mock_client.get_file_url = MagicMock(return_value="https://minio.example.com/test.jpg")
        mock_client.delete_file = MagicMock(return_value=True)
        mock_client.download_file = MagicMock(return_value=b"fake_image_bytes")
        mock_client.get_file_info = MagicMock(return_value={
            "size": 102400,
            "last_modified": "2024-01-01T00:00:00Z",
            "content_type": "image/jpeg",
            "etag": "abc123"
        })
        mock_client.list_files = MagicMock(return_value=[])
        
        yield mock_client


@pytest.fixture
def client(db_session, test_user, mock_milvus):
    """Тестовый клиент FastAPI"""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass
    
    async def override_get_current_user():
        return test_user
    
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user
    
    # Устанавливаем мок для векторной БД в роутерах
    from app.routers import samples, search
    samples.vector_db = mock_milvus
    search.vector_db = mock_milvus
    
    client = TestClient(app)
    yield client
    
    app.dependency_overrides.clear()


@pytest.fixture
def test_image_bytes():
    """Создание тестового изображения"""
    from PIL import Image
    import io
    
    img = Image.new('RGB', (100, 100), color='red')
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format='JPEG')
    img_byte_arr.seek(0)
    return img_byte_arr.getvalue()


@pytest.fixture
def test_image_file(test_image_bytes):
    """Тестовый файл изображения"""
    from fastapi import UploadFile
    import io
    
    return UploadFile(
        filename="test.jpg",
        file=io.BytesIO(test_image_bytes),
        headers={"content-type": "image/jpeg"}
    )


# Фикстура для тестового семпла
@pytest.fixture
def test_sample(db_session, test_user):
    """Создание тестового семпла"""
    from app.models import Sample, ProcessStatus, ImageModel
    
    image = ImageModel(
        image_path="samples/test/path.jpg",
        image_hash="test_hash_123",
        mime_type="image/jpeg"
    )
    db_session.add(image)
    db_session.flush()
    
    sample = Sample(
        user_id=test_user.id,
        name="Test Sample",
        description="Test Description",
        image_id=image.id,
        status=ProcessStatus.PENDING
    )
    db_session.add(sample)
    db_session.commit()
    db_session.refresh(sample)
    
    return sample


# Фикстура для тестового кропа
@pytest.fixture
def test_crop(db_session, test_sample):
    """Создание тестового кропа"""
    from app.models import Crop, Vector
    
    crop = Crop(
        image_id=test_sample.image_id,
        crop_index=0,
        bbox_x1=10, bbox_y1=20, bbox_x2=50, bbox_y2=60,
        class_name="test_object",
        confidence=0.95,
        crop_path="crops/test_crop.jpg"
    )
    db_session.add(crop)
    db_session.flush()
    
    vector = Vector(
        crop_id=crop.id,
        milvus_id="test_milvus_id"
    )
    db_session.add(vector)
    db_session.commit()
    
    return crop


@pytest.fixture(autouse=True)
def auto_mock_ml_processor():
    """Автоматический мок ML processor для всех тестов"""
    with patch('app.ml.processor.process_image_with_crops') as mock_processor:
        mock_processor.return_value = (
            [np.random.rand(1280).tolist()],
            [{"bbox": [10, 20, 50, 60], "class": "object", "confidence": 0.95}],
            [{"crop_index": 0, "bbox": [10, 20, 50, 60]}]
        )
        yield mock_processor


# Фикстура для тестового эмбеддинга
@pytest.fixture
def test_embedding():
    """Тестовый эмбеддинг размерности 1280"""
    return np.random.rand(1280).astype(np.float32).tolist()


# Для решения проблем с asyncio
@pytest.fixture(scope="session")
def event_loop():
    """Создание event loop для тестов"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()
