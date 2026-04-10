# main.py
import os
import uuid
import hashlib
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, HTTPException, Depends, status, Form
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, Column, String, DateTime, Integer, Float, Text, ForeignKey, Boolean
# from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, relationship, declarative_base
from pydantic import BaseModel, Field
import bcrypt
import jwt
from PIL import Image
import numpy as np
import io
import logging

# Импорт ML компонентов (предполагаем, что они реализованы отдельно)
from backend.app.ml.detector import ImageDetector
from backend.app.ml.encoder import ImageEncoder
from vector_db import VectorDatabase

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============= Конфигурация =============
class Config:
    SECRET_KEY = "your-secret-key-change-in-production"
    ALGORITHM = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES = 30
    DATABASE_URL = "postgresql://user:password@localhost/mydb"
    VECTOR_DB_PATH = "./vector_db"
    UPLOAD_DIR = "./uploads"
    MODEL_PATH = "./models"

config = Config()

# ============= Инициализация ML компонентов =============
detector = ImageDetector(model_path=os.path.join(config.MODEL_PATH, "detector.pth"))
encoder = ImageEncoder(model_path=os.path.join(config.MODEL_PATH, "encoder.pth"))
vector_db = VectorDatabase(db_path=config.VECTOR_DB_PATH)

# ============= База данных =============
engine = create_engine(config.DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Модели SQLAlchemy
class User(Base):
    __tablename__ = "users"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    username = Column(String(100), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    # Отношения
    samples = relationship("Sample", back_populates="user", cascade="all, delete-orphan")

class Sample(Base):
    __tablename__ = "samples"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    image_path = Column(String(500), nullable=False)
    image_hash = Column(String(64), unique=True, nullable=False, index=True)
    vector_id = Column(String(100), unique=True, nullable=False)  # ID в векторной БД
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    # Отношения
    user = relationship("User", back_populates="samples")

# Создание таблиц
Base.metadata.create_all(bind=engine)

# ============= Pydantic схемы =============
class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=100)
    email: str = Field(..., pattern=r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
    password: str = Field(..., min_length=6)

class UserLogin(BaseModel):
    username: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    user_id: str
    username: str

class SampleCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None

class SampleUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None

class SampleResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    image_path: str
    created_at: datetime
    updated_at: datetime

class SimilarImage(BaseModel):
    sample_id: str
    name: str
    description: Optional[str]
    similarity_score: float
    image_path: str

class SimilarResponse(BaseModel):
    query_sample_id: str
    query_name: str
    similar_images: List[SimilarImage]

# ============= Вспомогательные функции =============
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def hash_image(image_bytes: bytes) -> str:
    """Вычисление хэша изображения для проверки дубликатов"""
    return hashlib.sha256(image_bytes).hexdigest()

def save_image_file(file: UploadFile, user_id: str, sample_id: str) -> str:
    """Сохранение загруженного изображения"""
    os.makedirs(config.UPLOAD_DIR, exist_ok=True)
    
    file_extension = Path(file.filename).suffix
    filename = f"{user_id}_{sample_id}_{datetime.now().timestamp()}{file_extension}"
    file_path = os.path.join(config.UPLOAD_DIR, filename)
    
    content = file.file.read()
    with open(file_path, "wb") as f:
        f.write(content)
    
    # Сброс указателя для дальнейшего использования
    file.file.seek(0)
    
    return file_path

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now() + expires_delta
    else:
        expire = datetime.now() + timedelta(minutes=config.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, config.SECRET_KEY, algorithm=config.ALGORITHM)
    return encoded_jwt

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer()),
    db: Session = Depends(get_db)
) -> User:
    """Получение текущего пользователя из JWT токена"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        token = credentials.credentials
        payload = jwt.decode(token, config.SECRET_KEY, algorithms=[config.ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
        token_data = TokenData(user_id=user_id, username=payload.get("username"))
    except jwt.PyJWTError:
        raise credentials_exception
    
    user = db.query(User).filter(User.id == token_data.user_id).first()
    if user is None:
        raise credentials_exception
    
    return user

def process_image(image_bytes: bytes) -> np.ndarray:
    """Обработка изображения: детекция и извлечение признаков"""
    # Загрузка изображения
    image = Image.open(io.BytesIO(image_bytes))
    image_array = np.array(image)
    
    # Детекция объектов (если нужно)
    detections = detector.detect(image_array)
    
    # Извлечение эмбеддингов
    embedding = encoder.encode(image_array)
    
    return embedding, detections

# ============= FastAPI приложение =============
app = FastAPI(
    title="Duplicate Detection System",
    description="Система для распознавания дубликатов изображений",
    version="1.0.0"
)

# CORS настройки
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============= Эндпоинты аутентификации =============
@app.post("/api/register", response_model=Token, status_code=status.HTTP_201_CREATED)
async def register(user_data: UserCreate, db: Session = Depends(get_db)):
    """Регистрация нового пользователя"""
    
    # Проверка существования пользователя
    existing_user = db.query(User).filter(
        (User.username == user_data.username) | (User.email == user_data.email)
    ).first()
    
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username or email already registered"
        )
    
    # Создание пользователя
    user = User(
        username=user_data.username,
        email=user_data.email,
        password_hash=hash_password(user_data.password)
    )
    
    db.add(user)
    db.commit()
    db.refresh(user)
    
    # Создание токена
    access_token = create_access_token(
        data={"sub": user.id, "username": user.username}
    )
    
    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/api/login", response_model=Token)
async def login(user_data: UserLogin, db: Session = Depends(get_db)):
    """Вход в аккаунт"""
    
    user = db.query(User).filter(User.username == user_data.username).first()
    
    if not user or not verify_password(user_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password"
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled"
        )
    
    access_token = create_access_token(
        data={"sub": user.id, "username": user.username}
    )
    
    return {"access_token": access_token, "token_type": "bearer"}

# ============= Эндпоинты для работы с эталонами =============
@app.post("/api/samples", response_model=SampleResponse, status_code=status.HTTP_201_CREATED)
async def create_new_sample(
    name: str = Form(...),
    description: Optional[str] = Form(None),
    image: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Создание нового эталона изображения"""
    
    # Валидация файла
    if not image.content_type or not image.content_type.startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be an image"
        )
    
    # Чтение содержимого
    image_bytes = await image.read()
    
    # Проверка дубликата по хэшу
    image_hash = hash_image(image_bytes)
    existing_sample = db.query(Sample).filter(Sample.image_hash == image_hash).first()
    
    if existing_sample:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Duplicate image already exists as sample: {existing_sample.id}"
        )
    
    # Создание записи в БД
    sample = Sample(
        user_id=current_user.id,
        name=name,
        description=description,
        image_path="",  # Временно
        image_hash=image_hash,
        vector_id=""    # Временно
    )
    
    db.add(sample)
    db.commit()
    db.refresh(sample)
    
    try:
        # Сохранение файла
        image_path = save_image_file(image, current_user.id, sample.id)
        sample.image_path = image_path
        
        # Обработка изображения ML
        embedding, detections = process_image(image_bytes)
        
        # Сохранение в векторной БД
        vector_id = f"sample_{sample.id}"
        vector_db.add_vector(vector_id, embedding, {
            "sample_id": sample.id,
            "user_id": current_user.id,
            "name": name,
            "detections": detections
        })
        sample.vector_id = vector_id
        
        db.commit()
        
    except Exception as e:
        # Откат при ошибке
        db.delete(sample)
        db.commit()
        logger.error(f"Error processing image: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process image: {str(e)}"
        )
    
    return sample

@app.get("/api/samples/{sample_id}", response_model=SampleResponse)
async def read_sample(
    sample_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Прочитать информацию об эталоне"""
    
    sample = db.query(Sample).filter(
        Sample.id == sample_id,
        Sample.user_id == current_user.id
    ).first()
    
    if not sample:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sample not found"
        )
    
    return sample

@app.get("/api/samples/{sample_id}/similar", response_model=SimilarResponse)
async def get_similar(
    sample_id: str,
    limit: int = 10,
    threshold: float = 0.7,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Найти ближайшие изображения к эталону"""
    
    # Получение эталона
    sample = db.query(Sample).filter(
        Sample.id == sample_id,
        Sample.user_id == current_user.id
    ).first()
    
    if not sample:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sample not found"
        )
    
    # Получение эмбеддинга из векторной БД
    embedding = vector_db.get_vector(sample.vector_id)
    if embedding is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vector embedding not found"
        )
    
    # Поиск похожих
    similar_vectors = vector_db.search_similar(
        embedding, 
        k=limit + 1,  # +1 для исключения самого себя
        threshold=threshold
    )
    
    # Фильтрация результатов
    similar_images = []
    for vec_id, score, metadata in similar_vectors:
        # Пропускаем сам эталон
        if vec_id == sample.vector_id:
            continue
            
        # Получаем информацию о найденном образце
        similar_sample_id = metadata.get("sample_id")
        if similar_sample_id:
            similar_sample = db.query(Sample).filter(Sample.id == similar_sample_id).first()
            if similar_sample and similar_sample.user_id == current_user.id:
                similar_images.append(SimilarImage(
                    sample_id=similar_sample.id,
                    name=similar_sample.name,
                    description=similar_sample.description,
                    similarity_score=float(score),
                    image_path=similar_sample.image_path
                ))
    
    return SimilarResponse(
        query_sample_id=sample.id,
        query_name=sample.name,
        similar_images=similar_images[:limit]
    )

@app.put("/api/samples/{sample_id}", response_model=SampleResponse)
async def update_sample(
    sample_id: str,
    sample_update: SampleUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Обновить информацию об эталоне"""
    
    sample = db.query(Sample).filter(
        Sample.id == sample_id,
        Sample.user_id == current_user.id
    ).first()
    
    if not sample:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sample not found"
        )
    
    # Обновление полей
    if sample_update.name is not None:
        sample.name = sample_update.name
    if sample_update.description is not None:
        sample.description = sample_update.description
    
    sample.updated_at = datetime.now()
    
    db.commit()
    db.refresh(sample)
    
    # Обновление метаданных в векторной БД
    vector_db.update_metadata(sample.vector_id, {
        "name": sample.name,
        "description": sample.description
    })
    
    return sample

@app.delete("/api/samples/{sample_id}")
async def delete_sample(
    sample_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Удалить эталон"""
    
    sample = db.query(Sample).filter(
        Sample.id == sample_id,
        Sample.user_id == current_user.id
    ).first()
    
    if not sample:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sample not found"
        )
    
    # Удаление из векторной БД
    vector_db.delete_vector(sample.vector_id)
    
    # Удаление файла изображения
    if os.path.exists(sample.image_path):
        os.remove(sample.image_path)
    
    # Удаление из реляционной БД
    db.delete(sample)
    db.commit()
    
    return {"message": "Sample deleted successfully"}

@app.get("/api/samples", response_model=List[SampleResponse])
async def list_samples(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Получить список всех эталонов пользователя"""
    
    samples = db.query(Sample).filter(
        Sample.user_id == current_user.id
    ).offset(skip).limit(limit).all()
    
    return samples

# ============= Дополнительный эндпоинт для поиска по загруженному изображению =============
@app.post("/api/search/similar", response_model=List[SimilarImage])
async def search_similar_by_image(
    image: UploadFile = File(...),
    limit: int = 10,
    threshold: float = 0.7,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Поиск похожих изображений по загруженному файлу (без сохранения)"""
    
    # Валидация файла
    if not image.content_type or not image.content_type.startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be an image"
        )
    
    # Обработка изображения
    image_bytes = await image.read()
    embedding, detections = process_image(image_bytes)
    
    # Поиск в векторной БД
    similar_vectors = vector_db.search_similar(embedding, k=limit, threshold=threshold)
    
    # Формирование ответа
    similar_images = []
    for vec_id, score, metadata in similar_vectors:
        sample_id = metadata.get("sample_id")
        if sample_id:
            sample = db.query(Sample).filter(
                Sample.id == sample_id,
                Sample.user_id == current_user.id
            ).first()
            
            if sample:
                similar_images.append(SimilarImage(
                    sample_id=sample.id,
                    name=sample.name,
                    description=sample.description,
                    similarity_score=float(score),
                    image_path=sample.image_path
                ))
    
    return similar_images[:limit]

# ============= Health check =============
@app.get("/api/health")
async def health_check():
    """Проверка состояния системы"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "vector_db": vector_db.health_check(),
        "ml_models": {
            "detector": detector.is_loaded(),
            "encoder": encoder.is_loaded()
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
