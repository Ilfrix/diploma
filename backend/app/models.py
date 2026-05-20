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

    samples = relationship("Sample", back_populates="user", cascade="all, delete-orphan")


class ImageModel(Base):
    """Таблица оригинальных изображений"""
    __tablename__ = "images"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    image_path = Column(String(500), nullable=False)
    image_hash = Column(String(64), nullable=False, index=True)
    mime_type = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    
    samples = relationship("Sample", back_populates="image")
    crops = relationship("Crop", back_populates="image", cascade="all, delete-orphan")

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
    
    user = relationship("User", back_populates="samples")
    image = relationship("ImageModel", back_populates="samples")


class Crop(Base):
    """Таблица вырезанных фрагментов (кропов)"""
    __tablename__ = "crops"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    image_id = Column(String(36), ForeignKey("images.id", ondelete="CASCADE"), nullable=False)
    crop_index = Column(Integer, nullable=False)
    crop_path = Column(String(500), nullable=False)
    bbox_x1 = Column(Float, nullable=False)
    bbox_y1 = Column(Float, nullable=False)
    bbox_x2 = Column(Float, nullable=False)
    bbox_y2 = Column(Float, nullable=False)
    class_name = Column(String(100), nullable=True)
    confidence = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    
    image = relationship("ImageModel", back_populates="crops")
    vector = relationship("Vector", back_populates="crop", uselist=False, cascade="all, delete-orphan")
    
    __table_args__ = (
        UniqueConstraint('image_id', 'crop_index', name='uq_crops_image_id_crop_index'),
    )


class Vector(Base):
    """Таблица связи с Milvus (векторные эмбеддинги)"""
    __tablename__ = "vectors"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    crop_id = Column(String(36), ForeignKey("crops.id", ondelete="CASCADE"), nullable=False, unique=True)
    milvus_id = Column(String(100), unique=True, nullable=False)
    created_at = Column(DateTime, default=datetime.now)

    crop = relationship("Crop", back_populates="vector")
