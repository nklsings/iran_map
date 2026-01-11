from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import text
from . import models, schemas, database
from .services.ingestion import IngestionService
from typing import List, Dict, Any
from datetime import datetime, timedelta, timezone
import os

app = FastAPI(title="Iran Protest Heatmap API")

# CORS
origins = [
    "http://localhost:3000",
    "https://iran-protest-heatmap.vercel.app", # Example
    "*" # Allow all for now
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

# Create tables on startup (for local/simple deployments)
# In production, use Alembic migrations
@app.on_event("startup")
async def startup_event():
    import time
    max_retries = 5
    retry_delay = 2
    
    for attempt in range(max_retries):
        try:
            # Test connection first
            with database.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            
            # Create tables
            models.Base.metadata.create_all(bind=database.engine)
            print(f"✓ Database tables created/verified successfully (attempt {attempt + 1})")
            return
        except Exception as e:
            if attempt < max_retries - 1:
                print(f"⚠ Database connection failed (attempt {attempt + 1}/{max_retries}): {e}")
                print(f"   Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
            else:
                print(f"✗ Could not create tables after {max_retries} attempts: {e}")
                print("   Tables will be created on first database access")
                # Don't raise - allow service to start even if DB init fails

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
    db: Session = Depends(get_db)
):
    # Calculate cutoff time
    cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)
    
    query = db.query(models.ProtestEvent).filter(
        models.ProtestEvent.timestamp >= cutoff_time
    )
    
    if verified_only:
        query = query.filter(models.ProtestEvent.verified == True)
    
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
                "media_type": event.media_type
            }
        })
        
    return {
        "type": "FeatureCollection",
        "features": features
    }

@app.get("/api/stats")
def get_stats(hours: int = 12, db: Session = Depends(get_db)):
    # Calculate cutoff time (same as events endpoint)
    cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)
    
    total_events = db.query(models.ProtestEvent).filter(
        models.ProtestEvent.timestamp >= cutoff_time
    ).count()
    
    verified_events = db.query(models.ProtestEvent).filter(
        models.ProtestEvent.timestamp >= cutoff_time,
        models.ProtestEvent.verified == True
    ).count()
    
    return {
        "total_reports": total_events,
        "verified_incidents": verified_events,
        "hours_window": hours
    }

@app.post("/api/ingest")
def trigger_ingestion(
    request: schemas.IngestRequest,
    db: Session = Depends(get_db)
):
    # Simple secret check (replace with proper auth in prod)
    expected_key = os.getenv("CRON_SECRET", "dev_secret")
    if request.trigger_key != expected_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid trigger key")
        
    service = IngestionService(db)
    count = service.run_ingestion()
    
    return {"status": "success", "new_events": count}


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

