import os
from typing import Optional, List
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, BackgroundTasks
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, Sample, SampleStatus
from app.schemas import SampleCreate, SampleUpdate, SampleResponse
from app.auth import get_current_user
from app.utils import hash_image, save_image_file, delete_image_file
from app.ml.processor import process_image
from app.vector_db import VectorDatabase
from app.config import config
from app.kafka_producer import kafka_producer

router = APIRouter(prefix="/api/samples", tags=["samples"])

# Инициализация векторной БД (будет установлена из main)
vector_db = None

def set_vector_db(db):
    global vector_db
    vector_db = db

@router.post("", response_model=SampleResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_new_sample(
    name: str = Form(...),
    description: Optional[str] = Form(None),
    image: UploadFile = File(...),
    background_tasks: BackgroundTasks = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Создание нового эталона изображения (асинхронная обработка)"""
    
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
    
    # Сохранение файла
    sample = Sample(
        user_id=current_user.id,
        name=name,
        description=description,
        image_path="",  # Будет заполнено после сохранения
        image_hash=image_hash,
        vector_id=None,
        status=SampleStatus.PENDING
    )
    
    db.add(sample)
    db.commit()
    db.refresh(sample)
    
    try:
        # Сохранение файла на диск
        await image.seek(0)
        image_path = save_image_file(image, current_user.id, sample.id)
        sample.image_path = image_path
        db.commit()
        
        # Отправка в Kafka для асинхронной обработки
        await kafka_producer.send_image_for_processing(
            image_id=sample.id,
            image_bytes=image_bytes,
            metadata={
                "user_id": current_user.id,
                "username": current_user.username,
                "name": name,
                "description": description,
                "image_path": image_path,
                "image_hash": image_hash
            }
        )
        
        # Обновление статуса
        sample.status = SampleStatus.PROCESSING
        db.commit()
        
    except Exception as e:
        # Откат при ошибке
        db.delete(sample)
        db.commit()
        if image_path:
            delete_image_file(image_path)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to queue image for processing: {str(e)}"
        )
    
    return sample


@router.get("/{sample_id}/status")
async def get_sample_status(
    sample_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Получение статуса обработки эталона"""
    
    sample = db.query(Sample).filter(
        Sample.id == sample_id,
        Sample.user_id == current_user.id
    ).first()
    
    if not sample:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sample not found"
        )
    
    return {
        "id": sample.id,
        "status": sample.status.value,
        "error_message": sample.error_message,
        "is_ready": sample.status == SampleStatus.PROCESSED
    }


@router.get("/{sample_id}", response_model=SampleResponse)
async def read_sample(
    sample_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Прочитать информацию об эталоне"""
    print('router_get ' * 10)
    
    sample = db.query(Sample).filter(
        Sample.id == sample_id,
        Sample.user_id == current_user.id
    ).first()
    print(sample)
    
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
