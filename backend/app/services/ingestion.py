from abc import ABC, abstractmethod
from typing import List, Dict, Tuple, Optional
import feedparser
import requests
import random
import re
from datetime import datetime, timezone
from bs4 import BeautifulSoup
from .. import models, schemas
from sqlalchemy.orm import Session
from geoalchemy2.elements import WKTElement

# Iranian cities with coordinates for geo-inference
IRAN_CITIES: Dict[str, Tuple[float, float]] = {
    # Major cities
    "tehran": (35.6892, 51.3890),
    "تهران": (35.6892, 51.3890),
    "isfahan": (32.6546, 51.6680),
    "اصفهان": (32.6546, 51.6680),
    "mashhad": (36.2605, 59.6168),
    "مشهد": (36.2605, 59.6168),
    "tabriz": (38.0962, 46.2919),
    "تبریز": (38.0962, 46.2919),
    "shiraz": (29.5918, 52.5837),
    "شیراز": (29.5918, 52.5837),
    "karaj": (35.8400, 50.9391),
    "کرج": (35.8400, 50.9391),
    "ahvaz": (31.3183, 48.6706),
    "اهواز": (31.3183, 48.6706),
    "qom": (34.6416, 50.8746),
    "قم": (34.6416, 50.8746),
    # Kurdish cities
    "sanandaj": (35.3145, 46.9923),
    "سنندج": (35.3145, 46.9923),
    "mahabad": (36.7631, 45.7222),
    "مهاباد": (36.7631, 45.7222),
    "urmia": (37.5527, 45.0761),
    "ارومیه": (37.5527, 45.0761),
    "kermanshah": (34.3142, 47.0650),
    "کرمانشاه": (34.3142, 47.0650),
    # Baluchistan
    "zahedan": (29.4963, 60.8629),
    "زاهدان": (29.4963, 60.8629),
    "chabahar": (25.2919, 60.6430),
    "چابهار": (25.2919, 60.6430),
    # Other major cities
    "rasht": (37.2808, 49.5832),
    "رشت": (37.2808, 49.5832),
    "kerman": (30.2839, 57.0834),
    "کرمان": (30.2839, 57.0834),
    "yazd": (31.8974, 54.3569),
    "یزد": (31.8974, 54.3569),
    "bandar abbas": (27.1832, 56.2666),
    "بندرعباس": (27.1832, 56.2666),
    "hamadan": (34.7990, 48.5150),
    "همدان": (34.7990, 48.5150),
    "arak": (34.0954, 49.7013),
    "اراک": (34.0954, 49.7013),
    "ardabil": (38.2498, 48.2933),
    "اردبیل": (38.2498, 48.2933),
    "gorgan": (36.8427, 54.4353),
    "گرگان": (36.8427, 54.4353),
    "zanjan": (36.6736, 48.4787),
    "زنجان": (36.6736, 48.4787),
    "sari": (36.5633, 53.0601),
    "ساری": (36.5633, 53.0601),
    "qazvin": (36.2688, 50.0041),
    "قزوین": (36.2688, 50.0041),
    "borujerd": (33.8974, 48.7516),
    "بروجرد": (33.8974, 48.7516),
    "dezful": (32.3811, 48.4018),
    "دزفول": (32.3811, 48.4018),
    "kashan": (33.9850, 51.4100),
    "کاشان": (33.9850, 51.4100),
    # Universities
    "sharif": (35.7022, 51.3513),
    "دانشگاه شریف": (35.7022, 51.3513),
    "amirkabir": (35.7005, 51.4056),
    "دانشگاه امیرکبیر": (35.7005, 51.4056),
    "tehran university": (35.7129, 51.3981),
    "دانشگاه تهران": (35.7129, 51.3981),
    # Additional cities
    "ilam": (33.6374, 46.4227),
    "ایلام": (33.6374, 46.4227),
    "bojnurd": (37.4747, 57.3290),
    "بجنورد": (37.4747, 57.3290),
    "bushehr": (28.9684, 50.8385),
    "بوشهر": (28.9684, 50.8385),
    "birjand": (32.8663, 59.2211),
    "بیرجند": (32.8663, 59.2211),
    "khorramabad": (33.4878, 48.3558),
    "خرم‌آباد": (33.4878, 48.3558),
    "semnan": (35.5769, 53.3970),
    "سمنان": (35.5769, 53.3970),
    "shahr-e kord": (32.3256, 50.8645),
    "شهرکرد": (32.3256, 50.8645),
    "yasuj": (30.6684, 51.5880),
    "یاسوج": (30.6684, 51.5880),
}

# International cities with Iranian diaspora (for solidarity protests)
DIASPORA_CITIES: Dict[str, Tuple[float, float]] = {
    # Europe
    "stockholm": (59.3293, 18.0686),
    "استکهلم": (59.3293, 18.0686),
    "london": (51.5074, -0.1278),
    "لندن": (51.5074, -0.1278),
    "berlin": (52.5200, 13.4050),
    "برلین": (52.5200, 13.4050),
    "paris": (48.8566, 2.3522),
    "پاریس": (48.8566, 2.3522),
    "amsterdam": (52.3676, 4.9041),
    "آمستردام": (52.3676, 4.9041),
    "brussels": (50.8503, 4.3517),
    "بروکسل": (50.8503, 4.3517),
    "vienna": (48.2082, 16.3738),
    "وین": (48.2082, 16.3738),
    "frankfurt": (50.1109, 8.6821),
    "فرانکفورت": (50.1109, 8.6821),
    "hamburg": (53.5511, 9.9937),
    "هامبورگ": (53.5511, 9.9937),
    "cologne": (50.9375, 6.9603),
    "کلن": (50.9375, 6.9603),
    "munich": (48.1351, 11.5820),
    "مونیخ": (48.1351, 11.5820),
    "oslo": (59.9139, 10.7522),
    "اسلو": (59.9139, 10.7522),
    "copenhagen": (55.6761, 12.5683),
    "کپنهاگ": (55.6761, 12.5683),
    "geneva": (46.2044, 6.1432),
    "ژنو": (46.2044, 6.1432),
    "rome": (41.9028, 12.4964),
    "رم": (41.9028, 12.4964),
    "madrid": (40.4168, -3.7038),
    "مادرید": (40.4168, -3.7038),
    # North America
    "washington": (38.9072, -77.0369),
    "واشنگتن": (38.9072, -77.0369),
    "new york": (40.7128, -74.0060),
    "نیویورک": (40.7128, -74.0060),
    "los angeles": (34.0522, -118.2437),
    "لس آنجلس": (34.0522, -118.2437),
    "toronto": (43.6532, -79.3832),
    "تورنتو": (43.6532, -79.3832),
    "vancouver": (49.2827, -123.1207),
    "ونکوور": (49.2827, -123.1207),
    "san francisco": (37.7749, -122.4194),
    "سانفرانسیسکو": (37.7749, -122.4194),
    # Australia
    "sydney": (33.8688, 151.2093),
    "سیدنی": (33.8688, 151.2093),
    "melbourne": (37.8136, 144.9631),
    "ملبورن": (37.8136, 144.9631),
    # Other
    "dubai": (25.2048, 55.2708),
    "دبی": (25.2048, 55.2708),
    "istanbul": (41.0082, 28.9784),
    "استانبول": (41.0082, 28.9784),
    # Countries (for general references)
    "sweden": (59.3293, 18.0686),
    "سوئد": (59.3293, 18.0686),
    "germany": (52.5200, 13.4050),
    "آلمان": (52.5200, 13.4050),
    "france": (48.8566, 2.3522),
    "فرانسه": (48.8566, 2.3522),
    "england": (51.5074, -0.1278),
    "انگلیس": (51.5074, -0.1278),
    "uk": (51.5074, -0.1278),
    "canada": (43.6532, -79.3832),
    "کانادا": (43.6532, -79.3832),
    "usa": (38.9072, -77.0369),
    "آمریکا": (38.9072, -77.0369),
    "america": (38.9072, -77.0369),
}

# Protest-related keywords in Persian and English
PROTEST_KEYWORDS = [
    # Persian - Core protest terms
    "اعتراض", "تظاهرات", "اعتصاب", "شورش", "درگیری",
    "تجمع", "راهپیمایی", "شعار", "بازداشت", "زن زندگی آزادی",
    "مهسا امینی", "کشته", "زخمی", "گلوله", "سرکوب",
    "بسیج", "سپاه", "نیروی انتظامی", "اینترنت", "قطعی",
    # Persian - Additional terms
    "معترض", "معترضان", "خیابان", "آتش", "ناآرامی",
    "حکومت", "رژیم", "دیکتاتور", "آزادی", "انقلاب",
    "مردم", "خشونت", "پلیس", "ضرب و شتم", "شهید",
    # English
    "protest", "demonstration", "strike", "unrest", "clash",
    "rally", "march", "arrest", "detained", "woman life freedom",
    "mahsa amini", "killed", "shot", "crackdown", "shutdown",
    "basij", "irgc", "police", "internet", "blackout",
    "uprising", "revolution", "regime", "dictator", "freedom",
    # Hashtags (without #)
    "iranprotests", "iranrevolution", "mahsaamini", "womanlifefreedom",
    "زن_زندگی_آزادی", "مهسا_امینی",
]

# ============================================================================
# POLICE PRESENCE KEYWORDS (PPU - Police Presence Unit)
# Keywords indicating security force presence, checkpoints, raids
# ============================================================================
POLICE_KEYWORDS = [
    # Persian - Security forces
    "نیروی انتظامی", "پلیس", "گشت", "ایست بازرسی", "بازداشت",
    "یگان ویژه", "نوپو", "بسیج", "سپاه", "لباس شخصی",
    "ماشین پلیس", "ون", "موتورسوار", "گارد", "نیروی امنیتی",
    "ایستگاه پلیس", "کلانتری", "بازجویی", "احضار", "تعقیب",
    "مستقر", "حضور نیرو", "محاصره", "بلوکه", "راه‌بندان",
    # English - Security forces
    "police", "security forces", "checkpoint", "raid", "patrol",
    "riot police", "anti-riot", "basij", "irgc", "plainclothes",
    "police van", "security vehicle", "motorcycle unit", "guard",
    "police station", "detained", "interrogation", "summoned",
    "deployed", "heavy presence", "surrounded", "blocked", "roadblock",
    # Specific units
    "sepah", "basiji", "etelaat", "intelligence", "morality police",
    "گشت ارشاد", "پلیس امنیت", "اطلاعات",
]

# ============================================================================
# REDDIT SUBREDDITS TO MONITOR
# ============================================================================
REDDIT_SUBREDDITS = [
    "iran",             # Main Iran subreddit
    "NewIran",          # Pro-democracy Iran
    "iranian",          # Iranian community
    "persianews",       # Persian news
    "ProIran",          # Iran news/discussion
]

# ============================================================================
# INSTAGRAM ACCOUNTS TO MONITOR (via public profile scraping)
# ============================================================================
INSTAGRAM_ACCOUNTS = [
    "1500tasvir",           # Citizen journalism
    "iranintl",             # Iran International
    "rich_kids_of_tehran",  # May have protest content
    "vahid_online",         # News
]

# ============================================================================
# YOUTUBE CHANNELS (Persian News - via RSS feeds)
# ============================================================================
YOUTUBE_CHANNELS = {
    "iran_international": {
        "channel_id": "UCJ3lrLkWpLiR6DbnduzVnlw",
        "name": "Iran International",
        "reliability": 0.85,
    },
    "manoto_tv": {
        "channel_id": "UCUjNk0F6sl1WuEoMKWmRWYg",
        "name": "Manoto TV",
        "reliability": 0.8,
    },
    "voa_persian": {
        "channel_id": "UCgj6OVPPpSCz2bfYqEHO4Fg",
        "name": "VOA Persian",
        "reliability": 0.85,
    },
    "bbc_persian": {
        "channel_id": "UCQfwfsi5VrQ8yKZ-UWmAEFg",
        "name": "BBC Persian",
        "reliability": 0.9,
    },
    # New media channels
    "bayan": {
        "channel_id": "UCZCh5EFHJRWLmzDvs1K2-xQ",
        "name": "Bayan",
        "reliability": 0.75,
    },
    "euronews_farsi": {
        "channel_id": "UCYsNi1_qkLQxJRKGmJjCcLA",
        "name": "Euro News FA",
        "reliability": 0.85,
    },
    "iranefarda": {
        "channel_id": "UCNJnFahJdYOihkpH_Kj2I1g",
        "name": "Iranefarda",
        "reliability": 0.75,
    },
    "afghan_intl": {
        "channel_id": "UCh1jJuInZIWdM-k8lpCq7Wg",
        "name": "Afghan Intl",
        "reliability": 0.8,
    },
    "mohammad_manzarpour": {
        "channel_id": "UC5kfz8OqPj6KJi8PLYCk4Jg",
        "name": "Mohammad Manzarpour",
        "reliability": 0.7,
    },
    "radis": {
        "channel_id": "UCKwNYMPdS3b8iQB5eOgXw3A",
        "name": "Radis",
        "reliability": 0.7,
    },
}

# ============================================================================
# RSS FEEDS - News Outlets
# ============================================================================
RSS_FEEDS = {
    # Persian Language News
    "bbc_persian": {
        "url": "https://feeds.bbci.co.uk/persian/rss.xml",
        "name": "BBC Persian",
        "reliability": 0.9,
    },
    "dw_persian": {
        "url": "https://rss.dw.com/xml/rss-fa-all",
        "name": "DW Persian",
        "reliability": 0.85,
    },
    "voa_persian": {
        "url": "https://ir.voanews.com/api/ziqp$eqopi",
        "name": "VOA Persian",
        "reliability": 0.85,
    },
    # New media outlets
    "iran_intl": {
        "url": "https://www.iranintl.com/en/rss",
        "name": "IRAN INTL",
        "reliability": 0.85,
    },
    "euronews_farsi": {
        "url": "https://fa.euronews.com/rss",
        "name": "Euro News FA",
        "reliability": 0.85,
    },
    "iranefarda": {
        "url": "https://iranefarda.com/feed",
        "name": "Iranefarda",
        "reliability": 0.75,
    },
    "afghan_intl": {
        "url": "https://www.afi.tv/feed",
        "name": "Afghan Intl",
        "reliability": 0.8,
    },
    # International News in English
    "reuters_world": {
        "url": "https://www.reutersagency.com/feed/?best-regions=middle-east&post_type=best",
        "name": "Reuters Middle East",
        "reliability": 0.9,
    },
    "aljazeera": {
        "url": "https://www.aljazeera.com/xml/rss/all.xml",
        "name": "Al Jazeera",
        "reliability": 0.75,
    },
    # Human Rights Organizations
    "hrw": {
        "url": "https://www.hrw.org/rss/news_feed/all",
        "name": "Human Rights Watch",
        "reliability": 0.95,
    },
    "amnesty": {
        "url": "https://www.amnesty.org/en/feed/",
        "name": "Amnesty International",
        "reliability": 0.95,
    },
    # Iran Human Rights Organizations (NEW)
    "iran_hr": {
        "url": "https://iranhr.net/en/rss/",
        "name": "Iran Human Rights",
        "reliability": 0.95,
        "source_category": "human_rights",
    },
    "hrana": {
        "url": "https://www.en-hrana.org/feed/",
        "name": "HRANA News Agency",
        "reliability": 0.9,
        "source_category": "human_rights",
    },
    "radio_zamaneh": {
        "url": "https://www.radiozamaneh.com/feed/",
        "name": "Radio Zamaneh",
        "reliability": 0.85,
    },
    "radio_farda": {
        "url": "https://www.radiofarda.com/api/z-pqpiev$qi",
        "name": "Radio Farda",
        "reliability": 0.9,
    },
    "iranwire": {
        "url": "https://iranwire.com/en/feed/",
        "name": "IranWire",
        "reliability": 0.85,
    },
    # OSINT / Verification Sources
    "geoconfirmed": {
        "url": "https://geoconfirmed.org/feed",
        "name": "GeoConfirmed",
        "reliability": 0.9,
        "source_category": "osint",
    },
    "factnameh": {
        "url": "https://factnameh.com/feed",
        "name": "FactNameh",
        "reliability": 0.9,
        "source_category": "verification",
    },
}

# ============================================================================
# TWITTER/X ACCOUNTS TO MONITOR (via Nitter)
# ============================================================================
TWITTER_ACCOUNTS = [
    # News outlets
    "IranIntl_En",      # Iran International English
    "IranIntl",         # Iran International Persian
    "ABORSAT",          # Persian news
    "Aborsat_farsi",    # News
    "BBCPersian",       # BBC Persian
    "euaborsat",        # Euro News FA
    "IraneFardaTV",     # Iranefarda
    "AfghanIntl",       # Afghan Intl
    # Journalists & Activists
    "ManijehNasrabadi", # Journalist
    "AlinejadMasih",    # Activist
    "NiohBerg",         # Analyst
    "UK_REPT",          # UK-based coverage
    "RealPersianGod",   # Commentary
    "Savakzadeh",       # Coverage
    "maborsat",         # Mohammad Manzarpour
    # OSINT & Citizen journalism
    "1500tasvir",       # Citizen journalism
    "HengawO",          # Kurdistan human rights
    "GeoConfirmed",     # GeoConfirmed OSINT verification
    "MahsaAlert",       # MahsaAlert safety notifications
    "Aborsat_FactCh",   # FactNameh verification
    # Human Rights Organizations (NEW)
    "IranHrm",          # Iran Human Rights Monitor
    "ABORSAT_eng",      # HRANA English
    "IranHR_English",   # Iran Human Rights English
    "KolsareNet",       # Kolsare Network
]

# Nitter instances (public Twitter mirrors) - tested and working
NITTER_INSTANCES = [
    "twiiit.com",           # Currently working
    "nitter.net",           # Backup
    "xcancel.com",          # Backup
    "nitter.poast.org",     # Backup
]

# ============================================================================
# TELEGRAM CHANNELS (Public Web Interface)
# Note: Only channels with public preview enabled will work
# ============================================================================
TELEGRAM_CHANNELS = [
    # Working channels with public preview
    "bbcpersian",           # BBC Persian - WORKS
    "iranworkers",          # Labor protests - WORKS
    "Iran_Revolutionn",     # Revolution coverage - WORKS
    "irannc",               # Iran news - WORKS
    "Farsi_Iranwire",       # IranWire Persian - WORKS
    # May work (public preview status varies)
    "iranintl",             # IRAN INTL
    "manikiusa",
    "VOAfarsi",
    "radiofaborsat",
    "IranHrm",
    # New media channels
    "Bayan_news",           # Bayan
    "euronewsfarsi",        # Euro News FA
    "iranefardanews",       # Iranefarda
    "AfghanIntlTV",         # Afghan Intl
    "MohammadManzarpour",   # Mohammad Manzarpour
    "RadisMedia",           # Radis
    # OSINT / Verification
    "GeoConfirmed",         # GeoConfirmed OSINT
    "MahsaAlerts",          # MahsaAlert safety alerts
    "FactNameh",            # FactNameh verification
    # Human Rights (NEW)
    "HengawO",              # Hengaw Human Rights - Kurdish focus
    "1500tasvir",           # 1500Tasvir - Video verification / citizen journalism
    "HranaEnglish",         # HRANA English
    "IranHumanRights",      # Iran Human Rights org
    "KolsareNetwork",       # Kolsare Network - protests
    "shaaborsat",           # Activist coverage
]


class DataSource(ABC):
    source_type: str = "unknown"
    source_platform: str = "unknown"
    
    @abstractmethod
    def fetch_events(self) -> List[schemas.ProtestEventCreate]:
        pass

    def _extract_location(self, text: str) -> Optional[Tuple[str, float, float, bool]]:
        """Extract location from text by matching city names.
        Returns: (city_name, lat, lon, is_diaspora)
        """
        text_lower = text.lower()
        
        # Check diaspora cities FIRST (solidarity protests abroad)
        for city_name, coords in DIASPORA_CITIES.items():
            if city_name.lower() in text_lower or city_name in text:
                return (city_name, coords[0], coords[1], True)  # True = diaspora
        
        # Then check Iranian cities
        for city_name, coords in IRAN_CITIES.items():
            if city_name.lower() in text_lower or city_name in text:
                return (city_name, coords[0], coords[1], False)  # False = inside Iran
        
        return None

    def _calculate_intensity(self, text: str) -> float:
        """Calculate intensity score based on keyword density"""
        text_lower = text.lower()
        matches = sum(1 for kw in PROTEST_KEYWORDS if kw.lower() in text_lower or kw in text)
        
        intensity = min(matches / 5.0, 1.0)
        return max(intensity, 0.1)

    def _is_protest_related(self, text: str) -> bool:
        """Check if text contains protest-related keywords"""
        text_lower = text.lower()
        return any(kw.lower() in text_lower or kw in text for kw in PROTEST_KEYWORDS)
    
    def _is_police_related(self, text: str) -> bool:
        """Check if text contains police presence keywords (PPU)"""
        text_lower = text.lower()
        return any(kw.lower() in text_lower or kw in text for kw in POLICE_KEYWORDS)
    
    def _detect_event_type(self, text: str) -> str:
        """Detect event type based on keywords. Returns event_type string."""
        text_lower = text.lower()
        
        # Police presence detection (PPU) - check first as it's specific
        police_count = sum(1 for kw in POLICE_KEYWORDS if kw.lower() in text_lower or kw in text)
        if police_count >= 2:  # Strong police presence signal
            return "police_presence"
        
        # Strike detection
        strike_keywords = ["اعتصاب", "strike", "walkout", "تعطیل", "shutdown"]
        if any(kw.lower() in text_lower or kw in text for kw in strike_keywords):
            return "strike"
        
        # Clash detection
        clash_keywords = ["درگیری", "clash", "fight", "violence", "خشونت", "زد و خورد"]
        if any(kw.lower() in text_lower or kw in text for kw in clash_keywords):
            return "clash"
        
        # Arrest detection
        arrest_keywords = ["بازداشت", "arrest", "detained", "دستگیر", "زندان", "prison"]
        if any(kw.lower() in text_lower or kw in text for kw in arrest_keywords):
            return "arrest"
        
        # Default to protest
        return "protest"
    
    def _calculate_police_intensity(self, text: str) -> float:
        """Calculate police presence intensity (1-5 scale normalized to 0-1)"""
        text_lower = text.lower()
        
        # High intensity keywords
        high_intensity = ["یگان ویژه", "riot police", "heavy presence", "محاصره", 
                         "surrounded", "raid", "یورش", "حمله"]
        # Medium intensity keywords  
        medium_intensity = ["گشت", "patrol", "checkpoint", "ایست بازرسی", "deployed"]
        
        score = 0.3  # Base score
        
        if any(kw.lower() in text_lower or kw in text for kw in high_intensity):
            score = 0.9
        elif any(kw.lower() in text_lower or kw in text for kw in medium_intensity):
            score = 0.6
        
        # Add based on keyword density
        matches = sum(1 for kw in POLICE_KEYWORDS if kw.lower() in text_lower or kw in text)
        score = min(score + (matches * 0.1), 1.0)
        
        return score


class RSSSource(DataSource):
    """Fetch and parse RSS feeds from news sources"""
    source_type = "rss"
    
    def __init__(self, feeds: Dict = None):
        self.feeds = feeds or RSS_FEEDS

    def fetch_events(self) -> List[schemas.ProtestEventCreate]:
        events = []
        
        for feed_id, feed_config in self.feeds.items():
            url = feed_config["url"]
            source_name = feed_config["name"]
            reliability = feed_config.get("reliability", 0.5)
            
            try:
                feed = feedparser.parse(url)
                
                for entry in feed.entries[:25]:
                    title = entry.get('title', '')
                    summary = entry.get('summary', entry.get('description', ''))
                    full_text = f"{title} {summary}"
                    
                    # Must contain Iran-related AND protest-related content
                    if not self._is_protest_related(full_text):
                        continue
                    
                    if 'iran' not in full_text.lower() and 'ایران' not in full_text:
                        continue
                    
                    location = self._extract_location(full_text)
                    if not location:
                        location = ("Tehran (inferred)", 
                                   35.6892 + random.uniform(-0.1, 0.1), 
                                   51.3890 + random.uniform(-0.1, 0.1),
                                   False)
                    
                    city_name, lat, lon, is_diaspora = location
                    
                    # Parse timestamp with timezone
                    try:
                        if hasattr(entry, 'published_parsed') and entry.published_parsed:
                            timestamp = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
                        else:
                            timestamp = datetime.now(timezone.utc)
                    except:
                        timestamp = datetime.now(timezone.utc)
                    
                    intensity = self._calculate_intensity(full_text)
                    source_url = entry.get('link', '')
                    
                    events.append(schemas.ProtestEventCreate(
                        title=f"[{source_name}] {title[:180]}" if title else f"[{source_name}] Report",
                        description=summary[:500] if summary else "",
                        latitude=lat,
                        longitude=lon,
                        intensity_score=intensity,
                        verified=(reliability >= 0.9),  # High reliability = verified
                        timestamp=timestamp,
                        source_url=source_url
                    ))
                    
            except Exception as e:
                print(f"Error fetching RSS feed {feed_id}: {e}")
                continue
        
        return events


class TwitterSource(DataSource):
    """Fetch tweets via Nitter (public Twitter mirror)"""
    source_type = "twitter"
    
    def __init__(self, accounts: List[str] = None, instances: List[str] = None):
        self.accounts = accounts or TWITTER_ACCOUNTS
        self.instances = instances or NITTER_INSTANCES

    def _get_working_instance(self) -> Optional[str]:
        """Find a working Nitter instance by testing RSS feed"""
        # Note: Nitter instances are frequently blocked by Twitter/X
        # This is a best-effort approach
        test_accounts = ["bbcpersian", "voaborsat"]  # Less likely to be blocked
        
        for instance in self.instances:
            for test_account in test_accounts:
                try:
                    url = f"https://{instance}/{test_account}/rss"
                    resp = requests.get(url, timeout=5, headers={
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                        'Accept': 'application/rss+xml, application/xml'
                    })
                    # Check for actual RSS content, not error pages
                    if (resp.status_code == 200 and 
                        len(resp.text) > 1000 and 
                        '<item>' in resp.text and
                        'whitelisted' not in resp.text.lower()):
                        print(f"  Found working Nitter: {instance}")
                        return instance
                except:
                    continue
        print("  Note: Nitter instances are blocked/rate-limited. Consider using Twitter API.")
        return None

    def fetch_events(self) -> List[schemas.ProtestEventCreate]:
        events = []
        instance = self._get_working_instance()
        
        if not instance:
            print("No working Nitter instance found")
            return events
        
        for account in self.accounts:
            try:
                url = f"https://{instance}/{account}/rss"
                feed = feedparser.parse(url)
                
                for entry in feed.entries[:15]:
                    title = entry.get('title', '')
                    content = entry.get('summary', '')
                    full_text = f"{title} {content}"
                    
                    # For Twitter, be more lenient - just check for Iran mention
                    has_iran = 'iran' in full_text.lower() or 'ایران' in full_text
                    has_protest = self._is_protest_related(full_text)
                    
                    if not (has_iran or has_protest):
                        continue
                    
                    location = self._extract_location(full_text)
                    if not location:
                        # Default to Tehran for Iran-related tweets without specific city
                        location = ("Iran (Twitter)", 
                                   35.6892 + random.uniform(-0.15, 0.15), 
                                   51.3890 + random.uniform(-0.15, 0.15),
                                   False)
                    
                    city_name, lat, lon, is_diaspora = location
                    
                    try:
                        if hasattr(entry, 'published_parsed') and entry.published_parsed:
                            timestamp = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
                        else:
                            timestamp = datetime.now(timezone.utc)
                    except:
                        timestamp = datetime.now(timezone.utc)
                    
                    intensity = self._calculate_intensity(full_text)
                    source_url = entry.get('link', '')
                    
                    # Clean up Nitter URL to Twitter URL
                    if instance in source_url:
                        source_url = source_url.replace(f"https://{instance}", "https://twitter.com")
                    
                    events.append(schemas.ProtestEventCreate(
                        title=f"[@{account}] {title[:150]}" if title else f"[@{account}] Tweet",
                        description=content[:500] if content else "",
                        latitude=lat + random.uniform(-0.02, 0.02),
                        longitude=lon + random.uniform(-0.02, 0.02),
                        intensity_score=intensity,
                        verified=False,  # Social media is unverified by default
                        timestamp=timestamp,
                        source_url=source_url
                    ))
                    
            except Exception as e:
                print(f"Error fetching Twitter account @{account}: {e}")
                continue
        
        return events


class TelegramSource(DataSource):
    """Fetch posts from public Telegram channels"""
    source_type = "telegram"
    
    def __init__(self, channels: List[str] = None):
        self.channels = channels or TELEGRAM_CHANNELS

    def fetch_events(self) -> List[schemas.ProtestEventCreate]:
        events = []
        
        for channel in self.channels:
            # Strip @ if present
            channel = channel.lstrip('@')
            
            try:
                # Use Telegram's public web preview
                url = f"https://t.me/s/{channel}"
                resp = requests.get(url, timeout=10, headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                })
                
                if resp.status_code != 200:
                    print(f"    @{channel}: HTTP {resp.status_code}")
                    continue
                
                soup = BeautifulSoup(resp.text, 'html.parser')
                messages = soup.find_all('div', class_='tgme_widget_message_wrap')
                
                if not messages:
                    continue
                
                channel_events = 0
                for msg in messages[:20]:  # Check more messages
                    try:
                        text_elem = msg.find('div', class_='tgme_widget_message_text')
                        if not text_elem:
                            continue
                        
                        text = text_elem.get_text()
                        
                        # Less strict filtering for Iran-focused channels
                        # Include if: has protest keywords OR mentions Iran/city
                        has_iran = 'iran' in text.lower() or 'ایران' in text
                        has_protest = self._is_protest_related(text)
                        location = self._extract_location(text)
                        has_location = location is not None
                        
                        if not (has_protest or (has_iran and has_location)):
                            continue
                        
                        # Get location or default to Tehran area (only if no diaspora city found)
                        if not location:
                            location = ("Iran (Telegram)", 
                                       35.6892 + random.uniform(-0.2, 0.2), 
                                       51.3890 + random.uniform(-0.2, 0.2),
                                       False)
                        
                        city_name, lat, lon, is_diaspora = location
                        
                        # Try to get timestamp
                        time_elem = msg.find('time')
                        if time_elem and time_elem.get('datetime'):
                            try:
                                timestamp = datetime.fromisoformat(time_elem['datetime'].replace('Z', '+00:00'))
                            except:
                                timestamp = datetime.now(timezone.utc)
                        else:
                            timestamp = datetime.now(timezone.utc)
                        
                        # Get message link
                        link_elem = msg.find('a', class_='tgme_widget_message_date')
                        source_url = link_elem['href'] if link_elem else f"https://t.me/{channel}"
                        
                        # Extract media (image or video)
                        media_url = None
                        media_type = None
                        
                        # Check for photo
                        photo_elem = msg.find('a', class_='tgme_widget_message_photo_wrap')
                        if photo_elem and photo_elem.get('style'):
                            style = photo_elem['style']
                            # Extract URL from background-image:url('...')
                            import re
                            match = re.search(r"url\(['\"]?(https?://[^'\"]+)['\"]?\)", style)
                            if match:
                                media_url = match.group(1)
                                media_type = 'image'
                        
                        # Check for video if no photo
                        if not media_url:
                            # Try to find actual video element with src
                            video_elem = msg.find('video')
                            if video_elem and video_elem.get('src'):
                                video_src = video_elem.get('src')
                                if video_src.startswith('http'):
                                    media_url = video_src
                                    media_type = 'video'
                            
                            # Fallback to video thumbnail
                            if not media_url:
                                video_wrap = msg.find('div', class_='tgme_widget_message_video_wrap')
                                if video_wrap:
                                    thumb = video_wrap.find('i', class_='tgme_widget_message_video_thumb')
                                    if thumb and thumb.get('style'):
                                        style = thumb['style']
                                        import re
                                        match = re.search(r"url\(['\"]?(https?://[^'\"]+)['\"]?\)", style)
                                        if match:
                                            media_url = match.group(1)
                                            media_type = 'video_thumb'  # Indicates it's just a thumbnail
                        
                        intensity = self._calculate_intensity(text)
                        
                        # Mark diaspora events in title
                        if is_diaspora:
                            title_prefix = f"[TG @{channel}] 🌍 {city_name}: "
                        else:
                            title_prefix = f"[TG @{channel}] "
                        
                        events.append(schemas.ProtestEventCreate(
                            title=f"{title_prefix}{text[:90]}...",
                            description=text[:500],
                            latitude=lat + random.uniform(-0.02, 0.02),
                            longitude=lon + random.uniform(-0.02, 0.02),
                            intensity_score=intensity,
                            verified=False,
                            timestamp=timestamp,
                            source_url=source_url,
                            media_url=media_url,
                            media_type=media_type
                        ))
                        channel_events += 1
                        
                    except Exception as e:
                        continue
                
                if channel_events > 0:
                    print(f"    @{channel}: {channel_events} events")
                        
            except Exception as e:
                print(f"    @{channel}: Error - {str(e)[:30]}")
                continue
        
        return events


class RedditSource(DataSource):
    """Fetch posts from Reddit subreddits via public JSON API"""
    source_type = "reddit"
    source_platform = "reddit"
    
    def __init__(self, subreddits: List[str] = None):
        self.subreddits = subreddits or REDDIT_SUBREDDITS
    
    def fetch_events(self) -> List[schemas.ProtestEventCreate]:
        events = []
        
        for subreddit in self.subreddits:
            try:
                # Use Reddit's public JSON API (no auth required for public subreddits)
                url = f"https://www.reddit.com/r/{subreddit}/new.json?limit=25"
                resp = requests.get(url, timeout=10, headers={
                    'User-Agent': 'IranProtestMap/1.0 (Educational Research)'
                })
                
                if resp.status_code != 200:
                    print(f"    r/{subreddit}: HTTP {resp.status_code}")
                    continue
                
                data = resp.json()
                posts = data.get('data', {}).get('children', [])
                
                subreddit_events = 0
                for post in posts:
                    post_data = post.get('data', {})
                    title = post_data.get('title', '')
                    selftext = post_data.get('selftext', '')
                    full_text = f"{title} {selftext}"
                    
                    # Filter for Iran/protest content
                    has_iran = 'iran' in full_text.lower() or 'ایران' in full_text
                    has_protest = self._is_protest_related(full_text)
                    has_police = self._is_police_related(full_text)
                    
                    if not (has_iran and (has_protest or has_police)):
                        continue
                    
                    location = self._extract_location(full_text)
                    if not location:
                        location = ("Iran (Reddit)", 
                                   35.6892 + random.uniform(-0.2, 0.2), 
                                   51.3890 + random.uniform(-0.2, 0.2),
                                   False)
                    
                    city_name, lat, lon, is_diaspora = location
                    
                    # Parse timestamp
                    created_utc = post_data.get('created_utc', 0)
                    timestamp = datetime.fromtimestamp(created_utc, tz=timezone.utc) if created_utc else datetime.now(timezone.utc)
                    
                    # Detect event type
                    event_type = self._detect_event_type(full_text)
                    intensity = self._calculate_police_intensity(full_text) if event_type == "police_presence" else self._calculate_intensity(full_text)
                    
                    # Get media if available
                    media_url = None
                    media_type = None
                    if post_data.get('is_video'):
                        media_type = 'video_thumb'
                        media_url = post_data.get('thumbnail')
                    elif post_data.get('post_hint') == 'image':
                        media_type = 'image'
                        media_url = post_data.get('url')
                    
                    source_url = f"https://reddit.com{post_data.get('permalink', '')}"
                    
                    # Add PPU indicator for police presence
                    if event_type == "police_presence":
                        title_prefix = f"[Reddit] 🚨 PPU: "
                    else:
                        title_prefix = f"[Reddit r/{subreddit}] "
                    
                    events.append(schemas.ProtestEventCreate(
                        title=f"{title_prefix}{title[:120]}",
                        description=selftext[:500] if selftext else "",
                        latitude=lat + random.uniform(-0.02, 0.02),
                        longitude=lon + random.uniform(-0.02, 0.02),
                        intensity_score=intensity,
                        verified=False,
                        timestamp=timestamp,
                        source_url=source_url,
                        media_url=media_url,
                        media_type=media_type,
                        event_type=event_type,
                        source_platform="reddit"
                    ))
                    subreddit_events += 1
                
                if subreddit_events > 0:
                    print(f"    r/{subreddit}: {subreddit_events} events")
                    
            except Exception as e:
                print(f"    r/{subreddit}: Error - {str(e)[:40]}")
                continue
        
        return events


class InstagramSource(DataSource):
    """Fetch posts from Instagram public profiles"""
    source_type = "instagram"
    source_platform = "instagram"
    
    def __init__(self, accounts: List[str] = None):
        self.accounts = accounts or INSTAGRAM_ACCOUNTS
    
    def fetch_events(self) -> List[schemas.ProtestEventCreate]:
        events = []
        
        for account in self.accounts:
            try:
                # Try to fetch via Instagram's public web interface
                # Note: Instagram heavily rate-limits and blocks scraping
                # This is a best-effort approach
                url = f"https://www.instagram.com/{account}/?__a=1&__d=dis"
                resp = requests.get(url, timeout=10, headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                    'Accept': 'application/json',
                    'X-Requested-With': 'XMLHttpRequest'
                })
                
                if resp.status_code != 200:
                    # Try alternative: public profile page scraping
                    url = f"https://www.instagram.com/{account}/"
                    resp = requests.get(url, timeout=10, headers={
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                    })
                    
                    if resp.status_code != 200:
                        continue
                    
                    # Parse HTML for shared data
                    soup = BeautifulSoup(resp.text, 'html.parser')
                    scripts = soup.find_all('script', type='application/ld+json')
                    
                    for script in scripts:
                        try:
                            import json
                            data = json.loads(script.string)
                            if '@type' in data and data['@type'] == 'ProfilePage':
                                # Found profile, but Instagram limits what we can get
                                print(f"    @{account}: Found profile (limited data)")
                        except:
                            continue
                    continue
                
                # If we got JSON response
                try:
                    data = resp.json()
                    user_data = data.get('graphql', {}).get('user', {})
                    media = user_data.get('edge_owner_to_timeline_media', {}).get('edges', [])
                    
                    account_events = 0
                    for edge in media[:10]:
                        node = edge.get('node', {})
                        caption_edges = node.get('edge_media_to_caption', {}).get('edges', [])
                        caption = caption_edges[0].get('node', {}).get('text', '') if caption_edges else ''
                        
                        # Filter for Iran/protest content
                        has_iran = 'iran' in caption.lower() or 'ایران' in caption
                        has_protest = self._is_protest_related(caption)
                        has_police = self._is_police_related(caption)
                        
                        if not (has_iran and (has_protest or has_police)):
                            continue
                        
                        location = self._extract_location(caption)
                        if not location:
                            location = ("Iran (Instagram)", 
                                       35.6892 + random.uniform(-0.2, 0.2), 
                                       51.3890 + random.uniform(-0.2, 0.2),
                                       False)
                        
                        city_name, lat, lon, is_diaspora = location
                        
                        timestamp_unix = node.get('taken_at_timestamp', 0)
                        timestamp = datetime.fromtimestamp(timestamp_unix, tz=timezone.utc) if timestamp_unix else datetime.now(timezone.utc)
                        
                        event_type = self._detect_event_type(caption)
                        intensity = self._calculate_police_intensity(caption) if event_type == "police_presence" else self._calculate_intensity(caption)
                        
                        media_url = node.get('display_url')
                        media_type = 'video' if node.get('is_video') else 'image'
                        source_url = f"https://www.instagram.com/p/{node.get('shortcode', '')}/"
                        
                        title_prefix = "🚨 PPU: " if event_type == "police_presence" else ""
                        
                        events.append(schemas.ProtestEventCreate(
                            title=f"[IG @{account}] {title_prefix}{caption[:100]}...",
                            description=caption[:500],
                            latitude=lat + random.uniform(-0.02, 0.02),
                            longitude=lon + random.uniform(-0.02, 0.02),
                            intensity_score=intensity,
                            verified=False,
                            timestamp=timestamp,
                            source_url=source_url,
                            media_url=media_url,
                            media_type=media_type,
                            event_type=event_type,
                            source_platform="instagram"
                        ))
                        account_events += 1
                    
                    if account_events > 0:
                        print(f"    @{account}: {account_events} events")
                        
                except Exception as e:
                    print(f"    @{account}: JSON parse error - {str(e)[:30]}")
                    continue
                    
            except Exception as e:
                print(f"    @{account}: Error - {str(e)[:40]}")
                continue
        
        return events


class YouTubeSource(DataSource):
    """Fetch videos from YouTube channels via RSS feeds"""
    source_type = "youtube"
    source_platform = "youtube"
    
    def __init__(self, channels: Dict = None):
        self.channels = channels or YOUTUBE_CHANNELS
    
    def fetch_events(self) -> List[schemas.ProtestEventCreate]:
        events = []
        
        for channel_id, channel_config in self.channels.items():
            youtube_channel_id = channel_config["channel_id"]
            channel_name = channel_config["name"]
            reliability = channel_config.get("reliability", 0.5)
            
            try:
                # YouTube provides RSS feeds for channels
                url = f"https://www.youtube.com/feeds/videos.xml?channel_id={youtube_channel_id}"
                feed = feedparser.parse(url)
                
                channel_events = 0
                for entry in feed.entries[:15]:
                    title = entry.get('title', '')
                    summary = entry.get('summary', entry.get('description', ''))
                    full_text = f"{title} {summary}"
                    
                    # Filter for Iran/protest content
                    has_iran = 'iran' in full_text.lower() or 'ایران' in full_text
                    has_protest = self._is_protest_related(full_text)
                    has_police = self._is_police_related(full_text)
                    
                    if not (has_iran and (has_protest or has_police)):
                        continue
                    
                    location = self._extract_location(full_text)
                    if not location:
                        location = ("Iran (YouTube)", 
                                   35.6892 + random.uniform(-0.15, 0.15), 
                                   51.3890 + random.uniform(-0.15, 0.15),
                                   False)
                    
                    city_name, lat, lon, is_diaspora = location
                    
                    try:
                        if hasattr(entry, 'published_parsed') and entry.published_parsed:
                            timestamp = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
                        else:
                            timestamp = datetime.now(timezone.utc)
                    except:
                        timestamp = datetime.now(timezone.utc)
                    
                    event_type = self._detect_event_type(full_text)
                    intensity = self._calculate_police_intensity(full_text) if event_type == "police_presence" else self._calculate_intensity(full_text)
                    
                    source_url = entry.get('link', '')
                    
                    # Get video thumbnail
                    media_url = None
                    video_id = None
                    if 'yt_videoid' in entry:
                        video_id = entry.yt_videoid
                    elif '/watch?v=' in source_url:
                        video_id = source_url.split('/watch?v=')[-1].split('&')[0]
                    
                    if video_id:
                        media_url = f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg"
                    
                    title_prefix = "🚨 PPU: " if event_type == "police_presence" else ""
                    
                    events.append(schemas.ProtestEventCreate(
                        title=f"[YT {channel_name}] {title_prefix}{title[:120]}",
                        description=summary[:500] if summary else "",
                        latitude=lat + random.uniform(-0.02, 0.02),
                        longitude=lon + random.uniform(-0.02, 0.02),
                        intensity_score=intensity,
                        verified=(reliability >= 0.85),  # High reliability channels = verified
                        timestamp=timestamp,
                        source_url=source_url,
                        media_url=media_url,
                        media_type='video_thumb',
                        event_type=event_type,
                        source_platform="youtube"
                    ))
                    channel_events += 1
                
                if channel_events > 0:
                    print(f"    {channel_name}: {channel_events} events")
                    
            except Exception as e:
                print(f"    {channel_name}: Error - {str(e)[:40]}")
                continue
        
        return events


class IngestionService:
    def __init__(self, db: Session):
        self.db = db

    def run_ingestion(self, source_type: str = "all"):
        """Run ingestion from all or specific sources
        
        Args:
            source_type: 'all', 'rss', 'twitter', 'telegram', 'reddit', 'instagram', 'youtube'
        """
        all_events = []
        
        # 1. RSS News Sources (most reliable)
        if source_type in ("all", "rss"):
            print("Fetching from RSS feeds...")
            rss_source = RSSSource()
            rss_events = rss_source.fetch_events()
            all_events.extend(rss_events)
            print(f"  -> {len(rss_events)} events from RSS")
        
        # 2. Twitter/X via Nitter
        if source_type in ("all", "twitter"):
            print("Fetching from Twitter/Nitter...")
            try:
                twitter_source = TwitterSource()
                twitter_events = twitter_source.fetch_events()
                all_events.extend(twitter_events)
                print(f"  -> {len(twitter_events)} events from Twitter")
            except Exception as e:
                print(f"  -> Twitter fetch failed: {e}")
        
        # 3. Telegram public channels
        if source_type in ("all", "telegram"):
            print("Fetching from Telegram...")
            try:
                telegram_source = TelegramSource()
                telegram_events = telegram_source.fetch_events()
                all_events.extend(telegram_events)
                print(f"  -> {len(telegram_events)} events from Telegram")
            except Exception as e:
                print(f"  -> Telegram fetch failed: {e}")
        
        # 4. Reddit subreddits
        if source_type in ("all", "reddit"):
            print("Fetching from Reddit...")
            try:
                reddit_source = RedditSource()
                reddit_events = reddit_source.fetch_events()
                all_events.extend(reddit_events)
                print(f"  -> {len(reddit_events)} events from Reddit")
            except Exception as e:
                print(f"  -> Reddit fetch failed: {e}")
        
        # 5. Instagram profiles
        if source_type in ("all", "instagram"):
            print("Fetching from Instagram...")
            try:
                instagram_source = InstagramSource()
                instagram_events = instagram_source.fetch_events()
                all_events.extend(instagram_events)
                print(f"  -> {len(instagram_events)} events from Instagram")
            except Exception as e:
                print(f"  -> Instagram fetch failed: {e}")
        
        # 6. YouTube channels
        if source_type in ("all", "youtube"):
            print("Fetching from YouTube...")
            try:
                youtube_source = YouTubeSource()
                youtube_events = youtube_source.fetch_events()
                all_events.extend(youtube_events)
                print(f"  -> {len(youtube_events)} events from YouTube")
            except Exception as e:
                print(f"  -> YouTube fetch failed: {e}")
        
        # Save to DB (with duplicate checking)
        count = 0
        police_count = 0
        for event_data in all_events:
            # Check for duplicates by title
            existing = self.db.query(models.ProtestEvent).filter(
                models.ProtestEvent.title == event_data.title
            ).first()
            
            if existing:
                continue
            
            db_event = models.ProtestEvent(
                title=event_data.title,
                description=event_data.description,
                latitude=event_data.latitude,
                longitude=event_data.longitude,
                location=WKTElement(f'POINT({event_data.longitude} {event_data.latitude})', srid=4326),
                intensity_score=event_data.intensity_score,
                verified=event_data.verified,
                timestamp=event_data.timestamp,
                source_url=event_data.source_url,
                media_url=event_data.media_url,
                media_type=event_data.media_type,
                event_type=event_data.event_type or "protest",
                source_platform=event_data.source_platform
            )
            self.db.add(db_event)
            count += 1
            if event_data.event_type == "police_presence":
                police_count += 1
        
        self.db.commit()
        print(f"Total new events saved: {count} (including {police_count} PPU alerts)")
        return count
