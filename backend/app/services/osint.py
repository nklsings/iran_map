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
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional, Tuple
from sqlalchemy.orm import Session
from geoalchemy2.elements import WKTElement

from .. import models, schemas


class GeoConfirmedFetcher:
    """
    Fetches data from GeoConfirmed.org
    
    GeoConfirmed is an OSINT verification platform that geolocates events.
    Uses their internal API discovered via network inspection.
    
    API Structure:
    - List: GET /api/placemark/Iran?search= -> returns [{id, date, la, lo, icon}, ...]
    - Detail: GET /api/placemark/Iran/{id} -> returns full placemark with description, sources
    """
    
    BASE_URL = "https://geoconfirmed.org"
    COUNTRY = "Iran"
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': f'https://geoconfirmed.org/{self.COUNTRY.lower()}',
            'Origin': 'https://geoconfirmed.org',
        })
    
    def fetch_iran_data(self, max_items: int = 100, days_limit: int = 7) -> List[Dict]:
        """
        Fetch GeoConfirmed Iran data from their API.
        
        First fetches the list of placemarks, then fetches details for each one
        to get full description and source links.
        
        Args:
            max_items: Maximum number of placemarks to fetch details for
            days_limit: Only fetch events from the last N days (default: 7)
                        Note: GeoConfirmed uses date-only timestamps, so we use days not hours.
                        The API layer (/api/events?hours=168) handles display filtering.
        """
        events = []
        
        print("  Fetching from GeoConfirmed API...")
        
        try:
            # Step 1: Get list of placemarks
            list_url = f"{self.BASE_URL}/api/placemark/{self.COUNTRY}?search="
            response = self.session.get(list_url, timeout=30)
            
            if response.status_code != 200:
                print(f"    GeoConfirmed: HTTP {response.status_code}")
                return events
            
            try:
                placemark_list = response.json()
            except json.JSONDecodeError as e:
                print(f"    GeoConfirmed: JSON decode error: {e}")
                return events
            
            if not isinstance(placemark_list, list):
                print(f"    GeoConfirmed: Unexpected response format")
                return events
            
            print(f"    GeoConfirmed: found {len(placemark_list)} total placemarks")
            
            # Filter by date - only last N days (GeoConfirmed uses date-only timestamps)
            cutoff_time = datetime.now(timezone.utc) - timedelta(days=days_limit)
            recent_placemarks = []
            
            for pm in placemark_list:
                date_str = pm.get('date', '')
                if date_str:
                    try:
                        # Parse date (format: "2026-01-11T00:00:00" or similar)
                        pm_date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                        # Make timezone-aware if not already
                        if pm_date.tzinfo is None:
                            pm_date = pm_date.replace(tzinfo=timezone.utc)
                        
                        if pm_date >= cutoff_time:
                            recent_placemarks.append(pm)
                    except (ValueError, TypeError):
                        # If date parsing fails, still include it (might be valid)
                        recent_placemarks.append(pm)
            
            print(f"    GeoConfirmed: {len(recent_placemarks)} placemarks from last {days_limit} days")
            
            if not recent_placemarks:
                print(f"    GeoConfirmed: No recent events (all older than {days_limit} days)")
                return events
            
            # Sort by date (most recent first)
            recent_placemarks.sort(key=lambda x: x.get('date', ''), reverse=True)
            
            fetched_count = 0
            for pm in recent_placemarks[:max_items]:
                pm_id = pm.get('id')
                if not pm_id:
                    continue
                
                try:
                    # Fetch full details
                    detail_url = f"{self.BASE_URL}/api/placemark/{self.COUNTRY}/{pm_id}"
                    detail_resp = self.session.get(detail_url, timeout=10)
                    
                    if detail_resp.status_code == 200:
                        detail = detail_resp.json()
                        if detail:  # Not empty
                            event = self._parse_detailed_placemark(detail)
                            if event:
                                events.append(event)
                                fetched_count += 1
                except Exception as e:
                    continue
            
            print(f"    GeoConfirmed: fetched {fetched_count} detailed placemarks")
                
        except requests.exceptions.RequestException as e:
            print(f"    GeoConfirmed: Request error: {e}")
        
        return events
    
    def _parse_detailed_placemark(self, pm: Dict) -> Optional[Dict]:
        """
        Parse a detailed placemark response from GeoConfirmed API.
        
        Expected format:
        {
            "id": "uuid",
            "date": "2026-01-11T00:00:00",
            "name": "11 JAN 2026",
            "description": "Event description...",
            "coordinates": [lat, lon],
            "originalSource": "Vid1\nhttps://x.com/...\nVid2\nhttps://...",
            "geolocation": "https://x.com/GeoConfirmed/...",
            "plusCode": "G999+6RX Location, Province, Iran",
            ...
        }
        """
        # Get coordinates
        coords = pm.get('coordinates', [])
        if len(coords) < 2:
            return None
        
        lat, lon = coords[0], coords[1]
        
        # Validate Iran region
        if not (25 <= lat <= 40 and 44 <= lon <= 64):
            return None
        
        # Get title (use name or generate from date)
        title = pm.get('name') or pm.get('description', '')[:50] or 'GeoConfirmed Event'
        
        # Get description
        description = pm.get('description') or ''
        
        # Extract source links
        social_links = []
        original_source = pm.get('originalSource') or ''
        geolocation = pm.get('geolocation') or ''
        
        # Parse originalSource (contains X/Twitter links, one per line)
        for line in original_source.split('\n'):
            line = line.strip()
            if line.startswith('http'):
                if 'x.com' in line or 'twitter.com' in line:
                    social_links.append(f"🐦 X/Twitter: {line}")
                elif 't.me' in line:
                    social_links.append(f"📱 Telegram: {line}")
                elif 'youtube.com' in line or 'youtu.be' in line:
                    social_links.append(f"📺 YouTube: {line}")
                else:
                    social_links.append(f"🔗 Source: {line}")
        
        # Parse geolocation (GeoConfirmed verification links)
        gc_verification_link = None
        for line in geolocation.split('\n'):
            line = line.strip()
            if line.startswith('http') and 'GeoConfirmed' in line:
                gc_verification_link = line
                break
        
        # Get first X/Twitter link as primary source
        primary_source_url = None
        for link in social_links:
            if 'x.com' in link or 'twitter.com' in link:
                match = re.search(r'https?://\S+', link)
                if match:
                    primary_source_url = match.group(0)
                    break
        
        # Build enhanced description with links
        enhanced_desc = description
        if social_links:
            enhanced_desc += "\n\n📎 Sources:\n" + "\n".join(social_links[:10])
        
        # Add GeoConfirmed verification link
        gc_id = pm.get('id')
        gc_url = f"https://geoconfirmed.org/{self.COUNTRY.lower()}#pm{gc_id}" if gc_id else None
        if gc_url:
            enhanced_desc += f"\n\n🌍 GeoConfirmed: {gc_url}"
        
        # Add Plus Code location if available
        plus_code = pm.get('plusCode')
        if plus_code:
            enhanced_desc += f"\n📍 {plus_code}"
        
        # Get date - prefer dateCreated (has actual time) over date (midnight only)
        date_str = pm.get('dateCreated') or pm.get('date')
        
        return {
            'title': title,
            'description': enhanced_desc,
            'latitude': float(lat),
            'longitude': float(lon),
            'source': 'geoconfirmed',
            'source_url': primary_source_url or gc_url or f"https://geoconfirmed.org/{self.COUNTRY.lower()}",
            'category': 'verified',
            'date': date_str,
            'media_url': None,  # Could extract from sources if needed
            'social_links': social_links,
            'gc_id': gc_id,
        }
    
    def _parse_placemarks(self, data: any) -> List[Dict]:
        """Parse the placemark response from GeoConfirmed API (basic list format)"""
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
        
        # === EXTRACT SOCIAL MEDIA LINKS ===
        social_links = []
        media_url = None
        
        # Check for links array (GeoConfirmed often has this)
        links = props.get('links') or props.get('sources') or props.get('source_links') or []
        if isinstance(links, str):
            links = [links]
        
        # Also check for specific URL fields
        for field in ['twitterUrl', 'twitter', 'xUrl', 'x', 'telegramUrl', 'telegram', 
                      'sourceUrl', 'source', 'originalUrl', 'videoUrl', 'imageUrl',
                      'link', 'url', 'media', 'mediaUrl']:
            val = props.get(field)
            if val and isinstance(val, str) and val.startswith('http'):
                links.append(val)
        
        # Parse links and categorize them
        for link in links:
            if not isinstance(link, str):
                continue
            link = link.strip()
            if not link.startswith('http'):
                continue
            
            # Categorize link
            if 'twitter.com' in link or 'x.com' in link:
                social_links.append(f"🐦 X/Twitter: {link}")
            elif 't.me' in link or 'telegram' in link.lower():
                social_links.append(f"📱 Telegram: {link}")
            elif 'youtube.com' in link or 'youtu.be' in link:
                social_links.append(f"📺 YouTube: {link}")
            elif 'instagram.com' in link:
                social_links.append(f"📸 Instagram: {link}")
            elif 'facebook.com' in link or 'fb.com' in link:
                social_links.append(f"📘 Facebook: {link}")
            elif any(ext in link.lower() for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']):
                if not media_url:
                    media_url = link
            elif any(ext in link.lower() for ext in ['.mp4', '.webm', '.mov']):
                if not media_url:
                    media_url = link
            else:
                social_links.append(f"🔗 Source: {link}")
        
        # Also extract links from description using regex
        url_pattern = r'https?://[^\s<>"\']+(?:\.[a-zA-Z]{2,})[^\s<>"\']*'
        desc_links = re.findall(url_pattern, description)
        for link in desc_links:
            link = link.rstrip('.,;:!?)')
            if 'twitter.com' in link or 'x.com' in link:
                if f"🐦 X/Twitter: {link}" not in social_links:
                    social_links.append(f"🐦 X/Twitter: {link}")
            elif 't.me' in link:
                if f"📱 Telegram: {link}" not in social_links:
                    social_links.append(f"📱 Telegram: {link}")
        
        # Build enhanced description with links
        enhanced_desc = description
        if social_links:
            enhanced_desc += "\n\n📎 Sources:\n" + "\n".join(social_links[:5])  # Limit to 5 links
        
        # Get main source URL (prefer X/Twitter if available)
        source_url = props.get('url') or props.get('source') or f"https://geoconfirmed.org/iran"
        
        # Check if there's an X/Twitter link to use as primary source
        for link in (links if isinstance(links, list) else [links]):
            if isinstance(link, str):
                if 'x.com' in link or 'twitter.com' in link:
                    source_url = link
                    break
        
        if props.get('id'):
            geoconfirmed_url = f"https://geoconfirmed.org/iran#pm{props.get('id')}"
            if source_url == f"https://geoconfirmed.org/iran":
                source_url = geoconfirmed_url
            else:
                # Add GeoConfirmed reference to description
                enhanced_desc += f"\n\n🌍 GeoConfirmed: {geoconfirmed_url}"
        
        return {
            'title': title,
            'description': enhanced_desc,
            'latitude': float(lat),
            'longitude': float(lon),
            'source': 'geoconfirmed',
            'source_url': source_url,
            'category': category,
            'date': date_str,
            'media_url': media_url,
            'social_links': social_links,
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
                if 'features' in data and data['features']:
                    for feature in data['features']:
                        if not feature:
                            continue
                        geom = feature.get('geometry')
                        props = feature.get('properties') or {}
                        
                        # Handle None geometry
                        if not geom or not isinstance(geom, dict):
                            continue
                        
                        if geom.get('type') == 'Point':
                            coords = geom.get('coordinates', [])
                            if coords and len(coords) >= 2:
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
            
            # Create source-tagged title with better date formatting
            source_tag = source.upper().replace('_', ' ')
            
            # Format title - if it's just a date like "08 JAN 2026", make it more descriptive
            date_str = event.get('date')
            if date_str:
                try:
                    event_dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                    if event_dt.tzinfo is None:
                        event_dt = event_dt.replace(tzinfo=timezone.utc)
                    # Format as "Today HH:MM" or "Yesterday HH:MM" or "DD MMM HH:MM"
                    now = datetime.now(timezone.utc)
                    if event_dt.date() == now.date():
                        time_str = f"Today {event_dt.strftime('%H:%M')}"
                    elif event_dt.date() == (now - timedelta(days=1)).date():
                        time_str = f"Yesterday {event_dt.strftime('%H:%MM')}"
                    else:
                        time_str = event_dt.strftime('%d %b %H:%M')
                    tagged_title = f"[{source_tag}] {time_str} - {title[:120]}"
                except (ValueError, TypeError):
                    tagged_title = f"[{source_tag}] {title[:150]}"
            else:
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
            
            # Get source URL (prefer X/Twitter link if available from GeoConfirmed)
            source_url = event.get('source_url') or event.get('url') or f"https://geoconfirmed.org/iran"
            
            # Get media URL if available
            media_url = event.get('media_url')
            media_type = None
            if media_url:
                if any(ext in media_url.lower() for ext in ['.mp4', '.webm', '.mov']):
                    media_type = 'video'
                elif any(ext in media_url.lower() for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']):
                    media_type = 'image'
            
            # Parse event date if available, otherwise use current time
            event_timestamp = datetime.now(timezone.utc)
            date_str = event.get('date')
            if date_str:
                try:
                    event_timestamp = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                    if event_timestamp.tzinfo is None:
                        event_timestamp = event_timestamp.replace(tzinfo=timezone.utc)
                except (ValueError, TypeError):
                    pass  # Keep default timestamp
            
            # Get intensity and verified status
            intensity = event.get('intensity', 0.8)
            verified = event.get('verified', True)
            
            # Create the event
            db_event = models.ProtestEvent(
                title=tagged_title,
                description=event.get('description', '')[:1000],  # Increased for links
                latitude=lat,
                longitude=lon,
                location=WKTElement(f'POINT({lon} {lat})', srid=4326),
                intensity_score=intensity,
                verified=verified,
                timestamp=event_timestamp,  # Use actual event date
                event_type=event_type,
                source_platform=source,
                source_url=source_url,
                media_url=media_url,
                media_type=media_type,
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

