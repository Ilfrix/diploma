import os
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, Sample
from app.schemas import SampleCreate, SampleUpdate, SampleResponse
from app.auth import get_current_user
from app.utils import hash_image, save_image_file, delete_image_file
from app.ml.processor import process_image
from app.vector_db import VectorDatabase
from app.config import config

router = APIRouter(prefix="/api/samples", tags=["samples"])

# Инициализация векторной БД (будет установлена из main)
vector_db = None

def set_vector_db(db):
    global vector_db
    vector_db = db

@router.post("", response_model=SampleResponse, status_code=status.HTTP_201_CREATED)
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
        image_path="",
        image_hash=image_hash,
        vector_id=""
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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process image: {str(e)}"
        )
    
    return sample

@router.get("/{sample_id}", response_model=SampleResponse)
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

@router.put("/{sample_id}", response_model=SampleResponse)
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
    if vector_db:
        vector_db.update_metadata(sample.vector_id, {
            "name": sample.name,
            "description": sample.description
        })
    
    return sample

@router.delete("/{sample_id}")
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
    if vector_db:
        vector_db.delete_vector(sample.vector_id)
    
    # Удаление файла изображения
    delete_image_file(sample.image_path)
    
    # Удаление из реляционной БД
    db.delete(sample)
    db.commit()
    
    return {"message": "Sample deleted successfully"}

@router.get("", response_model=List[SampleResponse])
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
