import os

from dotenv import load_dotenv

load_dotenv('app/1.env')

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "key")
    ALGORITHM = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES = 30
    DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:user@localhost/db")
    VECTOR_DB_PATH = os.getenv("VECTOR_DB_PATH", "./vector_db")
    UPLOAD_DIR = os.getenv("UPLOAD_DIR", "./uploads")
    MODEL_PATH = os.getenv("MODEL_PATH", "./models")

    # Kafka
    KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
    KAFKA_IMAGE_TOPIC = os.getenv("KAFKA_IMAGE_TOPIC", "image-processing")
    KAFKA_RESULT_TOPIC = os.getenv("KAFKA_RESULT_TOPIC", "image-results")
    KAFKA_CONSUMER_GROUP = os.getenv("KAFKA_CONSUMER_GROUP", "ml-processor-group")
    
    @classmethod
    def ensure_directories(cls):
        """Создание необходимых директорий"""
        os.makedirs(cls.UPLOAD_DIR, exist_ok=True)
        # os.makedirs(cls.MODEL_PATH, exist_ok=True)
        os.makedirs(cls.VECTOR_DB_PATH, exist_ok=True)

config = Config()
