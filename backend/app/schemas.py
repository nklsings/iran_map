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


# ============================================================================
# TELEGRAM MESSAGE SCHEMAS (Live Feed)
# ============================================================================
class TelegramMessageBase(BaseModel):
    """Base schema for Telegram messages"""
    channel: str
    message_id: str
    text: str
    text_translated: Optional[str] = None
    media_url: Optional[str] = None
    media_type: Optional[str] = None
    timestamp: datetime
    
    # NLP fields
    sentiment: Optional[str] = None
    keywords: Optional[str] = None  # JSON array
    locations_mentioned: Optional[str] = None  # JSON array
    event_type_detected: Optional[str] = None
    urgency_score: float = 0.5


class TelegramMessageCreate(TelegramMessageBase):
    """Schema for creating Telegram messages"""
    is_processed: bool = False
    is_relevant: bool = True


class TelegramMessage(TelegramMessageBase):
    """Schema for Telegram message response"""
    id: int
    linked_event_id: Optional[int] = None
    is_processed: bool
    is_relevant: bool
    created_at: datetime
    
    class Config:
        from_attributes = True


class TelegramFeedResponse(BaseModel):
    """Response for the Telegram feed"""
    messages: List[TelegramMessage]
    total_count: int
    channels: List[str]
    latest_timestamp: Optional[datetime] = None


# ============================================================================
# CITY ANALYTICS SCHEMAS
# ============================================================================
class CityStatisticsBase(BaseModel):
    """Base schema for city statistics"""
    city_name: str
    city_name_fa: Optional[str] = None
    latitude: float
    longitude: float
    province: Optional[str] = None
    
    # Event counts
    total_events: int = 0
    protest_count: int = 0
    clash_count: int = 0
    arrest_count: int = 0
    police_count: int = 0
    strike_count: int = 0
    
    # Trend data
    events_24h: int = 0
    events_7d: int = 0
    trend_direction: str = "stable"
    trend_percentage: float = 0.0
    
    # Activity
    peak_hour: Optional[int] = None
    avg_daily_events: float = 0.0
    activity_level: str = "low"


class CityStatistics(CityStatisticsBase):
    """Schema for city statistics response"""
    id: int
    hourly_pattern: Optional[str] = None  # JSON
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None
    updated_at: datetime
    
    class Config:
        from_attributes = True


class CityRanking(BaseModel):
    """City ranking item for dashboard"""
    rank: int
    city_name: str
    city_name_fa: Optional[str] = None
    latitude: float
    longitude: float
    total_events: int
    events_24h: int
    trend_direction: str
    trend_percentage: float
    activity_level: str
    top_event_type: Optional[str] = None


class AnalyticsSummary(BaseModel):
    """Overall analytics summary"""
    total_cities: int
    total_events: int
    events_24h: int
    events_7d: int
    most_active_city: Optional[str] = None
    most_active_hour: Optional[int] = None
    top_cities: List[CityRanking]
    hourly_distribution: dict  # {"0": count, "1": count, ...}
    event_type_distribution: dict  # {"protest": count, "clash": count, ...}

