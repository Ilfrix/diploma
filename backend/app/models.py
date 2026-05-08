import uuid
from datetime import datetime

from sqlalchemy import Column, String, DateTime, Text, ForeignKey, Boolean, Enum, UniqueConstraint, Float, Integer
from sqlalchemy.orm import relationship
import enum

from app.database import Base


class SampleStatus(enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    PROCESSED = "processed"
    FAILED = "failed"


class User(Base):
    __tablename__ = "users"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    username = Column(String(100), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    # Relationships
    samples = relationship("Sample", back_populates="user", cascade="all, delete-orphan")


class ImageModel(Base):
    """Таблица оригинальных изображений"""
    __tablename__ = "images"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    image_path = Column(String(500), nullable=False)
    image_hash = Column(String(64), nullable=False, index=True)
    mime_type = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    
    # Relationships
    samples = relationship("Sample", back_populates="image")
    crops = relationship("Crop", back_populates="image", cascade="all, delete-orphan")
    
    # Уникальный индекс на хэш (предотвращает дублирование одного и того же изображения)
    __table_args__ = (
        UniqueConstraint('image_hash', name='uq_image_hash'),
    )


class Sample(Base):
    __tablename__ = "samples"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    image_id = Column(String(36), ForeignKey("images.id", ondelete="SET NULL"), nullable=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(Enum(SampleStatus), default=SampleStatus.PENDING, nullable=False)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    # Relationships
    user = relationship("User", back_populates="samples")
    image = relationship("ImageModel", back_populates="samples")


class Crop(Base):
    """Таблица вырезанных фрагментов (кропов)"""
    __tablename__ = "crops"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    image_id = Column(String(36), ForeignKey("images.id", ondelete="CASCADE"), nullable=False)
    crop_index = Column(Integer, nullable=False)  # Порядковый номер кропа в изображении
    crop_path = Column(String(500), nullable=False)  # Путь к файлу кропа в MinIO
    bbox_x1 = Column(Float, nullable=False)  # Левая координата bounding box
    bbox_y1 = Column(Float, nullable=False)  # Верхняя координата bounding box
    bbox_x2 = Column(Float, nullable=False)  # Правая координата bounding box
    bbox_y2 = Column(Float, nullable=False)  # Нижняя координата bounding box
    class_name = Column(String(100), nullable=True)  # Класс объекта
    confidence = Column(Float, nullable=True)  # Уверенность детекции
    created_at = Column(DateTime, default=datetime.now)
    
    # Relationships
    image = relationship("ImageModel", back_populates="crops")
    vector = relationship("Vector", back_populates="crop", uselist=False, cascade="all, delete-orphan")
    
    # Составной уникальный индекс на (image_id, crop_index)
    __table_args__ = (
        UniqueConstraint('image_id', 'crop_index', name='uq_crops_image_id_crop_index'),
    )


class Vector(Base):
    """Таблица связи с Milvus (векторные эмбеддинги)"""
    __tablename__ = "vectors"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    crop_id = Column(String(36), ForeignKey("crops.id", ondelete="CASCADE"), nullable=False, unique=True)
    milvus_id = Column(String(100), unique=True, nullable=False)  # ID вектора в Milvus
    created_at = Column(DateTime, default=datetime.now)
    
    # Relationships
    crop = relationship("Crop", back_populates="vector")
