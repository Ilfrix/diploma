from datetime import datetime
import logging
import os

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
    status,
)
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.kafka_producer import kafka_producer
from app.minio_client import minio_client
from app.models import ImageModel, ProcessStatus, Sample, User
from app.schemas import SampleResponse, SampleUpdate
from app.utils import hash_image


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/samples", tags=["samples"])


@router.post("", response_model=SampleResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_new_sample(
    name: str = Form(...),
    description: str | None = Form(None),
    image: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Создание нового эталона изображения (асинхронная обработка)"""

    # Валидация файла
    if not image.content_type or not image.content_type.startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="File must be an image"
        )

    # Чтение содержимого
    image_bytes = await image.read()
    image_hash = hash_image(image_bytes)

    existing_image = (
        db.query(ImageModel).filter(ImageModel.image_hash == image_hash).first()
    )

    if existing_image:
        existing_sample = (
            db.query(Sample)
            .filter(
                Sample.user_id == current_user.id, Sample.image_id == existing_image.id
            )
            .first()
        )

        if existing_sample:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Duplicate image already exists as sample: {existing_sample.id}",
            )

    sample = Sample(
        user_id=current_user.id,
        name=name,
        description=description,
        status=ProcessStatus.PENDING,
    )

    db.add(sample)
    db.commit()
    db.refresh(sample)

    try:
        if image.filename is None:
            raise Exception("no filename in image")
        file_extension = os.path.splitext(image.filename)[1]
        object_path = f"samples/{current_user.id}/{sample.id}{file_extension}"

        minio_client.upload_file(
            file_data=image_bytes,
            object_path=object_path,
            content_type=image.content_type,
        )

        if existing_image:
            image_model = existing_image
        else:
            # Создание записи в таблице images
            image_model = ImageModel(
                image_path=object_path,
                image_hash=image_hash,
                mime_type=image.content_type,
            )
            db.add(image_model)
            db.flush()

        sample.image_id = image_model.id
        sample.status = ProcessStatus.PROCESSING
        db.commit()
        # Отправка в Kafka для асинхронной обработки
        await kafka_producer.send_image_for_processing(
            image_id=sample.id,
            image_bytes=image_bytes,
            metadata={
                "sample_id": sample.id,
                "user_id": current_user.id,
                "username": current_user.username,
                "name": name,
                "description": description,
                "image_path": object_path,
                "image_hash": image_hash,
                "image_id": image_model.id,
                "mime_type": image.content_type,
            },
        )

    except Exception as e:
        # Откат при ошибке
        db.delete(sample)
        db.commit()
        if object_path:
            minio_client.delete_file(object_path)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to queue image for processing: {e!s}",
        ) from e

    return sample


@router.get("/{sample_id}", response_model=SampleResponse)
async def read_sample(
    sample_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Прочитать информацию об эталоне"""
    sample = (
        db.query(Sample)
        .filter(
            Sample.id == sample_id,
        )
        .first()
    )

    if not sample:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Sample not found"
        )
    sample.isOwner = current_user.id == sample.user_id
    sample.owner_name = None
    if sample.user_id != current_user.id:
        user = db.query(User).filter(User.id == sample.user_id).first()
        if user is not None:
            sample.owner_name = user.username

    return sample


@router.get("/{sample_id}/image")
async def get_sample_image(
    sample_id: str,
    expires: int = 3600,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Получить временную ссылку на изображение из MinIO"""

    sample = (
        db.query(Sample)
        .filter(Sample.id == sample_id, Sample.user_id == current_user.id)
        .first()
    )

    if not sample:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Sample not found"
        )

    if not sample.image:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Image not found for this sample",
        )

    # Получение временной ссылки из MinIO
    image_url = minio_client.get_file_url(sample.image.image_path, expires)

    return {"sample_id": sample_id, "image_url": image_url, "expires_in": expires}


@router.get("/{sample_id}/crops")
async def get_sample_crops(
    sample_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Получить список кропов для сэмпла"""

    sample = (
        db.query(Sample)
        .filter(Sample.id == sample_id, Sample.user_id == current_user.id)
        .first()
    )

    if not sample:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Sample not found"
        )

    if not sample.image:
        return {"sample_id": sample_id, "crops": [], "count": 0}

    # Получение всех кропов для изображения
    crops = sample.image.crops if sample.image.crops else []

    # Формирование ответа с временными ссылками
    crops_data = []
    for crop in crops:
        crop_url = minio_client.get_file_url(crop.crop_path, expires=3600)
        crops_data.append(
            {
                "id": crop.id,
                "crop_index": crop.crop_index,
                "crop_url": crop_url,
                "bbox": {
                    "x1": crop.bbox_x1,
                    "y1": crop.bbox_y1,
                    "x2": crop.bbox_x2,
                    "y2": crop.bbox_y2,
                },
                "class_name": crop.class_name,
                "confidence": crop.confidence,
                "vector_id": crop.vector.id if crop.vector else None,
            }
        )

    return {"sample_id": sample_id, "crops": crops_data, "count": len(crops_data)}


@router.get("/{sample_id}/vectors")
async def get_sample_vectors(
    sample_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Получить информацию о векторах для сэмпла"""

    sample = (
        db.query(Sample)
        .filter(Sample.id == sample_id, Sample.user_id == current_user.id)
        .first()
    )

    if not sample:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Sample not found"
        )

    if not sample.image:
        return {"sample_id": sample_id, "vectors": [], "count": 0}

    # Сбор информации о векторах для всех кропов
    vectors_data = []
    for crop in sample.image.crops:
        if crop.vector:
            vectors_data.append(
                {
                    "crop_id": crop.id,
                    "crop_index": crop.crop_index,
                    "vector_id": crop.vector.id,
                    "milvus_id": crop.vector.milvus_id,
                    "class_name": crop.class_name,
                    "confidence": crop.confidence,
                }
            )

    return {"sample_id": sample_id, "vectors": vectors_data, "count": len(vectors_data)}


@router.put("/{sample_id}", response_model=SampleResponse)
async def update_sample(
    sample_id: str,
    sample_update: SampleUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Обновить информацию об эталоне"""

    sample = (
        db.query(Sample)
        .filter(Sample.id == sample_id, Sample.user_id == current_user.id)
        .first()
    )

    if not sample:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Sample not found"
        )

    # Обновление полей
    if sample_update.name is not None:
        sample.name = sample_update.name
    if sample_update.description is not None:
        sample.description = sample_update.description

    sample.updated_at = datetime.now()

    db.commit()
    db.refresh(sample)

    return sample


@router.delete("/{sample_id}")
async def delete_sample(
    sample_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    vector_db = request.app.state.vector_db
    """Удалить эталон"""

    sample = (
        db.query(Sample)
        .filter(Sample.id == sample_id, Sample.user_id == current_user.id)
        .first()
    )

    if not sample:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Sample not found"
        )

    # Сохранение image_id перед удалением сэмпла
    image_id = sample.image_id

    # Удаляем сэмпл
    db.delete(sample)
    db.commit()

    if vector_db:
        vector_db.delete_by_sample_id(sample.id)
    else:
        logger.warning("vector_db не найден")

    # Проверка есть ли другие сэмплы, использующие это изображение
    if image_id:
        other_samples = db.query(Sample).filter(Sample.image_id == image_id).first()

        # Если изображение больше не используется, удаление его и связанных данных
        if not other_samples:
            image = db.query(ImageModel).filter(ImageModel.id == image_id).first()
            if image:
                for crop in image.crops:
                    minio_client.delete_file(crop.crop_path)

                minio_client.delete_file(image.image_path)

                # Удаление изображения из БД (каскадно удалятся кропы и векторы)
                db.delete(image)
                db.commit()

    return {"message": "Sample deleted successfully"}


@router.get("", response_model=list[SampleResponse])
async def list_samples(
    skip: int = 0,
    limit: int = 100,
    status_filter: ProcessStatus | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Получить список всех эталонов пользователя с фильтрацией по статусу"""

    query = db.query(Sample).filter(Sample.user_id == current_user.id)

    if status_filter:
        query = query.filter(Sample.status == status_filter)

    samples = query.order_by(Sample.created_at.desc()).offset(skip).limit(limit).all()

    return samples


@router.get("/stats/summary")
async def get_samples_stats(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """Получить статистику по сэмплам пользователя"""
    stats = (
        db.query(Sample.status, func.count(Sample.id))
        .filter(Sample.user_id == current_user.id)
        .group_by(Sample.status)
        .all()
    )

    total_crops = 0
    total_vectors = 0

    # Подсчет общего количества кропов и векторов
    samples = db.query(Sample).filter(Sample.user_id == current_user.id).all()
    for sample in samples:
        if sample.image and sample.image.crops:
            total_crops += len(sample.image.crops)
            total_vectors += len([c for c in sample.image.crops if c.vector])

    return {
        "total_samples": sum(count for _, count in stats),
        "by_status": {status.value: count for status, count in stats},
        "total_crops": total_crops,
        "total_vectors": total_vectors,
    }
