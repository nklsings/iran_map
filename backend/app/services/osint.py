"""
OSINT Data Integration Service

Fetches geolocated event data from various OSINT sources:
- GeoConfirmed (geoconfirmed.org)
- ArcGIS Feature Services
- Other verification sources
"""

import requests
import json
import re
from datetime import datetime, timezone
from typing import List, Dict, Optional, Tuple
from sqlalchemy.orm import Session
from geoalchemy2.elements import WKTElement

from .. import models, schemas


class GeoConfirmedFetcher:
    """
    Fetches data from GeoConfirmed.org
    
    GeoConfirmed is an OSINT verification platform that geolocates events.
    Uses their internal Blazor API endpoint discovered via network inspection.
    """
    
    BASE_URL = "https://geoconfirmed.org"
    
    # Discovered API endpoint (Blazor WebAssembly backend)
    PLACEMARK_API = "https://geoconfirmed.org/api/placemark/Iran"
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': 'https://geoconfirmed.org/iran',
            'Origin': 'https://geoconfirmed.org',
        })
    
    def fetch_iran_data(self) -> List[Dict]:
        """Fetch GeoConfirmed Iran data from their API"""
        events = []
        
        print("  Fetching from GeoConfirmed API...")
        
        try:
            # Main placemark API
            response = self.session.get(
                f"{self.PLACEMARK_API}?search=",
                timeout=30
            )
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    events = self._parse_placemarks(data)
                    print(f"    GeoConfirmed: fetched {len(events)} placemarks")
                except json.JSONDecodeError as e:
                    print(f"    GeoConfirmed: JSON decode error: {e}")
            else:
                print(f"    GeoConfirmed: HTTP {response.status_code}")
                
        except requests.exceptions.RequestException as e:
            print(f"    GeoConfirmed: Request error: {e}")
        
        return events
    
    def _parse_placemarks(self, data: any) -> List[Dict]:
        """Parse the placemark response from GeoConfirmed API"""
        events = []
        
        # Handle different response formats
        placemarks = []
        if isinstance(data, list):
            placemarks = data
        elif isinstance(data, dict):
            if 'placemarks' in data:
                placemarks = data['placemarks']
            elif 'data' in data:
                placemarks = data['data']
            elif 'features' in data:
                placemarks = data['features']
        
        for pm in placemarks:
            try:
                event = self._parse_single_placemark(pm)
                if event:
                    events.append(event)
            except Exception as e:
                continue
        
        return events
    
    def _parse_single_placemark(self, pm: Dict) -> Optional[Dict]:
        """Parse a single placemark into an event"""
        # Try different field names for coordinates
        lat = pm.get('latitude') or pm.get('lat') or pm.get('y')
        lon = pm.get('longitude') or pm.get('lng') or pm.get('lon') or pm.get('x')
        
        # If it's a GeoJSON feature
        if 'geometry' in pm:
            geom = pm['geometry']
            if geom.get('type') == 'Point':
                coords = geom.get('coordinates', [])
                if len(coords) >= 2:
                    lon, lat = coords[0], coords[1]
        
        if not lat or not lon:
            return None
        
        # Get properties
        props = pm.get('properties', pm)
        
        title = (
            props.get('title') or 
            props.get('name') or 
            props.get('description', '')[:100] or 
            'GeoConfirmed Event'
        )
        
        description = props.get('description') or props.get('text') or ''
        
        # Get date if available
        date_str = props.get('date') or props.get('created') or props.get('timestamp')
        
        # Get event type/category
        category = props.get('category') or props.get('type') or props.get('icon')
        
        # Get source URL
        source_url = props.get('url') or props.get('source') or f"https://geoconfirmed.org/iran"
        if props.get('id'):
            source_url = f"https://geoconfirmed.org/iran#pm{props.get('id')}"
        
        return {
            'title': title,
            'description': description,
            'latitude': float(lat),
            'longitude': float(lon),
            'source': 'geoconfirmed',
            'source_url': source_url,
            'category': category,
            'date': date_str,
        }
    
    def parse_kml(self, kml_content: str) -> List[Dict]:
        """Parse KML content from GeoConfirmed export"""
        events = []
        
        try:
            # Simple KML parsing (for Placemark elements)
            placemark_pattern = r'<Placemark>(.*?)</Placemark>'
            placemarks = re.findall(placemark_pattern, kml_content, re.DOTALL)
            
            for pm in placemarks:
                # Extract name
                name_match = re.search(r'<name>(.*?)</name>', pm)
                name = name_match.group(1) if name_match else "Unknown"
                
                # Extract description
                desc_match = re.search(r'<description>(.*?)</description>', pm, re.DOTALL)
                description = desc_match.group(1) if desc_match else ""
                
                # Extract coordinates
                coord_match = re.search(r'<coordinates>(.*?)</coordinates>', pm)
                if coord_match:
                    coords = coord_match.group(1).strip().split(',')
                    if len(coords) >= 2:
                        lon = float(coords[0])
                        lat = float(coords[1])
                        
                        events.append({
                            'title': name,
                            'description': description,
                            'latitude': lat,
                            'longitude': lon,
                            'source': 'geoconfirmed',
                        })
        except Exception as e:
            print(f"  KML parse error: {e}")
        
        return events


class ArcGISFetcher:
    """
    Fetches data from ArcGIS Feature Services
    
    Uses publicly available ArcGIS services with Iran-related data.
    """
    
    # ArcGIS Feature Service for Iran
    # Source: https://services-eu1.arcgis.com/cOhMqNf3ihcdtO7J/ArcGIS/rest/services/IRAN/FeatureServer
    IRAN_SERVICE = "https://services-eu1.arcgis.com/cOhMqNf3ihcdtO7J/ArcGIS/rest/services/IRAN/FeatureServer"
    
    # Layer IDs (based on the service)
    LAYERS = {
        0: "Israeli_Operations_in_Iran",
        1: "Iran_Missile_Bases",
        2: "Power_Plants",
        3: "Naval_Bases",
        4: "Nuclear_Sites",
    }
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        })
    
    def fetch_layer(self, layer_id: int) -> List[Dict]:
        """Fetch features from a specific layer"""
        events = []
        
        try:
            url = f"{self.IRAN_SERVICE}/{layer_id}/query"
            params = {
                'where': '1=1',  # All features
                'outFields': '*',
                'returnGeometry': 'true',
                'f': 'geojson',
            }
            
            response = self.session.get(url, params=params, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                if 'features' in data:
                    for feature in data['features']:
                        geom = feature.get('geometry', {})
                        props = feature.get('properties', {})
                        
                        if geom.get('type') == 'Point':
                            coords = geom.get('coordinates', [])
                            if len(coords) >= 2:
                                events.append({
                                    'latitude': coords[1],
                                    'longitude': coords[0],
                                    'title': props.get('name', props.get('Name', f"ArcGIS Feature")),
                                    'description': props.get('description', props.get('Description', '')),
                                    'layer': self.LAYERS.get(layer_id, 'unknown'),
                                    'source': 'arcgis',
                                    'properties': props,
                                })
                                
        except Exception as e:
            print(f"    ArcGIS layer {layer_id} error: {e}")
        
        return events
    
    def fetch_all_layers(self) -> List[Dict]:
        """Fetch all available layers"""
        all_events = []
        
        print("  Fetching from ArcGIS Feature Service...")
        
        for layer_id, layer_name in self.LAYERS.items():
            events = self.fetch_layer(layer_id)
            all_events.extend(events)
            if events:
                print(f"    Layer {layer_name}: {len(events)} features")
        
        print(f"  ArcGIS total: {len(all_events)} features")
        return all_events


class OSINTService:
    """Main service for fetching and storing OSINT data"""
    
    def __init__(self, db: Session):
        self.db = db
        self.geoconfirmed = GeoConfirmedFetcher()
        self.arcgis = ArcGISFetcher()
    
    def fetch_and_store(self) -> Dict[str, int]:
        """Fetch from all OSINT sources and store in database"""
        results = {
            'geoconfirmed': 0,
            'arcgis': 0,
            'total': 0,
        }
        
        print("Fetching OSINT data...")
        
        # 1. Try GeoConfirmed
        gc_events = self.geoconfirmed.fetch_iran_data()
        for event in gc_events:
            if self._store_event(event, 'geoconfirmed'):
                results['geoconfirmed'] += 1
        
        # 2. Fetch ArcGIS data
        arcgis_events = self.arcgis.fetch_all_layers()
        for event in arcgis_events:
            if self._store_event(event, 'arcgis'):
                results['arcgis'] += 1
        
        self.db.commit()
        results['total'] = results['geoconfirmed'] + results['arcgis']
        
        print(f"OSINT fetch complete: {results['total']} events")
        return results
    
    def _store_event(self, event: Dict, source: str) -> bool:
        """Store an OSINT event in the database"""
        try:
            title = event.get('title', 'OSINT Event')
            lat = event.get('latitude')
            lon = event.get('longitude')
            
            if not lat or not lon:
                return False
            
            # Validate coordinates are in Iran region (roughly 25-40 lat, 44-64 lon)
            if not (25 <= lat <= 40 and 44 <= lon <= 64):
                return False
            
            # Create source-tagged title
            source_tag = source.upper().replace('_', ' ')
            tagged_title = f"[{source_tag}] {title[:150]}"
            
            # Check for duplicates by source-tagged title + location
            existing = self.db.query(models.ProtestEvent).filter(
                models.ProtestEvent.title == tagged_title,
                models.ProtestEvent.latitude.between(lat - 0.001, lat + 0.001),
                models.ProtestEvent.longitude.between(lon - 0.001, lon + 0.001),
            ).first()
            
            if existing:
                return False
            
            # Also check for same location without title match (avoid duplicating same spot)
            existing_loc = self.db.query(models.ProtestEvent).filter(
                models.ProtestEvent.latitude.between(lat - 0.0001, lat + 0.0001),
                models.ProtestEvent.longitude.between(lon - 0.0001, lon + 0.0001),
                models.ProtestEvent.title.like(f"[{source_tag}]%")
            ).first()
            
            if existing_loc:
                return False
            
            # Determine event type from content
            event_type = self._detect_event_type(event)
            
            # Get source URL
            source_url = event.get('source_url') or event.get('url') or f"https://geoconfirmed.org/iran"
            
            # Create the event
            db_event = models.ProtestEvent(
                title=tagged_title,
                description=event.get('description', '')[:500],
                latitude=lat,
                longitude=lon,
                location=WKTElement(f'POINT({lon} {lat})', srid=4326),
                intensity_score=0.8,  # OSINT/verified data is high-value
                verified=True,  # GeoConfirmed data is verified
                timestamp=datetime.now(timezone.utc),
                event_type=event_type,
                source_platform="multiple",
                source_url=source_url,
            )
            self.db.add(db_event)
            return True
            
        except Exception as e:
            print(f"  Error storing OSINT event: {e}")
            return False
    
    def _detect_event_type(self, event: Dict) -> str:
        """Detect event type from OSINT data"""
        title = event.get('title', '').lower()
        desc = event.get('description', '').lower()
        layer = event.get('layer', '').lower()
        category = event.get('category', '').lower() if event.get('category') else ''
        text = f"{title} {desc} {layer} {category}"
        
        # GeoConfirmed icon/category IDs (based on their internal numbering)
        # Approximate mappings based on observed patterns
        if any(kw in text for kw in ['10', '20', '30', '100', '101', '111', '112']):
            # These appear to be various military/infrastructure categories
            pass
        
        # Military/police presence
        if any(kw in text for kw in ['missile', 'military', 'naval', 'base', 'nuclear', 'operation', 'army', 'irgc', 'basij', 'police', 'checkpoint']):
            return 'police_presence'
        
        # Clashes/attacks
        if any(kw in text for kw in ['attack', 'strike', 'explosion', 'clash', 'bombing', 'airstrike', 'drone', 'rocket', 'damage', 'destroyed', 'fire', 'killed']):
            return 'clash'
        
        # Arrests
        if any(kw in text for kw in ['arrest', 'detained', 'prison', 'capture', 'execution']):
            return 'arrest'
        
        # Protests/demonstrations
        if any(kw in text for kw in ['protest', 'demonstration', 'rally', 'march', 'chant', 'crowd', 'gathering']):
            return 'protest'
        
        # Strike/work stoppage
        if any(kw in text for kw in ['strike', 'shutdown', 'closed', 'stoppage', 'boycott']):
            return 'strike'
        
        # Default to protest for Iran context
        return 'protest'
    
    def import_kml(self, kml_content: str) -> int:
        """Import events from KML file (e.g., from GeoConfirmed export)"""
        events = self.geoconfirmed.parse_kml(kml_content)
        
        count = 0
        for event in events:
            if self._store_event(event, 'geoconfirmed_kml'):
                count += 1
        
        self.db.commit()
        return count


def fetch_osint_data(db: Session) -> Dict[str, int]:
    """Convenience function to fetch all OSINT data"""
    service = OSINTService(db)
    return service.fetch_and_store()

