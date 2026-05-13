from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status, Query
from sqlalchemy.orm import Session
import numpy as np

from app.database import get_db
from app.models import User, Sample, Crop, Vector as VectorModel
from app.schemas import SimilarImage, SimilarResponse, SampleResponse, CropResponse
from app.auth import get_current_user
from app.ml.processor import process_image_with_crops

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
    use_all_crops: bool = False,  # Если True - ищем по всем кропам, если False - по первому
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Найти ближайшие изображения к эталону"""
    print('sample_id', sample_id)

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
    
    if not sample.image:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Image not found for this sample"
        )
    
    # Получаем кропы и их векторы
    crops_with_vectors = db.query(Crop, VectorModel).join(
        VectorModel, Crop.id == VectorModel.crop_id
    ).filter(
        Crop.image_id == sample.image_id,
    ).all()
    
    if not crops_with_vectors:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No crop vectors found for this sample"
        )
    
    # Собираем результаты от всех кропов
    all_similar = {}
    
    for crop, vector in crops_with_vectors:
        # Получаем эмбеддинг из векторной БД по milvus_id
        embedding = vector_db.get_vector(vector.milvus_id)
        if embedding is None:
            continue

        # Поиск похожих векторов
        similar_vectors = vector_db.search_similar(
            embedding, 
            k=limit + 1,
            threshold=threshold
        )
        
        # Агрегируем результаты
        for vec_id, score, metadata in similar_vectors:
            if vec_id == vector.milvus_id:
                continue
                
            similar_sample_id = metadata.get("sample_id")
            if not similar_sample_id or similar_sample_id == sample_id:
                continue
            
            # Сохраняем максимальную схожесть для каждого сэмпла
            if similar_sample_id not in all_similar or score > all_similar[similar_sample_id]["score"]:
                all_similar[similar_sample_id] = {
                    "score": score,
                    "metadata": metadata
                }
    
    # Формируем ответ
    similar_images = []
    for sample_id, data in sorted(all_similar.items(), key=lambda x: x[1]["score"], reverse=True)[:limit]:
        similar_sample = db.query(Sample).filter(
            Sample.id == sample_id,
            Sample.user_id == current_user.id
        ).first()
        
        if similar_sample and similar_sample.image:
            similar_images.append(SimilarImage(
                sample_id=similar_sample.id,
                name=similar_sample.name,
                description=similar_sample.description,
                similarity_score=float(data["score"]),
                image_id=similar_sample.image_id,
                image_url=None  # Можно добавить генерацию временной ссылки
            ))
    print('end of get_similar')
    
    return SimilarResponse(
        query_sample_id=sample.id,
        query_name=sample.name,
        similar_images=similar_images,
        processing_time_ms=None
    )


@router.get("/samples/{sample_id}/crops", response_model=List[CropResponse])
async def get_sample_crops(
    sample_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Получить все кропы для сэмпла"""
    
    sample = db.query(Sample).filter(
        Sample.id == sample_id,
        Sample.user_id == current_user.id
    ).first()
    
    if not sample:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sample not found"
        )
    
    if not sample.image:
        return []
    
    crops = db.query(Crop).filter(Crop.image_id == sample.image_id).all()
    return crops


@router.get("/samples/{sample_id}/vectors")
async def get_sample_vectors(
    sample_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Получить информацию о векторах для сэмпла"""
    
    sample = db.query(Sample).filter(
        Sample.id == sample_id,
        Sample.user_id == current_user.id
    ).first()
    
    if not sample:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sample not found"
        )
    
    if not sample.image:
        return {"vectors": []}
    
    crops_with_vectors = db.query(Crop, VectorModel).join(
        VectorModel, Crop.id == VectorModel.crop_id
    ).filter(
        Crop.image_id == sample.image_id
    ).all()
    
    vectors_info = []
    for crop, vector in crops_with_vectors:
        vectors_info.append({
            "crop_id": crop.id,
            "crop_index": crop.crop_index,
            "class_name": crop.class_name,
            "confidence": crop.confidence,
            "milvus_id": vector.milvus_id,
            "bbox": {
                "x1": crop.bbox_x1,
                "y1": crop.bbox_y1,
                "x2": crop.bbox_x2,
                "y2": crop.bbox_y2
            }
        })
    
    return {"vectors": vectors_info, "count": len(vectors_info)}


@router.get("/search/by-crop/{crop_id}/similar", response_model=List[SimilarImage])
async def search_similar_by_crop(
    crop_id: str,
    limit: int = 10,
    threshold: float = 0.7,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Поиск похожих изображений по ID кропа"""
    
    # Получаем кроп
    crop = db.query(Crop).filter(Crop.id == crop_id).first()
    if not crop:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Crop not found"
        )
    
    # Проверяем права доступа (через сэмпл)
    sample = db.query(Sample).filter(
        Sample.image_id == crop.image_id,
        Sample.user_id == current_user.id
    ).first()
    
    if not sample:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    # Получаем вектор
    vector = db.query(VectorModel).filter(VectorModel.crop_id == crop_id).first()
    if not vector:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vector not found"
        )
    
    # Получаем эмбеддинг из Milvus
    embedding = vector_db.get_vector(vector.milvus_id)
    if embedding is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Embedding not found in vector database"
        )
    
    # Поиск похожих
    similar_vectors = vector_db.search_similar(embedding, k=limit, threshold=threshold)
    
    # Формирование ответа
    similar_images = []
    for vec_id, score, metadata in similar_vectors:
        if vec_id == vector.milvus_id:
            continue
        
        similar_sample_id = metadata.get("sample_id")
        if similar_sample_id:
            similar_sample = db.query(Sample).filter(
                Sample.id == similar_sample_id,
                Sample.user_id == current_user.id
            ).first()
            
            if similar_sample and similar_sample.image:
                similar_images.append(SimilarImage(
                    sample_id=similar_sample.id,
                    name=similar_sample.name,
                    description=similar_sample.description,
                    similarity_score=float(score),
                    image_id=similar_sample.image_id,
                    image_url=None
                ))
    
    return similar_images


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
    
    # Получаем эмбеддинги для кропов
    embeddings, detections, crops_data = process_image_with_crops(
        image_bytes=image_bytes,
        db=None,  # Не сохраняем в БД
        image_id=None
    )
    
    if not embeddings:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCIVABLE_ENTITY,
            detail="Could not extract features from image"
        )
    
    # Ищем в векторной БД (используем первый эмбеддинг или усредняем все)
    # Для простоты используем первый кроп
    query_embedding = embeddings[0] if embeddings else None
    
    if query_embedding is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCIVABLE_ENTITY,
            detail="Could not generate embedding for image"
        )
    
    # Поиск в векторной БД
    similar_vectors = vector_db.search_similar(
        query_embedding, 
        k=limit, 
        threshold=threshold
    )
    
    # Формирование ответа
    similar_images = []
    seen_samples = set()
    
    for vec_id, score, metadata in similar_vectors:
        sample_id = metadata.get("sample_id")
        if not sample_id or sample_id in seen_samples:
            continue
        
        sample = db.query(Sample).filter(
            Sample.id == sample_id,
            Sample.user_id == current_user.id
        ).first()
        
        if sample and sample.image:
            seen_samples.add(sample_id)
            similar_images.append(SimilarImage(
                sample_id=sample.id,
                name=sample.name,
                description=sample.description,
                similarity_score=float(score),
                image_id=sample.image_id,
                image_url=None
            ))
    
    return similar_images


@router.get("/search/crops/{crop_id}")
async def get_crop_info(
    crop_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Получить информацию о кропе и связанном векторе"""
    
    crop = db.query(Crop).filter(Crop.id == crop_id).first()
    if not crop:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Crop not found"
        )
    
    # Проверяем права доступа
    sample = db.query(Sample).filter(
        Sample.image_id == crop.image_id,
        Sample.user_id == current_user.id
    ).first()
    
    if not sample:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    vector = db.query(VectorModel).filter(VectorModel.crop_id == crop_id).first()
    
    return {
        "crop": {
            "id": crop.id,
            "crop_index": crop.crop_index,
            "bbox": {
                "x1": crop.bbox_x1,
                "y1": crop.bbox_y1,
                "x2": crop.bbox_x2,
                "y2": crop.bbox_y2
            },
            "class_name": crop.class_name,
            "confidence": crop.confidence,
            "crop_path": crop.crop_path
        },
        "vector": {
            "id": vector.id if vector else None,
            "milvus_id": vector.milvus_id if vector else None
        },
        "sample": {
            "id": sample.id,
            "name": sample.name,
            "description": sample.description
        }
    }