import os

from dotenv import load_dotenv


load_dotenv('app/1.env')  # Этот путь относительно место запуска main.py

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

    KAFKA_SEARCH_TOPIC = os.getenv("KAFKA_SEARCH_TOPIC", "search-requests")
    KAFKA_SEARCH_RESULT_TOPIC = os.getenv("KAFKA_SEARCH_RESULT_TOPIC", "search-results")
    KAFKA_SEARCH_CONSUMER_GROUP = os.getenv("KAFKA_SEARCH_CONSUMER_GROUP", "search-processor-group")

    # Milvus
    MILVUS_HOST = os.getenv("MILVUS_HOST", "localhost")
    MILVUS_PORT = os.getenv("MILVUS_PORT", "19530")
    MILVUS_COLLECTION_NAME = os.getenv("MILVUS_COLLECTION_NAME", "image_vectors")
    VECTOR_DIM = int(os.getenv("VECTOR_DIM", "1280"))
    
    # S3
    MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT")
    MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY")
    MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY")
    MINIO_BUCKET_NAME = os.getenv("MINIO_BUCKET_NAME")

config = Config()
