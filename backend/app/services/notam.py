"""
NOTAM (Notice to Airmen) Parser and Fetcher

Parses ICAO NOTAM format and converts to GeoJSON for map display.
Supports coordinate extraction from Q-line and creation of circular/polygon geometry.
"""

import re
import math
from datetime import datetime, timezone
from typing import List, Dict, Tuple, Optional
from sqlalchemy.orm import Session
from geoalchemy2.elements import WKTElement

from .. import models, schemas


# ============================================================================
# IRAN FIR (Flight Information Regions)
# ============================================================================
IRAN_FIRS = ["OIIX", "OIXX"]  # Tehran FIR, Shiraz FIR

# NOTAM purpose/scope codes that indicate restrictions
RESTRICTION_CODES = [
    "QRTCA",  # Temporary restricted area
    "QRDCA",  # Danger area activated
    "QRRCA",  # Restricted area activated
    "QRPCA",  # Prohibited area activated
    "QWPLW",  # Warning area
    "QFALC",  # Aerodrome closed
    "QFAXX",  # Aerodrome unspecified
]


def parse_icao_coordinates(coord_str: str) -> Optional[Tuple[float, float]]:
    """
    Parse ICAO coordinate format to decimal degrees.
    
    Examples:
        "5129N00028W" -> (51.4833, -0.4667)
        "3541N05124E" -> (35.6833, 51.4000)
        "3200N05300E" -> (32.0, 53.0)
    
    Format: DDMMN/SDDDMME/W (degrees, minutes, hemisphere)
    """
    if not coord_str:
        return None
    
    # Pattern: 4 digits lat + N/S + 5 digits lon + E/W
    pattern = r'(\d{2})(\d{2})([NS])(\d{3})(\d{2})([EW])'
    match = re.match(pattern, coord_str.strip())
    
    if not match:
        # Try alternate format with 3-digit lat degrees (rare)
        pattern_alt = r'(\d{4})([NS])(\d{5})([EW])'
        match_alt = re.match(pattern_alt, coord_str.strip())
        if match_alt:
            lat_deg = int(match_alt.group(1)[:2])
            lat_min = int(match_alt.group(1)[2:])
            lat_hem = match_alt.group(2)
            lon_deg = int(match_alt.group(3)[:3])
            lon_min = int(match_alt.group(3)[3:])
            lon_hem = match_alt.group(4)
        else:
            return None
    else:
        lat_deg = int(match.group(1))
        lat_min = int(match.group(2))
        lat_hem = match.group(3)
        lon_deg = int(match.group(4))
        lon_min = int(match.group(5))
        lon_hem = match.group(6)
    
    # Convert to decimal
    lat = lat_deg + lat_min / 60.0
    lon = lon_deg + lon_min / 60.0
    
    # Apply hemisphere
    if lat_hem == 'S':
        lat = -lat
    if lon_hem == 'W':
        lon = -lon
    
    return (lat, lon)


def parse_notam_datetime(dt_str: str) -> Optional[datetime]:
    """
    Parse NOTAM datetime format.
    
    Examples:
        "2501120800" -> 2025-01-12 08:00 UTC
        "PERM" -> None (indicates permanent)
    
    Format: YYMMDDHHMM
    """
    if not dt_str or dt_str.upper() == "PERM":
        return None
    
    try:
        # Clean the string
        dt_str = dt_str.strip().upper()
        
        if len(dt_str) >= 10:
            year = 2000 + int(dt_str[0:2])
            month = int(dt_str[2:4])
            day = int(dt_str[4:6])
            hour = int(dt_str[6:8])
            minute = int(dt_str[8:10])
            return datetime(year, month, day, hour, minute, tzinfo=timezone.utc)
    except (ValueError, IndexError):
        pass
    
    return None


def parse_q_line(q_line: str) -> Dict:
    """
    Parse NOTAM Q) line to extract metadata and coordinates.
    
    Q) line format:
        Q) FIR/QCODE/TRAFFIC/PURPOSE/SCOPE/LOWER/UPPER/COORDS
        
    Example:
        Q) OIIX/QRTCA/IV/NBO/W/000/120/3541N05124E005
        
    Returns dict with:
        - fir: Flight Information Region
        - codes: NOTAM codes
        - traffic: Traffic type (I=IFR, V=VFR, IV=both)
        - purpose: Purpose codes
        - scope: Scope codes
        - lower: Lower altitude limit (flight level)
        - upper: Upper altitude limit (flight level)
        - lat, lon: Center coordinates
        - radius_nm: Radius in nautical miles
    """
    result = {
        'fir': None,
        'codes': None,
        'traffic': None,
        'lower': 0,
        'upper': 999,
        'lat': None,
        'lon': None,
        'radius_nm': None,
    }
    
    if not q_line:
        return result
    
    # Remove "Q)" prefix if present
    q_line = q_line.replace("Q)", "").strip()
    
    parts = q_line.split("/")
    
    if len(parts) >= 1:
        result['fir'] = parts[0].strip()
    if len(parts) >= 2:
        result['codes'] = parts[1].strip()
    if len(parts) >= 3:
        result['traffic'] = parts[2].strip()
    if len(parts) >= 6:
        try:
            result['lower'] = int(parts[5].strip())
        except ValueError:
            pass
    if len(parts) >= 7:
        try:
            result['upper'] = int(parts[6].strip())
        except ValueError:
            pass
    if len(parts) >= 8:
        # Coordinates with radius: "3541N05124E005"
        coord_radius = parts[7].strip()
        # Extract coordinates (first 11 chars) and radius (last 3 chars)
        if len(coord_radius) >= 11:
            coord_part = coord_radius[:11]
            coords = parse_icao_coordinates(coord_part)
            if coords:
                result['lat'] = coords[0]
                result['lon'] = coords[1]
            
            # Radius (in nautical miles)
            if len(coord_radius) >= 14:
                try:
                    result['radius_nm'] = int(coord_radius[11:14])
                except ValueError:
                    result['radius_nm'] = 5  # Default 5nm radius
            else:
                result['radius_nm'] = 5  # Default
    
    return result


def create_circle_polygon(center_lat: float, center_lon: float, radius_nm: float, num_points: int = 32) -> str:
    """
    Create a circular polygon as WKT from center point and radius.
    
    Args:
        center_lat: Center latitude in decimal degrees
        center_lon: Center longitude in decimal degrees
        radius_nm: Radius in nautical miles
        num_points: Number of points to approximate the circle
        
    Returns:
        WKT POLYGON string
    """
    # Convert nautical miles to degrees (approximate)
    # 1 nautical mile = 1.852 km
    # 1 degree latitude ≈ 111 km
    # 1 degree longitude ≈ 111 km * cos(lat)
    
    radius_km = radius_nm * 1.852
    radius_lat = radius_km / 111.0
    radius_lon = radius_km / (111.0 * math.cos(math.radians(center_lat)))
    
    points = []
    for i in range(num_points):
        angle = 2 * math.pi * i / num_points
        lat = center_lat + radius_lat * math.sin(angle)
        lon = center_lon + radius_lon * math.cos(angle)
        points.append(f"{lon} {lat}")
    
    # Close the polygon
    points.append(points[0])
    
    return f"POLYGON(({', '.join(points)}))"


def parse_notam_text(notam_text: str) -> Optional[schemas.AirspaceEventCreate]:
    """
    Parse a full NOTAM text and extract structured data.
    
    NOTAM format:
        A) Location indicator
        B) Start time (YYMMDDHHMM)
        C) End time (YYMMDDHHMM or PERM)
        D) Schedule (optional)
        E) Plain language text
        F) Lower limit (optional)
        G) Upper limit (optional)
        Q) Qualifier line (contains coords)
    """
    if not notam_text:
        return None
    
    # Extract fields using regex
    notam_id_match = re.search(r'([A-Z]\d{4}/\d{2})', notam_text)
    a_match = re.search(r'A\)\s*([A-Z]{4})', notam_text)
    b_match = re.search(r'B\)\s*(\d{10})', notam_text)
    c_match = re.search(r'C\)\s*(\d{10}|PERM)', notam_text, re.IGNORECASE)
    e_match = re.search(r'E\)\s*(.+?)(?=[A-G]\)|$)', notam_text, re.DOTALL)
    q_match = re.search(r'Q\)\s*([^\n]+)', notam_text)
    
    # Parse Q line for coordinates
    q_data = {}
    if q_match:
        q_data = parse_q_line(q_match.group(1))
    
    # If no coordinates from Q line, try to extract from E) text
    if not q_data.get('lat'):
        coord_match = re.search(r'(\d{4}[NS]\d{5}[EW])', notam_text)
        if coord_match:
            coords = parse_icao_coordinates(coord_match.group(1))
            if coords:
                q_data['lat'] = coords[0]
                q_data['lon'] = coords[1]
                q_data['radius_nm'] = 5  # Default radius
    
    # Must have coordinates to create event
    if not q_data.get('lat') or not q_data.get('lon'):
        return None
    
    # Parse times
    ts_start = parse_notam_datetime(b_match.group(1)) if b_match else datetime.now(timezone.utc)
    ts_end = parse_notam_datetime(c_match.group(1)) if c_match else None
    is_permanent = c_match and c_match.group(1).upper() == "PERM" if c_match else False
    
    # Determine airspace type from codes
    codes = q_data.get('codes', '')
    airspace_type = models.AIRSPACE_TYPE_RESTRICTION
    if 'FAL' in codes or 'FAX' in codes:
        airspace_type = models.AIRSPACE_TYPE_CLOSURE
    elif 'WPL' in codes or 'WRL' in codes:
        airspace_type = models.AIRSPACE_TYPE_WARNING
    elif 'RDC' in codes:
        airspace_type = models.AIRSPACE_TYPE_HAZARD
    elif 'RTC' in codes or 'RRC' in codes or 'RPC' in codes:
        airspace_type = models.AIRSPACE_TYPE_TEMPORARY
    
    # Build title and description
    location = a_match.group(1) if a_match else "Unknown"
    description = e_match.group(1).strip() if e_match else notam_text[:500]
    title = f"NOTAM: {location} - {airspace_type.replace('_', ' ').title()}"
    
    return schemas.AirspaceEventCreate(
        ts_start=ts_start,
        ts_end=ts_end,
        is_permanent=is_permanent,
        center_lat=q_data['lat'],
        center_lon=q_data['lon'],
        radius_nm=q_data.get('radius_nm', 5),
        lower_limit=q_data.get('lower', 0),
        upper_limit=q_data.get('upper', 999),
        airspace_type=airspace_type,
        source="notam",
        notam_id=notam_id_match.group(1) if notam_id_match else None,
        title=title,
        description=description[:1000],
        raw_text=notam_text[:2000],
        q_line=q_match.group(0) if q_match else None,
        fir=q_data.get('fir'),
        notam_codes=codes
    )


class NOTAMService:
    """Service for fetching and parsing NOTAMs"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def parse_and_store(self, notam_texts: List[str]) -> int:
        """Parse multiple NOTAM texts and store in database"""
        count = 0
        
        for text in notam_texts:
            try:
                event_data = parse_notam_text(text)
                if not event_data:
                    continue
                
                # Check for duplicate by NOTAM ID
                if event_data.notam_id:
                    existing = self.db.query(models.AirspaceEvent).filter(
                        models.AirspaceEvent.notam_id == event_data.notam_id
                    ).first()
                    if existing:
                        continue
                
                # Create geometry
                geometry_wkt = None
                if event_data.center_lat and event_data.center_lon and event_data.radius_nm:
                    geometry_wkt = create_circle_polygon(
                        event_data.center_lat,
                        event_data.center_lon,
                        event_data.radius_nm
                    )
                
                # Create database record
                db_event = models.AirspaceEvent(
                    ts_start=event_data.ts_start,
                    ts_end=event_data.ts_end,
                    is_permanent=event_data.is_permanent,
                    geometry=WKTElement(geometry_wkt, srid=4326) if geometry_wkt else None,
                    center_lat=event_data.center_lat,
                    center_lon=event_data.center_lon,
                    radius_nm=event_data.radius_nm,
                    lower_limit=event_data.lower_limit,
                    upper_limit=event_data.upper_limit,
                    airspace_type=event_data.airspace_type,
                    source=event_data.source,
                    notam_id=event_data.notam_id,
                    title=event_data.title,
                    description=event_data.description,
                    raw_text=event_data.raw_text,
                    q_line=event_data.q_line,
                    fir=event_data.fir,
                    notam_codes=event_data.notam_codes
                )
                self.db.add(db_event)
                count += 1
                
            except Exception as e:
                print(f"Error parsing NOTAM: {e}")
                continue
        
        self.db.commit()
        return count
    
    def get_active_airspace(self, fir: str = None) -> List[models.AirspaceEvent]:
        """Get currently active airspace restrictions"""
        now = datetime.now(timezone.utc)
        
        query = self.db.query(models.AirspaceEvent).filter(
            models.AirspaceEvent.ts_start <= now,
            (models.AirspaceEvent.ts_end >= now) | (models.AirspaceEvent.is_permanent == True)
        )
        
        if fir:
            query = query.filter(models.AirspaceEvent.fir == fir)
        
        return query.all()
    
    def to_geojson(self, events: List[models.AirspaceEvent]) -> dict:
        """Convert airspace events to GeoJSON FeatureCollection"""
        features = []
        
        for event in events:
            # Create circle geometry for display
            if event.center_lat and event.center_lon and event.radius_nm:
                # Create GeoJSON polygon (circle approximation)
                geometry_wkt = create_circle_polygon(
                    event.center_lat,
                    event.center_lon,
                    event.radius_nm
                )
                
                # Convert WKT to GeoJSON coordinates
                # Parse POLYGON((lon lat, lon lat, ...))
                coords_str = geometry_wkt.replace("POLYGON((", "").replace("))", "")
                coords = []
                for point in coords_str.split(", "):
                    lon, lat = point.split(" ")
                    coords.append([float(lon), float(lat)])
                
                geometry = {
                    "type": "Polygon",
                    "coordinates": [coords]
                }
            else:
                # Fallback to point
                geometry = {
                    "type": "Point",
                    "coordinates": [event.center_lon, event.center_lat]
                }
            
            features.append({
                "type": "Feature",
                "geometry": geometry,
                "properties": {
                    "id": event.id,
                    "notam_id": event.notam_id,
                    "title": event.title,
                    "description": event.description,
                    "airspace_type": event.airspace_type,
                    "ts_start": event.ts_start.isoformat() if event.ts_start else None,
                    "ts_end": event.ts_end.isoformat() if event.ts_end else None,
                    "is_permanent": event.is_permanent,
                    "lower_limit": event.lower_limit,
                    "upper_limit": event.upper_limit,
                    "radius_nm": event.radius_nm,
                    "fir": event.fir,
                    "source": event.source
                }
            })
        
        return {
            "type": "FeatureCollection",
            "features": features,
            "count": len(features)
        }
    
    def cleanup_expired(self) -> int:
        """Remove expired non-permanent NOTAMs"""
        now = datetime.now(timezone.utc)
        
        count = self.db.query(models.AirspaceEvent).filter(
            models.AirspaceEvent.is_permanent == False,
            models.AirspaceEvent.ts_end < now
        ).delete(synchronize_session=False)
        
        self.db.commit()
        return count


# ============================================================================
# REAL NOTAM DATA FETCHING - FREE SOURCES
# ============================================================================
import requests
import os
import json

# Iran ICAO airport codes for NOTAM queries
IRAN_AIRPORTS = [
    "OIII",  # Tehran Imam Khomeini
    "OIIE",  # Tehran Mehrabad
    "OISS",  # Shiraz
    "OIMM",  # Mashhad
    "OITT",  # Tabriz
    "OIFM",  # Isfahan
    "OIKB",  # Bandar Abbas
    "OICC",  # Abadan
    "OIAW",  # Ahvaz
    "OIKK",  # Kerman
]

# Iran FIR code
IRAN_FIR = "OIIX"


class NOTAMFetcher:
    """Fetches real NOTAM data from free public sources"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json, text/html, */*',
        })
    
    def fetch_from_aviationapi(self, icao_codes: List[str]) -> List[str]:
        """
        Fetch from AviationAPI.com - FREE, no auth required
        https://aviationapi.com/ - Returns FAA data in JSON
        """
        notams = []
        try:
            # Try batch endpoint first
            codes_str = ",".join(icao_codes[:10])
            url = f"https://api.aviationapi.com/v1/vfr/notams?apt={codes_str}"
            
            response = self.session.get(url, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                # Handle different response formats
                if isinstance(data, dict):
                    for apt_code, apt_notams in data.items():
                        if isinstance(apt_notams, list):
                            for notam in apt_notams:
                                if isinstance(notam, dict):
                                    text = notam.get('notam', notam.get('text', ''))
                                    if text:
                                        notams.append(text)
                                elif isinstance(notam, str):
                                    notams.append(notam)
                elif isinstance(data, list):
                    for notam in data:
                        if isinstance(notam, dict) and 'notam' in notam:
                            notams.append(notam['notam'])
                        elif isinstance(notam, str):
                            notams.append(notam)
                            
            print(f"    AviationAPI: {len(notams)} NOTAMs")
                                
        except Exception as e:
            print(f"    AviationAPI error: {e}")
        
        return notams
    
    def fetch_from_pilotweb(self, icao_codes: List[str]) -> List[str]:
        """
        Fetch from FAA PilotWeb - FREE public interface
        https://pilotweb.nas.faa.gov/PilotWeb/
        """
        notams = []
        try:
            url = "https://pilotweb.nas.faa.gov/PilotWeb/notamRetrievalByICAOAction.do"
            
            for icao in icao_codes[:5]:
                response = self.session.post(
                    url,
                    data={
                        'retrieveLocId': icao,
                        'reportType': 'RAW',
                        'formatType': 'DOMESTIC',
                        'actionType': 'notamRetrievalByICAOs',
                    },
                    timeout=15
                )
                
                if response.status_code == 200 and 'NOTAM' in response.text:
                    # Extract NOTAMs from HTML response
                    text = response.text
                    # Look for NOTAM patterns
                    import re
                    # Match NOTAM format: !ABC 01/001 ... or A0001/25
                    matches = re.findall(
                        r'(!?[A-Z]{3,4}\s+\d{2}/\d{3,4}[^\n]+(?:\n(?![!A-Z]{3,4}\s+\d{2}/)[^\n]+)*)',
                        text
                    )
                    notams.extend(matches)
                    
            print(f"    PilotWeb: {len(notams)} NOTAMs")
                    
        except Exception as e:
            print(f"    PilotWeb error: {e}")
        
        return notams
    
    def fetch_from_notaminfo(self) -> List[str]:
        """
        Fetch from notaminfo.com - aggregates global NOTAMs
        """
        notams = []
        try:
            # Try to get Iran FIR NOTAMs
            url = f"https://notaminfo.com/api/notams?fir={IRAN_FIR}"
            
            response = self.session.get(url, timeout=15)
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    if isinstance(data, list):
                        for notam in data:
                            if isinstance(notam, dict):
                                text = notam.get('raw', notam.get('text', notam.get('message', '')))
                                if text:
                                    notams.append(text)
                except json.JSONDecodeError:
                    pass
                    
            print(f"    NotamInfo: {len(notams)} NOTAMs")
                    
        except Exception as e:
            print(f"    NotamInfo error: {e}")
        
        return notams
    
    def fetch_from_eurocontrol_ead(self) -> List[str]:
        """
        Try EUROCONTROL EAD public interface
        Note: May require authentication for full access
        """
        notams = []
        try:
            # EAD basic public interface
            url = "https://www.ead.eurocontrol.int/fwf-eadbasic/restricted/user/pib/pibretrieve.faces"
            
            # This typically requires session/authentication
            # Just try basic access
            response = self.session.get(
                "https://www.ead.eurocontrol.int/cms-eadbasic/opencms/en/pib/",
                timeout=10
            )
            
            if response.status_code == 200:
                print(f"    EUROCONTROL: Accessible (requires login for data)")
                    
        except Exception as e:
            print(f"    EUROCONTROL error: {e}")
        
        return notams
    
    def fetch_from_skybriefing(self) -> List[str]:
        """
        Try skybriefing.com for Swiss/European NOTAMs
        """
        notams = []
        try:
            # This is primarily for Swiss airspace but may have some data
            url = "https://www.skybriefing.com/portal/public/notam"
            response = self.session.get(url, timeout=10)
            
            if response.status_code == 200:
                print(f"    SkyBriefing: Accessible")
                    
        except Exception as e:
            print(f"    SkyBriefing error: {e}")
        
        return notams

    def fetch_from_checkwx(self, icao_codes: List[str]) -> List[str]:
        """
        CheckWX API - Free tier available with API key
        https://www.checkwxapi.com/
        """
        notams = []
        api_key = os.getenv("CHECKWX_API_KEY", "")
        
        if not api_key:
            return notams
            
        try:
            for icao in icao_codes[:5]:
                url = f"https://api.checkwx.com/notam/{icao}"
                response = self.session.get(
                    url,
                    headers={'X-API-Key': api_key},
                    timeout=10
                )
                
                if response.status_code == 200:
                    data = response.json()
                    for notam in data.get('data', []):
                        if isinstance(notam, dict) and 'raw' in notam:
                            notams.append(notam['raw'])
                            
            print(f"    CheckWX: {len(notams)} NOTAMs")
                            
        except Exception as e:
            print(f"    CheckWX error: {e}")
        
        return notams
    
    def fetch_iran_notams(self) -> List[str]:
        """Fetch NOTAMs for Iran from all available free sources"""
        all_notams = []
        
        print("  Fetching NOTAMs from free sources...")
        
        # 1. AviationAPI (free, no auth)
        notams = self.fetch_from_aviationapi(IRAN_AIRPORTS)
        all_notams.extend(notams)
        
        # 2. FAA PilotWeb (free, no auth)
        notams = self.fetch_from_pilotweb(IRAN_AIRPORTS)
        all_notams.extend(notams)
        
        # 3. NotamInfo (if available)
        notams = self.fetch_from_notaminfo()
        all_notams.extend(notams)
        
        # 4. CheckWX (if API key available)
        notams = self.fetch_from_checkwx(IRAN_AIRPORTS)
        all_notams.extend(notams)
        
        # Deduplicate
        unique_notams = list(set(all_notams))
        print(f"  Total unique NOTAMs: {len(unique_notams)}")
        
        return unique_notams


def fetch_real_notams(db: Session) -> int:
    """Fetch and store real NOTAMs from available free sources"""
    fetcher = NOTAMFetcher()
    notam_texts = fetcher.fetch_iran_notams()
    
    if not notam_texts:
        print("  No real NOTAMs available, using sample data as fallback...")
        return load_sample_notams(db)
    
    service = NOTAMService(db)
    count = service.parse_and_store(notam_texts)
    
    # If parsing failed for all, use samples
    if count == 0:
        print("  Could not parse any NOTAMs, using sample data...")
        return load_sample_notams(db)
    
    return count


# ============================================================================
# SAMPLE NOTAMS (fallback when real data unavailable)
# ============================================================================
def get_sample_notams() -> List[str]:
    """Generate sample NOTAMs with current dates as fallback"""
    from datetime import timedelta
    
    now = datetime.now(timezone.utc)
    start_time = now.strftime("%y%m%d0000")
    end_time_24h = (now + timedelta(hours=24)).strftime("%y%m%d2359")
    end_time_48h = (now + timedelta(hours=48)).strftime("%y%m%d2359")
    end_time_72h = (now + timedelta(hours=72)).strftime("%y%m%d2359")
    
    return [
        f"""
        A0123/25 NOTAMN
        Q) OIIX/QRTCA/IV/NBO/W/000/120/3541N05124E025
        A) OIII
        B) {start_time}
        C) {end_time_48h}
        E) TEMPORARY RESTRICTED AREA ACTIVATED DUE TO VIP MOVEMENT.
        AREA: 25NM RADIUS CENTERED ON 3541N05124E (TEHRAN MEHRABAD).
        ALTITUDES: SFC TO FL120.
        """,
        f"""
        A0124/25 NOTAMN
        Q) OIIX/QRDCA/IV/BO/W/000/150/3629N04611E015
        A) OITT
        B) {start_time}
        C) {end_time_72h}
        E) DANGER AREA D-IR-1 ACTIVATED.
        MILITARY EXERCISES IN PROGRESS.
        AREA: 15NM RADIUS CENTERED ON TABRIZ.
        """,
        f"""
        A0125/25 NOTAMN
        Q) OIIX/QFALC/IV/NBO/A/000/999/3239N05240E005
        A) OIFM
        B) {start_time}
        C) {end_time_24h}
        E) ESFAHAN SHAHID BEHESHTI INTL AIRPORT CLOSED FOR RUNWAY MAINTENANCE.
        """,
        f"""
        A0126/25 NOTAMN
        Q) OIIX/QWPLW/IV/NBO/W/000/200/2958N05234E020
        A) OISS
        B) {start_time}
        C) {end_time_48h}
        E) WARNING AREA ACTIVATED OVER SHIRAZ REGION.
        UNMANNED AIRCRAFT OPERATIONS IN PROGRESS.
        AREA: 20NM RADIUS CENTERED ON SHIRAZ.
        """,
        f"""
        A0127/25 NOTAMN
        Q) OIIX/QRTCA/IV/NBO/W/000/100/3626N05925E010
        A) OIMM
        B) {start_time}
        C) PERM
        E) PERMANENT RESTRICTED AREA OVER MASHHAD HOLY SHRINE.
        NO OVERFLIGHT PERMITTED BELOW FL100.
        """,
    ]


def load_sample_notams(db: Session) -> int:
    """Load sample NOTAMs as fallback"""
    service = NOTAMService(db)
    return service.parse_and_store(get_sample_notams())

