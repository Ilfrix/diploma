import os
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Optional

from fastapi import UploadFile

from app.config import config

def hash_image(image_bytes: bytes) -> str:
    """Вычисление хэша изображения для проверки дубликатов"""
    return hashlib.sha256(image_bytes).hexdigest()

def save_image_file(file: UploadFile, user_id: str, sample_id: str) -> str:
    """Сохранение загруженного изображения"""
    os.makedirs(config.UPLOAD_DIR, exist_ok=True)
    
    file_extension = Path(file.filename).suffix
    filename = f"{user_id}_{sample_id}_{datetime.now().timestamp()}{file_extension}"
    file_path = os.path.join(config.UPLOAD_DIR, filename)
    
    content = file.file.read()
    
    with open(file_path, "wb") as f:
        f.write(content)
    
    # Проверка сигнатуры файла (magic bytes)
    with open(file_path, "rb") as f:
        header = f.read(20)
    
    file.file.seek(0)
    
    return file_path

def delete_image_file(image_path: str) -> bool:
    """Удаление файла изображения"""
    if os.path.exists(image_path):
        os.remove(image_path)
        return True
    return False
