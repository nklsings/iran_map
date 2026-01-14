"""
City Analytics Service

Provides aggregated statistics and analytics for cities based on event data.
Includes:
- Event counts by type and city
- Hourly activity patterns
- Trend analysis
- City rankings
"""

import json
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional, Tuple
from collections import defaultdict
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, and_

from .. import models


# ============================================================================
# IRANIAN CITIES FOR ANALYTICS
# ============================================================================
ANALYTICS_CITIES = {
    "Tehran": {"lat": 35.6892, "lon": 51.3890, "fa": "تهران", "province": "Tehran"},
    "Isfahan": {"lat": 32.6546, "lon": 51.6680, "fa": "اصفهان", "province": "Isfahan"},
    "Mashhad": {"lat": 36.2605, "lon": 59.6168, "fa": "مشهد", "province": "Razavi Khorasan"},
    "Tabriz": {"lat": 38.0962, "lon": 46.2919, "fa": "تبریز", "province": "East Azerbaijan"},
    "Shiraz": {"lat": 29.5918, "lon": 52.5837, "fa": "شیراز", "province": "Fars"},
    "Karaj": {"lat": 35.8400, "lon": 50.9391, "fa": "کرج", "province": "Alborz"},
    "Ahvaz": {"lat": 31.3183, "lon": 48.6706, "fa": "اهواز", "province": "Khuzestan"},
    "Qom": {"lat": 34.6416, "lon": 50.8746, "fa": "قم", "province": "Qom"},
    
    # Kurdish region
    "Sanandaj": {"lat": 35.3145, "lon": 46.9923, "fa": "سنندج", "province": "Kurdistan"},
    "Mahabad": {"lat": 36.7631, "lon": 45.7222, "fa": "مهاباد", "province": "West Azerbaijan"},
    "Urmia": {"lat": 37.5527, "lon": 45.0761, "fa": "ارومیه", "province": "West Azerbaijan"},
    "Kermanshah": {"lat": 34.3142, "lon": 47.0650, "fa": "کرمانشاه", "province": "Kermanshah"},
    "Saqqez": {"lat": 36.2500, "lon": 46.2667, "fa": "سقز", "province": "Kurdistan"},
    "Bukan": {"lat": 36.5214, "lon": 46.2086, "fa": "بوکان", "province": "West Azerbaijan"},
    
    # Baluchistan
    "Zahedan": {"lat": 29.4963, "lon": 60.8629, "fa": "زاهدان", "province": "Sistan and Baluchestan"},
    "Chabahar": {"lat": 25.2919, "lon": 60.6430, "fa": "چابهار", "province": "Sistan and Baluchestan"},
    
    # Other cities
    "Rasht": {"lat": 37.2808, "lon": 49.5832, "fa": "رشت", "province": "Gilan"},
    "Kerman": {"lat": 30.2839, "lon": 57.0834, "fa": "کرمان", "province": "Kerman"},
    "Yazd": {"lat": 31.8974, "lon": 54.3569, "fa": "یزد", "province": "Yazd"},
    "Bandar Abbas": {"lat": 27.1832, "lon": 56.2666, "fa": "بندرعباس", "province": "Hormozgan"},
    "Hamadan": {"lat": 34.7990, "lon": 48.5150, "fa": "همدان", "province": "Hamadan"},
    "Arak": {"lat": 34.0954, "lon": 49.7013, "fa": "اراک", "province": "Markazi"},
    "Ardabil": {"lat": 38.2498, "lon": 48.2933, "fa": "اردبیل", "province": "Ardabil"},
    "Gorgan": {"lat": 36.8427, "lon": 54.4353, "fa": "گرگان", "province": "Golestan"},
    "Zanjan": {"lat": 36.6736, "lon": 48.4787, "fa": "زنجان", "province": "Zanjan"},
    "Sari": {"lat": 36.5633, "lon": 53.0601, "fa": "ساری", "province": "Mazandaran"},
    "Qazvin": {"lat": 36.2688, "lon": 50.0041, "fa": "قزوین", "province": "Qazvin"},
    "Khorramabad": {"lat": 33.4878, "lon": 48.3558, "fa": "خرم‌آباد", "province": "Lorestan"},
    "Ilam": {"lat": 33.6374, "lon": 46.4227, "fa": "ایلام", "province": "Ilam"},
    "Bushehr": {"lat": 28.9684, "lon": 50.8385, "fa": "بوشهر", "province": "Bushehr"},
    "Semnan": {"lat": 35.5769, "lon": 53.3970, "fa": "سمنان", "province": "Semnan"},
}


class CityAnalyticsService:
    """
    Service for computing and caching city-level analytics.
    """
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_city_from_event(self, event: models.ProtestEvent) -> Optional[str]:
        """
        Determine which city an event belongs to based on coordinates.
        Uses simple distance calculation.
        """
        if not event.latitude or not event.longitude:
            return None
        
        # Find closest city within 50km
        min_dist = float('inf')
        closest_city = None
        
        for city_name, data in ANALYTICS_CITIES.items():
            # Simple Euclidean distance (approximate for small distances)
            dist = ((event.latitude - data["lat"]) ** 2 + 
                   (event.longitude - data["lon"]) ** 2) ** 0.5
            
            if dist < min_dist:
                min_dist = dist
                closest_city = city_name
        
        # Roughly 0.5 degrees ≈ 50km at Iran's latitude
        if min_dist < 0.5:
            return closest_city
        
        return None
    
    def compute_city_stats(self, city_name: str, days: int = 30) -> Dict:
        """
        Compute statistics for a single city.
        
        Args:
            city_name: Name of the city
            days: Number of days to analyze
            
        Returns:
            Dictionary of statistics
        """
        if city_name not in ANALYTICS_CITIES:
            return {}
        
        city_data = ANALYTICS_CITIES[city_name]
        lat, lon = city_data["lat"], city_data["lon"]
        
        try:
            # Define bounding box (roughly 30km radius)
            delta = 0.3  # ~30km
            min_lat, max_lat = lat - delta, lat + delta
            min_lon, max_lon = lon - delta, lon + delta
            
            now = datetime.now(timezone.utc)
            period_start = now - timedelta(days=days)
            
            # Query events in bounding box
            events = self.db.query(models.ProtestEvent).filter(
                and_(
                    models.ProtestEvent.latitude >= min_lat,
                    models.ProtestEvent.latitude <= max_lat,
                    models.ProtestEvent.longitude >= min_lon,
                    models.ProtestEvent.longitude <= max_lon,
                    models.ProtestEvent.timestamp >= period_start
                )
            ).all()
            
            # Compute statistics
            total = len(events)
            
            # By event type
            type_counts = defaultdict(int)
            for e in events:
                type_counts[e.event_type or "protest"] += 1
            
            # Last 24 hours
            cutoff_24h = now - timedelta(hours=24)
            events_24h = sum(1 for e in events if e.timestamp and e.timestamp >= cutoff_24h)
            
            # Last 7 days
            cutoff_7d = now - timedelta(days=7)
            events_7d = sum(1 for e in events if e.timestamp and e.timestamp >= cutoff_7d)
            
            # Hourly pattern
            hourly = defaultdict(int)
            for e in events:
                if e.timestamp:
                    hour = e.timestamp.hour
                    hourly[hour] += 1
            
            # Find peak hour
            peak_hour = max(hourly, key=hourly.get) if hourly else None
            
            # Trend calculation (compare last 7 days to previous 7 days)
            cutoff_prev_7d = now - timedelta(days=14)
            events_prev_7d = sum(1 for e in events 
                               if e.timestamp and e.timestamp >= cutoff_prev_7d and e.timestamp < cutoff_7d)
            
            if events_prev_7d > 0:
                trend_pct = ((events_7d - events_prev_7d) / events_prev_7d) * 100
            else:
                trend_pct = 100 if events_7d > 0 else 0
            
            if trend_pct > 20:
                trend_dir = "up"
            elif trend_pct < -20:
                trend_dir = "down"
            else:
                trend_dir = "stable"
            
            # Activity level
            if events_24h >= 10:
                activity = "critical"
            elif events_24h >= 5:
                activity = "high"
            elif events_24h >= 2:
                activity = "medium"
            else:
                activity = "low"
            
            return {
                "city_name": city_name,
                "city_name_fa": city_data["fa"],
                "latitude": lat,
                "longitude": lon,
                "province": city_data["province"],
                "total_events": total,
                "protest_count": type_counts.get("protest", 0),
                "clash_count": type_counts.get("clash", 0),
                "arrest_count": type_counts.get("arrest", 0),
                "police_count": type_counts.get("police_presence", 0),
                "strike_count": type_counts.get("strike", 0),
                "events_24h": events_24h,
                "events_7d": events_7d,
                "trend_direction": trend_dir,
                "trend_percentage": round(trend_pct, 1),
                "hourly_pattern": dict(hourly),
                "peak_hour": peak_hour,
                "avg_daily_events": round(total / days, 2) if days > 0 else 0,
                "activity_level": activity,
                "period_start": period_start,
                "period_end": now,
            }
        except Exception as e:
            print(f"  CityAnalytics: Error computing stats for {city_name} - {e}")
            now = datetime.now(timezone.utc)
            return {
                "city_name": city_name,
                "city_name_fa": city_data["fa"],
                "latitude": lat,
                "longitude": lon,
                "province": city_data["province"],
                "total_events": 0,
                "protest_count": 0,
                "clash_count": 0,
                "arrest_count": 0,
                "police_count": 0,
                "strike_count": 0,
                "events_24h": 0,
                "events_7d": 0,
                "trend_direction": "stable",
                "trend_percentage": 0.0,
                "hourly_pattern": {},
                "peak_hour": None,
                "avg_daily_events": 0.0,
                "activity_level": "low",
                "period_start": now - timedelta(days=days),
                "period_end": now,
            }
    
    def compute_all_cities(self, days: int = 30) -> List[Dict]:
        """
        Compute statistics for all cities.
        
        Returns:
            List of city statistics sorted by activity
        """
        stats = []
        
        for city_name in ANALYTICS_CITIES:
            city_stats = self.compute_city_stats(city_name, days)
            if city_stats:
                stats.append(city_stats)
        
        # Sort by 24h events, then 7d events
        stats.sort(key=lambda x: (x["events_24h"], x["events_7d"]), reverse=True)
        
        # Add rank
        for i, s in enumerate(stats):
            s["rank"] = i + 1
        
        return stats
    
    def get_city_ranking(self, limit: int = 20) -> List[Dict]:
        """
        Get top cities by activity.
        
        Args:
            limit: Maximum cities to return
            
        Returns:
            List of city rankings
        """
        all_stats = self.compute_all_cities(days=30)
        return all_stats[:limit]
    
    def get_hourly_distribution(self, days: int = 7) -> Dict[int, int]:
        """
        Get hourly distribution of events across all cities.
        
        Returns:
            Dictionary mapping hour (0-23) to event count
        """
        try:
            cutoff = datetime.now(timezone.utc) - timedelta(days=days)
            
            events = self.db.query(models.ProtestEvent).filter(
                models.ProtestEvent.timestamp >= cutoff
            ).all()
            
            hourly = defaultdict(int)
            for e in events:
                if e.timestamp:
                    hour = e.timestamp.hour
                    hourly[hour] += 1
            
            # Ensure all hours are present
            return {h: hourly.get(h, 0) for h in range(24)}
        except Exception as e:
            print(f"  CityAnalytics: Error getting hourly distribution - {e}")
            return {h: 0 for h in range(24)}
    
    def get_event_type_distribution(self, days: int = 30) -> Dict[str, int]:
        """
        Get distribution of event types.
        
        Returns:
            Dictionary mapping event type to count
        """
        try:
            cutoff = datetime.now(timezone.utc) - timedelta(days=days)
            
            events = self.db.query(models.ProtestEvent).filter(
                models.ProtestEvent.timestamp >= cutoff
            ).all()
            
            types = defaultdict(int)
            for e in events:
                event_type = e.event_type or "protest"
                types[event_type] += 1
            
            return dict(types)
        except Exception as e:
            print(f"  CityAnalytics: Error getting event type distribution - {e}")
            return {}
    
    def get_analytics_summary(self) -> Dict:
        """
        Get overall analytics summary.
        
        Returns:
            Summary dictionary with key metrics
        """
        try:
            now = datetime.now(timezone.utc)
            cutoff_24h = now - timedelta(hours=24)
            cutoff_7d = now - timedelta(days=7)
            
            # Total events
            total_events = self.db.query(models.ProtestEvent).count()
            events_24h = self.db.query(models.ProtestEvent).filter(
                models.ProtestEvent.timestamp >= cutoff_24h
            ).count()
            events_7d = self.db.query(models.ProtestEvent).filter(
                models.ProtestEvent.timestamp >= cutoff_7d
            ).count()
            
            # Get rankings
            top_cities = self.get_city_ranking(limit=10)
            
            # Most active city
            most_active = top_cities[0]["city_name"] if top_cities else None
            
            # Hourly distribution
            hourly = self.get_hourly_distribution(days=7)
            most_active_hour = max(hourly, key=hourly.get) if hourly else None
            
            # Event type distribution
            type_dist = self.get_event_type_distribution(days=30)
            
            return {
                "total_cities": len(ANALYTICS_CITIES),
                "total_events": total_events,
                "events_24h": events_24h,
                "events_7d": events_7d,
                "most_active_city": most_active,
                "most_active_hour": most_active_hour,
                "top_cities": top_cities,
                "hourly_distribution": hourly,
                "event_type_distribution": type_dist,
            }
        except Exception as e:
            print(f"  CityAnalytics: Error getting summary - {e}")
            return {
                "total_cities": len(ANALYTICS_CITIES),
                "total_events": 0,
                "events_24h": 0,
                "events_7d": 0,
                "most_active_city": None,
                "most_active_hour": None,
                "top_cities": [],
                "hourly_distribution": {h: 0 for h in range(24)},
                "event_type_distribution": {},
            }
    
    def update_city_statistics(self) -> int:
        """
        Update stored city statistics in the database.
        Called periodically by scheduler.
        
        Returns:
            Number of cities updated
        """
        count = 0
        now = datetime.now(timezone.utc)
        period_start = now - timedelta(days=30)
        
        for city_name in ANALYTICS_CITIES:
            stats = self.compute_city_stats(city_name, days=30)
            
            if not stats:
                continue
            
            # Check if exists
            existing = self.db.query(models.CityStatistics).filter(
                models.CityStatistics.city_name == city_name
            ).first()
            
            if existing:
                # Update
                existing.city_name_fa = stats["city_name_fa"]
                existing.latitude = stats["latitude"]
                existing.longitude = stats["longitude"]
                existing.province = stats["province"]
                existing.total_events = stats["total_events"]
                existing.protest_count = stats["protest_count"]
                existing.clash_count = stats["clash_count"]
                existing.arrest_count = stats["arrest_count"]
                existing.police_count = stats["police_count"]
                existing.strike_count = stats["strike_count"]
                existing.events_24h = stats["events_24h"]
                existing.events_7d = stats["events_7d"]
                existing.trend_direction = stats["trend_direction"]
                existing.trend_percentage = stats["trend_percentage"]
                existing.hourly_pattern = json.dumps(stats["hourly_pattern"])
                existing.peak_hour = stats["peak_hour"]
                existing.avg_daily_events = stats["avg_daily_events"]
                existing.activity_level = stats["activity_level"]
                existing.period_start = period_start
                existing.period_end = now
            else:
                # Create new
                db_stats = models.CityStatistics(
                    city_name=city_name,
                    city_name_fa=stats["city_name_fa"],
                    latitude=stats["latitude"],
                    longitude=stats["longitude"],
                    province=stats["province"],
                    total_events=stats["total_events"],
                    protest_count=stats["protest_count"],
                    clash_count=stats["clash_count"],
                    arrest_count=stats["arrest_count"],
                    police_count=stats["police_count"],
                    strike_count=stats["strike_count"],
                    events_24h=stats["events_24h"],
                    events_7d=stats["events_7d"],
                    trend_direction=stats["trend_direction"],
                    trend_percentage=stats["trend_percentage"],
                    hourly_pattern=json.dumps(stats["hourly_pattern"]),
                    peak_hour=stats["peak_hour"],
                    avg_daily_events=stats["avg_daily_events"],
                    activity_level=stats["activity_level"],
                    period_start=period_start,
                    period_end=now,
                )
                self.db.add(db_stats)
            
            count += 1
        
        self.db.commit()
        return count


def update_analytics(db: Session) -> int:
    """Convenience function for scheduler"""
    service = CityAnalyticsService(db)
    return service.update_city_statistics()

