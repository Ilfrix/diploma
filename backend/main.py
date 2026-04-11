from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
import logging

from app.config import config
from app.database import engine, Base
from app.vector_db import VectorDatabase
from app.ml.processor import init_ml_models
from app.ml.worker import MLProcessingWorker
from app.kafka_producer import kafka_producer
from app.kafka_consumer import kafka_consumer
from app.routers import auth_router, samples_router, search_router, upload_router
from app.routers.search import set_vector_db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Глобальные объекты
vector_db = None
ml_worker = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Управление жизненным циклом приложения"""
    # Startup
    logger.info("Starting up...")
    
    # Создание директорий
    config.ensure_directories()
    
    # Инициализация ML моделей
    init_ml_models(
        detector_model_path=f"{config.MODEL_PATH}/detector.pth",
        encoder_model_path=f"{config.MODEL_PATH}/encoder.pth"
    )
    
    # Инициализация векторной БД
    global vector_db, ml_worker
    vector_db = VectorDatabase(db_path=config.VECTOR_DB_PATH)
    set_vector_db(vector_db)
    
    # Инициализация Kafka продюсера
    await kafka_producer.start()
    
    # Инициализация ML worker
    ml_worker = MLProcessingWorker(vector_db)
    await ml_worker.start()
    
    # Запуск Kafka консюмера с обработчиком
    await kafka_consumer.start(ml_worker.process_image_message)
    
    # Создание таблиц БД
    Base.metadata.create_all(bind=engine)
    
    yield
    
    # Shutdown
    logger.info("Shutting down...")
    await kafka_consumer.stop()
    await ml_worker.stop()
    await kafka_producer.stop()

# Создание FastAPI приложения
app = FastAPI(
    title="Duplicate Detection System",
    description="Система для распознавания дубликатов изображений с асинхронной обработкой",
    version="2.0.0",
    lifespan=lifespan
)

# CORS настройки
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Подключение роутеров
app.include_router(auth_router)
app.include_router(samples_router)
app.include_router(search_router)
app.include_router(upload_router)

# Health check
@app.get("/api/health")
async def health_check():
    """Проверка состояния системы"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "services": {
            "vector_db": vector_db.health_check() if vector_db else "not initialized",
            "kafka_producer": "running" if kafka_producer._running else "stopped",
            "kafka_consumer": "running" if kafka_consumer._running else "stopped",
            "ml_worker": "running" if ml_worker and ml_worker._running else "stopped"
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
