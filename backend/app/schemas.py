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


# ============================================================================
# AIRSPACE / NOTAM SCHEMAS
# ============================================================================
AirspaceType = Literal["airspace_restriction", "airport_closure", "hazard_notice", "temporary_restriction", "warning_area"]


class AirspaceEventBase(BaseModel):
    """Base schema for airspace events"""
    ts_start: datetime
    ts_end: Optional[datetime] = None
    is_permanent: bool = False
    center_lat: float
    center_lon: float
    radius_nm: Optional[float] = None
    lower_limit: int = 0
    upper_limit: int = 999
    airspace_type: str = "airspace_restriction"
    source: str = "notam"
    notam_id: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    raw_text: Optional[str] = None
    q_line: Optional[str] = None
    fir: Optional[str] = None
    notam_codes: Optional[str] = None


class AirspaceEventCreate(AirspaceEventBase):
    """Schema for creating airspace events"""
    pass


class AirspaceEvent(AirspaceEventBase):
    """Schema for airspace event response"""
    id: int
    created_at: datetime
    
    class Config:
        from_attributes = True


class AirspaceGeoJSON(BaseModel):
    """GeoJSON feature for airspace"""
    type: str = "Feature"
    geometry: dict
    properties: dict


# ============================================================================
# SITUATION SUMMARY SCHEMAS
# ============================================================================
class SituationSummaryBase(BaseModel):
    """Base schema for situation summaries"""
    title: str
    summary: str
    key_developments: Optional[str] = None  # JSON string of key points
    hotspots: Optional[str] = None  # JSON string of active locations
    risk_assessment: Optional[str] = None
    event_count: int = 0
    protest_count: int = 0
    clash_count: int = 0
    arrest_count: int = 0
    police_count: int = 0
    period_start: datetime
    period_end: datetime
    model_used: str = "gpt-4o-mini"


class SituationSummaryCreate(SituationSummaryBase):
    """Schema for creating situation summaries"""
    tokens_used: Optional[int] = 0
    generation_time_ms: Optional[int] = 0


class SituationSummary(SituationSummaryBase):
    """Schema for situation summary response"""
    id: int
    is_current: bool
    tokens_used: int
    generation_time_ms: int
    created_at: datetime
    
    class Config:
        from_attributes = True


class SummaryResponse(BaseModel):
    """Formatted response for the summary view"""
    id: int
    title: str
    summary: str
    key_developments: List[str]
    hotspots: List[dict]
    risk_assessment: str
    stats: dict
    period: dict
    generated_at: datetime
    model: str

