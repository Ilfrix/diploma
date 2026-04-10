from datetime import datetime
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

from app.config import config
from app.database import engine, Base
from app.vector_db import VectorDatabase
from app.ml.processor import init_ml_models
from app.routers import auth_router, samples_router, search_router
from app.routers.samples import set_vector_db as set_samples_vector_db
from app.routers.search import set_vector_db as set_search_vector_db

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Создание необходимых директорий
config.ensure_directories()

# Инициализация ML компонентов
detector, encoder = init_ml_models(
    detector_model_path=f"{config.MODEL_PATH}/detector.pth",
    encoder_model_path=f"{config.MODEL_PATH}/encoder.pth"
)

# Инициализация векторной БД
vector_db = VectorDatabase(db_path=config.VECTOR_DB_PATH)

# Установка векторной БД в роутеры
set_samples_vector_db(vector_db)
set_search_vector_db(vector_db)

# Создание таблиц БД
Base.metadata.create_all(bind=engine)

# Создание FastAPI приложения
app = FastAPI(
    title="Duplicate Detection System",
    description="Система для распознавания дубликатов изображений",
    version="1.0.0"
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

# Health check
@app.get("/api/health")
async def health_check():
    """Проверка состояния системы"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "vector_db": vector_db.health_check(),
        "ml_models": {
            "detector": detector.is_loaded(),
            "encoder": encoder.is_loaded()
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
