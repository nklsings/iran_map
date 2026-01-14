from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, ForeignKey, Text
from sqlalchemy.orm import relationship
from geoalchemy2 import Geometry
from sqlalchemy.sql import func
from .database import Base

# Event type constants
EVENT_TYPE_PROTEST = "protest"
EVENT_TYPE_POLICE = "police_presence"
EVENT_TYPE_STRIKE = "strike"
EVENT_TYPE_CLASH = "clash"
EVENT_TYPE_ARREST = "arrest"

class ProtestEvent(Base):
    __tablename__ = "protest_events"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    description = Column(Text, nullable=True)
    # Using Geometry(geometry_type='POINT', srid=4326) for Lat/Lon
    location = Column(Geometry(geometry_type='POINT', srid=4326))
    
    intensity_score = Column(Float, default=0.0) # 0.0 to 1.0 or higher
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    verified = Column(Boolean, default=False)
    
    # Event categorization (protest, police_presence, strike, clash, arrest)
    event_type = Column(String, default=EVENT_TYPE_PROTEST, index=True)
    
    # Store lat/lon explicitly as well for easier serialization if needed, 
    # though PostGIS is the source of truth for location.
    latitude = Column(Float)
    longitude = Column(Float)
    source_url = Column(String, nullable=True)  # Original source URL
    media_url = Column(String, nullable=True)   # Image or video URL
    media_type = Column(String, nullable=True)  # 'image', 'video', or null
    
    # Source platform tracking
    source_platform = Column(String, nullable=True)  # 'telegram', 'reddit', 'instagram', 'youtube', 'rss', 'twitter'

    sources = relationship("Source", back_populates="event")

class Source(Base):
    __tablename__ = "sources"

    id = Column(Integer, primary_key=True, index=True)
    url = Column(String, unique=True, index=True)
    source_type = Column(String) # 'twitter', 'telegram', 'news', 'rss'
    reliability_score = Column(Float, default=0.5)
    
    event_id = Column(Integer, ForeignKey("protest_events.id"), nullable=True)
    event = relationship("ProtestEvent", back_populates="sources")
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# ============================================================================
# AIRSPACE EVENTS (NOTAMs)
# ============================================================================
AIRSPACE_TYPE_RESTRICTION = "airspace_restriction"
AIRSPACE_TYPE_CLOSURE = "airport_closure"
AIRSPACE_TYPE_HAZARD = "hazard_notice"
AIRSPACE_TYPE_TEMPORARY = "temporary_restriction"
AIRSPACE_TYPE_WARNING = "warning_area"


class AirspaceEvent(Base):
    """Airspace restrictions from NOTAMs and similar sources"""
    __tablename__ = "airspace_events"

    id = Column(Integer, primary_key=True, index=True)
    
    # Time validity
    ts_start = Column(DateTime(timezone=True), nullable=False, index=True)
    ts_end = Column(DateTime(timezone=True), nullable=True)  # NULL = permanent (PERM)
    is_permanent = Column(Boolean, default=False)
    
    # Geometry - stored as GeoJSON in a Geometry column (polygon/circle)
    geometry = Column(Geometry(geometry_type='POLYGON', srid=4326), nullable=True)
    # Also store center point for quick lookups
    center_lat = Column(Float)
    center_lon = Column(Float)
    radius_nm = Column(Float, nullable=True)  # Radius in nautical miles (if circular)
    
    # Lower and upper altitude limits (in flight levels, e.g., 000 = surface, 999 = unlimited)
    lower_limit = Column(Integer, default=0)
    upper_limit = Column(Integer, default=999)
    
    # Classification
    airspace_type = Column(String, default=AIRSPACE_TYPE_RESTRICTION, index=True)
    
    # Source tracking
    source = Column(String, default="notam")  # 'notam', 'faa', 'eurocontrol', etc.
    notam_id = Column(String, nullable=True, unique=True, index=True)  # Original NOTAM ID
    
    # Payload (raw data)
    raw_text = Column(Text, nullable=True)
    q_line = Column(String, nullable=True)  # Q) line from NOTAM
    fir = Column(String, nullable=True)  # Flight Information Region (e.g., OIIX for Iran)
    notam_codes = Column(String, nullable=True)  # NOTAM codes (e.g., QRTCA)
    
    # Description
    title = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


# ============================================================================
# SITUATION SUMMARIES (AI-Generated)
# ============================================================================
class SituationSummary(Base):
    """AI-generated situation summaries from collected events"""
    __tablename__ = "situation_summaries"

    id = Column(Integer, primary_key=True, index=True)
    
    # Summary content
    title = Column(String, nullable=False)
    summary = Column(Text, nullable=False)  # Main summary text
    key_developments = Column(Text, nullable=True)  # JSON array of key points
    hotspots = Column(Text, nullable=True)  # JSON array of active locations
    risk_assessment = Column(Text, nullable=True)  # Risk level and analysis
    
    # Statistics at time of generation
    event_count = Column(Integer, default=0)
    protest_count = Column(Integer, default=0)
    clash_count = Column(Integer, default=0)
    arrest_count = Column(Integer, default=0)
    police_count = Column(Integer, default=0)
    
    # Time range covered
    period_start = Column(DateTime(timezone=True), nullable=False)
    period_end = Column(DateTime(timezone=True), nullable=False)
    
    # Generation metadata
    model_used = Column(String, default="gpt-4o-mini")
    tokens_used = Column(Integer, default=0)
    generation_time_ms = Column(Integer, default=0)
    
    # Status
    is_current = Column(Boolean, default=True, index=True)  # Latest summary
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


# ============================================================================
# TELEGRAM MESSAGES (Live Feed with NLP)
# ============================================================================
class TelegramMessage(Base):
    """Telegram messages from monitored channels with NLP analysis"""
    __tablename__ = "telegram_messages"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Message identification
    channel = Column(String, index=True, nullable=False)
    message_id = Column(String, unique=True, index=True)
    
    # Content
    text = Column(Text, nullable=False)
    text_translated = Column(Text, nullable=True)  # English translation
    
    # Media
    media_url = Column(String, nullable=True)
    media_type = Column(String, nullable=True)  # 'image', 'video', 'video_thumb'
    
    # Timestamp
    timestamp = Column(DateTime(timezone=True), index=True, server_default=func.now())
    
    # NLP extracted fields
    sentiment = Column(String, nullable=True)  # 'positive', 'negative', 'neutral'
    keywords = Column(Text, nullable=True)  # JSON array of extracted keywords
    locations_mentioned = Column(Text, nullable=True)  # JSON array of cities
    event_type_detected = Column(String, nullable=True)  # protest, clash, arrest, etc.
    urgency_score = Column(Float, default=0.5)  # 0-1, higher = more urgent
    
    # Linked event (if created as protest_event)
    linked_event_id = Column(Integer, ForeignKey("protest_events.id"), nullable=True)
    
    # Processing status
    is_processed = Column(Boolean, default=False)
    is_relevant = Column(Boolean, default=True)  # False if filtered out as irrelevant
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class TwitterMessage(Base):
    """Twitter/X messages fetched via API with NLP analysis"""
    __tablename__ = "twitter_messages"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Tweet identification
    tweet_id = Column(String, unique=True, index=True)
    username = Column(String, index=True, nullable=False)
    author_id = Column(String, nullable=True)
    
    # Content
    text = Column(Text, nullable=False)
    text_translated = Column(Text, nullable=True)  # English translation
    
    # Media (if any)
    media_url = Column(String, nullable=True)
    media_type = Column(String, nullable=True)
    
    # Timestamp
    timestamp = Column(DateTime(timezone=True), index=True, server_default=func.now())
    
    # NLP extracted fields
    sentiment = Column(String, nullable=True)
    keywords = Column(Text, nullable=True)  # JSON array
    locations_mentioned = Column(Text, nullable=True)  # JSON array
    event_type_detected = Column(String, nullable=True)
    urgency_score = Column(Float, default=0.5)
    
    # Engagement metrics
    retweet_count = Column(Integer, default=0)
    like_count = Column(Integer, default=0)
    reply_count = Column(Integer, default=0)
    
    # Linked event (if created as protest_event)
    linked_event_id = Column(Integer, ForeignKey("protest_events.id"), nullable=True)
    
    # Processing status
    is_processed = Column(Boolean, default=False)
    is_relevant = Column(Boolean, default=True)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# ============================================================================
# CITY ANALYTICS (Aggregated Statistics)
# ============================================================================
class CityStatistics(Base):
    """Aggregated statistics for cities - updated periodically"""
    __tablename__ = "city_statistics"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # City identification
    city_name = Column(String, index=True, nullable=False)
    city_name_fa = Column(String, nullable=True)  # Persian name
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    province = Column(String, nullable=True)
    
    # Event counts (in current time window)
    total_events = Column(Integer, default=0)
    protest_count = Column(Integer, default=0)
    clash_count = Column(Integer, default=0)
    arrest_count = Column(Integer, default=0)
    police_count = Column(Integer, default=0)
    strike_count = Column(Integer, default=0)
    
    # Trend data
    events_24h = Column(Integer, default=0)  # Events in last 24 hours
    events_7d = Column(Integer, default=0)   # Events in last 7 days
    trend_direction = Column(String, default="stable")  # 'up', 'down', 'stable'
    trend_percentage = Column(Float, default=0.0)  # Percentage change
    
    # Hourly pattern (JSON: {"0": count, "1": count, ...})
    hourly_pattern = Column(Text, nullable=True)
    
    # Peak activity
    peak_hour = Column(Integer, nullable=True)  # 0-23
    avg_daily_events = Column(Float, default=0.0)
    
    # Activity level
    activity_level = Column(String, default="low")  # 'low', 'medium', 'high', 'critical'
    
    # Last update
    period_start = Column(DateTime(timezone=True), nullable=True)
    period_end = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


# ============================================================================
# DATA SOURCES (Dynamically Managed)
# ============================================================================
SOURCE_TYPE_TELEGRAM = "telegram"
SOURCE_TYPE_RSS = "rss"
SOURCE_TYPE_TWITTER = "twitter"
SOURCE_TYPE_YOUTUBE = "youtube"
SOURCE_TYPE_REDDIT = "reddit"
SOURCE_TYPE_INSTAGRAM = "instagram"

class DataSource(Base):
    """Dynamically managed data sources for ingestion"""
    __tablename__ = "data_sources"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Source identification
    source_type = Column(String, index=True, nullable=False)  # telegram, rss, twitter, youtube, reddit, instagram
    identifier = Column(String, index=True, nullable=False)  # channel name, feed URL, account handle, etc.
    name = Column(String, nullable=True)  # Display name
    
    # Configuration
    url = Column(String, nullable=True)  # Full URL (for RSS feeds)
    reliability_score = Column(Float, default=0.7)  # 0.0 to 1.0
    priority = Column(Integer, default=2)  # 1=high, 2=medium, 3=low
    category = Column(String, nullable=True)  # news, human_rights, activist, osint, citizen_journalism
    
    # Status
    is_active = Column(Boolean, default=True, index=True)
    last_fetch_at = Column(DateTime(timezone=True), nullable=True)
    last_fetch_status = Column(String, nullable=True)  # success, error, rate_limited
    error_count = Column(Integer, default=0)
    
    # Metadata
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

