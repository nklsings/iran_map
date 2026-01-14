from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import text
from . import models, schemas, database
from .services.ingestion import IngestionService
from typing import List, Dict, Any, Optional
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
# Per-source ingestion intervals (in minutes)
RSS_INTERVAL_MINUTES = int(os.getenv("RSS_INTERVAL_MINUTES", "5"))           # RSS feeds - fast, low cost
TELEGRAM_INTERVAL_MINUTES = int(os.getenv("TELEGRAM_INTERVAL_MINUTES", "5")) # Telegram - fast, web scraping
TWITTER_INTERVAL_MINUTES = int(os.getenv("TWITTER_INTERVAL_MINUTES", "30"))  # Twitter API - rate limited
YOUTUBE_INTERVAL_MINUTES = int(os.getenv("YOUTUBE_INTERVAL_MINUTES", "15"))  # YouTube RSS - moderate
REDDIT_INTERVAL_MINUTES = int(os.getenv("REDDIT_INTERVAL_MINUTES", "10"))    # Reddit JSON - moderate
OSINT_INTERVAL_MINUTES = int(os.getenv("OSINT_INTERVAL_MINUTES", "10"))      # ArcGIS/GeoConfirmed - moderate

# Legacy setting (used if specific intervals not set)
INGESTION_INTERVAL_MINUTES = int(os.getenv("INGESTION_INTERVAL_MINUTES", "15"))
ENABLE_AUTO_INGESTION = os.getenv("ENABLE_AUTO_INGESTION", "true").lower() == "true"
REPORT_MAX_AGE_HOURS = int(os.getenv("REPORT_MAX_AGE_HOURS", "168"))  # Delete reports older than 7 days
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
    """Background task to fetch new events from all sources (legacy, for manual triggers)"""
    print(f"\n{'='*50}")
    print(f"⏰ Full ingestion started at {datetime.now(timezone.utc).isoformat()}")
    print(f"{'='*50}")
    
    try:
        db = next(database.get_db())
        try:
            service = IngestionService(db)
            count = service.run_ingestion(source_type="all")
            print(f"✓ Full ingestion complete: {count} new events")
        finally:
            db.close()
    except Exception as e:
        print(f"✗ Full ingestion failed: {e}")


def run_ingestion_rss():
    """Fetch from RSS feeds (fast, low API cost)"""
    try:
        db = next(database.get_db())
        try:
            service = IngestionService(db)
            count = service.run_ingestion(source_type="rss")
            if count > 0:
                print(f"📰 RSS: {count} new events")
        finally:
            db.close()
    except Exception as e:
        print(f"✗ RSS ingestion failed: {e}")


def run_ingestion_telegram():
    """Fetch from Telegram channels"""
    try:
        db = next(database.get_db())
        try:
            service = IngestionService(db)
            count = service.run_ingestion(source_type="telegram")
            if count > 0:
                print(f"📱 Telegram: {count} new events")
        finally:
            db.close()
    except Exception as e:
        print(f"✗ Telegram ingestion failed: {e}")


def run_ingestion_twitter():
    """Fetch from Twitter/X API"""
    try:
        db = next(database.get_db())
        try:
            service = IngestionService(db)
            count = service.run_ingestion(source_type="twitter")
            if count > 0:
                print(f"🐦 Twitter: {count} new events")
        finally:
            db.close()
    except Exception as e:
        print(f"✗ Twitter ingestion failed: {e}")


def run_ingestion_youtube():
    """Fetch from YouTube channels"""
    try:
        db = next(database.get_db())
        try:
            service = IngestionService(db)
            count = service.run_ingestion(source_type="youtube")
            if count > 0:
                print(f"▶️ YouTube: {count} new events")
        finally:
            db.close()
    except Exception as e:
        print(f"✗ YouTube ingestion failed: {e}")


def run_ingestion_reddit():
    """Fetch from Reddit subreddits"""
    try:
        db = next(database.get_db())
        try:
            service = IngestionService(db)
            count = service.run_ingestion(source_type="reddit")
            if count > 0:
                print(f"🔴 Reddit: {count} new events")
        finally:
            db.close()
    except Exception as e:
        print(f"✗ Reddit ingestion failed: {e}")


def run_ingestion_osint():
    """Fetch from OSINT sources (ArcGIS, GeoConfirmed)"""
    try:
        db = next(database.get_db())
        try:
            from .services.osint import fetch_osint_data
            results = fetch_osint_data(db)
            if results.get('total', 0) > 0:
                print(f"🌍 OSINT: {results['total']} events")
        finally:
            db.close()
    except Exception as e:
        print(f"✗ OSINT ingestion failed: {e}")

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
            
            count = service.run_ingestion(source_type="twitter")
            print(f"✓ Initial Twitter ingestion complete: {count} events")
            
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
            
            # Fetch Twitter/X feed for live display
            from .services.twitter_feed import fetch_twitter_feed
            print("🐦 Fetching Twitter/X live feed...")
            twitter_feed_count = fetch_twitter_feed(db)
            print(f"✓ Twitter feed complete: {twitter_feed_count} tweets")
            
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


def run_scheduled_twitter_feed():
    """Background task to fetch Twitter live feed"""
    try:
        db = next(database.get_db())
        try:
            from .services.twitter_feed import fetch_twitter_feed
            count = fetch_twitter_feed(db)
            if count > 0:
                print(f"🐦 Twitter feed: {count} new tweets")
        finally:
            db.close()
    except Exception as e:
        print(f"✗ Twitter feed failed: {e}")


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
        print(f"\n📡 Auto-ingestion enabled (per-source intervals):")
        print(f"🧹 Auto-cleanup enabled (every {CLEANUP_INTERVAL_MINUTES} min, removing reports >{REPORT_MAX_AGE_HOURS}h)")
        
        # Schedule per-source ingestion with different intervals
        if ENABLE_AUTO_INGESTION:
            # RSS feeds - fast updates (default: 5 min)
            scheduler.add_job(
                run_ingestion_rss,
                trigger=IntervalTrigger(minutes=RSS_INTERVAL_MINUTES),
                id='ingestion_rss',
                name='RSS ingestion',
                replace_existing=True
            )
            print(f"  📰 RSS: every {RSS_INTERVAL_MINUTES} min")
            
            # Telegram - fast updates (default: 5 min)
            scheduler.add_job(
                run_ingestion_telegram,
                trigger=IntervalTrigger(minutes=TELEGRAM_INTERVAL_MINUTES),
                id='ingestion_telegram',
                name='Telegram ingestion',
                replace_existing=True
            )
            print(f"  📱 Telegram: every {TELEGRAM_INTERVAL_MINUTES} min")
            
            # Twitter - rate limited (default: 30 min)
            scheduler.add_job(
                run_ingestion_twitter,
                trigger=IntervalTrigger(minutes=TWITTER_INTERVAL_MINUTES),
                id='ingestion_twitter',
                name='Twitter ingestion',
                replace_existing=True
            )
            print(f"  🐦 Twitter: every {TWITTER_INTERVAL_MINUTES} min")
            
            # YouTube - moderate (default: 15 min)
            scheduler.add_job(
                run_ingestion_youtube,
                trigger=IntervalTrigger(minutes=YOUTUBE_INTERVAL_MINUTES),
                id='ingestion_youtube',
                name='YouTube ingestion',
                replace_existing=True
            )
            print(f"  ▶️ YouTube: every {YOUTUBE_INTERVAL_MINUTES} min")
            
            # Reddit - moderate (default: 10 min)
            scheduler.add_job(
                run_ingestion_reddit,
                trigger=IntervalTrigger(minutes=REDDIT_INTERVAL_MINUTES),
                id='ingestion_reddit',
                name='Reddit ingestion',
                replace_existing=True
            )
            print(f"  🔴 Reddit: every {REDDIT_INTERVAL_MINUTES} min")
            
            # OSINT (ArcGIS, GeoConfirmed) - moderate (default: 10 min)
            scheduler.add_job(
                run_ingestion_osint,
                trigger=IntervalTrigger(minutes=OSINT_INTERVAL_MINUTES),
                id='ingestion_osint',
                name='OSINT ingestion',
                replace_existing=True
            )
            print(f"  🌍 OSINT: every {OSINT_INTERVAL_MINUTES} min")
        
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
        print(f"  📡 Telegram feed: every 10 min")
        
        # Schedule Twitter feed updates (every 30 minutes due to rate limits)
        scheduler.add_job(
            run_scheduled_twitter_feed,
            trigger=IntervalTrigger(minutes=TWITTER_INTERVAL_MINUTES),
            id='scheduled_twitter_feed',
            name='Twitter feed update',
            replace_existing=True
        )
        print(f"  🐦 Twitter feed: every {TWITTER_INTERVAL_MINUTES} min")
        
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

@app.get("/api/config/status")
def config_status():
    """Check which API keys are configured (for debugging)"""
    return {
        "status": "ok",
        "apis": {
            "twitter": bool(os.getenv("TWITTER_BEARER_TOKEN")),
            "openai": bool(os.getenv("OPENAI_API_KEY")),
            "checkwx": bool(os.getenv("CHECKWX_API_KEY")),
            "acled": bool(os.getenv("ACLED_EMAIL") and os.getenv("ACLED_PASSWORD")),
            "cloudflare_radar": bool(os.getenv("CLOUDFLARE_RADAR_API_KEY")),
        },
        "auto_ingestion": ENABLE_AUTO_INGESTION,
        "intervals": {
            "twitter_minutes": TWITTER_INTERVAL_MINUTES,
            "telegram_minutes": TELEGRAM_INTERVAL_MINUTES,
            "rss_minutes": RSS_INTERVAL_MINUTES,
        }
    }

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


# ============================================================================
# PPU-EVENT CORRELATION (Link Police Presence with Reports)
# ============================================================================
CORRELATION_RADIUS_KM = 2.0  # Search radius for correlating events
CORRELATION_TIME_WINDOW_HOURS = 12  # Time window for correlation analysis


def find_nearby_events(db: Session, lat: float, lon: float, exclude_id: int, 
                       exclude_type: str = None, hours: int = CORRELATION_TIME_WINDOW_HOURS) -> list:
    """Find events near a location within time window, excluding a specific event"""
    cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)
    degree_radius = CORRELATION_RADIUS_KM / 111.0
    
    query = db.query(models.ProtestEvent).filter(
        models.ProtestEvent.id != exclude_id,
        models.ProtestEvent.timestamp >= cutoff_time,
        models.ProtestEvent.latitude.between(lat - degree_radius, lat + degree_radius),
        models.ProtestEvent.longitude.between(lon - degree_radius, lon + degree_radius)
    )
    
    if exclude_type:
        query = query.filter(models.ProtestEvent.event_type != exclude_type)
    
    return query.order_by(models.ProtestEvent.timestamp.desc()).all()


def calculate_time_delta_minutes(event1_time: datetime, event2_time: datetime) -> int:
    """Calculate time difference in minutes (positive = event2 is after event1)"""
    if not event1_time or not event2_time:
        return 0
    delta = (event2_time - event1_time).total_seconds() / 60
    return int(delta)


@app.get("/api/ppu/correlations")
def get_ppu_correlations(
    hours: int = 24,
    radius_km: float = CORRELATION_RADIUS_KM,
    db: Session = Depends(get_db)
):
    """
    Get police presence events with their correlated nearby reports/events.
    
    For each police presence, finds:
    - Nearby protests, clashes, arrests, strikes within the radius
    - Temporal relationship (did police arrive before/during/after event)
    - Time delta in minutes
    
    Returns GeoJSON with correlation data in properties.
    """
    cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)
    degree_radius = radius_km / 111.0
    
    # Get all police presence events
    ppu_events = db.query(models.ProtestEvent).filter(
        models.ProtestEvent.event_type == "police_presence",
        models.ProtestEvent.timestamp >= cutoff_time
    ).order_by(models.ProtestEvent.timestamp.desc()).all()
    
    features = []
    total_correlations = 0
    
    for ppu in ppu_events:
        # Find nearby non-police events
        nearby_events = db.query(models.ProtestEvent).filter(
            models.ProtestEvent.id != ppu.id,
            models.ProtestEvent.event_type != "police_presence",
            models.ProtestEvent.timestamp >= cutoff_time,
            models.ProtestEvent.latitude.between(ppu.latitude - degree_radius, ppu.latitude + degree_radius),
            models.ProtestEvent.longitude.between(ppu.longitude - degree_radius, ppu.longitude + degree_radius)
        ).order_by(models.ProtestEvent.timestamp.desc()).all()
        
        # Build correlation details
        correlations = []
        for event in nearby_events:
            time_delta = calculate_time_delta_minutes(event.timestamp, ppu.timestamp)
            
            # Determine temporal relationship
            if abs(time_delta) < 30:
                temporal_relation = "concurrent"
            elif time_delta > 0:
                temporal_relation = "after_event"  # Police arrived after the event
            else:
                temporal_relation = "before_event"  # Police arrived before the event
            
            correlations.append({
                "event_id": event.id,
                "event_type": event.event_type or "protest",
                "title": event.title,
                "timestamp": event.timestamp.isoformat() if event.timestamp else None,
                "time_delta_minutes": time_delta,
                "temporal_relation": temporal_relation,
                "intensity": event.intensity_score,
                "verified": event.verified
            })
        
        total_correlations += len(correlations)
        
        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [ppu.longitude, ppu.latitude]
            },
            "properties": {
                "id": ppu.id,
                "title": ppu.title,
                "description": ppu.description,
                "intensity": ppu.intensity_score,
                "verified": ppu.verified,
                "timestamp": ppu.timestamp.isoformat() if ppu.timestamp else None,
                "event_type": "police_presence",
                "source_platform": ppu.source_platform,
                "age_minutes": int((datetime.now(timezone.utc) - ppu.timestamp).total_seconds() / 60) if ppu.timestamp else None,
                # Correlation data
                "correlated_events": correlations,
                "correlation_count": len(correlations),
                "has_nearby_protests": any(c["event_type"] == "protest" for c in correlations),
                "has_nearby_clashes": any(c["event_type"] == "clash" for c in correlations),
                "has_nearby_arrests": any(c["event_type"] == "arrest" for c in correlations)
            }
        })
    
    return {
        "type": "FeatureCollection",
        "features": features,
        "ppu_count": len(features),
        "total_correlations": total_correlations,
        "avg_correlations_per_ppu": round(total_correlations / len(features), 2) if features else 0,
        "search_radius_km": radius_km,
        "hours_window": hours
    }


@app.get("/api/events/{event_id}/nearby-ppu")
def get_nearby_ppu_for_event(
    event_id: int,
    hours: int = 12,
    radius_km: float = CORRELATION_RADIUS_KM,
    db: Session = Depends(get_db)
):
    """
    Get police presence reports near a specific event.
    
    Shows:
    - All PPU reports within radius of the event
    - When they appeared relative to the event
    - If any were verified by crowd consensus
    """
    # Get the target event
    event = db.query(models.ProtestEvent).filter(
        models.ProtestEvent.id == event_id
    ).first()
    
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    
    # Time window around the event
    time_before = event.timestamp - timedelta(hours=hours) if event.timestamp else datetime.now(timezone.utc) - timedelta(hours=hours*2)
    time_after = event.timestamp + timedelta(hours=hours) if event.timestamp else datetime.now(timezone.utc)
    
    degree_radius = radius_km / 111.0
    
    # Find nearby PPU reports
    ppu_events = db.query(models.ProtestEvent).filter(
        models.ProtestEvent.event_type == "police_presence",
        models.ProtestEvent.id != event_id,
        models.ProtestEvent.timestamp >= time_before,
        models.ProtestEvent.timestamp <= time_after,
        models.ProtestEvent.latitude.between(event.latitude - degree_radius, event.latitude + degree_radius),
        models.ProtestEvent.longitude.between(event.longitude - degree_radius, event.longitude + degree_radius)
    ).order_by(models.ProtestEvent.timestamp).all()
    
    # Categorize by timing
    ppu_before = []
    ppu_during = []
    ppu_after = []
    
    for ppu in ppu_events:
        time_delta = calculate_time_delta_minutes(event.timestamp, ppu.timestamp)
        
        ppu_data = {
            "id": ppu.id,
            "title": ppu.title,
            "timestamp": ppu.timestamp.isoformat() if ppu.timestamp else None,
            "intensity": ppu.intensity_score,
            "verified": ppu.verified,
            "time_delta_minutes": time_delta,
            "source_platform": ppu.source_platform
        }
        
        if abs(time_delta) < 30:
            ppu_during.append(ppu_data)
        elif time_delta > 0:
            ppu_after.append(ppu_data)
        else:
            ppu_before.append(ppu_data)
    
    return {
        "event": {
            "id": event.id,
            "title": event.title,
            "event_type": event.event_type,
            "timestamp": event.timestamp.isoformat() if event.timestamp else None,
            "latitude": event.latitude,
            "longitude": event.longitude,
            "verified": event.verified
        },
        "nearby_ppu": {
            "total": len(ppu_events),
            "verified_count": sum(1 for p in ppu_events if p.verified),
            "before_event": ppu_before,
            "during_event": ppu_during,
            "after_event": ppu_after
        },
        "analysis": {
            "police_response_detected": len(ppu_events) > 0,
            "earliest_ppu_minutes": min((p["time_delta_minutes"] for p in ppu_before), default=None) if ppu_before else None,
            "response_pattern": "preemptive" if ppu_before and not ppu_after else "reactive" if ppu_after and not ppu_before else "concurrent" if ppu_during else "none"
        },
        "search_radius_km": radius_km,
        "hours_window": hours
    }


@app.get("/api/ppu/analysis")
def get_ppu_analysis(
    hours: int = 48,
    db: Session = Depends(get_db)
):
    """
    Get aggregate analysis of police presence patterns.
    
    Returns:
    - Overall PPU statistics
    - Correlation patterns with event types
    - Response time analysis
    - Hotspot areas
    """
    cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)
    degree_radius = CORRELATION_RADIUS_KM / 111.0
    
    # Get all events in window
    all_events = db.query(models.ProtestEvent).filter(
        models.ProtestEvent.timestamp >= cutoff_time
    ).all()
    
    ppu_events = [e for e in all_events if e.event_type == "police_presence"]
    other_events = [e for e in all_events if e.event_type != "police_presence"]
    
    # Analyze correlations
    events_with_ppu = 0
    events_without_ppu = 0
    response_times = []
    event_type_correlations = {"protest": 0, "clash": 0, "arrest": 0, "strike": 0}
    
    for event in other_events:
        # Find nearby PPU for this event
        nearby_ppu = [
            ppu for ppu in ppu_events
            if abs(ppu.latitude - event.latitude) <= degree_radius
            and abs(ppu.longitude - event.longitude) <= degree_radius
        ]
        
        if nearby_ppu:
            events_with_ppu += 1
            event_type = event.event_type or "protest"
            if event_type in event_type_correlations:
                event_type_correlations[event_type] += 1
            
            # Calculate response times (PPU after event)
            for ppu in nearby_ppu:
                time_delta = calculate_time_delta_minutes(event.timestamp, ppu.timestamp)
                if time_delta > 0:  # PPU arrived after event
                    response_times.append(time_delta)
        else:
            events_without_ppu += 1
    
    # Calculate average response time
    avg_response_time = round(sum(response_times) / len(response_times), 1) if response_times else None
    
    # Find hotspots (areas with most PPU activity)
    # Simple grid-based aggregation
    ppu_grid = {}
    for ppu in ppu_events:
        # Round to ~10km grid
        grid_key = (round(ppu.latitude, 1), round(ppu.longitude, 1))
        if grid_key not in ppu_grid:
            ppu_grid[grid_key] = {"count": 0, "lat": ppu.latitude, "lon": ppu.longitude, "verified": 0}
        ppu_grid[grid_key]["count"] += 1
        if ppu.verified:
            ppu_grid[grid_key]["verified"] += 1
    
    # Sort hotspots by count
    hotspots = sorted(ppu_grid.values(), key=lambda x: x["count"], reverse=True)[:10]
    
    return {
        "period": {
            "hours": hours,
            "start": cutoff_time.isoformat(),
            "end": datetime.now(timezone.utc).isoformat()
        },
        "summary": {
            "total_ppu_reports": len(ppu_events),
            "verified_ppu_reports": sum(1 for p in ppu_events if p.verified),
            "total_other_events": len(other_events),
            "events_with_nearby_ppu": events_with_ppu,
            "events_without_ppu": events_without_ppu,
            "ppu_coverage_rate": round(events_with_ppu / len(other_events) * 100, 1) if other_events else 0
        },
        "event_type_correlations": event_type_correlations,
        "response_analysis": {
            "avg_response_time_minutes": avg_response_time,
            "min_response_time": min(response_times) if response_times else None,
            "max_response_time": max(response_times) if response_times else None,
            "responses_under_30min": sum(1 for t in response_times if t < 30),
            "responses_under_60min": sum(1 for t in response_times if t < 60)
        },
        "hotspots": hotspots,
        "correlation_radius_km": CORRELATION_RADIUS_KM
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


# ============================================================================
# DATA SOURCE MANAGEMENT ENDPOINTS
# ============================================================================

@app.get("/api/admin/sources")
def list_data_sources(
    source_type: str = None,
    is_active: Optional[bool] = None,
    active_only: bool = False,  # Deprecated
    admin_key: str = None,
    db: Session = Depends(get_db)
):
    """
    List all configured data sources.
    If admin_key is provided, returns full details; otherwise returns summary only.
    """
    try:
        query = db.query(models.DataSource)
        
        if source_type:
            query = query.filter(models.DataSource.source_type == source_type)
        
        if is_active is not None:
            query = query.filter(models.DataSource.is_active == is_active)
        elif active_only:
            query = query.filter(models.DataSource.is_active == True)
        
        sources = query.order_by(models.DataSource.is_active.asc(), models.DataSource.priority).all()
        
        # Count by type
        by_type = {}
        for source in sources:
            by_type[source.source_type] = by_type.get(source.source_type, 0) + 1
        
        # If not admin, return limited info
        is_admin = admin_key == ADMIN_KEY
        
        source_list = []
        for s in sources:
            source_data = {
                "id": s.id,
                "source_type": s.source_type,
                "identifier": s.identifier,
                "name": s.name,
                "category": s.category,
                "priority": s.priority,
                "reliability_score": s.reliability_score,
                "is_active": s.is_active,
            }
            if is_admin:
                source_data.update({
                    "url": s.url,
                    "last_fetch_at": s.last_fetch_at.isoformat() if s.last_fetch_at else None,
                    "last_fetch_status": s.last_fetch_status,
                    "error_count": s.error_count,
                    "notes": s.notes,
                    "created_at": s.created_at.isoformat() if s.created_at else None,
                })
            source_list.append(source_data)
        
        return {
            "sources": source_list,
            "total_count": len(sources),
            "by_type": by_type
        }
    except Exception as e:
        return {
            "sources": [],
            "total_count": 0,
            "by_type": {},
            "error": str(e)
        }


@app.post("/api/sources/suggest")
def suggest_data_source(
    suggestion: schemas.DataSourceSuggest,
    db: Session = Depends(get_db)
):
    """Public endpoint to suggest a new data source"""
    # Check for duplicate
    existing = db.query(models.DataSource).filter(
        models.DataSource.source_type == suggestion.source_type,
        models.DataSource.identifier == suggestion.identifier
    ).first()
    
    if existing:
        if existing.is_active:
            raise HTTPException(status_code=400, detail="Source already exists and is active")
        else:
            raise HTTPException(status_code=400, detail="Source has already been suggested")
            
    # Create inactive source
    db_source = models.DataSource(
        source_type=suggestion.source_type,
        identifier=suggestion.identifier,
        name=suggestion.name or suggestion.identifier,
        url=suggestion.url,
        notes=f"[Public Suggestion] {suggestion.notes or ''}",
        is_active=False,
        priority=3, # Low priority by default
        reliability_score=0.5 # Default reliability
    )
    
    db.add(db_source)
    db.commit()
    
    return {"status": "success", "message": "Source suggested successfully. It will be reviewed by admins."}


@app.post("/api/admin/sources")
def create_data_source(
    source: schemas.DataSourceCreate,
    db: Session = Depends(get_db)
):
    """Create a new data source (admin only)."""
    if source.admin_key != ADMIN_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin key"
        )
    
    # Check for duplicate
    existing = db.query(models.DataSource).filter(
        models.DataSource.source_type == source.source_type,
        models.DataSource.identifier == source.identifier
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Source already exists: {source.source_type}/{source.identifier}"
        )
    
    db_source = models.DataSource(
        source_type=source.source_type,
        identifier=source.identifier,
        name=source.name or source.identifier,
        url=source.url,
        reliability_score=source.reliability_score,
        priority=source.priority,
        category=source.category,
        notes=source.notes,
        is_active=True
    )
    
    db.add(db_source)
    db.commit()
    db.refresh(db_source)
    
    return {
        "status": "success",
        "message": f"Source created: {source.source_type}/{source.identifier}",
        "source_id": db_source.id
    }


@app.put("/api/admin/sources/{source_id}")
def update_data_source(
    source_id: int,
    update: schemas.DataSourceUpdate,
    db: Session = Depends(get_db)
):
    """Update a data source (admin only)."""
    if update.admin_key != ADMIN_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin key"
        )
    
    source = db.query(models.DataSource).filter(models.DataSource.id == source_id).first()
    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Source not found"
        )
    
    # Update fields if provided
    if update.name is not None:
        source.name = update.name
    if update.url is not None:
        source.url = update.url
    if update.reliability_score is not None:
        source.reliability_score = update.reliability_score
    if update.priority is not None:
        source.priority = update.priority
    if update.category is not None:
        source.category = update.category
    if update.is_active is not None:
        source.is_active = update.is_active
    if update.notes is not None:
        source.notes = update.notes
    
    db.commit()
    
    return {
        "status": "success",
        "message": f"Source updated: {source.source_type}/{source.identifier}",
        "source_id": source_id
    }


@app.delete("/api/admin/sources/{source_id}")
def delete_data_source(
    source_id: int,
    admin_key: str,
    db: Session = Depends(get_db)
):
    """Delete a data source (admin only)."""
    if admin_key != ADMIN_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin key"
        )
    
    source = db.query(models.DataSource).filter(models.DataSource.id == source_id).first()
    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Source not found"
        )
    
    source_info = f"{source.source_type}/{source.identifier}"
    db.delete(source)
    db.commit()
    
    return {
        "status": "success",
        "message": f"Source deleted: {source_info}"
    }


@app.post("/api/admin/sources/{source_id}/toggle")
def toggle_data_source(
    source_id: int,
    admin_key: str,
    db: Session = Depends(get_db)
):
    """Toggle a data source active/inactive (admin only)."""
    if admin_key != ADMIN_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin key"
        )
    
    source = db.query(models.DataSource).filter(models.DataSource.id == source_id).first()
    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Source not found"
        )
    
    source.is_active = not source.is_active
    db.commit()
    
    return {
        "status": "success",
        "message": f"Source {'activated' if source.is_active else 'deactivated'}: {source.source_type}/{source.identifier}",
        "is_active": source.is_active
    }


@app.post("/api/admin/sources/import-defaults")
def import_default_sources(
    admin_key: str,
    db: Session = Depends(get_db)
):
    """Import default sources from ingestion.py configuration (admin only)."""
    if admin_key != ADMIN_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin key"
        )
    
    from .services.ingestion import (
        TELEGRAM_CHANNELS, RSS_FEEDS, TWITTER_ACCOUNTS, 
        YOUTUBE_CHANNELS, REDDIT_SUBREDDITS
    )
    
    imported = 0
    skipped = 0
    
    # Import Telegram channels
    for channel in TELEGRAM_CHANNELS:
        existing = db.query(models.DataSource).filter(
            models.DataSource.source_type == "telegram",
            models.DataSource.identifier == channel
        ).first()
        if not existing:
            db.add(models.DataSource(
                source_type="telegram",
                identifier=channel,
                name=channel,
                priority=2,
                category="news",
                is_active=True
            ))
            imported += 1
        else:
            skipped += 1
    
    # Import RSS feeds
    for feed_id, feed_config in RSS_FEEDS.items():
        existing = db.query(models.DataSource).filter(
            models.DataSource.source_type == "rss",
            models.DataSource.identifier == feed_id
        ).first()
        if not existing:
            db.add(models.DataSource(
                source_type="rss",
                identifier=feed_id,
                name=feed_config.get("name", feed_id),
                url=feed_config.get("url"),
                reliability_score=feed_config.get("reliability", 0.7),
                category=feed_config.get("source_category", "news"),
                is_active=True
            ))
            imported += 1
        else:
            skipped += 1
    
    # Import Twitter accounts
    for account in TWITTER_ACCOUNTS:
        existing = db.query(models.DataSource).filter(
            models.DataSource.source_type == "twitter",
            models.DataSource.identifier == account
        ).first()
        if not existing:
            db.add(models.DataSource(
                source_type="twitter",
                identifier=account,
                name=f"@{account}",
                priority=2,
                category="news",
                is_active=True
            ))
            imported += 1
        else:
            skipped += 1
    
    # Import YouTube channels
    for channel_id, channel_config in YOUTUBE_CHANNELS.items():
        existing = db.query(models.DataSource).filter(
            models.DataSource.source_type == "youtube",
            models.DataSource.identifier == channel_id
        ).first()
        if not existing:
            db.add(models.DataSource(
                source_type="youtube",
                identifier=channel_id,
                name=channel_config.get("name", channel_id),
                url=channel_config.get("channel_id"),  # Store YT channel ID in url
                reliability_score=channel_config.get("reliability", 0.7),
                category="news",
                is_active=True
            ))
            imported += 1
        else:
            skipped += 1
    
    # Import Reddit subreddits
    for subreddit in REDDIT_SUBREDDITS:
        existing = db.query(models.DataSource).filter(
            models.DataSource.source_type == "reddit",
            models.DataSource.identifier == subreddit
        ).first()
        if not existing:
            db.add(models.DataSource(
                source_type="reddit",
                identifier=subreddit,
                name=f"r/{subreddit}",
                priority=3,
                category="news",
                is_active=True
            ))
            imported += 1
        else:
            skipped += 1
    
    db.commit()
    
    return {
        "status": "success",
        "message": f"Imported {imported} sources, skipped {skipped} duplicates",
        "imported": imported,
        "skipped": skipped
    }


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
    try:
        service = TelegramFeedService(db)
        count = service.fetch_and_process_all()
        
        return {
            "status": "success",
            "message": f"Fetched {count} new messages",
            "new_messages": count
        }
    except Exception as e:
        print(f"⚠ Telegram refresh error: {e}")
        return {
            "status": "error",
            "message": f"Failed to refresh: {str(e)}",
            "new_messages": 0
        }


@app.get("/api/telegram/channels")
def get_telegram_channels(db: Session = Depends(get_db)):
    """Get list of monitored Telegram channels"""
    from .services.telegram_feed import PRIORITY_CHANNELS
    
    try:
        service = TelegramFeedService(db)
        active_channels = service.get_channels()
    except Exception as e:
        print(f"⚠ Channels error: {e}")
        active_channels = []
    
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
# TWITTER FEED ENDPOINTS
# ============================================================================

@app.get("/api/twitter/feed")
def get_twitter_feed(
    limit: int = 50,
    min_urgency: float = 0.0,
    relevant_only: bool = True,
    hours: int = 24,
    db: Session = Depends(get_db)
):
    """
    Get Twitter/X feed with NLP analysis.
    
    - **limit**: Maximum tweets to return (default: 50)
    - **min_urgency**: Minimum urgency score 0-1 (default: 0)
    - **relevant_only**: Only return protest-relevant tweets (default: true)
    - **hours**: Limit to tweets from last N hours (default: 24)
    """
    try:
        from .services.twitter_feed import TwitterFeedService
        service = TwitterFeedService(db)
        messages, total = service.get_feed(
            limit=limit,
            min_urgency=min_urgency,
            relevant_only=relevant_only,
            hours=hours
        )
        
        formatted = []
        for msg in messages:
            formatted.append({
                "id": msg.id,
                "source": "twitter",
                "username": msg.username,
                "tweet_id": msg.tweet_id,
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
                "metrics": {
                    "retweets": msg.retweet_count,
                    "likes": msg.like_count,
                    "replies": msg.reply_count,
                }
            })
        
        return {
            "status": "success",
            "messages": formatted,
            "total_count": total,
        }
    except Exception as e:
        print(f"⚠ Twitter feed error: {e}")
        return {
            "status": "success",
            "messages": [],
            "total_count": 0,
            "warning": str(e)
        }


@app.post("/api/twitter/refresh")
def refresh_twitter_feed(
    admin_key: str = None,
    db: Session = Depends(get_db)
):
    """Manually trigger Twitter feed refresh."""
    try:
        from .services.twitter_feed import TwitterFeedService
        service = TwitterFeedService(db)
        count = service.fetch_and_process_all()
        
        return {
            "status": "success",
            "message": f"Fetched {count} new tweets",
            "new_tweets": count
        }
    except Exception as e:
        print(f"⚠ Twitter refresh error: {e}")
        return {
            "status": "error",
            "message": str(e),
            "new_tweets": 0
        }


@app.get("/api/twitter/status")
def get_twitter_status(db: Session = Depends(get_db)):
    """Check Twitter feed status and configuration."""
    import os
    
    bearer_token = os.getenv("TWITTER_BEARER_TOKEN", "")
    has_token = bool(bearer_token and len(bearer_token) > 10)
    
    # Check if table exists and has data
    try:
        count = db.query(models.TwitterMessage).count()
        table_exists = True
    except Exception as e:
        count = 0
        table_exists = False
        print(f"Twitter table check error: {e}")
    
    return {
        "configured": has_token,
        "token_set": has_token,
        "token_preview": f"{bearer_token[:10]}..." if has_token else None,
        "table_exists": table_exists,
        "message_count": count,
        "help": "Call POST /api/twitter/refresh to fetch tweets" if has_token else "Set TWITTER_BEARER_TOKEN in .env"
    }


# ============================================================================
# UNIFIED FEED ENDPOINT (Telegram + Twitter combined)
# ============================================================================

@app.get("/api/feed")
def get_unified_feed(
    limit: int = 50,
    min_urgency: float = 0.0,
    relevant_only: bool = True,
    hours: int = 24,
    sources: str = "all",  # 'all', 'telegram', 'twitter', 'rss'
    db: Session = Depends(get_db)
):
    """
    Get unified feed from all sources (Telegram + Twitter + RSS).
    
    - **limit**: Maximum messages to return (default: 50)
    - **min_urgency**: Minimum urgency score 0-1 (default: 0)
    - **relevant_only**: Only return protest-relevant messages (default: true)
    - **hours**: Limit to messages from last N hours (default: 24)
    - **sources**: Filter by source: 'all', 'telegram', 'twitter', 'rss'
    """
    all_messages = []
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    
    # Fetch Telegram messages
    if sources in ("all", "telegram"):
        try:
            service = TelegramFeedService(db)
            tg_messages, _ = service.get_feed(
                limit=limit,
                min_urgency=min_urgency,
                relevant_only=relevant_only,
                hours=hours
            )
            
            for msg in tg_messages:
                all_messages.append({
                    "id": f"tg_{msg.id}",
                    "source": "telegram",
                    "channel": msg.channel,
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
                    "source_url": f"https://t.me/{msg.channel}/{msg.message_id}" if msg.message_id else None,
                })
        except Exception as e:
            print(f"⚠ Telegram in unified feed: {e}")
    
    # Fetch RSS events from ProtestEvent table
    if sources in ("all", "rss"):
        try:
            rss_events = db.query(models.ProtestEvent).filter(
                models.ProtestEvent.source_platform == "rss",
                models.ProtestEvent.timestamp >= cutoff
            ).order_by(
                models.ProtestEvent.timestamp.desc()
            ).limit(limit).all()
            
            for event in rss_events:
                all_messages.append({
                    "id": f"rss_{event.id}",
                    "source": "rss",
                    "channel": event.source_url.split('/')[2] if event.source_url and '/' in event.source_url else "RSS",
                    "text": f"{event.title}\n\n{event.description or ''}".strip(),
                    "text_translated": None,
                    "media_url": event.media_url,
                    "timestamp": event.timestamp.isoformat() if event.timestamp else None,
                    "sentiment": None,
                    "keywords": None,
                    "locations_mentioned": None,
                    "event_type_detected": event.event_type,
                    "urgency_score": event.intensity_score or 0.5,
                    "is_relevant": True,
                    "source_url": event.source_url,
                })
        except Exception as e:
            print(f"⚠ RSS in unified feed: {e}")
    
    # Fetch Twitter messages
    if sources in ("all", "twitter"):
        try:
            from .services.twitter_feed import TwitterFeedService
            service = TwitterFeedService(db)
            tw_messages, _ = service.get_feed(
                limit=limit,
                min_urgency=min_urgency,
                relevant_only=relevant_only,
                hours=hours
            )
            
            for msg in tw_messages:
                all_messages.append({
                    "id": f"tw_{msg.id}",
                    "source": "twitter",
                    "channel": f"@{msg.username}",
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
                    "source_url": f"https://twitter.com/{msg.username}/status/{msg.tweet_id}",
                })
        except Exception as e:
            print(f"⚠ Twitter in unified feed: {e}")
    
    # Sort by timestamp (newest first)
    all_messages.sort(
        key=lambda x: x.get("timestamp") or "1970-01-01",
        reverse=True
    )
    
    # Limit results
    all_messages = all_messages[:limit]
    
    return {
        "status": "success",
        "messages": all_messages,
        "total_count": len(all_messages),
        "sources": sources
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
    try:
        service = CityAnalyticsService(db)
        summary = service.get_analytics_summary()
        
        return {
            "status": "success",
            "summary": summary
        }
    except Exception as e:
        print(f"⚠ Analytics summary error: {e}")
        # Return empty summary on error
        return {
            "status": "success",
            "summary": {
                "total_cities": 0,
                "total_events": 0,
                "events_24h": 0,
                "events_7d": 0,
                "most_active_city": None,
                "most_active_hour": None,
                "top_cities": [],
                "hourly_distribution": {h: 0 for h in range(24)},
                "event_type_distribution": {},
            },
            "warning": "Analytics temporarily unavailable"
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
    try:
        service = CityAnalyticsService(db)
        cities = service.get_city_ranking(limit=limit)
        
        return {
            "status": "success",
            "count": len(cities),
            "cities": cities
        }
    except Exception as e:
        print(f"⚠ Cities analytics error: {e}")
        return {
            "status": "success",
            "count": 0,
            "cities": [],
            "warning": "Analytics temporarily unavailable"
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
    try:
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
    except Exception as e:
        print(f"⚠ Hourly analytics error: {e}")
        return {
            "status": "success",
            "days_analyzed": days,
            "total_events": 0,
            "peak_hour": None,
            "peak_count": 0,
            "hourly": {h: 0 for h in range(24)}
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
    try:
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
    except Exception as e:
        print(f"⚠ Trends analytics error: {e}")
        return {
            "status": "success",
            "summary": {
                "trending_up": 0,
                "trending_down": 0,
                "stable": 0,
            },
            "top_trending": [],
            "declining": [],
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
    try:
        service = CityAnalyticsService(db)
        count = service.update_city_statistics()
        
        return {
            "status": "success",
            "message": f"Updated analytics for {count} cities",
            "cities_updated": count
        }
    except Exception as e:
        print(f"⚠ Analytics refresh error: {e}")
        return {
            "status": "error",
            "message": f"Failed to refresh analytics: {str(e)}",
            "cities_updated": 0
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
    
    Note: Requires ACLED_EMAIL and ACLED_PASSWORD environment variables.
    Uses OAuth token authentication per: https://acleddata.com/api-documentation/getting-started
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
    """Check if ACLED API is configured (OAuth authentication)"""
    email = os.getenv("ACLED_EMAIL")
    password = os.getenv("ACLED_PASSWORD")
    
    return {
        "configured": bool(email and password),
        "has_email": bool(email),
        "has_password": bool(password),
        "auth_method": "OAuth token-based",
        "registration_url": "https://acleddata.com/register/",
        "api_docs": "https://acleddata.com/api-documentation/getting-started"
    }

