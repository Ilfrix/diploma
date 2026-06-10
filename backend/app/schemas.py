from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ========== Auth schemas ==========
class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=100)
    email: str = Field(..., pattern=r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
    password: str = Field(..., min_length=6)

class UserLogin(BaseModel):
    username: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    user_id: str
    username: str

# ========== Sample schemas ==========
class SampleCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None

class SampleUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None

class ProcessStatusEnum(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    PROCESSED = "processed"
    FAILED = "failed"

class SampleResponse(BaseModel):
    id: str
    name: str
    description: str | None
    status: ProcessStatusEnum
    error_message: str | None = None
    isOwner: bool | None = False
    owner_name: str | None = None
    created_at: datetime
    updated_at: datetime
    image: Optional['ImageResponse'] = None
    
    class Config:
        from_attributes = True

# ========== Image schemas ==========
class ImageResponse(BaseModel):
    id: str
    image_path: str
    image_hash: str
    mime_type: str | None = None
    created_at: datetime
    crops: list['CropResponse'] | None = None
    
    class Config:
        from_attributes = True

# ========== Crop schemas ==========
class VectorResponse(BaseModel):
    id: str
    crop_id: str
    milvus_id: str
    created_at: datetime
    
    class Config:
        from_attributes = True

class CropResponse(BaseModel):
    id: str
    image_id: str
    crop_index: int
    crop_path: str
    bbox_x1: float
    bbox_y1: float
    bbox_x2: float
    bbox_y2: float
    class_name: str | None = None
    confidence: float | None = None
    created_at: datetime
    vector: VectorResponse | None = None
    
    class Config:
        from_attributes = True

# ========== Search/Similarity schemas ==========
class SimilarImage(BaseModel):
    sample_id: str
    name: str
    description: str | None
    similarity_score: float
    image_id: str
    image_url: str | None = None

class SimilarResponse(BaseModel):
    query_sample_id: str
    query_name: str
    similar_images: list[SimilarImage]
    processing_time_ms: float | None = None


SampleResponse.model_rebuild()
ImageResponse.model_rebuild()
CropResponse.model_rebuild()