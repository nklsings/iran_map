"""
ACLED (Armed Conflict Location & Event Data) Integration

ACLED is an academic project that collects and codes information on political violence
and protest events worldwide. This service fetches data specific to Iran.

API Documentation: https://acleddata.com/resources/quick-guide-to-acled-data/
"""

import os
import requests
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional
from sqlalchemy.orm import Session
from geoalchemy2.elements import WKTElement

from .. import models, schemas


# ACLED event types mapped to our system
ACLED_EVENT_TYPE_MAP = {
    "Protests": "protest",
    "Riots": "clash",
    "Violence against civilians": "clash",
    "Battles": "clash",
    "Explosions/Remote violence": "clash",
    "Strategic developments": "protest",
}

# ACLED sub-event types for more granular mapping
ACLED_SUB_EVENT_MAP = {
    "Peaceful protest": "protest",
    "Protest with intervention": "clash",
    "Excessive force against protesters": "clash",
    "Violent demonstration": "clash",
    "Mob violence": "clash",
    "Armed clash": "clash",
    "Arrests": "arrest",
    "Abduction/forced disappearance": "arrest",
    "Attack": "clash",
    "Shelling/artillery/missile attack": "clash",
    "Air/drone strike": "clash",
    "Looting/property destruction": "clash",
}


class ACLEDService:
    """
    Service to fetch and process ACLED conflict data for Iran.
    
    Requires ACLED_API_KEY and ACLED_EMAIL environment variables.
    Register for free at: https://acleddata.com/register/
    """
    
    BASE_URL = "https://api.acleddata.com/acled/read"
    COUNTRY = "Iran"
    
    def __init__(self, db: Session):
        self.db = db
        self.api_key = os.getenv("ACLED_API_KEY")
        self.email = os.getenv("ACLED_EMAIL")
        
        if not self.api_key or not self.email:
            print("⚠ ACLED credentials not set (ACLED_API_KEY, ACLED_EMAIL)")
    
    def _is_configured(self) -> bool:
        """Check if ACLED API is configured"""
        return bool(self.api_key and self.email)
    
    def fetch_recent_events(self, days: int = 30) -> List[Dict]:
        """
        Fetch recent events from ACLED for Iran.
        
        Args:
            days: Number of days to look back
            
        Returns:
            List of event dictionaries
        """
        if not self._is_configured():
            print("  ACLED: API not configured, using sample data")
            return self._get_sample_data()
        
        try:
            # Calculate date range
            end_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            start_date = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
            
            params = {
                "key": self.api_key,
                "email": self.email,
                "country": self.COUNTRY,
                "event_date": f"{start_date}|{end_date}",
                "event_date_where": "BETWEEN",
                "limit": 500,  # Max events to fetch
            }
            
            response = requests.get(self.BASE_URL, params=params, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                if data.get("success"):
                    events = data.get("data", [])
                    print(f"  ACLED: Fetched {len(events)} events")
                    return events
                else:
                    print(f"  ACLED: API error - {data.get('error', 'Unknown')}")
                    return []
            else:
                print(f"  ACLED: HTTP {response.status_code}")
                return []
                
        except Exception as e:
            print(f"  ACLED: Fetch error - {e}")
            return []
    
    def _get_sample_data(self) -> List[Dict]:
        """Return sample ACLED-style data for testing when API not configured"""
        now = datetime.now(timezone.utc)
        
        return [
            {
                "event_id_cnty": "IRN123456",
                "event_date": now.strftime("%Y-%m-%d"),
                "event_type": "Protests",
                "sub_event_type": "Peaceful protest",
                "actor1": "Protesters (Iran)",
                "actor2": "",
                "country": "Iran",
                "admin1": "Tehran",
                "admin2": "Tehran",
                "location": "Tehran",
                "latitude": "35.6892",
                "longitude": "51.3890",
                "notes": "[SAMPLE] Protest reported in Tehran area. ACLED API not configured.",
                "fatalities": "0",
                "source": "Sample Data",
            },
            {
                "event_id_cnty": "IRN123457",
                "event_date": now.strftime("%Y-%m-%d"),
                "event_type": "Protests",
                "sub_event_type": "Protest with intervention",
                "actor1": "Protesters (Iran)",
                "actor2": "Police Forces of Iran",
                "country": "Iran",
                "admin1": "Isfahan",
                "admin2": "Isfahan",
                "location": "Isfahan",
                "latitude": "32.6546",
                "longitude": "51.6680",
                "notes": "[SAMPLE] Protest with security response in Isfahan. Configure ACLED_API_KEY for real data.",
                "fatalities": "0",
                "source": "Sample Data",
            },
        ]
    
    def _map_event_type(self, event: Dict) -> str:
        """Map ACLED event type to our event type"""
        sub_event = event.get("sub_event_type", "")
        event_type = event.get("event_type", "")
        
        # Check sub-event first (more specific)
        if sub_event in ACLED_SUB_EVENT_MAP:
            return ACLED_SUB_EVENT_MAP[sub_event]
        
        # Fall back to main event type
        if event_type in ACLED_EVENT_TYPE_MAP:
            return ACLED_EVENT_TYPE_MAP[event_type]
        
        return "protest"
    
    def _calculate_intensity(self, event: Dict) -> float:
        """Calculate intensity score from ACLED event"""
        fatalities = int(event.get("fatalities", 0) or 0)
        event_type = event.get("event_type", "")
        sub_event = event.get("sub_event_type", "")
        
        # Base intensity
        intensity = 0.4
        
        # Increase for fatalities
        if fatalities > 0:
            intensity = min(0.9 + (fatalities * 0.02), 1.0)
        
        # Increase for violent events
        violent_types = ["Riots", "Battles", "Violence against civilians"]
        if event_type in violent_types:
            intensity = max(intensity, 0.7)
        
        violent_sub = ["Violent demonstration", "Armed clash", "Excessive force"]
        if any(v in sub_event for v in violent_sub):
            intensity = max(intensity, 0.8)
        
        return min(intensity, 1.0)
    
    def process_and_store(self, events: List[Dict]) -> int:
        """
        Process ACLED events and store them in the database.
        
        Args:
            events: List of ACLED event dictionaries
            
        Returns:
            Number of new events stored
        """
        count = 0
        
        for event in events:
            try:
                # Check for duplicate by ACLED event ID
                acled_id = event.get("event_id_cnty", "")
                if acled_id:
                    existing = self.db.query(models.ProtestEvent).filter(
                        models.ProtestEvent.title.like(f"%[ACLED:{acled_id}]%")
                    ).first()
                    if existing:
                        continue
                
                # Extract coordinates
                lat = float(event.get("latitude", 0))
                lon = float(event.get("longitude", 0))
                
                if lat == 0 or lon == 0:
                    continue
                
                # Map event type
                event_type = self._map_event_type(event)
                intensity = self._calculate_intensity(event)
                
                # Parse date
                date_str = event.get("event_date", "")
                try:
                    timestamp = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                except:
                    timestamp = datetime.now(timezone.utc)
                
                # Build title and description
                location = event.get("location", "Unknown")
                admin1 = event.get("admin1", "")
                actor1 = event.get("actor1", "")
                actor2 = event.get("actor2", "")
                notes = event.get("notes", "")
                fatalities = int(event.get("fatalities", 0) or 0)
                
                title = f"[ACLED:{acled_id}] {event.get('event_type', 'Event')} in {location}"
                if admin1 and admin1 != location:
                    title += f", {admin1}"
                
                description = notes[:500] if notes else ""
                if fatalities > 0:
                    description = f"⚠️ {fatalities} fatalities reported. " + description
                if actor2:
                    description = f"Involving: {actor1} vs {actor2}. " + description
                
                # Create event
                db_event = models.ProtestEvent(
                    title=title[:200],
                    description=description[:500],
                    latitude=lat,
                    longitude=lon,
                    location=WKTElement(f'POINT({lon} {lat})', srid=4326),
                    intensity_score=intensity,
                    verified=True,  # ACLED data is academically verified
                    timestamp=timestamp,
                    event_type=event_type,
                    source_platform="acled",
                    source_url=f"https://acleddata.com/data-export-tool/"
                )
                
                self.db.add(db_event)
                count += 1
                
            except Exception as e:
                print(f"  ACLED: Error processing event - {e}")
                continue
        
        if count > 0:
            self.db.commit()
            print(f"  ACLED: Stored {count} new events")
        
        return count
    
    def fetch_and_store(self, days: int = 30) -> int:
        """Convenience method to fetch and store in one call"""
        events = self.fetch_recent_events(days=days)
        return self.process_and_store(events)


def fetch_acled_data(db: Session, days: int = 30) -> int:
    """Convenience function for use in ingestion"""
    service = ACLEDService(db)
    return service.fetch_and_store(days=days)

