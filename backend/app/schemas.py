from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field
from enum import Enum

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

class SampleCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None

class SampleUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None

class SampleStatusEnum(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    PROCESSED = "processed"
    FAILED = "failed"

class SampleResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    image_path: str
    status: SampleStatusEnum
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

class SimilarImage(BaseModel):
    sample_id: str
    name: str
    description: Optional[str]
    similarity_score: float
    image_path: str

class SimilarResponse(BaseModel):
    query_sample_id: str
    query_name: str
    similar_images: List[SimilarImage]
