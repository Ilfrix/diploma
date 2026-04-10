from typing import List

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, Sample
from app.schemas import SimilarImage, SimilarResponse
from app.auth import get_current_user
from app.ml.processor import process_image

router = APIRouter(prefix="/api", tags=["search"])

# Будет установлен из main
vector_db = None

def set_vector_db(db):
    global vector_db
    vector_db = db

@router.get("/samples/{sample_id}/similar", response_model=SimilarResponse)
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
        k=limit + 1,
        threshold=threshold
    )
    
    # Фильтрация результатов
    similar_images = []
    for vec_id, score, metadata in similar_vectors:
        if vec_id == sample.vector_id:
            continue
            
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

@router.post("/search/similar", response_model=List[SimilarImage])
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
