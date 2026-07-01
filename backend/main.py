from contextlib import asynccontextmanager
from datetime import datetime
import logging
from typing import cast

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

from app.config import config
from app.database import Base, engine
from app.kafka_consumer import kafka_consumer, kafka_search_consumer
from app.kafka_producer import kafka_producer
from app.milvus_db import MilvusDatabase
from app.minio_client import minio_client
from app.ml.processor import init_ml_models
from app.ml.worker import MLProcessingWorker
from app.routers import auth_router, samples_router, search_router, upload_router
from app.search_worker import SearchWorker


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

vector_db = None
ml_worker = None
search_worker = None
minio = minio_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Управление жизненным циклом приложения"""
    logger.info("Запуск системы...")

    detector, encoder = init_ml_models(
        detector_model_path="triton:8000",
        encoder_model_path="tf_efficientnetv2_m.in21k",
    )
    app.state.detector = detector
    app.state.encode = encoder

    vector_db = MilvusDatabase(
        host=config.MILVUS_HOST,
        port=config.MILVUS_PORT,
        collection_name=config.MILVUS_COLLECTION_NAME,
        dim=config.VECTOR_DIM,
    )
    app.state.vector_db = vector_db

    await kafka_producer.start()

    ml_worker = MLProcessingWorker(vector_db, detector, encoder)
    await ml_worker.start()

    await kafka_consumer.start(ml_worker.process_image_message)
    search_worker = SearchWorker(vector_db, detector, encoder)
    await kafka_search_consumer.start(search_worker.process_search_message)

    Base.metadata.create_all(bind=engine)

    yield

    logger.info("Выключение системы...")
    await kafka_consumer.stop()
    await ml_worker.stop()
    await kafka_producer.stop()


app = FastAPI(
    title="FlexSearch",
    description="Система для поиска похожих изображений",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(samples_router)
app.include_router(search_router)
app.include_router(upload_router)


def get_vector_db(request: Request) -> MilvusDatabase:
    if not hasattr(request.app.state, "vector_db"):
        raise HTTPException(503, "Vector DB not initialized")
    return cast(MilvusDatabase, request.app.state.vector_db)


# Health check
@app.get("/api/health")
async def health_check():
    """Проверка состояния системы"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "services": {
            "milvus": vector_db.health_check() if vector_db else "not initialized",
            "kafka_producer": "running" if kafka_producer._running else "stopped",
            "kafka_consumer": "running" if kafka_consumer._running else "stopped",
            "ml_worker": "running" if ml_worker and ml_worker._running else "stopped",
            "minio": minio.health_check(),
        },
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
