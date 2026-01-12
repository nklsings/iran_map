"""
AI-Powered Situation Summary Service

Generates periodic summaries of the situation in Iran using OpenAI GPT models.
Analyzes collected events and produces:
- Executive summary
- Key developments
- Active hotspots
- Risk assessment
"""

import os
import json
import time
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func

from .. import models, schemas

# OpenAI client - lazy loaded
_openai_client = None


def get_openai_client():
    """Lazy-load OpenAI client"""
    global _openai_client
    if _openai_client is None:
        try:
            from openai import OpenAI
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                print("⚠ OPENAI_API_KEY not set - summaries will use fallback")
                return None
            _openai_client = OpenAI(api_key=api_key)
        except ImportError:
            print("⚠ OpenAI package not installed")
            return None
    return _openai_client


# Iranian city names for location extraction
IRAN_CITIES = [
    "Tehran", "Mashhad", "Isfahan", "Karaj", "Shiraz", "Tabriz", "Qom",
    "Ahvaz", "Kermanshah", "Urmia", "Rasht", "Zahedan", "Kerman", "Yazd",
    "Arak", "Ardabil", "Bandar Abbas", "Hamadan", "Sanandaj", "Zanjan",
    "Qazvin", "Sari", "Gorgan", "Birjand", "Bushehr", "Khorramabad",
    "Ilam", "Bojnurd", "Semnan", "Yasuj", "Shahrekord", "Esfahan",
    "Mahabad", "Bukan", "Saqqez", "Marivan", "Javanrud", "Piranshahr",
    "Izeh", "Dezful", "Abadan", "Khorramshahr", "Khuzestan", "Kurdistan",
    "Baluchistan", "Sistan", "Azerbaijan", "Gilan", "Mazandaran"
]


class SummaryService:
    """Service for generating AI-powered situation summaries"""
    
    MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    HOURS_WINDOW = 12  # Analyze last 12 hours
    
    def __init__(self, db: Session):
        self.db = db
        self.client = get_openai_client()
    
    def get_current_summary(self) -> Optional[models.SituationSummary]:
        """Get the most recent summary"""
        return self.db.query(models.SituationSummary).filter(
            models.SituationSummary.is_current == True
        ).order_by(models.SituationSummary.created_at.desc()).first()
    
    def get_summary_history(self, limit: int = 24) -> List[models.SituationSummary]:
        """Get summary history (last 24 hours worth)"""
        return self.db.query(models.SituationSummary).order_by(
            models.SituationSummary.created_at.desc()
        ).limit(limit).all()
    
    def collect_events_for_summary(self, hours: int = None) -> Tuple[List[models.ProtestEvent], Dict]:
        """Collect events and statistics for summary generation"""
        hours = hours or self.HOURS_WINDOW
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        
        # Get all events in the window
        events = self.db.query(models.ProtestEvent).filter(
            models.ProtestEvent.timestamp >= cutoff
        ).order_by(models.ProtestEvent.timestamp.desc()).all()
        
        # Calculate statistics
        stats = {
            'total': len(events),
            'protest': 0,
            'clash': 0,
            'arrest': 0,
            'police_presence': 0,
            'strike': 0,
            'verified': 0,
            'by_source': {},
            'by_location': {},
        }
        
        for event in events:
            event_type = event.event_type or 'protest'
            if event_type in stats:
                stats[event_type] += 1
            if event.verified:
                stats['verified'] += 1
            
            # Track sources
            platform = event.source_platform or 'unknown'
            stats['by_source'][platform] = stats['by_source'].get(platform, 0) + 1
            
            # Extract city mentions for location tracking
            title_lower = event.title.lower() if event.title else ''
            for city in IRAN_CITIES:
                if city.lower() in title_lower:
                    stats['by_location'][city] = stats['by_location'].get(city, 0) + 1
        
        return events, stats
    
    def format_events_for_prompt(self, events: List[models.ProtestEvent], max_events: int = 50) -> str:
        """Format events into a text summary for the AI prompt"""
        if not events:
            return "No events reported in this period."
        
        # Take most recent events
        selected = events[:max_events]
        
        lines = []
        for event in selected:
            timestamp = event.timestamp.strftime("%H:%M") if event.timestamp else "Unknown"
            verified = "✓" if event.verified else ""
            event_type = event.event_type or "protest"
            title = event.title[:100] if event.title else "No title"
            
            lines.append(f"[{timestamp}] [{event_type.upper()}]{verified} {title}")
        
        return "\n".join(lines)
    
    def generate_summary(self, force: bool = False) -> Optional[models.SituationSummary]:
        """Generate a new situation summary using OpenAI"""
        start_time = time.time()
        
        # Collect data
        events, stats = self.collect_events_for_summary()
        
        if stats['total'] == 0 and not force:
            print("  No events to summarize")
            return None
        
        # Period info
        period_end = datetime.now(timezone.utc)
        period_start = period_end - timedelta(hours=self.HOURS_WINDOW)
        
        # Format events for prompt
        events_text = self.format_events_for_prompt(events)
        
        # Build prompt
        system_prompt = """You are an expert analyst providing situation reports on civil unrest and protests in Iran. 
Your role is to synthesize event reports into clear, actionable intelligence summaries.

Guidelines:
- Be objective and factual
- Highlight significant patterns and developments
- Identify geographic hotspots
- Assess risk levels based on event intensity and type
- Use clear, professional language
- Focus on verified information when available
- Note any limitations in the data"""

        user_prompt = f"""Generate a situation summary for Iran based on the following event reports from the last {self.HOURS_WINDOW} hours.

STATISTICS:
- Total Events: {stats['total']}
- Protests: {stats['protest']}
- Clashes: {stats['clash']}
- Arrests: {stats['arrest']}
- Police Presence Reports: {stats['police_presence']}
- Strikes: {stats['strike']}
- Verified Events: {stats['verified']}

TOP LOCATIONS:
{json.dumps(dict(sorted(stats['by_location'].items(), key=lambda x: -x[1])[:10]), indent=2)}

EVENT REPORTS:
{events_text}

Please provide your analysis in the following JSON format:
{{
    "title": "Brief headline summarizing the situation (max 100 chars)",
    "summary": "2-3 paragraph executive summary of the current situation",
    "key_developments": [
        "Development 1",
        "Development 2",
        "Development 3"
    ],
    "hotspots": [
        {{"city": "City Name", "activity_level": "high/medium/low", "notes": "Brief description"}},
    ],
    "risk_assessment": "Overall risk assessment paragraph with threat level (CRITICAL/HIGH/ELEVATED/MODERATE/LOW)"
}}"""

        # Try to generate with OpenAI
        if self.client:
            try:
                response = self.client.chat.completions.create(
                    model=self.MODEL,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=0.3,
                    max_tokens=2000,
                    response_format={"type": "json_object"}
                )
                
                content = response.choices[0].message.content
                tokens_used = response.usage.total_tokens if response.usage else 0
                
                # Parse the response
                try:
                    result = json.loads(content)
                except json.JSONDecodeError:
                    print("  Failed to parse OpenAI response as JSON")
                    result = self._generate_fallback_summary(stats, events)
                
            except Exception as e:
                print(f"  OpenAI API error: {e}")
                result = self._generate_fallback_summary(stats, events)
                tokens_used = 0
        else:
            # Fallback when OpenAI is not available
            result = self._generate_fallback_summary(stats, events)
            tokens_used = 0
        
        generation_time = int((time.time() - start_time) * 1000)
        
        # Mark previous summaries as not current
        self.db.query(models.SituationSummary).filter(
            models.SituationSummary.is_current == True
        ).update({"is_current": False})
        
        # Create new summary
        summary = models.SituationSummary(
            title=result.get('title', 'Situation Summary')[:200],
            summary=result.get('summary', 'No summary available'),
            key_developments=json.dumps(result.get('key_developments', [])),
            hotspots=json.dumps(result.get('hotspots', [])),
            risk_assessment=result.get('risk_assessment', 'Unable to assess'),
            event_count=stats['total'],
            protest_count=stats['protest'],
            clash_count=stats['clash'],
            arrest_count=stats['arrest'],
            police_count=stats['police_presence'],
            period_start=period_start,
            period_end=period_end,
            model_used=self.MODEL if self.client else "fallback",
            tokens_used=tokens_used,
            generation_time_ms=generation_time,
            is_current=True
        )
        
        self.db.add(summary)
        self.db.commit()
        self.db.refresh(summary)
        
        print(f"  ✓ Summary generated: {summary.title[:50]}... ({tokens_used} tokens, {generation_time}ms)")
        return summary
    
    def _generate_fallback_summary(self, stats: Dict, events: List) -> Dict:
        """Generate a basic summary without AI when OpenAI is unavailable"""
        
        # Determine activity level
        total = stats['total']
        if total == 0:
            level = "QUIET"
            desc = "minimal activity"
        elif total < 10:
            level = "LOW"
            desc = "limited activity"
        elif total < 30:
            level = "MODERATE"
            desc = "moderate activity"
        elif total < 50:
            level = "ELEVATED"
            desc = "significant activity"
        else:
            level = "HIGH"
            desc = "high activity levels"
        
        # Get top locations
        top_locations = sorted(stats['by_location'].items(), key=lambda x: -x[1])[:5]
        hotspots = [
            {
                "city": city,
                "activity_level": "high" if count > 5 else "medium" if count > 2 else "low",
                "notes": f"{count} events reported"
            }
            for city, count in top_locations
        ]
        
        # Key developments
        developments = []
        if stats['clash'] > 0:
            developments.append(f"{stats['clash']} clash(es) reported between protesters and security forces")
        if stats['arrest'] > 0:
            developments.append(f"{stats['arrest']} arrest(s) documented")
        if stats['police_presence'] > 0:
            developments.append(f"{stats['police_presence']} police presence reports filed")
        if stats['protest'] > 0:
            developments.append(f"{stats['protest']} protest event(s) recorded")
        if stats['strike'] > 0:
            developments.append(f"{stats['strike']} strike action(s) reported")
        
        if not developments:
            developments = ["No significant developments in this reporting period"]
        
        return {
            "title": f"Iran Situation Report: {level} Activity - {total} Events",
            "summary": f"""Over the past {self.HOURS_WINDOW} hours, monitoring systems have recorded {total} events across Iran, indicating {desc}.

Of these events, {stats['verified']} have been verified through multiple sources. The breakdown includes {stats['protest']} protest events, {stats['clash']} clashes, {stats['arrest']} arrests, and {stats['police_presence']} police presence reports.

{"Key areas of activity include " + ", ".join([loc[0] for loc in top_locations[:3]]) + "." if top_locations else "Activity is distributed across multiple regions."}""",
            "key_developments": developments[:5],
            "hotspots": hotspots,
            "risk_assessment": f"Current threat level: {level}. Based on {total} recorded events in the past {self.HOURS_WINDOW} hours. {'Exercise caution in all areas.' if level in ['HIGH', 'ELEVATED'] else 'Standard monitoring continues.'}"
        }
    
    def format_for_response(self, summary: models.SituationSummary) -> Dict:
        """Format a summary model for API response"""
        try:
            key_developments = json.loads(summary.key_developments) if summary.key_developments else []
        except json.JSONDecodeError:
            key_developments = []
        
        try:
            hotspots = json.loads(summary.hotspots) if summary.hotspots else []
        except json.JSONDecodeError:
            hotspots = []
        
        return {
            "id": summary.id,
            "title": summary.title,
            "summary": summary.summary,
            "key_developments": key_developments,
            "hotspots": hotspots,
            "risk_assessment": summary.risk_assessment,
            "stats": {
                "total": summary.event_count,
                "protests": summary.protest_count,
                "clashes": summary.clash_count,
                "arrests": summary.arrest_count,
                "police_presence": summary.police_count,
            },
            "period": {
                "start": summary.period_start.isoformat() if summary.period_start else None,
                "end": summary.period_end.isoformat() if summary.period_end else None,
                "hours": self.HOURS_WINDOW,
            },
            "generated_at": summary.created_at.isoformat() if summary.created_at else None,
            "model": summary.model_used,
            "tokens_used": summary.tokens_used,
            "generation_time_ms": summary.generation_time_ms,
        }


def generate_hourly_summary(db: Session) -> Optional[models.SituationSummary]:
    """Convenience function for scheduled task"""
    service = SummaryService(db)
    return service.generate_summary()

