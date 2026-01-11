from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import text
from . import models, schemas, database
from .services.ingestion import IngestionService
from typing import List, Dict, Any
from datetime import datetime, timedelta, timezone
from contextlib import asynccontextmanager
import os
import threading

# APScheduler for background tasks
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

# ============================================================================
# SCHEDULED INGESTION CONFIGURATION
# ============================================================================
INGESTION_INTERVAL_MINUTES = int(os.getenv("INGESTION_INTERVAL_MINUTES", "15"))
ENABLE_AUTO_INGESTION = os.getenv("ENABLE_AUTO_INGESTION", "true").lower() == "true"

# Global scheduler
scheduler = BackgroundScheduler()

def run_scheduled_ingestion():
    """Background task to fetch new events from all sources"""
    print(f"\n{'='*50}")
    print(f"⏰ Scheduled ingestion started at {datetime.now(timezone.utc).isoformat()}")
    print(f"{'='*50}")
    
    try:
        # Create a new database session for this background task
        db = next(database.get_db())
        try:
            service = IngestionService(db)
            count = service.run_ingestion(source_type="all")
            print(f"✓ Scheduled ingestion complete: {count} new events")
        finally:
            db.close()
    except Exception as e:
        print(f"✗ Scheduled ingestion failed: {e}")

def run_initial_ingestion():
    """Run initial ingestion in a background thread to not block startup"""
    print("\n🚀 Running initial data ingestion...")
    try:
        db = next(database.get_db())
        try:
            service = IngestionService(db)
            # Start with RSS only for faster initial load
            count = service.run_ingestion(source_type="rss")
            print(f"✓ Initial RSS ingestion complete: {count} events")
            
            # Then fetch from other sources
            count = service.run_ingestion(source_type="telegram")
            print(f"✓ Initial Telegram ingestion complete: {count} events")
            
            count = service.run_ingestion(source_type="youtube")
            print(f"✓ Initial YouTube ingestion complete: {count} events")
        finally:
            db.close()
    except Exception as e:
        print(f"⚠ Initial ingestion error: {e}")

app = FastAPI(title="Iran Protest Heatmap API")

# CORS
origins = [
    "http://localhost:3000",
    "http://localhost:3001",
    "https://iran-protest-heatmap.vercel.app",
    "*"  # Allow all for now
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Dependency
get_db = database.get_db

def run_schema_migrations(conn):
    """Add missing columns to existing tables (simple migration without Alembic)"""
    migrations = [
        # Add event_type column if missing
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name = 'protest_events' AND column_name = 'event_type'
            ) THEN
                ALTER TABLE protest_events ADD COLUMN event_type VARCHAR(50) DEFAULT 'protest';
                RAISE NOTICE 'Added event_type column';
            END IF;
        END $$;
        """,
        # Add source_platform column if missing
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name = 'protest_events' AND column_name = 'source_platform'
            ) THEN
                ALTER TABLE protest_events ADD COLUMN source_platform VARCHAR(50);
                RAISE NOTICE 'Added source_platform column';
            END IF;
        END $$;
        """,
    ]
    
    for migration in migrations:
        try:
            conn.execute(text(migration))
            conn.commit()
        except Exception as e:
            print(f"  Migration warning: {e}")


# Create tables on startup and start scheduler
@app.on_event("startup")
async def startup_event():
    import time
    max_retries = 5
    retry_delay = 2
    
    # Step 1: Initialize database
    db_ready = False
    for attempt in range(max_retries):
        try:
            with database.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            
            # Create tables if they don't exist
            models.Base.metadata.create_all(bind=database.engine)
            print(f"✓ Database tables created/verified successfully (attempt {attempt + 1})")
            
            # Run schema migrations for existing tables
            with database.engine.connect() as conn:
                print("  Running schema migrations...")
                run_schema_migrations(conn)
                print("  ✓ Schema migrations complete")
            
            db_ready = True
            break
        except Exception as e:
            if attempt < max_retries - 1:
                print(f"⚠ Database connection failed (attempt {attempt + 1}/{max_retries}): {e}")
                print(f"   Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
            else:
                print(f"✗ Could not create tables after {max_retries} attempts: {e}")
                print("   Tables will be created on first database access")
    
    # Step 2: Start automatic ingestion if enabled
    if ENABLE_AUTO_INGESTION and db_ready:
        print(f"\n📡 Auto-ingestion enabled (every {INGESTION_INTERVAL_MINUTES} minutes)")
        
        # Schedule periodic ingestion
        scheduler.add_job(
            run_scheduled_ingestion,
            trigger=IntervalTrigger(minutes=INGESTION_INTERVAL_MINUTES),
            id='scheduled_ingestion',
            name='Periodic data ingestion',
            replace_existing=True
        )
        scheduler.start()
        print("✓ Scheduler started")
        
        # Run initial ingestion in background thread (don't block startup)
        ingestion_thread = threading.Thread(target=run_initial_ingestion, daemon=True)
        ingestion_thread.start()
        print("✓ Initial ingestion started in background")
    else:
        if not ENABLE_AUTO_INGESTION:
            print("📡 Auto-ingestion disabled (set ENABLE_AUTO_INGESTION=true to enable)")
        if not db_ready:
            print("⚠ Skipping auto-ingestion: database not ready")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        print("✓ Scheduler stopped")

@app.get("/")
def read_root():
    return {"status": "ok", "message": "Iran Protest Heatmap API Operational"}

@app.get("/health")
def health_check():
    """Health check endpoint for Cloud Run"""
    return {"status": "healthy"}

@app.post("/api/init-db")
def init_database(db: Session = Depends(get_db)):
    """Initialize database tables (run once after deployment)"""
    try:
        models.Base.metadata.create_all(bind=database.engine)
        return {"status": "success", "message": "Database tables created successfully"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create tables: {str(e)}"
        )

@app.get("/api/events")
def get_events(
    verified_only: bool = False,
    hours: int = 12,  # Default to last 12 hours
    event_type: str = None,  # Filter by event type: 'protest', 'police_presence', 'strike', etc.
    db: Session = Depends(get_db)
):
    """
    Get events as GeoJSON FeatureCollection.
    
    - **verified_only**: Filter to verified events only
    - **hours**: Time window in hours (default 12)
    - **event_type**: Filter by type: 'protest', 'police_presence', 'strike', 'clash', 'arrest'
    """
    # Calculate cutoff time
    cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)
    
    query = db.query(models.ProtestEvent).filter(
        models.ProtestEvent.timestamp >= cutoff_time
    )
    
    if verified_only:
        query = query.filter(models.ProtestEvent.verified == True)
    
    if event_type:
        query = query.filter(models.ProtestEvent.event_type == event_type)
    
    # Order by most recent first
    query = query.order_by(models.ProtestEvent.timestamp.desc())
    events = query.all()
    
    # Convert to GeoJSON
    features = []
    for event in events:
        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [event.longitude, event.latitude]
            },
            "properties": {
                "id": event.id,
                "title": event.title,
                "description": event.description,
                "intensity": event.intensity_score,
                "verified": event.verified,
                "timestamp": event.timestamp.isoformat() if event.timestamp else None,
                "source_url": event.source_url,
                "media_url": event.media_url,
                "media_type": event.media_type,
                "event_type": event.event_type or "protest",
                "source_platform": event.source_platform
            }
        })
        
    return {
        "type": "FeatureCollection",
        "features": features
    }

@app.get("/api/stats")
def get_stats(hours: int = 12, db: Session = Depends(get_db)):
    """Get statistics including PPU (Police Presence Unit) counts"""
    # Calculate cutoff time (same as events endpoint)
    cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)
    
    total_events = db.query(models.ProtestEvent).filter(
        models.ProtestEvent.timestamp >= cutoff_time
    ).count()
    
    verified_events = db.query(models.ProtestEvent).filter(
        models.ProtestEvent.timestamp >= cutoff_time,
        models.ProtestEvent.verified == True
    ).count()
    
    # PPU - Police Presence Unit stats
    police_events = db.query(models.ProtestEvent).filter(
        models.ProtestEvent.timestamp >= cutoff_time,
        models.ProtestEvent.event_type == "police_presence"
    ).count()
    
    # Breakdown by event type
    protest_events = db.query(models.ProtestEvent).filter(
        models.ProtestEvent.timestamp >= cutoff_time,
        models.ProtestEvent.event_type == "protest"
    ).count()
    
    clash_events = db.query(models.ProtestEvent).filter(
        models.ProtestEvent.timestamp >= cutoff_time,
        models.ProtestEvent.event_type == "clash"
    ).count()
    
    arrest_events = db.query(models.ProtestEvent).filter(
        models.ProtestEvent.timestamp >= cutoff_time,
        models.ProtestEvent.event_type == "arrest"
    ).count()
    
    return {
        "total_reports": total_events,
        "verified_incidents": verified_events,
        "police_presence": police_events,  # PPU count
        "protests": protest_events,
        "clashes": clash_events,
        "arrests": arrest_events,
        "hours_window": hours
    }


# ============================================================================
# PPU AUTO-VERIFICATION CONFIG
# ============================================================================
PPU_VERIFICATION_THRESHOLD = 5  # Number of nearby reports needed to auto-verify
PPU_PROXIMITY_KM = 1.0  # Reports within 1km are considered "nearby"
PPU_TIME_WINDOW_HOURS = 6  # Only count recent reports


def count_nearby_ppu_reports(db: Session, lat: float, lon: float, hours: int = PPU_TIME_WINDOW_HOURS) -> int:
    """Count PPU reports within proximity radius in the time window"""
    cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)
    
    # Haversine approximation: 1 degree ≈ 111km at equator
    # For 1km radius, we use ~0.009 degrees
    degree_radius = PPU_PROXIMITY_KM / 111.0
    
    count = db.query(models.ProtestEvent).filter(
        models.ProtestEvent.event_type == "police_presence",
        models.ProtestEvent.timestamp >= cutoff_time,
        models.ProtestEvent.latitude.between(lat - degree_radius, lat + degree_radius),
        models.ProtestEvent.longitude.between(lon - degree_radius, lon + degree_radius)
    ).count()
    
    return count


def auto_verify_nearby_ppu(db: Session, lat: float, lon: float):
    """Auto-verify all nearby PPU reports when threshold is reached"""
    cutoff_time = datetime.now(timezone.utc) - timedelta(hours=PPU_TIME_WINDOW_HOURS)
    degree_radius = PPU_PROXIMITY_KM / 111.0
    
    # Update all nearby unverified PPU reports to verified
    db.query(models.ProtestEvent).filter(
        models.ProtestEvent.event_type == "police_presence",
        models.ProtestEvent.timestamp >= cutoff_time,
        models.ProtestEvent.verified == False,
        models.ProtestEvent.latitude.between(lat - degree_radius, lat + degree_radius),
        models.ProtestEvent.longitude.between(lon - degree_radius, lon + degree_radius)
    ).update({"verified": True}, synchronize_session=False)
    
    db.commit()


@app.post("/api/ppu/report")
def report_police_presence(
    report: schemas.PoliceReportCreate,
    db: Session = Depends(get_db)
):
    """
    Submit a crowdsourced Police Presence Unit (PPU) report.
    Similar to Ukraine's air raid alert system but for police/security force presence.
    
    Reports are unverified by default. When 5+ reports exist within 1km in 6 hours,
    all nearby reports are automatically verified (crowd consensus).
    """
    from geoalchemy2.elements import WKTElement
    
    # Count existing nearby reports BEFORE adding new one
    nearby_count = count_nearby_ppu_reports(db, report.latitude, report.longitude)
    
    # Check if this report will trigger auto-verification
    will_verify = (nearby_count + 1) >= PPU_VERIFICATION_THRESHOLD
    
    # Create the event
    db_event = models.ProtestEvent(
        title=f"🚨 PPU: Police presence reported",
        description=report.description or "Police/security forces spotted in area",
        latitude=report.latitude,
        longitude=report.longitude,
        location=WKTElement(f'POINT({report.longitude} {report.latitude})', srid=4326),
        intensity_score=min(report.intensity / 5.0, 1.0) if report.intensity else 0.5,
        verified=will_verify,  # Auto-verify if threshold reached
        timestamp=datetime.now(timezone.utc),
        event_type="police_presence",
        source_platform="crowdsourced"
    )
    db.add(db_event)
    db.commit()
    db.refresh(db_event)
    
    # If threshold reached, verify ALL nearby reports
    if will_verify:
        auto_verify_nearby_ppu(db, report.latitude, report.longitude)
        return {
            "status": "success",
            "message": "PPU report submitted and AUTO-VERIFIED",
            "event_id": db_event.id,
            "verified": True,
            "nearby_reports": nearby_count + 1,
            "info": f"Verified by crowd consensus ({nearby_count + 1} reports in area)"
        }
    
    return {
        "status": "success",
        "message": "PPU report submitted",
        "event_id": db_event.id,
        "verified": False,
        "nearby_reports": nearby_count + 1,
        "reports_needed": PPU_VERIFICATION_THRESHOLD - (nearby_count + 1),
        "warning": "Stay safe. This report is unverified."
    }


@app.get("/api/ppu/active")
def get_active_ppu(
    hours: int = 6,  # PPU alerts are time-sensitive, default to 6 hours
    db: Session = Depends(get_db)
):
    """
    Get active Police Presence Unit alerts.
    Returns only police_presence events from the last N hours.
    """
    cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)
    
    query = db.query(models.ProtestEvent).filter(
        models.ProtestEvent.timestamp >= cutoff_time,
        models.ProtestEvent.event_type == "police_presence"
    ).order_by(models.ProtestEvent.timestamp.desc())
    
    events = query.all()
    
    # Convert to GeoJSON
    features = []
    for event in events:
        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [event.longitude, event.latitude]
            },
            "properties": {
                "id": event.id,
                "title": event.title,
                "description": event.description,
                "intensity": event.intensity_score,
                "verified": event.verified,
                "timestamp": event.timestamp.isoformat() if event.timestamp else None,
                "event_type": "police_presence",
                "source_platform": event.source_platform,
                "age_minutes": int((datetime.now(timezone.utc) - event.timestamp).total_seconds() / 60) if event.timestamp else None
            }
        })
    
    return {
        "type": "FeatureCollection",
        "features": features,
        "count": len(features),
        "hours_window": hours
    }

@app.post("/api/ingest")
def trigger_ingestion(
    request: schemas.IngestRequest,
    db: Session = Depends(get_db)
):
    """
    Trigger data ingestion from sources.
    
    - **source_type**: 'all', 'rss', 'twitter', 'telegram', 'reddit', 'instagram', 'youtube'
    - **trigger_key**: Secret key for authentication
    """
    # Simple secret check (replace with proper auth in prod)
    expected_key = os.getenv("CRON_SECRET", "dev_secret")
    if request.trigger_key != expected_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid trigger key")
        
    service = IngestionService(db)
    count = service.run_ingestion(source_type=request.source_type or "all")
    
    return {"status": "success", "new_events": count, "source_type": request.source_type or "all"}


# ============================================================================
# ADMIN ENDPOINTS (Protected)
# ============================================================================
ADMIN_KEY = os.getenv("ADMIN_KEY", "admin_secret_change_me")


@app.post("/api/admin/event")
def admin_create_event(
    event: schemas.AdminEventCreate,
    db: Session = Depends(get_db)
):
    """
    Create a verified event (admin only).
    Requires admin_key for authentication.
    """
    from geoalchemy2.elements import WKTElement
    
    # Verify admin key
    if event.admin_key != ADMIN_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin key"
        )
    
    # Create the event
    db_event = models.ProtestEvent(
        title=event.title,
        description=event.description,
        latitude=event.latitude,
        longitude=event.longitude,
        location=WKTElement(f'POINT({event.longitude} {event.latitude})', srid=4326),
        intensity_score=min(event.intensity / 5.0, 1.0) if event.intensity else 0.6,
        verified=event.verified if event.verified is not None else True,
        timestamp=datetime.now(timezone.utc),
        event_type=event.event_type or "protest",
        source_platform="admin",
        source_url=event.source_url
    )
    db.add(db_event)
    db.commit()
    db.refresh(db_event)
    
    return {
        "status": "success",
        "message": "Event created by admin",
        "event_id": db_event.id,
        "event_type": db_event.event_type,
        "verified": db_event.verified
    }


@app.get("/api/admin/verify/{event_id}")
def admin_verify_event(
    event_id: int,
    admin_key: str,
    db: Session = Depends(get_db)
):
    """Manually verify an event by ID"""
    if admin_key != ADMIN_KEY:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid admin key")
    
    event = db.query(models.ProtestEvent).filter(models.ProtestEvent.id == event_id).first()
    if not event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    
    event.verified = True
    db.commit()
    
    return {"status": "success", "message": f"Event {event_id} verified", "event_id": event_id}


@app.delete("/api/admin/event/{event_id}")
def admin_delete_event(
    event_id: int,
    admin_key: str,
    db: Session = Depends(get_db)
):
    """Delete an event by ID (admin only)"""
    if admin_key != ADMIN_KEY:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid admin key")
    
    event = db.query(models.ProtestEvent).filter(models.ProtestEvent.id == event_id).first()
    if not event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    
    db.delete(event)
    db.commit()
    
    return {"status": "success", "message": f"Event {event_id} deleted"}


@app.post("/api/translate")
def translate_text(request: schemas.TranslateRequest):
    """Translate Persian text to English using Google Translate API"""
    import requests
    
    text = request.text
    if not text:
        return {"translated": ""}
    
    try:
        # Use Google Translate free API
        url = "https://translate.googleapis.com/translate_a/single"
        params = {
            "client": "gtx",
            "sl": "fa",  # Persian/Farsi
            "tl": "en",  # English
            "dt": "t",
            "q": text
        }
        
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            result = response.json()
            # Extract translated text from response
            translated_parts = []
            if result and result[0]:
                for part in result[0]:
                    if part[0]:
                        translated_parts.append(part[0])
            translated = " ".join(translated_parts)
            return {"translated": translated, "original": text}
        else:
            return {"translated": text, "error": "Translation service unavailable"}
    except Exception as e:
        return {"translated": text, "error": str(e)}

