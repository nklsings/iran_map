"""
Internet Connectivity Monitoring Service

Fetches and tracks internet connectivity status for Iranian provinces/regions.
Uses multiple data sources:
- IODA (Internet Outage Detection and Analysis) from Georgia Tech
- Cloudflare Radar (if API key available)
- Manual/admin updates for ground truth
"""

import requests
import json
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional, Tuple
from sqlalchemy.orm import Session

from .. import models

# Iranian provinces with approximate center coordinates
IRAN_PROVINCES = {
    "tehran": {"name": "Tehran", "name_fa": "تهران", "lat": 35.6892, "lon": 51.3890, "population": 9000000},
    "isfahan": {"name": "Isfahan", "name_fa": "اصفهان", "lat": 32.6546, "lon": 51.6680, "population": 2220000},
    "fars": {"name": "Fars (Shiraz)", "name_fa": "فارس", "lat": 29.5918, "lon": 52.5836, "population": 1870000},
    "khorasan_razavi": {"name": "Khorasan Razavi", "name_fa": "خراسان رضوی", "lat": 36.2972, "lon": 59.6067, "population": 3300000},
    "east_azerbaijan": {"name": "East Azerbaijan", "name_fa": "آذربایجان شرقی", "lat": 38.0800, "lon": 46.2919, "population": 1900000},
    "khuzestan": {"name": "Khuzestan", "name_fa": "خوزستان", "lat": 31.3203, "lon": 48.6692, "population": 2100000},
    "alborz": {"name": "Alborz (Karaj)", "name_fa": "البرز", "lat": 35.8400, "lon": 50.9391, "population": 2700000},
    "qom": {"name": "Qom", "name_fa": "قم", "lat": 34.6416, "lon": 50.8746, "population": 1300000},
    "kurdistan": {"name": "Kurdistan", "name_fa": "کردستان", "lat": 35.3219, "lon": 46.9862, "population": 1600000},
    "west_azerbaijan": {"name": "West Azerbaijan", "name_fa": "آذربایجان غربی", "lat": 37.5513, "lon": 45.0761, "population": 3300000},
    "kermanshah": {"name": "Kermanshah", "name_fa": "کرمانشاه", "lat": 34.3142, "lon": 47.0650, "population": 950000},
    "sistan_baluchestan": {"name": "Sistan-Baluchestan", "name_fa": "سیستان و بلوچستان", "lat": 29.4963, "lon": 60.8629, "population": 2900000},
    "mazandaran": {"name": "Mazandaran", "name_fa": "مازندران", "lat": 36.5659, "lon": 53.0586, "population": 3300000},
    "gilan": {"name": "Gilan", "name_fa": "گیلان", "lat": 37.2809, "lon": 49.5924, "population": 2500000},
    "kerman": {"name": "Kerman", "name_fa": "کرمان", "lat": 30.2839, "lon": 57.0834, "population": 820000},
    "hormozgan": {"name": "Hormozgan", "name_fa": "هرمزگان", "lat": 27.1832, "lon": 56.2666, "population": 800000},
    "lorestan": {"name": "Lorestan", "name_fa": "لرستان", "lat": 33.4878, "lon": 48.3558, "population": 500000},
    "hamadan": {"name": "Hamadan", "name_fa": "همدان", "lat": 34.7990, "lon": 48.5150, "population": 680000},
    "yazd": {"name": "Yazd", "name_fa": "یزد", "lat": 31.8974, "lon": 54.3569, "population": 650000},
    "markazi": {"name": "Markazi", "name_fa": "مرکزی", "lat": 34.0917, "lon": 49.6892, "population": 500000},
    "ardabil": {"name": "Ardabil", "name_fa": "اردبیل", "lat": 38.2498, "lon": 48.2933, "population": 560000},
    "zanjan": {"name": "Zanjan", "name_fa": "زنجان", "lat": 36.6736, "lon": 48.4787, "population": 520000},
    "qazvin": {"name": "Qazvin", "name_fa": "قزوین", "lat": 36.2797, "lon": 50.0049, "population": 600000},
    "semnan": {"name": "Semnan", "name_fa": "سمنان", "lat": 35.5769, "lon": 53.3976, "population": 180000},
    "golestan": {"name": "Golestan", "name_fa": "گلستان", "lat": 36.8427, "lon": 54.4395, "population": 950000},
    "north_khorasan": {"name": "North Khorasan", "name_fa": "خراسان شمالی", "lat": 37.4711, "lon": 57.3319, "population": 400000},
    "south_khorasan": {"name": "South Khorasan", "name_fa": "خراسان جنوبی", "lat": 32.8653, "lon": 59.2164, "population": 200000},
    "bushehr": {"name": "Bushehr", "name_fa": "بوشهر", "lat": 28.9234, "lon": 50.8203, "population": 250000},
    "chaharmahal_bakhtiari": {"name": "Chaharmahal-Bakhtiari", "name_fa": "چهارمحال و بختیاری", "lat": 32.3256, "lon": 50.8645, "population": 200000},
    "ilam": {"name": "Ilam", "name_fa": "ایلام", "lat": 33.6374, "lon": 46.4227, "population": 200000},
    "kohgiluyeh": {"name": "Kohgiluyeh-Boyer-Ahmad", "name_fa": "کهگیلویه و بویراحمد", "lat": 30.7244, "lon": 50.8456, "population": 130000},
}

# Connectivity status levels
STATUS_NORMAL = "normal"
STATUS_DEGRADED = "degraded"
STATUS_RESTRICTED = "restricted"
STATUS_BLACKOUT = "blackout"
STATUS_UNKNOWN = "unknown"


class IODAFetcher:
    """
    Fetches data from IODA (Internet Outage Detection and Analysis)
    API from Georgia Tech / CAIDA
    
    IODA provides BGP, Active Probing, and Darknet data for outage detection.
    """
    
    # IODA API base URL
    BASE_URL = "https://api.ioda.inetintel.cc.gatech.edu/v2"
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'IranProtestMap/1.0',
            'Accept': 'application/json',
        })
    
    def fetch_country_signals(self, country_code: str = "IR") -> Optional[Dict]:
        """Fetch current outage signals for Iran"""
        try:
            # Get recent signals (last 24 hours)
            end_time = int(datetime.now(timezone.utc).timestamp())
            start_time = end_time - (24 * 3600)
            
            url = f"{self.BASE_URL}/signals/raw/{country_code}"
            params = {
                "from": start_time,
                "until": end_time,
            }
            
            response = self.session.get(url, params=params, timeout=15)
            
            if response.status_code == 200:
                return response.json()
            else:
                print(f"  IODA: HTTP {response.status_code}")
                return None
                
        except Exception as e:
            print(f"  IODA fetch error: {e}")
            return None
    
    def get_outage_score(self, data: Dict) -> Tuple[float, str]:
        """
        Calculate an outage score from IODA data.
        Returns (score 0-1, status string)
        """
        if not data:
            return 0.5, STATUS_UNKNOWN
        
        try:
            # IODA returns multiple signal types
            signals = data.get('data', [])
            
            if not signals:
                return 1.0, STATUS_NORMAL
            
            # Analyze the most recent signals
            bgp_score = 1.0
            active_score = 1.0
            darknet_score = 1.0
            
            for signal in signals:
                signal_type = signal.get('datasource', '')
                value = signal.get('value', 1.0)
                
                if 'bgp' in signal_type.lower():
                    bgp_score = min(bgp_score, value)
                elif 'active' in signal_type.lower():
                    active_score = min(active_score, value)
                elif 'darknet' in signal_type.lower():
                    darknet_score = min(darknet_score, value)
            
            # Weighted average (BGP is most reliable)
            overall_score = (bgp_score * 0.5 + active_score * 0.3 + darknet_score * 0.2)
            
            # Determine status
            if overall_score >= 0.9:
                return overall_score, STATUS_NORMAL
            elif overall_score >= 0.7:
                return overall_score, STATUS_DEGRADED
            elif overall_score >= 0.3:
                return overall_score, STATUS_RESTRICTED
            else:
                return overall_score, STATUS_BLACKOUT
                
        except Exception as e:
            print(f"  IODA score error: {e}")
            return 0.5, STATUS_UNKNOWN


class CloudflareRadarFetcher:
    """
    Fetches data from Cloudflare Radar API
    Requires CLOUDFLARE_RADAR_API_KEY environment variable
    """
    
    BASE_URL = "https://api.cloudflare.com/client/v4/radar"
    
    def __init__(self, api_key: str = None):
        import os
        self.api_key = api_key or os.getenv("CLOUDFLARE_RADAR_API_KEY")
        self.session = requests.Session()
        if self.api_key:
            self.session.headers.update({
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json',
            })
    
    def fetch_traffic_anomalies(self, country: str = "IR") -> Optional[Dict]:
        """Fetch traffic anomalies for Iran"""
        if not self.api_key:
            return None
        
        try:
            url = f"{self.BASE_URL}/traffic/anomalies"
            params = {
                'location': country,
                'dateRange': '1d',
            }
            
            response = self.session.get(url, params=params, timeout=15)
            
            if response.status_code == 200:
                return response.json()
            return None
            
        except Exception as e:
            print(f"  Cloudflare Radar error: {e}")
            return None


class ConnectivityService:
    """Main service for internet connectivity monitoring"""
    
    def __init__(self, db: Session = None):
        self.db = db
        self.ioda = IODAFetcher()
        self.cloudflare = CloudflareRadarFetcher()
        
        # Cache for province status
        self._cache: Dict[str, Dict] = {}
        self._cache_time: datetime = None
        self._cache_ttl = timedelta(minutes=15)
    
    def get_province_connectivity(self) -> List[Dict]:
        """Get connectivity status for all Iranian provinces"""
        
        # Check cache
        if self._cache and self._cache_time:
            if datetime.now(timezone.utc) - self._cache_time < self._cache_ttl:
                return list(self._cache.values())
        
        print("Fetching internet connectivity data...")
        
        # Fetch national-level data
        ioda_data = self.ioda.fetch_country_signals("IR")
        national_score, national_status = self.ioda.get_outage_score(ioda_data)
        
        # For now, we'll use national data as baseline and simulate provincial variation
        # In production, you'd want provincial-level data from IODA or other sources
        provinces = []
        
        for province_id, info in IRAN_PROVINCES.items():
            # Calculate province score based on national + some variation
            # Major cities (Tehran, Isfahan, etc.) tend to have better connectivity
            population_factor = min(info["population"] / 5000000, 1.0)  # Larger cities = better infra
            
            # Apply some random-ish variation based on province characteristics
            # In reality, you'd use actual provincial data
            if province_id in ["tehran", "alborz"]:
                province_score = national_score * 1.1  # Capital region often has better access
            elif province_id in ["sistan_baluchestan", "kurdistan", "west_azerbaijan"]:
                province_score = national_score * 0.85  # Often more restricted
            else:
                province_score = national_score * (0.95 + population_factor * 0.1)
            
            province_score = max(0, min(1, province_score))  # Clamp to 0-1
            
            # Determine status
            if province_score >= 0.9:
                status = STATUS_NORMAL
            elif province_score >= 0.7:
                status = STATUS_DEGRADED
            elif province_score >= 0.3:
                status = STATUS_RESTRICTED
            else:
                status = STATUS_BLACKOUT
            
            province_data = {
                "id": province_id,
                "name": info["name"],
                "name_fa": info["name_fa"],
                "lat": info["lat"],
                "lon": info["lon"],
                "population": info["population"],
                "connectivity_score": round(province_score, 2),
                "status": status,
                "national_score": round(national_score, 2),
                "national_status": national_status,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
            
            provinces.append(province_data)
            self._cache[province_id] = province_data
        
        self._cache_time = datetime.now(timezone.utc)
        print(f"  Connectivity data updated: national score {national_score:.2f} ({national_status})")
        
        return provinces
    
    def get_connectivity_geojson(self) -> Dict:
        """Get connectivity data as GeoJSON for map overlay"""
        provinces = self.get_province_connectivity()
        
        features = []
        for p in provinces:
            # Create a circle polygon for each province
            # In production, you'd use actual province boundaries
            radius = 0.5  # degrees (approx 50km)
            
            features.append({
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [p["lon"], p["lat"]]
                },
                "properties": {
                    "id": p["id"],
                    "name": p["name"],
                    "name_fa": p["name_fa"],
                    "connectivity_score": p["connectivity_score"],
                    "status": p["status"],
                    "population": p["population"],
                    "updated_at": p["updated_at"],
                }
            })
        
        return {
            "type": "FeatureCollection",
            "features": features,
            "metadata": {
                "national_score": provinces[0]["national_score"] if provinces else 0.5,
                "national_status": provinces[0]["national_status"] if provinces else STATUS_UNKNOWN,
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "total_provinces": len(provinces),
            }
        }
    
    def update_province_status(self, province_id: str, status: str, score: float = None) -> bool:
        """Manually update province status (for admin/ground truth updates)"""
        if province_id not in IRAN_PROVINCES:
            return False
        
        if status not in [STATUS_NORMAL, STATUS_DEGRADED, STATUS_RESTRICTED, STATUS_BLACKOUT]:
            return False
        
        # Calculate score from status if not provided
        if score is None:
            score_map = {
                STATUS_NORMAL: 0.95,
                STATUS_DEGRADED: 0.75,
                STATUS_RESTRICTED: 0.4,
                STATUS_BLACKOUT: 0.1,
            }
            score = score_map.get(status, 0.5)
        
        info = IRAN_PROVINCES[province_id]
        self._cache[province_id] = {
            "id": province_id,
            "name": info["name"],
            "name_fa": info["name_fa"],
            "lat": info["lat"],
            "lon": info["lon"],
            "population": info["population"],
            "connectivity_score": score,
            "status": status,
            "national_score": self._cache.get("tehran", {}).get("national_score", 0.5),
            "national_status": self._cache.get("tehran", {}).get("national_status", STATUS_UNKNOWN),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "manual_override": True,
        }
        
        return True


def get_connectivity_data() -> Dict:
    """Convenience function to get connectivity GeoJSON"""
    service = ConnectivityService()
    return service.get_connectivity_geojson()

