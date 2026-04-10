import os
import mimetypes
import io
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Response
from fastapi.responses import FileResponse
from PIL import Image
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, Sample
from app.auth import get_current_user
from app.config import config

router = APIRouter(prefix="/api/uploads", tags=["uploads"])

@router.get("/{image_id}")
async def get_uploaded_image(
    image_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Получение загруженного изображения по ID семпла или имени файла
    
    Args:
        image_id: ID семпла или имя файла (с расширением или без)
    """
    print('get_uploaded_image!')
    
    # Пытаемся найти семпл по ID
    sample = db.query(Sample).filter(
        Sample.id == image_id,
        Sample.user_id == current_user.id
    ).first()
    print('sample', sample)
    
    file_path = None
    
    # Если семпл найден, используем его путь
    if sample and sample.image_path and os.path.exists(sample.image_path):
        file_path = sample.image_path
    else:
        # Иначе ищем файл по имени в папке uploads
        upload_dir = Path(config.UPLOAD_DIR)
        
        # Пробуем различные варианты имени файла
        possible_names = [
            image_id,  # как есть
            f"{image_id}.jpg", f"{image_id}.jpeg", f"{image_id}.png",
            f"{image_id}.gif", f"{image_id}.bmp", f"{image_id}.webp"
        ]
        
        # Ищем среди файлов пользователя
        for filename in possible_names:
            candidate_path = upload_dir / filename
            if candidate_path.exists() and candidate_path.is_file():
                # Проверяем, принадлежит ли файл пользователю
                # Имя файла имеет формат: {user_id}_{sample_id}_{timestamp}.ext
                if filename.startswith(current_user.id):
                    file_path = str(candidate_path)
                    break
        
        # Ищем среди всех файлов (если не нашли по user_id)
        if not file_path:
            for ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']:
                candidate_path = upload_dir / f"{image_id}{ext}"
                if candidate_path.exists():
                    file_path = str(candidate_path)
                    break
    
    # Если файл не найден
    if not file_path or not os.path.exists(file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Image with id '{image_id}' not found"
        )
    
    # Определяем MIME тип
    mime_type, _ = mimetypes.guess_type(file_path)
    if not mime_type:
        mime_type = "application/octet-stream"
    
    # Возвращаем файл
    return FileResponse(
        path=file_path,
        media_type=mime_type,
        filename=os.path.basename(file_path),
        headers={
            "Cache-Control": "public, max-age=3600",  # Кэширование на 1 час
            "Access-Control-Expose-Headers": "Content-Disposition"
        }
    )

@router.get("/thumbnail/{image_id}")
async def get_image_thumbnail(
    image_id: str,
    size: int = 200,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Получение миниатюры изображения"""
    print('GETTTTT')
    # Получаем оригинальное изображение
    sample = db.query(Sample).filter(
        Sample.id == image_id,
        Sample.user_id == current_user.id
    ).first()
    
    file_path = None
    if sample and sample.image_path and os.path.exists(sample.image_path):
        file_path = sample.image_path
    else:
        upload_dir = Path(config.UPLOAD_DIR)
        for ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']:
            candidate_path = upload_dir / f"{image_id}{ext}"
            if candidate_path.exists():
                file_path = str(candidate_path)
                break
    
    if not file_path or not os.path.exists(file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Image with id '{image_id}' not found"
        )
    
    try:
        # Создание миниатюры
        with Image.open(file_path) as img:
            # Конвертируем в RGB если нужно
            if img.mode in ('RGBA', 'LA', 'P'):
                img = img.convert('RGB')
            
            # Создаем миниатюру
            img.thumbnail((size, size), Image.Resampling.LANCZOS)
            
            # Сохраняем в байты
            img_bytes = io.BytesIO()
            img.save(img_bytes, format='JPEG', quality=85, optimize=True)
            img_bytes.seek(0)
            
            # Возвращаем Response с байтами
            return Response(
                content=img_bytes.getvalue(),
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


@router.get("/direct/{filename:path}")
async def get_image_direct(
    filename: str,
    current_user: User = Depends(get_current_user)
):
    """
    Прямая загрузка изображения по имени файла (с проверкой прав)
    
    Args:
        filename: Имя файла (относительный путь от ./uploads)
    """
    # Безопасная проверка пути (предотвращение directory traversal)
    upload_dir = Path(config.UPLOAD_DIR).resolve()
    requested_path = (upload_dir / filename).resolve()

    # Проверяем, что путь находится внутри uploads директории
    if not str(requested_path).startswith(str(upload_dir)):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    # Проверяем, что файл принадлежит пользователю
    # Имя файла имеет формат: {user_id}_{sample_id}_{timestamp}.ext
    if not requested_path.name.startswith(current_user.id):
        # Проверяем, есть ли семпл с таким путем в БД и принадлежит ли он пользователю
        from app.database import SessionLocal
        db = SessionLocal()
        try:
            sample = db.query(Sample).filter(
                Sample.image_path == str(requested_path),
                Sample.user_id == current_user.id
            ).first()
            
            if not sample:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied to this file"
                )
        finally:
            db.close()
    
    if not requested_path.exists() or not requested_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found"
        )
    
    # Определяем MIME тип
    mime_type, _ = mimetypes.guess_type(str(requested_path))
    if not mime_type:
        mime_type = "application/octet-stream"
    
    return FileResponse(
        path=str(requested_path),
        media_type=mime_type,
        filename=filename,
        headers={"Cache-Control": "public, max-age=3600"}
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
    Получение изображения семпла по ID семпла
    
    Args:
        sample_id: ID семпла
        thumbnail: Вернуть миниатюру вместо полного изображения
        size: Размер миниатюры (если thumbnail=True)
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
    
    if not sample.image_path or not os.path.exists(sample.image_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Image file not found"
        )
    
    # Если нужна миниатюра
    if thumbnail:
        from PIL import Image
        import io
        
        try:
            with Image.open(sample.image_path) as img:
                if img.mode in ('RGBA', 'LA', 'P'):
                    img = img.convert('RGB')
                
                img.thumbnail((size, size), Image.Resampling.LANCZOS)
                
                img_bytes = io.BytesIO()
                img.save(img_bytes, format='JPEG', quality=85, optimize=True)
                img_bytes.seek(0)
                
                return FileResponse(
                    path=None,
                    content=img_bytes.getvalue(),
                    media_type="image/jpeg",
                    filename=f"sample_{sample_id}_thumb.jpg",
                    headers={"Cache-Control": "public, max-age=3600"}
                )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to create thumbnail: {str(e)}"
            )
    
    # Возвращаем оригинал
    mime_type, _ = mimetypes.guess_type(sample.image_path)
    if not mime_type:
        mime_type = "application/octet-stream"
    
    return FileResponse(
        path=sample.image_path,
        media_type=mime_type,
        filename=os.path.basename(sample.image_path),
        headers={"Cache-Control": "public, max-age=3600"}
    )
