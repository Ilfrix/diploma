import os
from pathlib import Path

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
    ALGORITHM = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES = 30
    DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@localhost/mydb")
    VECTOR_DB_PATH = os.getenv("VECTOR_DB_PATH", "./vector_db")
    UPLOAD_DIR = os.getenv("UPLOAD_DIR", "./uploads")
    MODEL_PATH = os.getenv("MODEL_PATH", "./models")
    
    @classmethod
    def ensure_directories(cls):
        """Создание необходимых директорий"""
        os.makedirs(cls.UPLOAD_DIR, exist_ok=True)
        os.makedirs(cls.MODEL_PATH, exist_ok=True)
        os.makedirs(cls.VECTOR_DB_PATH, exist_ok=True)

config = Config()
