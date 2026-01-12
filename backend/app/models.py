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

