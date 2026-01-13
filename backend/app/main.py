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
REPORT_MAX_AGE_HOURS = int(os.getenv("REPORT_MAX_AGE_HOURS", "168"))  # Delete reports older than 7 days (168h) to keep date-only sources like GeoConfirmed
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
            
            # Fetch ACLED data (if configured)
            from .services.acled import fetch_acled_data
            print("📊 Fetching ACLED conflict data...")
            acled_count = fetch_acled_data(db, days=30)
            print(f"✓ ACLED fetch complete: {acled_count} events")
            
            # Fetch Telegram feed
            from .services.telegram_feed import fetch_telegram_feed
            print("📡 Fetching Telegram live feed...")
            telegram_count = fetch_telegram_feed(db)
            print(f"✓ Telegram fetch complete: {telegram_count} messages")
            
            # Update city analytics
            from .services.city_analytics import update_analytics
            print("🏙️ Computing city analytics...")
            analytics_count = update_analytics(db)
            print(f"✓ Analytics updated for {analytics_count} cities")
            
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


def run_scheduled_telegram_feed():
    """Background task to fetch Telegram live feed"""
    print(f"\n📡 Fetching Telegram feed at {datetime.now(timezone.utc).isoformat()}")
    
    try:
        db = next(database.get_db())
        try:
            from .services.telegram_feed import fetch_telegram_feed
            count = fetch_telegram_feed(db)
            if count > 0:
                print(f"✓ Telegram feed: {count} new messages")
            else:
                print("✓ Telegram feed: no new messages")
        finally:
            db.close()
    except Exception as e:
        print(f"✗ Telegram feed failed: {e}")


def run_scheduled_analytics():
    """Background task to update city analytics"""
    print(f"\n🏙️ Updating analytics at {datetime.now(timezone.utc).isoformat()}")
    
    try:
        db = next(database.get_db())
        try:
            from .services.city_analytics import update_analytics
            count = update_analytics(db)
            print(f"✓ Analytics updated: {count} cities")
        finally:
            db.close()
    except Exception as e:
        print(f"✗ Analytics update failed: {e}")

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
        # Create telegram_messages table
        """
        CREATE TABLE IF NOT EXISTS telegram_messages (
            id SERIAL PRIMARY KEY,
            channel VARCHAR(255) NOT NULL,
            message_id VARCHAR(255) UNIQUE NOT NULL,
            text TEXT NOT NULL,
            text_translated TEXT,
            media_url VARCHAR(500),
            media_type VARCHAR(50),
            timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            sentiment VARCHAR(50),
            keywords TEXT,
            locations_mentioned TEXT,
            event_type_detected VARCHAR(50),
            urgency_score DOUBLE PRECISION DEFAULT 0.5,
            linked_event_id INTEGER REFERENCES protest_events(id),
            is_processed BOOLEAN DEFAULT FALSE,
            is_relevant BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );
        """,
        # Create indexes on telegram_messages
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_indexes WHERE indexname = 'idx_telegram_messages_channel'
            ) THEN
                CREATE INDEX idx_telegram_messages_channel ON telegram_messages(channel);
            END IF;
            IF NOT EXISTS (
                SELECT 1 FROM pg_indexes WHERE indexname = 'idx_telegram_messages_timestamp'
            ) THEN
                CREATE INDEX idx_telegram_messages_timestamp ON telegram_messages(timestamp);
            END IF;
            IF NOT EXISTS (
                SELECT 1 FROM pg_indexes WHERE indexname = 'idx_telegram_messages_urgency'
            ) THEN
                CREATE INDEX idx_telegram_messages_urgency ON telegram_messages(urgency_score);
            END IF;
        END $$;
        """,
        # Create city_statistics table
        """
        CREATE TABLE IF NOT EXISTS city_statistics (
            id SERIAL PRIMARY KEY,
            city_name VARCHAR(255) NOT NULL,
            city_name_fa VARCHAR(255),
            latitude DOUBLE PRECISION NOT NULL,
            longitude DOUBLE PRECISION NOT NULL,
            province VARCHAR(255),
            total_events INTEGER DEFAULT 0,
            protest_count INTEGER DEFAULT 0,
            clash_count INTEGER DEFAULT 0,
            arrest_count INTEGER DEFAULT 0,
            police_count INTEGER DEFAULT 0,
            strike_count INTEGER DEFAULT 0,
            events_24h INTEGER DEFAULT 0,
            events_7d INTEGER DEFAULT 0,
            trend_direction VARCHAR(50) DEFAULT 'stable',
            trend_percentage DOUBLE PRECISION DEFAULT 0.0,
            hourly_pattern TEXT,
            peak_hour INTEGER,
            avg_daily_events DOUBLE PRECISION DEFAULT 0.0,
            activity_level VARCHAR(50) DEFAULT 'low',
            period_start TIMESTAMP WITH TIME ZONE,
            period_end TIMESTAMP WITH TIME ZONE,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );
        """,
        # Create index on city_statistics
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_indexes WHERE indexname = 'idx_city_statistics_city_name'
            ) THEN
                CREATE INDEX idx_city_statistics_city_name ON city_statistics(city_name);
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
        
        # Schedule Telegram feed updates (every 10 minutes)
        scheduler.add_job(
            run_scheduled_telegram_feed,
            trigger=IntervalTrigger(minutes=10),
            id='scheduled_telegram_feed',
            name='Telegram feed update',
            replace_existing=True
        )
        print(f"📡 Telegram feed enabled (every 10 minutes)")
        
        # Schedule city analytics update (every 30 minutes)
        scheduler.add_job(
            run_scheduled_analytics,
            trigger=IntervalTrigger(minutes=30),
            id='scheduled_analytics',
            name='City analytics update',
            replace_existing=True
        )
        print(f"🏙️ Analytics update enabled (every 30 minutes)")
        
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
    hours: int = 24,  # Default to last 24 hours
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


# ============================================================================
# TELEGRAM LIVE FEED ENDPOINTS
# ============================================================================
from .services.telegram_feed import TelegramFeedService, fetch_telegram_feed


@app.get("/api/telegram/feed")
def get_telegram_feed(
    limit: int = 50,
    offset: int = 0,
    channel: str = None,
    min_urgency: float = 0.0,
    relevant_only: bool = True,
    hours: int = 24,
    db: Session = Depends(get_db)
):
    """
    Get Telegram live feed with NLP analysis.
    
    - **limit**: Maximum messages to return (default: 50)
    - **offset**: Pagination offset
    - **channel**: Filter by channel (e.g., 'HengawO', '1500tasvir')
    - **min_urgency**: Minimum urgency score 0-1 (default: 0, returns all)
    - **relevant_only**: Only return protest-relevant messages (default: true)
    - **hours**: Limit to messages from last N hours (default: 24)
    """
    service = TelegramFeedService(db)
    messages, total = service.get_feed(
        limit=limit,
        offset=offset,
        channel=channel,
        min_urgency=min_urgency,
        relevant_only=relevant_only,
        hours=hours
    )
    
    # Format for response
    formatted = []
    for msg in messages:
        formatted.append({
            "id": msg.id,
            "channel": msg.channel,
            "message_id": msg.message_id,
            "text": msg.text,
            "text_translated": msg.text_translated,
            "media_url": msg.media_url,
            "media_type": msg.media_type,
            "timestamp": msg.timestamp.isoformat() if msg.timestamp else None,
            "sentiment": msg.sentiment,
            "keywords": msg.keywords,
            "locations_mentioned": msg.locations_mentioned,
            "event_type_detected": msg.event_type_detected,
            "urgency_score": msg.urgency_score,
            "is_relevant": msg.is_relevant,
        })
    
    latest_ts = messages[0].timestamp if messages else None
    
    return {
        "status": "success",
        "messages": formatted,
        "total_count": total,
        "channels": service.get_channels(),
        "latest_timestamp": latest_ts.isoformat() if latest_ts else None
    }


@app.get("/api/telegram/urgent")
def get_urgent_messages(
    threshold: float = 0.8,
    limit: int = 10,
    db: Session = Depends(get_db)
):
    """
    Get high-urgency Telegram messages from the last 12 hours.
    
    - **threshold**: Minimum urgency score (default: 0.8)
    - **limit**: Maximum messages to return (default: 10)
    """
    service = TelegramFeedService(db)
    messages = service.get_high_urgency(threshold=threshold, limit=limit)
    
    formatted = []
    for msg in messages:
        formatted.append({
            "id": msg.id,
            "channel": msg.channel,
            "text": msg.text[:200] + "..." if len(msg.text) > 200 else msg.text,
            "urgency_score": msg.urgency_score,
            "event_type_detected": msg.event_type_detected,
            "locations_mentioned": msg.locations_mentioned,
            "timestamp": msg.timestamp.isoformat() if msg.timestamp else None,
        })
    
    return {
        "status": "success",
        "count": len(formatted),
        "threshold": threshold,
        "messages": formatted
    }


@app.post("/api/telegram/refresh")
def refresh_telegram_feed(
    admin_key: str = None,
    db: Session = Depends(get_db)
):
    """
    Manually trigger Telegram feed refresh.
    Fetches new messages from all monitored channels.
    """
    service = TelegramFeedService(db)
    count = service.fetch_and_process_all()
    
    return {
        "status": "success",
        "message": f"Fetched {count} new messages",
        "new_messages": count
    }


@app.get("/api/telegram/channels")
def get_telegram_channels(db: Session = Depends(get_db)):
    """Get list of monitored Telegram channels"""
    from .services.telegram_feed import PRIORITY_CHANNELS
    
    service = TelegramFeedService(db)
    active_channels = service.get_channels()
    
    channels = []
    for config in PRIORITY_CHANNELS:
        channels.append({
            "channel": config["channel"],
            "name": config["name"],
            "category": config["category"],
            "priority": config["priority"],
            "has_messages": config["channel"] in active_channels
        })
    
    return {
        "status": "success",
        "count": len(channels),
        "channels": channels
    }


# ============================================================================
# CITY ANALYTICS ENDPOINTS
# ============================================================================
from .services.city_analytics import CityAnalyticsService, update_analytics


@app.get("/api/analytics/summary")
def get_analytics_summary(db: Session = Depends(get_db)):
    """
    Get overall analytics summary.
    
    Returns:
    - Total cities and events
    - Most active city and hour
    - Top cities ranking
    - Hourly and event type distributions
    """
    service = CityAnalyticsService(db)
    summary = service.get_analytics_summary()
    
    return {
        "status": "success",
        "summary": summary
    }


@app.get("/api/analytics/cities")
def get_cities_analytics(
    limit: int = 30,
    db: Session = Depends(get_db)
):
    """
    Get analytics for all cities with event data.
    
    - **limit**: Maximum cities to return (default: 30)
    """
    service = CityAnalyticsService(db)
    cities = service.get_city_ranking(limit=limit)
    
    return {
        "status": "success",
        "count": len(cities),
        "cities": cities
    }


@app.get("/api/analytics/city/{city_name}")
def get_city_analytics(
    city_name: str,
    days: int = 30,
    db: Session = Depends(get_db)
):
    """
    Get detailed analytics for a specific city.
    
    - **city_name**: City name (e.g., 'Tehran', 'Isfahan', 'Sanandaj')
    - **days**: Number of days to analyze (default: 30)
    """
    service = CityAnalyticsService(db)
    stats = service.compute_city_stats(city_name, days=days)
    
    if not stats:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"City not found: {city_name}"
        )
    
    return {
        "status": "success",
        "city": stats
    }


@app.get("/api/analytics/hourly")
def get_hourly_analytics(
    days: int = 7,
    db: Session = Depends(get_db)
):
    """
    Get hourly distribution of events.
    
    - **days**: Number of days to analyze (default: 7)
    
    Returns hour-by-hour event counts (0-23).
    """
    service = CityAnalyticsService(db)
    hourly = service.get_hourly_distribution(days=days)
    
    # Find peak hour
    peak_hour = max(hourly, key=hourly.get) if hourly else None
    total = sum(hourly.values())
    
    return {
        "status": "success",
        "days_analyzed": days,
        "total_events": total,
        "peak_hour": peak_hour,
        "peak_count": hourly.get(peak_hour, 0) if peak_hour is not None else 0,
        "hourly": hourly
    }


@app.get("/api/analytics/trends")
def get_trend_analytics(
    days: int = 30,
    db: Session = Depends(get_db)
):
    """
    Get trend analysis for all cities.
    
    - **days**: Number of days to analyze (default: 30)
    """
    service = CityAnalyticsService(db)
    cities = service.compute_all_cities(days=days)
    
    # Summarize trends
    trending_up = [c for c in cities if c["trend_direction"] == "up"]
    trending_down = [c for c in cities if c["trend_direction"] == "down"]
    stable = [c for c in cities if c["trend_direction"] == "stable"]
    
    return {
        "status": "success",
        "summary": {
            "trending_up": len(trending_up),
            "trending_down": len(trending_down),
            "stable": len(stable),
        },
        "top_trending": trending_up[:5] if trending_up else [],
        "declining": trending_down[:5] if trending_down else [],
    }


@app.post("/api/analytics/refresh")
def refresh_analytics(
    admin_key: str = None,
    db: Session = Depends(get_db)
):
    """
    Manually refresh city analytics.
    Updates stored statistics for all cities.
    """
    service = CityAnalyticsService(db)
    count = service.update_city_statistics()
    
    return {
        "status": "success",
        "message": f"Updated analytics for {count} cities",
        "cities_updated": count
    }


# ============================================================================
# ACLED DATA ENDPOINTS
# ============================================================================
from .services.acled import ACLEDService, fetch_acled_data


@app.get("/api/acled/fetch")
def fetch_acled_events(
    days: int = 30,
    db: Session = Depends(get_db)
):
    """
    Fetch conflict events from ACLED (Armed Conflict Location & Event Data).
    
    - **days**: Number of days to look back (default: 30)
    
    Note: Requires ACLED_API_KEY and ACLED_EMAIL environment variables.
    Register at: https://acleddata.com/register/
    """
    count = fetch_acled_data(db, days=days)
    
    return {
        "status": "success",
        "message": f"Fetched {count} ACLED events",
        "events_stored": count,
        "days_queried": days
    }


@app.get("/api/acled/status")
def get_acled_status():
    """Check if ACLED API is configured"""
    api_key = os.getenv("ACLED_API_KEY")
    email = os.getenv("ACLED_EMAIL")
    
    return {
        "configured": bool(api_key and email),
        "has_api_key": bool(api_key),
        "has_email": bool(email),
        "registration_url": "https://acleddata.com/register/"
    }

