from datetime import datetime, timedelta
import enum
from typing import Optional
import uuid

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ProcessStatus(enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    PROCESSED = "processed"
    FAILED = "failed"


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    username: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False, index=True
    )
    email: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, index=True
    )
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, onupdate=datetime.now
    )

    samples: Mapped[list["Sample"]] = relationship(
        "Sample", back_populates="user", cascade="all, delete-orphan"
    )


class ImageModel(Base):
    """Таблица оригинальных изображений"""

    __tablename__ = "images"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    image_path: Mapped[str] = mapped_column(String(500), nullable=False)
    image_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    mime_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    samples: Mapped[list["Sample"]] = relationship("Sample", back_populates="image")
    crops: Mapped[list["Crop"]] = relationship(
        "Crop", back_populates="image", cascade="all, delete-orphan"
    )

    __table_args__ = (UniqueConstraint("image_hash", name="uq_image_hash"),)


class Sample(Base):
    __tablename__ = "samples"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    image_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("images.id", ondelete="SET NULL"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[ProcessStatus] = mapped_column(
        Enum(ProcessStatus), default=ProcessStatus.PENDING, nullable=False
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, onupdate=datetime.now
    )

    user: Mapped["User"] = relationship("User", back_populates="samples")
    image: Mapped[Optional["ImageModel"]] = relationship(
        "ImageModel", back_populates="samples"
    )


class Crop(Base):
    """Таблица вырезанных фрагментов (кропов)"""

    __tablename__ = "crops"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    image_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("images.id", ondelete="CASCADE"), nullable=False
    )
    crop_index: Mapped[int] = mapped_column(Integer, nullable=False)
    crop_path: Mapped[str] = mapped_column(String(500), nullable=False)
    color_name: Mapped[str | None] = mapped_column(
        String(50), nullable=True, index=True
    )
    class_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    bbox_x1: Mapped[float] = mapped_column(Float, nullable=False)
    bbox_y1: Mapped[float] = mapped_column(Float, nullable=False)
    bbox_x2: Mapped[float] = mapped_column(Float, nullable=False)
    bbox_y2: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    image: Mapped["ImageModel"] = relationship("ImageModel", back_populates="crops")
    vector: Mapped[Optional["Vector"]] = relationship(
        "Vector", back_populates="crop", uselist=False, cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("image_id", "crop_index", name="uq_crops_image_id_crop_index"),
    )


class Vector(Base):
    """Таблица связи с Milvus (векторные эмбеддинги)"""

    __tablename__ = "vectors"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    crop_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("crops.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    milvus_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    crop: Mapped["Crop"] = relationship("Crop", back_populates="vector")


class SearchRequest(Base):
    __tablename__ = "search_requests"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(36), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=ProcessStatus.PENDING.value
    )
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, onupdate=datetime.now
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now() + timedelta(hours=1)
    )

    # Индексы для быстрого поиска
    __table_args__ = (
        Index("idx_search_requests_user_id", "user_id"),
        Index("idx_search_requests_status", "status"),
        Index("idx_search_requests_expires", "expires_at"),
    )
