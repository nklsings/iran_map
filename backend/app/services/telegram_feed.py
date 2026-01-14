"""
Telegram Live Feed Service

Fetches messages from public Telegram channels, processes them with NLP,
and provides a live feed API for the frontend.
"""

import json
import re
import requests
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional, Tuple
from bs4 import BeautifulSoup
from sqlalchemy.orm import Session
from sqlalchemy import desc

from .. import models, schemas
from .persian_nlp import get_nlp_service, PersianNLPService


# ============================================================================
# MONITORED CHANNELS (Ordered by priority)
# ============================================================================
PRIORITY_CHANNELS = [
    # Human Rights (high priority)
    {"channel": "HengawO", "name": "Hengaw HR", "priority": 1, "category": "human_rights"},
    {"channel": "1500tasvir", "name": "1500Tasvir", "priority": 1, "category": "citizen_journalism"},
    {"channel": "IranHumanRights", "name": "Iran HR", "priority": 1, "category": "human_rights"},
    {"channel": "HranaEnglish", "name": "HRANA", "priority": 1, "category": "human_rights"},
    
    # News (medium priority)
    {"channel": "bbcpersian", "name": "BBC Persian", "priority": 2, "category": "news"},
    {"channel": "iranintl", "name": "Iran Intl", "priority": 2, "category": "news"},
    {"channel": "VOAfarsi", "name": "VOA Farsi", "priority": 2, "category": "news"},
    {"channel": "Farsi_Iranwire", "name": "IranWire", "priority": 2, "category": "news"},
    
    # Activist (medium priority)
    {"channel": "Iran_Revolutionn", "name": "Revolution", "priority": 2, "category": "activist"},
    {"channel": "iranworkers", "name": "Workers", "priority": 2, "category": "activist"},
    
    # OSINT (high priority)
    {"channel": "GeoConfirmed", "name": "GeoConfirmed", "priority": 1, "category": "osint"},
    {"channel": "MahsaAlerts", "name": "MahsaAlert", "priority": 1, "category": "osint"},
]


class TelegramFeedService:
    """
    Service to fetch and process Telegram messages for the live feed.
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.nlp = get_nlp_service()
    
    def fetch_channel_messages(self, channel: str, limit: int = 20) -> List[Dict]:
        """
        Fetch recent messages from a public Telegram channel.
        
        Args:
            channel: Channel username (without @)
            limit: Maximum messages to fetch
            
        Returns:
            List of message dictionaries
        """
        channel = channel.lstrip('@')
        messages = []
        
        try:
            url = f"https://t.me/s/{channel}"
            resp = requests.get(url, timeout=15, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            })
            
            if resp.status_code != 200:
                return []
            
            soup = BeautifulSoup(resp.text, 'html.parser')
            msg_wraps = soup.find_all('div', class_='tgme_widget_message_wrap')
            
            for wrap in msg_wraps[:limit]:
                try:
                    msg = self._parse_message(wrap, channel)
                    if msg:
                        messages.append(msg)
                except Exception as e:
                    continue
                    
        except Exception as e:
            print(f"  TelegramFeed: Error fetching @{channel} - {e}")
        
        return messages
    
    def _parse_message(self, wrap, channel: str) -> Optional[Dict]:
        """Parse a single message from HTML"""
        text_elem = wrap.find('div', class_='tgme_widget_message_text')
        if not text_elem:
            return None
        
        text = text_elem.get_text()
        if not text or len(text) < 10:
            return None
        
        # Get message ID from link
        link_elem = wrap.find('a', class_='tgme_widget_message_date')
        message_id = None
        source_url = f"https://t.me/{channel}"
        
        if link_elem and link_elem.get('href'):
            source_url = link_elem['href']
            # Extract message ID from URL like https://t.me/channel/12345
            match = re.search(r'/(\d+)$', source_url)
            if match:
                message_id = f"{channel}_{match.group(1)}"
        
        if not message_id:
            # Generate from content hash
            message_id = f"{channel}_{hash(text[:100])}"
        
        # Parse timestamp
        time_elem = wrap.find('time')
        timestamp = datetime.now(timezone.utc)
        if time_elem and time_elem.get('datetime'):
            try:
                timestamp = datetime.fromisoformat(time_elem['datetime'].replace('Z', '+00:00'))
            except:
                pass
        
        # Extract media
        media_url = None
        media_type = None
        
        # Photo
        photo_elem = wrap.find('a', class_='tgme_widget_message_photo_wrap')
        if photo_elem and photo_elem.get('style'):
            match = re.search(r"url\(['\"]?(https?://[^'\"]+)['\"]?\)", photo_elem['style'])
            if match:
                media_url = match.group(1)
                media_type = 'image'
        
        # Video
        if not media_url:
            video_elem = wrap.find('video')
            if video_elem and video_elem.get('src'):
                media_url = video_elem.get('src')
                media_type = 'video'
        
        return {
            "channel": channel,
            "message_id": message_id,
            "text": text,
            "timestamp": timestamp,
            "media_url": media_url,
            "media_type": media_type,
            "source_url": source_url,
        }
    
    def process_message(self, msg: Dict) -> Dict:
        """
        Process a message with NLP analysis.
        
        Args:
            msg: Message dictionary from fetch
            
        Returns:
            Enhanced message with NLP fields
        """
        text = msg.get("text", "")
        
        # Run NLP analysis
        analysis = self.nlp.analyze(text)
        
        # Add NLP results
        msg["keywords"] = json.dumps([k["keyword"] for k in analysis["keywords"][:10]])
        msg["locations_mentioned"] = json.dumps([
            {"city": loc["city"], "city_en": loc["city_en"]} 
            for loc in analysis["locations"]
        ])
        msg["sentiment"] = analysis["sentiment"]
        msg["urgency_score"] = analysis["urgency_score"]
        msg["event_type_detected"] = analysis["event_type"]
        msg["is_relevant"] = self.nlp.is_relevant(text)
        
        return msg
    
    def store_message(self, msg: Dict) -> Optional[models.TelegramMessage]:
        """
        Store a processed message in the database.
        
        Args:
            msg: Processed message dictionary
            
        Returns:
            Created TelegramMessage or None if duplicate
        """
        # Check for duplicate
        existing = self.db.query(models.TelegramMessage).filter(
            models.TelegramMessage.message_id == msg["message_id"]
        ).first()
        
        if existing:
            return None
        
        db_msg = models.TelegramMessage(
            channel=msg["channel"],
            message_id=msg["message_id"],
            text=msg["text"],
            media_url=msg.get("media_url"),
            media_type=msg.get("media_type"),
            timestamp=msg["timestamp"],
            keywords=msg.get("keywords"),
            locations_mentioned=msg.get("locations_mentioned"),
            sentiment=msg.get("sentiment"),
            urgency_score=msg.get("urgency_score", 0.5),
            event_type_detected=msg.get("event_type_detected"),
            is_processed=True,
            is_relevant=msg.get("is_relevant", True),
        )
        
        self.db.add(db_msg)
        return db_msg
    
    def fetch_and_process_all(self, channels: List[Dict] = None) -> int:
        """
        Fetch and process messages from all priority channels.
        
        Args:
            channels: Optional list of channel configs (uses DB or PRIORITY_CHANNELS if None)
            
        Returns:
            Number of new messages stored
        """
        if channels is None:
            # Try fetching from DB first
            try:
                db_channels = self.db.query(models.DataSource).filter(
                    models.DataSource.source_type == "telegram",
                    models.DataSource.is_active == True
                ).order_by(models.DataSource.priority).all()
                
                if db_channels:
                    channels = [
                        {
                            "channel": s.identifier, 
                            "name": s.name, 
                            "priority": s.priority,
                            "category": s.category
                        } 
                        for s in db_channels
                    ]
            except Exception as e:
                print(f"  TelegramFeed: Error fetching sources from DB - {e}")
        
        # Fallback to hardcoded if still None
        channels = channels or PRIORITY_CHANNELS
        
        total_stored = 0
        
        for config in channels:
            channel = config["channel"]
            print(f"  Fetching @{channel}...")
            
            messages = self.fetch_channel_messages(channel, limit=15)
            stored = 0
            
            for msg in messages:
                processed = self.process_message(msg)
                result = self.store_message(processed)
                if result:
                    stored += 1
            
            if stored > 0:
                print(f"    -> {stored} new messages")
                total_stored += stored
        
        if total_stored > 0:
            self.db.commit()
            print(f"  Total: {total_stored} new messages stored")
        
        return total_stored
    
    def get_feed(
        self,
        limit: int = 50,
        offset: int = 0,
        channel: Optional[str] = None,
        min_urgency: float = 0.0,
        relevant_only: bool = True,
        hours: int = 24
    ) -> Tuple[List[models.TelegramMessage], int]:
        """
        Get messages for the live feed.
        
        Args:
            limit: Maximum messages to return
            offset: Pagination offset
            channel: Filter by channel (optional)
            min_urgency: Minimum urgency score (0-1)
            relevant_only: Only return relevant messages
            hours: Limit to messages from last N hours
            
        Returns:
            Tuple of (messages, total_count)
        """
        try:
            query = self.db.query(models.TelegramMessage)
            
            # Time filter
            cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
            query = query.filter(models.TelegramMessage.timestamp >= cutoff)
            
            # Channel filter
            if channel:
                query = query.filter(models.TelegramMessage.channel == channel)
            
            # Urgency filter
            if min_urgency > 0:
                query = query.filter(models.TelegramMessage.urgency_score >= min_urgency)
            
            # Relevance filter
            if relevant_only:
                query = query.filter(models.TelegramMessage.is_relevant == True)
            
            # Get total count
            total = query.count()
            
            # Order by urgency (highest first) then timestamp
            messages = query.order_by(
                desc(models.TelegramMessage.urgency_score),
                desc(models.TelegramMessage.timestamp)
            ).offset(offset).limit(limit).all()
            
            return messages, total
        except Exception as e:
            print(f"  TelegramFeed: Error getting feed - {e}")
            return [], 0
    
    def get_channels(self) -> List[str]:
        """Get list of channels with stored messages"""
        try:
            channels = self.db.query(models.TelegramMessage.channel).distinct().all()
            return [c[0] for c in channels]
        except Exception as e:
            print(f"  TelegramFeed: Error getting channels - {e}")
            return []
    
    def get_high_urgency(self, threshold: float = 0.8, limit: int = 10) -> List[models.TelegramMessage]:
        """Get recent high-urgency messages"""
        try:
            cutoff = datetime.now(timezone.utc) - timedelta(hours=12)
            
            return self.db.query(models.TelegramMessage).filter(
                models.TelegramMessage.timestamp >= cutoff,
                models.TelegramMessage.urgency_score >= threshold,
                models.TelegramMessage.is_relevant == True
            ).order_by(
                desc(models.TelegramMessage.urgency_score),
                desc(models.TelegramMessage.timestamp)
            ).limit(limit).all()
        except Exception as e:
            print(f"  TelegramFeed: Error getting high urgency - {e}")
            return []
    
    def cleanup_old_messages(self, days: int = 7) -> int:
        """Remove messages older than N days"""
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        
        deleted = self.db.query(models.TelegramMessage).filter(
            models.TelegramMessage.timestamp < cutoff
        ).delete()
        
        self.db.commit()
        return deleted


def fetch_telegram_feed(db: Session) -> int:
    """Convenience function for scheduled tasks"""
    service = TelegramFeedService(db)
    return service.fetch_and_process_all()

