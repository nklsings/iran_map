from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class SourceBase(BaseModel):
    url: str
    source_type: str
    reliability_score: float

class SourceCreate(SourceBase):
    pass

class Source(SourceBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True

class ProtestEventBase(BaseModel):
    title: str
    description: Optional[str] = None
    latitude: float
    longitude: float
    intensity_score: float
    verified: bool
    timestamp: datetime
    source_url: Optional[str] = None
    media_url: Optional[str] = None
    media_type: Optional[str] = None  # 'image', 'video', or None

class ProtestEventCreate(ProtestEventBase):
    pass

class ProtestEvent(ProtestEventBase):
    id: int
    sources: List[Source] = []

    class Config:
        from_attributes = True

class IngestRequest(BaseModel):
    source_type: Optional[str] = "rss" 
    trigger_key: str # Simple security for cron

class TranslateRequest(BaseModel):
    text: str

