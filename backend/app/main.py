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
# SCHEDULED TASKS CONFIGURATION
# ============================================================================
INGESTION_INTERVAL_MINUTES = int(os.getenv("INGESTION_INTERVAL_MINUTES", "15"))
ENABLE_AUTO_INGESTION = os.getenv("ENABLE_AUTO_INGESTION", "true").lower() == "true"
REPORT_MAX_AGE_HOURS = int(os.getenv("REPORT_MAX_AGE_HOURS", "12"))  # Delete reports older than this
CLEANUP_INTERVAL_MINUTES = int(os.getenv("CLEANUP_INTERVAL_MINUTES", "30"))  # Run cleanup every 30 min

# Global scheduler
scheduler = BackgroundScheduler()


def run_cleanup_old_reports():
    """Delete reports older than REPORT_MAX_AGE_HOURS"""
    print(f"\n🧹 Cleanup started at {datetime.now(timezone.utc).isoformat()}")
    
    try:
        db = next(database.get_db())
        try:
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=REPORT_MAX_AGE_HOURS)
            
            # Count before deletion
            old_count = db.query(models.ProtestEvent).filter(
                models.ProtestEvent.timestamp < cutoff_time
            ).count()
            
            if old_count > 0:
                # Delete old reports
                db.query(models.ProtestEvent).filter(
                    models.ProtestEvent.timestamp < cutoff_time
                ).delete(synchronize_session=False)
                db.commit()
                print(f"✓ Cleanup complete: deleted {old_count} reports older than {REPORT_MAX_AGE_HOURS}h")
            else:
                print(f"✓ Cleanup complete: no reports older than {REPORT_MAX_AGE_HOURS}h")
        finally:
            db.close()
    except Exception as e:
        print(f"✗ Cleanup failed: {e}")


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
            
            # Fetch real NOTAMs if none exist
            from .services.notam import fetch_real_notams, NOTAMService
            notam_count = db.query(models.AirspaceEvent).count()
            if notam_count == 0:
                print("📡 Fetching real NOTAM data...")
                count = fetch_real_notams(db)
                print(f"✓ Loaded {count} NOTAMs")
            else:
                print(f"✓ Found {notam_count} existing NOTAMs")
            
            # Fetch OSINT data (GeoConfirmed, ArcGIS)
            from .services.osint import fetch_osint_data
            print("🌍 Fetching OSINT data (GeoConfirmed, ArcGIS)...")
            osint_results = fetch_osint_data(db)
            print(f"✓ OSINT fetch complete: {osint_results['total']} events")
            
            # Generate initial summary if none exists
            from .services.summary import generate_hourly_summary
            summary_count = db.query(models.SituationSummary).count()
            if summary_count == 0:
                print("📝 Generating initial situation summary...")
                summary = generate_hourly_summary(db)
                if summary:
                    print(f"✓ Initial summary generated: {summary.title[:50]}...")
        finally:
            db.close()
    except Exception as e:
        print(f"⚠ Initial ingestion error: {e}")


def run_scheduled_summary():
    """Background task to generate hourly situation summary"""
    print(f"\n📝 Generating situation summary at {datetime.now(timezone.utc).isoformat()}")
    
    try:
        db = next(database.get_db())
        try:
            from .services.summary import generate_hourly_summary
            summary = generate_hourly_summary(db)
            if summary:
                print(f"✓ Summary generated: {summary.title[:50]}...")
            else:
                print("✓ Summary skipped (no events)")
        finally:
            db.close()
    except Exception as e:
        print(f"✗ Summary generation failed: {e}")

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
        # Create airspace_events table if not exists
        """
        CREATE TABLE IF NOT EXISTS airspace_events (
            id SERIAL PRIMARY KEY,
            ts_start TIMESTAMP WITH TIME ZONE NOT NULL,
            ts_end TIMESTAMP WITH TIME ZONE,
            is_permanent BOOLEAN DEFAULT FALSE,
            geometry GEOMETRY(POLYGON, 4326),
            center_lat DOUBLE PRECISION,
            center_lon DOUBLE PRECISION,
            radius_nm DOUBLE PRECISION,
            lower_limit INTEGER DEFAULT 0,
            upper_limit INTEGER DEFAULT 999,
            airspace_type VARCHAR(50) DEFAULT 'airspace_restriction',
            source VARCHAR(50) DEFAULT 'notam',
            notam_id VARCHAR(50) UNIQUE,
            raw_text TEXT,
            q_line VARCHAR(255),
            fir VARCHAR(10),
            notam_codes VARCHAR(50),
            title VARCHAR(255),
            description TEXT,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE
        );
        """,
        # Create index on airspace_events
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_indexes WHERE indexname = 'idx_airspace_events_ts_start'
            ) THEN
                CREATE INDEX idx_airspace_events_ts_start ON airspace_events(ts_start);
            END IF;
            IF NOT EXISTS (
                SELECT 1 FROM pg_indexes WHERE indexname = 'idx_airspace_events_notam_id'
            ) THEN
                CREATE INDEX idx_airspace_events_notam_id ON airspace_events(notam_id);
            END IF;
            IF NOT EXISTS (
                SELECT 1 FROM pg_indexes WHERE indexname = 'idx_airspace_events_type'
            ) THEN
                CREATE INDEX idx_airspace_events_type ON airspace_events(airspace_type);
            END IF;
        END $$;
        """,
        # Create situation_summaries table if not exists
        """
        CREATE TABLE IF NOT EXISTS situation_summaries (
            id SERIAL PRIMARY KEY,
            title VARCHAR(255) NOT NULL,
            summary TEXT NOT NULL,
            key_developments TEXT,
            hotspots TEXT,
            risk_assessment TEXT,
            event_count INTEGER DEFAULT 0,
            protest_count INTEGER DEFAULT 0,
            clash_count INTEGER DEFAULT 0,
            arrest_count INTEGER DEFAULT 0,
            police_count INTEGER DEFAULT 0,
            period_start TIMESTAMP WITH TIME ZONE NOT NULL,
            period_end TIMESTAMP WITH TIME ZONE NOT NULL,
            model_used VARCHAR(50) DEFAULT 'gpt-4o-mini',
            tokens_used INTEGER DEFAULT 0,
            generation_time_ms INTEGER DEFAULT 0,
            is_current BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );
        """,
        # Create indexes on situation_summaries
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_indexes WHERE indexname = 'idx_situation_summaries_created_at'
            ) THEN
                CREATE INDEX idx_situation_summaries_created_at ON situation_summaries(created_at);
            END IF;
            IF NOT EXISTS (
                SELECT 1 FROM pg_indexes WHERE indexname = 'idx_situation_summaries_is_current'
            ) THEN
                CREATE INDEX idx_situation_summaries_is_current ON situation_summaries(is_current);
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
    
    # Step 2: Start scheduled tasks if database is ready
    if db_ready:
        print(f"\n📡 Auto-ingestion enabled (every {INGESTION_INTERVAL_MINUTES} minutes)")
        print(f"🧹 Auto-cleanup enabled (every {CLEANUP_INTERVAL_MINUTES} minutes, removing reports >{REPORT_MAX_AGE_HOURS}h)")
        
        # Schedule periodic ingestion
        if ENABLE_AUTO_INGESTION:
            scheduler.add_job(
                run_scheduled_ingestion,
                trigger=IntervalTrigger(minutes=INGESTION_INTERVAL_MINUTES),
                id='scheduled_ingestion',
                name='Periodic data ingestion',
                replace_existing=True
            )
        
        # Schedule periodic cleanup of old reports
        scheduler.add_job(
            run_cleanup_old_reports,
            trigger=IntervalTrigger(minutes=CLEANUP_INTERVAL_MINUTES),
            id='scheduled_cleanup',
            name='Cleanup old reports',
            replace_existing=True
        )
        
        # Schedule hourly situation summary generation
        SUMMARY_INTERVAL_MINUTES = int(os.getenv("SUMMARY_INTERVAL_MINUTES", "60"))
        scheduler.add_job(
            run_scheduled_summary,
            trigger=IntervalTrigger(minutes=SUMMARY_INTERVAL_MINUTES),
            id='scheduled_summary',
            name='Hourly situation summary',
            replace_existing=True
        )
        print(f"📝 Auto-summary enabled (every {SUMMARY_INTERVAL_MINUTES} minutes)")
        
        scheduler.start()
        print("✓ Scheduler started")
        
        # Run initial cleanup immediately
        cleanup_thread = threading.Thread(target=run_cleanup_old_reports, daemon=True)
        cleanup_thread.start()
        
        # Run initial ingestion in background thread (don't block startup)
        if ENABLE_AUTO_INGESTION:
            ingestion_thread = threading.Thread(target=run_initial_ingestion, daemon=True)
            ingestion_thread.start()
            print("✓ Initial ingestion started in background")
    else:
        print("⚠ Skipping scheduled tasks: database not ready")


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

# ============================================================================
# EVENT CLUSTERING
# ============================================================================
DEFAULT_CLUSTER_RADIUS_KM = 2.0  # Default clustering radius


def cluster_events(events: list, radius_km: float = DEFAULT_CLUSTER_RADIUS_KM) -> list:
    """
    Cluster nearby events within radius_km into single points.
    Uses simple greedy clustering algorithm.
    """
    if not events:
        return []
    
    # Convert radius to approximate degrees (1 degree ≈ 111km at equator)
    radius_deg = radius_km / 111.0
    
    clusters = []
    used = set()
    
    for i, event in enumerate(events):
        if i in used:
            continue
        
        # Start a new cluster with this event
        cluster_events = [event]
        cluster_lat = event.latitude
        cluster_lon = event.longitude
        used.add(i)
        
        # Find all nearby events
        for j, other in enumerate(events):
            if j in used:
                continue
            
            # Simple distance check (good enough for clustering)
            lat_diff = abs(other.latitude - cluster_lat)
            lon_diff = abs(other.longitude - cluster_lon)
            
            if lat_diff <= radius_deg and lon_diff <= radius_deg:
                cluster_events.append(other)
                used.add(j)
        
        # Create cluster summary
        if len(cluster_events) == 1:
            # Single event - no clustering needed
            e = cluster_events[0]
            clusters.append({
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [e.longitude, e.latitude]
                },
                "properties": {
                    "id": e.id,
                    "title": e.title,
                    "description": e.description,
                    "intensity": e.intensity_score,
                    "verified": e.verified,
                    "timestamp": e.timestamp.isoformat() if e.timestamp else None,
                    "source_url": e.source_url,
                    "media_url": e.media_url,
                    "media_type": e.media_type,
                    "event_type": e.event_type or "protest",
                    "source_platform": e.source_platform,
                    "cluster_count": 1,
                    "is_cluster": False
                }
            })
        else:
            # Multiple events - create cluster
            avg_lat = sum(e.latitude for e in cluster_events) / len(cluster_events)
            avg_lon = sum(e.longitude for e in cluster_events) / len(cluster_events)
            avg_intensity = sum(e.intensity_score for e in cluster_events) / len(cluster_events)
            has_verified = any(e.verified for e in cluster_events)
            latest = max(cluster_events, key=lambda e: e.timestamp if e.timestamp else datetime.min.replace(tzinfo=timezone.utc))
            
            # Count event types in cluster
            type_counts = {}
            for e in cluster_events:
                t = e.event_type or "protest"
                type_counts[t] = type_counts.get(t, 0) + 1
            dominant_type = max(type_counts, key=type_counts.get)
            
            # Build cluster title
            cluster_title = f"📍 {len(cluster_events)} reports in this area"
            
            # Build description with breakdown
            type_breakdown = ", ".join(f"{count} {t}" for t, count in sorted(type_counts.items(), key=lambda x: -x[1]))
            
            clusters.append({
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [avg_lon, avg_lat]
                },
                "properties": {
                    "id": f"cluster_{latest.id}",
                    "title": cluster_title,
                    "description": f"Cluster includes: {type_breakdown}",
                    "intensity": min(avg_intensity * (1 + len(cluster_events) * 0.1), 1.0),  # Boost intensity for clusters
                    "verified": has_verified,
                    "timestamp": latest.timestamp.isoformat() if latest.timestamp else None,
                    "source_url": latest.source_url,
                    "media_url": latest.media_url,
                    "media_type": latest.media_type,
                    "event_type": dominant_type,
                    "source_platform": "multiple",
                    "cluster_count": len(cluster_events),
                    "is_cluster": True,
                    "type_breakdown": type_counts,
                    "event_ids": [e.id for e in cluster_events]
                }
            })
    
    return clusters


@app.get("/api/events")
def get_events(
    verified_only: bool = False,
    hours: int = 12,  # Default to last 12 hours
    event_type: str = None,  # Filter by event type
    cluster: bool = True,  # Enable clustering by default
    cluster_radius: float = DEFAULT_CLUSTER_RADIUS_KM,  # Cluster radius in km
    db: Session = Depends(get_db)
):
    """
    Get events as GeoJSON FeatureCollection.
    
    - **verified_only**: Filter to verified events only
    - **hours**: Time window in hours (default 12)
    - **event_type**: Filter by type: 'protest', 'police_presence', 'strike', 'clash', 'arrest'
    - **cluster**: Enable clustering of nearby events (default: true)
    - **cluster_radius**: Clustering radius in km (default: 2.0)
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
    
    # Apply clustering if enabled
    if cluster and cluster_radius > 0:
        features = cluster_events(events, radius_km=cluster_radius)
    else:
        # No clustering - return all events individually
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
                    "source_platform": event.source_platform,
                    "cluster_count": 1,
                    "is_cluster": False
                }
            })
        
    return {
        "type": "FeatureCollection",
        "features": features,
        "total_events": len(events),
        "clustered_points": len(features),
        "cluster_radius_km": cluster_radius if cluster else 0
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


# ============================================================================
# AIRSPACE / NOTAM ENDPOINTS
# ============================================================================
from .services.notam import NOTAMService, fetch_real_notams, load_sample_notams


@app.get("/api/airspace")
def get_airspace(
    fir: str = None,  # Filter by FIR (e.g., OIIX for Tehran)
    active_only: bool = True,  # Only return currently active restrictions
    fetch_new: bool = False,  # Fetch new NOTAMs if empty
    db: Session = Depends(get_db)
):
    """
    Get airspace restrictions as GeoJSON FeatureCollection.
    
    - **fir**: Filter by Flight Information Region (e.g., OIIX for Iran/Tehran)
    - **active_only**: Only return currently active restrictions (default: true)
    - **fetch_new**: Fetch real NOTAMs if database is empty (default: false)
    """
    service = NOTAMService(db)
    
    # Auto-fetch real NOTAMs if requested and no data exists
    if fetch_new:
        count = db.query(models.AirspaceEvent).count()
        if count == 0:
            loaded = fetch_real_notams(db)
            print(f"Fetched {loaded} NOTAMs")
    
    if active_only:
        events = service.get_active_airspace(fir=fir)
    else:
        query = db.query(models.AirspaceEvent)
        if fir:
            query = query.filter(models.AirspaceEvent.fir == fir)
        events = query.order_by(models.AirspaceEvent.ts_start.desc()).limit(100).all()
    
    return service.to_geojson(events)


@app.post("/api/airspace/notam")
def submit_notam(
    notam_text: str,
    admin_key: str,
    db: Session = Depends(get_db)
):
    """
    Submit a NOTAM for parsing and storage (admin only).
    
    - **notam_text**: Raw NOTAM text in ICAO format
    - **admin_key**: Admin authentication key
    """
    if admin_key != ADMIN_KEY:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid admin key")
    
    service = NOTAMService(db)
    count = service.parse_and_store([notam_text])
    
    if count > 0:
        return {"status": "success", "message": "NOTAM parsed and stored", "count": count}
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not parse NOTAM. Check format and coordinates."
        )


@app.post("/api/airspace/load-samples")
def load_sample_airspace(
    admin_key: str,
    db: Session = Depends(get_db)
):
    """Load sample NOTAMs for testing (admin only)"""
    if admin_key != ADMIN_KEY:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid admin key")
    
    count = load_sample_notams(db)
    return {"status": "success", "message": f"Loaded {count} sample NOTAMs"}


@app.delete("/api/airspace/cleanup")
def cleanup_airspace(
    admin_key: str,
    db: Session = Depends(get_db)
):
    """Remove expired airspace restrictions (admin only)"""
    if admin_key != ADMIN_KEY:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid admin key")
    
    service = NOTAMService(db)
    count = service.cleanup_expired()
    return {"status": "success", "message": f"Removed {count} expired NOTAMs"}


@app.post("/api/airspace/refresh")
def refresh_airspace(
    admin_key: str = None,
    db: Session = Depends(get_db)
):
    """
    Refresh NOTAMs by fetching from real data sources.
    Admin key optional - will use sample data as fallback.
    """
    # Clear existing and fetch new
    try:
        # Delete old entries
        deleted = db.query(models.AirspaceEvent).delete(synchronize_session=False)
        db.commit()
        print(f"Cleared {deleted} old NOTAMs")
        
        # Fetch fresh data
        count = fetch_real_notams(db)
        
        return {
            "status": "success", 
            "message": f"Refreshed airspace data",
            "deleted": deleted,
            "fetched": count
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to refresh NOTAMs: {str(e)}"
        )


# ============================================================================
# OSINT DATA ENDPOINTS (GeoConfirmed, ArcGIS, etc.)
# ============================================================================
from .services.osint import fetch_osint_data, OSINTService


@app.get("/api/osint/fetch")
def fetch_osint_data_endpoint(
    db: Session = Depends(get_db)
):
    """
    Fetch OSINT data from available sources:
    - GeoConfirmed (geoconfirmed.org) - if API accessible
    - ArcGIS Feature Services (public layers for Iran)
    
    Returns count of events fetched from each source.
    """
    results = fetch_osint_data(db)
    return {
        "status": "success",
        "message": "OSINT data fetched",
        "results": results
    }


@app.post("/api/osint/import-kml")
def import_osint_kml(
    kml_content: str,
    admin_key: str,
    db: Session = Depends(get_db)
):
    """
    Import KML file content (e.g., from GeoConfirmed export).
    
    To use:
    1. Go to geoconfirmed.org/iran
    2. Click "Download KML"
    3. Paste the KML content here
    
    - **kml_content**: Raw KML file content
    - **admin_key**: Admin authentication key
    """
    if admin_key != ADMIN_KEY:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid admin key")
    
    service = OSINTService(db)
    count = service.import_kml(kml_content)
    
    return {
        "status": "success",
        "message": f"Imported {count} events from KML",
        "count": count
    }


@app.get("/api/osint/arcgis")
def fetch_arcgis_data(
    layer: int = None,  # Specific layer ID to fetch
    db: Session = Depends(get_db)
):
    """
    Fetch data from ArcGIS Feature Service for Iran.
    
    Available layers:
    - 0: Israeli Operations in Iran
    - 1: Iran Missile Bases
    - 2: Power Plants
    - 3: Naval Bases
    - 4: Nuclear Sites
    
    - **layer**: Specific layer ID (optional, fetches all if not specified)
    """
    service = OSINTService(db)
    
    if layer is not None:
        events = service.arcgis.fetch_layer(layer)
        for event in events:
            service._store_event(event, 'arcgis')
        service.db.commit()
        return {
            "status": "success",
            "layer": layer,
            "layer_name": service.arcgis.LAYERS.get(layer, "unknown"),
            "count": len(events)
        }
    else:
        events = service.arcgis.fetch_all_layers()
        count = 0
        for event in events:
            if service._store_event(event, 'arcgis'):
                count += 1
        service.db.commit()
        return {
            "status": "success",
            "total_features": len(events),
            "stored": count,
            "layers": list(service.arcgis.LAYERS.values())
        }


# ============================================================================
# SITUATION SUMMARY ENDPOINTS (AI-Generated)
# ============================================================================
from .services.summary import SummaryService


@app.get("/api/summary")
def get_current_summary(
    db: Session = Depends(get_db)
):
    """
    Get the current (most recent) AI-generated situation summary.
    
    Returns the latest analysis including:
    - Executive summary
    - Key developments
    - Active hotspots
    - Risk assessment
    - Statistics
    """
    service = SummaryService(db)
    summary = service.get_current_summary()
    
    if not summary:
        # Generate one if none exists
        summary = service.generate_summary(force=True)
        if not summary:
            return {
                "status": "no_data",
                "message": "No events to summarize yet",
                "summary": None
            }
    
    return {
        "status": "success",
        "summary": service.format_for_response(summary)
    }


@app.get("/api/summary/history")
def get_summary_history(
    limit: int = 24,
    db: Session = Depends(get_db)
):
    """
    Get historical summaries (default: last 24).
    
    Useful for tracking situation evolution over time.
    """
    service = SummaryService(db)
    summaries = service.get_summary_history(limit=limit)
    
    return {
        "status": "success",
        "count": len(summaries),
        "summaries": [service.format_for_response(s) for s in summaries]
    }


@app.post("/api/summary/generate")
def generate_summary(
    admin_key: str = None,
    force: bool = False,
    db: Session = Depends(get_db)
):
    """
    Manually trigger summary generation.
    
    - **admin_key**: Optional admin key (allows forced generation)
    - **force**: Generate even if no events (requires admin_key)
    """
    if force and admin_key != ADMIN_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin key required for forced generation"
        )
    
    service = SummaryService(db)
    summary = service.generate_summary(force=force)
    
    if not summary:
        return {
            "status": "skipped",
            "message": "No events to summarize"
        }
    
    return {
        "status": "success",
        "message": "Summary generated",
        "summary": service.format_for_response(summary)
    }


@app.get("/api/summary/{summary_id}")
def get_summary_by_id(
    summary_id: int,
    db: Session = Depends(get_db)
):
    """Get a specific summary by ID"""
    summary = db.query(models.SituationSummary).filter(
        models.SituationSummary.id == summary_id
    ).first()
    
    if not summary:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Summary not found"
        )
    
    service = SummaryService(db)
    return {
        "status": "success",
        "summary": service.format_for_response(summary)
    }


# ============================================================================
# INTERNET CONNECTIVITY MONITORING
# ============================================================================
from .services.connectivity import ConnectivityService, get_connectivity_data, IRAN_PROVINCES


@app.get("/api/connectivity")
def get_connectivity():
    """
    Get internet connectivity status for all Iranian provinces.
    
    Returns GeoJSON FeatureCollection with:
    - Province location (point)
    - Connectivity score (0-1, where 1 = full connectivity)
    - Status: 'normal', 'degraded', 'restricted', 'blackout'
    - National-level summary
    
    Data sources:
    - IODA (Internet Outage Detection and Analysis)
    - Cloudflare Radar (if API key configured)
    """
    return get_connectivity_data()


@app.get("/api/connectivity/provinces")
def get_connectivity_provinces():
    """Get list of all monitored provinces with their connectivity status"""
    service = ConnectivityService()
    provinces = service.get_province_connectivity()
    
    return {
        "status": "success",
        "count": len(provinces),
        "provinces": provinces
    }


@app.post("/api/connectivity/update")
def update_province_connectivity(
    province_id: str,
    status: str,
    score: float = None,
    admin_key: str = None,
):
    """
    Manually update connectivity status for a province (admin only).
    
    Use for ground-truth updates when automatic detection is delayed.
    
    - **province_id**: Province identifier (e.g., 'tehran', 'isfahan')
    - **status**: 'normal', 'degraded', 'restricted', 'blackout'
    - **score**: Optional specific score (0-1)
    - **admin_key**: Admin authentication
    """
    if admin_key != ADMIN_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin key required"
        )
    
    if province_id not in IRAN_PROVINCES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown province: {province_id}. Available: {list(IRAN_PROVINCES.keys())}"
        )
    
    service = ConnectivityService()
    success = service.update_province_status(province_id, status, score)
    
    if success:
        return {
            "status": "success",
            "message": f"Updated {province_id} to {status}",
            "province_id": province_id,
            "new_status": status,
            "new_score": score
        }
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid status. Must be: normal, degraded, restricted, blackout"
        )


@app.get("/api/connectivity/national")
def get_national_connectivity():
    """Get national-level connectivity summary"""
    service = ConnectivityService()
    geojson = service.get_connectivity_geojson()
    
    metadata = geojson.get("metadata", {})
    provinces = geojson.get("features", [])
    
    # Count by status
    status_counts = {}
    for p in provinces:
        s = p.get("properties", {}).get("status", "unknown")
        status_counts[s] = status_counts.get(s, 0) + 1
    
    return {
        "status": "success",
        "national": {
            "score": metadata.get("national_score", 0.5),
            "status": metadata.get("national_status", "unknown"),
            "updated_at": metadata.get("updated_at"),
        },
        "provinces_by_status": status_counts,
        "total_provinces": len(provinces),
    }

