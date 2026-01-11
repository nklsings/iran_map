from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, ForeignKey, Text
from sqlalchemy.orm import relationship
from geoalchemy2 import Geometry
from sqlalchemy.sql import func
from .database import Base

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
    
    # Store lat/lon explicitly as well for easier serialization if needed, 
    # though PostGIS is the source of truth for location.
    latitude = Column(Float)
    longitude = Column(Float)
    source_url = Column(String, nullable=True)  # Original source URL
    media_url = Column(String, nullable=True)   # Image or video URL
    media_type = Column(String, nullable=True)  # 'image', 'video', or null

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

