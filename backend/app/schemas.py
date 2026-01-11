from pydantic import BaseModel
from typing import List, Optional, Literal
from datetime import datetime

# Event type literals for validation
EventType = Literal["protest", "police_presence", "strike", "clash", "arrest"]
SourcePlatform = Literal["telegram", "reddit", "instagram", "youtube", "rss", "twitter"]

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
    event_type: Optional[str] = "protest"  # 'protest', 'police_presence', 'strike', 'clash', 'arrest'
    source_platform: Optional[str] = None  # 'telegram', 'reddit', 'instagram', 'youtube', 'rss', 'twitter'

class ProtestEventCreate(ProtestEventBase):
    pass

class ProtestEvent(ProtestEventBase):
    id: int
    sources: List[Source] = []

    class Config:
        from_attributes = True

class IngestRequest(BaseModel):
    source_type: Optional[str] = "all"  # 'all', 'rss', 'reddit', 'instagram', 'youtube', 'telegram', 'twitter'
    trigger_key: str  # Simple security for cron

class TranslateRequest(BaseModel):
    text: str

class PoliceReportCreate(BaseModel):
    """Schema for crowdsourced police presence reports"""
    latitude: float
    longitude: float
    description: Optional[str] = None
    intensity: Optional[int] = 1  # 1-5 scale: 1=low presence, 5=heavy presence/crackdown
    report_type: Optional[str] = "police_presence"  # police_presence, checkpoint, raid, etc.


class AdminEventCreate(BaseModel):
    """Schema for admin-created events (authenticated)"""
    title: str
    description: Optional[str] = None
    latitude: float
    longitude: float
    intensity: Optional[int] = 3  # 1-5 scale
    event_type: Optional[str] = "protest"  # protest, police_presence, strike, clash, arrest
    verified: Optional[bool] = True  # Admin entries are verified by default
    source_url: Optional[str] = None
    admin_key: str  # Required authentication

