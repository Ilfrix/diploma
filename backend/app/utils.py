import hashlib

def hash_image(image_bytes: bytes) -> str:
    """Вычисление хэша изображения для проверки дубликатов"""
    return hashlib.sha256(image_bytes).hexdigest()
