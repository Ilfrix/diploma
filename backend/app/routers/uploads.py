import io
import mimetypes
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.responses import RedirectResponse
from PIL import Image
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.minio_client import minio_client
from app.models import ImageModel, Sample, User

router = APIRouter(prefix="/api/uploads", tags=["uploads"])


def get_image_path_from_sample(sample: Sample) -> Optional[str]:
    """Получить путь к изображению в MinIO из семпла через связанную таблицу Image"""
    if sample and sample.image:
        if minio_client.file_exists(sample.image.image_path):
            return sample.image.image_path
    return None


def find_object_by_pattern(user_id: str, image_id: str) -> Optional[str]:
    """Найти объект в MinIO по паттерну (для совместимости со старыми данными)"""
    # Паттерн: samples/{user_id}/{image_id}/*
    prefix = f"samples/{user_id}/{image_id}/"
    files = minio_client.list_files(prefix=prefix, recursive=False)
    
    if files:
        return files[0]["name"]
    
    # Паттерн: samples/{user_id}/{image_id}.{ext}
    for ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']:
        object_path = f"samples/{user_id}/{image_id}{ext}"
        if minio_client.file_exists(object_path):
            return object_path
    
    return None


@router.get("/{image_id}")
async def get_uploaded_image(
    image_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Получение загруженного изображения по ID семпла или имени файла из MinIO
    """
    object_path = None
    
    # Пытаемся найти семпл по ID
    sample = db.query(Sample).filter(
        Sample.id == image_id,
        Sample.user_id == current_user.id
    ).first()
    
    if sample:
        object_path = get_image_path_from_sample(sample)
    
    # Если не нашли через семпл, ищем по паттерну (старые данные)
    if not object_path:
        object_path = find_object_by_pattern(current_user.id, image_id)
    
    # Если файл не найден
    if not object_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Image with id '{image_id}' not found"
        )
    
    # Получаем временную ссылку и перенаправляем
    image_url = minio_client.get_file_url(object_path, expires=3600)
    return RedirectResponse(url=image_url)


@router.get("/thumbnail/{image_id}")
async def get_image_thumbnail(
    image_id: str,
    size: int = 200,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Получение миниатюры изображения из MinIO"""
    object_path = None
    
    # Пытаемся найти семпл
    sample = db.query(Sample).filter(
        Sample.id == image_id,
        Sample.user_id == current_user.id
    ).first()
    
    if sample:
        object_path = get_image_path_from_sample(sample)
    
    # Если не нашли, ищем по паттерну
    if not object_path:
        object_path = find_object_by_pattern(current_user.id, image_id)
    
    if not object_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Image with id '{image_id}' not found"
        )
    
    try:
        # Скачиваем оригинал из MinIO
        image_bytes = minio_client.download_file(object_path)
        
        # Создаем миниатюру
        with Image.open(io.BytesIO(image_bytes)) as img:
            # Конвертируем в RGB если нужно
            if img.mode in ('RGBA', 'LA', 'P'):
                img = img.convert('RGB')
            
            # Создаем миниатюру
            img.thumbnail((size, size), Image.Resampling.LANCZOS)
            
            # Сохраняем в байты
            thumb_bytes = io.BytesIO()
            img.save(thumb_bytes, format='JPEG', quality=85, optimize=True)
            thumb_bytes.seek(0)
            
            return Response(
                content=thumb_bytes.getvalue(),
                media_type="image/jpeg",
                headers={
                    "Cache-Control": "public, max-age=3600",
                    "Content-Disposition": f"inline; filename=thumbnail_{image_id}.jpg"
                }
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create thumbnail: {str(e)}"
        )


@router.get("/sample/{sample_id}/image")
async def get_sample_image(
    sample_id: str,
    thumbnail: bool = False,
    size: int = 200,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Получение изображения семпла по ID семпла из MinIO
    """
    sample = db.query(Sample).filter(
        Sample.id == sample_id,
        # Sample.user_id == current_user.id
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
    
    image_path = sample.image.image_path
    
    if not minio_client.file_exists(image_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Image file not found in storage"
        )
    
    # Если нужна миниатюра
    if thumbnail:
        try:
            # Скачиваем оригинал из MinIO
            image_bytes = minio_client.download_file(image_path)
            
            # Создаем миниатюру
            with Image.open(io.BytesIO(image_bytes)) as img:
                if img.mode in ('RGBA', 'LA', 'P'):
                    img = img.convert('RGB')
                
                img.thumbnail((size, size), Image.Resampling.LANCZOS)
                
                thumb_bytes = io.BytesIO()
                img.save(thumb_bytes, format='JPEG', quality=85, optimize=True)
                thumb_bytes.seek(0)
                
                return Response(
                    content=thumb_bytes.getvalue(),
                    media_type="image/jpeg",
                    headers={
                        "Cache-Control": "public, max-age=3600",
                        "Content-Disposition": f"inline; filename=sample_{sample_id}_thumb.jpg"
                    }
                )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to create thumbnail: {str(e)}"
            )
    
    # Возвращаем временную ссылку на оригинал
    image_url = minio_client.get_file_url(image_path, expires=3600)
    return RedirectResponse(url=image_url)


@router.get("/sample/{sample_id}/presigned-url")
async def get_sample_presigned_url(
    sample_id: str,
    expires: int = 3600,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Получение подписанной URL для прямого доступа к изображению в MinIO
    """
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
    
    image_path = sample.image.image_path
    
    if not minio_client.file_exists(image_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Image file not found in storage"
        )
    
    image_url = minio_client.get_file_url(image_path, expires)
    
    return {
        "sample_id": sample_id,
        "image_url": image_url,
        "expires_in": expires,
        "expires_at": datetime.now().timestamp() + expires
    }


@router.get("/sample/{sample_id}/download")
async def download_sample_image(
    sample_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Скачивание изображения семпла из MinIO как вложение
    """
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
    
    image_path = sample.image.image_path
    
    # Скачиваем файл из MinIO
    image_bytes = minio_client.download_file(image_path)
    
    # Определяем MIME тип
    mime_type, _ = mimetypes.guess_type(image_path)
    if not mime_type:
        mime_type = "application/octet-stream"
    
    # Получаем имя файла
    filename = image_path.split('/')[-1]
    
    return Response(
        content=image_bytes,
        media_type=mime_type,
        headers={
            "Content-Disposition": f"attachment; filename={filename}",
            "Cache-Control": "public, max-age=3600"
        }
    )


@router.get("/sample/{sample_id}/info")
async def get_sample_image_info(
    sample_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Получение информации об изображении семпла из MinIO
    """
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
    
    image_path = sample.image.image_path
    file_info = minio_client.get_file_info(image_path)
    
    if not file_info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found in storage"
        )
    
    return {
        "sample_id": sample_id,
        "image_id": sample.image.id,
        "object_path": image_path,
        "size_bytes": file_info.get("size"),
        "size_kb": round(file_info.get("size", 0) / 1024, 2),
        "size_mb": round(file_info.get("size", 0) / (1024 * 1024), 2),
        "last_modified": file_info.get("last_modified"),
        "content_type": file_info.get("content_type"),
        "etag": file_info.get("etag")
    }


@router.get("/batch/presigned-urls")
async def get_batch_presigned_urls(
    sample_ids: str,
    expires: int = 3600,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Получение подписанных URL для нескольких изображений сразу
    
    Args:
        sample_ids: Список ID семплов через запятую
        expires: Время жизни ссылок в секундах
    """
    ids = [id.strip() for id in sample_ids.split(",")]
    result = []
    
    for sample_id in ids:
        sample = db.query(Sample).filter(
            Sample.id == sample_id,
            Sample.user_id == current_user.id
        ).first()
        
        if sample and sample.image and minio_client.file_exists(sample.image.image_path):
            image_url = minio_client.get_file_url(sample.image.image_path, expires)
            result.append({
                "sample_id": sample_id,
                "image_id": sample.image.id,
                "image_url": image_url,
                "exists": True
            })
        else:
            result.append({
                "sample_id": sample_id,
                "image_id": None,
                "image_url": None,
                "exists": False
            })
    
    return {
        "urls": result,
        "expires_in": expires,
        "expires_at": datetime.now().timestamp() + expires
    }


@router.get("/check/{image_id}")
async def check_image_exists(
    image_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Проверка существования изображения в MinIO
    """
    object_path = None
    image_model = None
    
    # Пытаемся найти семпл
    sample = db.query(Sample).filter(
        Sample.id == image_id,
        Sample.user_id == current_user.id
    ).first()
    
    if sample and sample.image:
        object_path = sample.image.image_path
        image_model = sample.image
    else:
        # Пытаемся найти напрямую в таблице Image
        image_model = db.query(ImageModel).filter(ImageModel.id == image_id).first()
        if image_model:
            object_path = image_model.image_path
    
    # Если не нашли через БД, ищем по паттерну (старые данные)
    if not object_path:
        object_path = find_object_by_pattern(current_user.id, image_id)
    
    if object_path:
        file_info = minio_client.get_file_info(object_path)
        return {
            "exists": True,
            "image_id": image_id,
            "object_path": object_path,
            "size_bytes": file_info.get("size") if file_info else None
        }
    
    return {
        "exists": False,
        "image_id": image_id
    }


@router.get("/by-image/{image_id}")
async def get_image_by_id(
    image_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Получение изображения напрямую по ID из таблицы images
    """
    # Проверяем, что изображение принадлежит пользователю (через семплы)
    image = db.query(ImageModel).filter(ImageModel.id == image_id).first()
    
    if not image:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Image not found"
        )
    
    # Проверяем, есть ли у пользователя семпл с этим изображением
    sample = db.query(Sample).filter(
        Sample.image_id == image_id,
        Sample.user_id == current_user.id
    ).first()
    
    if not sample:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this image"
        )
    
    if not minio_client.file_exists(image.image_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Image file not found in storage"
        )
    
    # Получаем временную ссылку
    image_url = minio_client.get_file_url(image.image_path, expires=3600)
    return RedirectResponse(url=image_url)
