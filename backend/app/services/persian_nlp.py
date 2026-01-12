"""
Persian NLP Service for Telegram Message Analysis

Provides:
- Persian text tokenization and keyword extraction
- City/location detection (Persian + transliterated)
- Sentiment analysis (rule-based)
- Urgency scoring
- Event type classification
"""

import re
import json
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timezone


# ============================================================================
# PERSIAN PROTEST KEYWORDS (with English translations in comments)
# ============================================================================
PROTEST_KEYWORDS = {
    # Core protest terms (high relevance)
    "تظاهرات": 1.0,      # demonstration
    "اعتراض": 1.0,       # protest
    "تجمع": 0.9,         # gathering
    "اعتصاب": 0.95,      # strike
    "راهپیمایی": 0.9,    # march
    "شورش": 0.95,        # uprising
    "قیام": 0.95,        # revolt
    "انقلاب": 0.9,       # revolution
    
    # Slogans and movements
    "زن زندگی آزادی": 1.0,   # Woman Life Freedom
    "مهسا امینی": 1.0,       # Mahsa Amini
    "ژینا امینی": 1.0,       # Jina Amini (Kurdish name)
    "مرگ بر دیکتاتور": 1.0,  # Death to dictator
    "آزادی": 0.8,            # Freedom
    
    # Violence indicators
    "تیراندازی": 0.95,   # shooting
    "کشته": 0.95,        # killed
    "زخمی": 0.9,         # injured
    "شهید": 0.9,         # martyr
    "خون": 0.7,          # blood
    "گلوله": 0.9,        # bullet
    
    # Security forces
    "بازداشت": 0.9,      # arrest
    "دستگیری": 0.9,      # detention
    "زندان": 0.8,        # prison
    "بسیج": 0.85,        # Basij
    "سپاه": 0.85,        # IRGC
    "نیروی انتظامی": 0.85,  # Police
    "لباس شخصی": 0.9,    # plainclothes (agents)
    "یگان ویژه": 0.9,    # riot police
    "گشت ارشاد": 0.9,    # morality police
    
    # Internet/communication
    "اینترنت": 0.6,      # internet
    "قطعی": 0.7,         # outage
    "فیلترینگ": 0.7,     # filtering
    "vpn": 0.6,
    
    # Actions
    "سرکوب": 0.9,        # crackdown
    "یورش": 0.9,         # raid
    "حمله": 0.85,        # attack
    "ضرب و شتم": 0.9,    # beating
    "شکنجه": 0.95,       # torture
}

# Negative sentiment keywords
NEGATIVE_KEYWORDS = [
    "کشته", "شهید", "زخمی", "بازداشت", "دستگیری", "زندان",
    "سرکوب", "شکنجه", "یورش", "حمله", "خون", "گلوله",
    "مرگ", "فوت", "اعدام", "نگرانی", "خطر", "هشدار",
    "killed", "martyred", "injured", "arrested", "detained",
    "crackdown", "torture", "attack", "blood", "death",
]

# Urgency indicators
URGENCY_KEYWORDS = {
    # Immediate urgency
    "فوری": 1.0,         # urgent
    "الان": 0.9,         # now
    "اکنون": 0.9,        # currently
    "همین لحظه": 1.0,    # this moment
    "زنده": 0.85,        # live
    "در حال": 0.7,       # ongoing
    "breaking": 1.0,
    "urgent": 1.0,
    
    # High urgency
    "کشته": 0.95,        # killed
    "تیراندازی": 0.95,   # shooting
    "اعدام": 1.0,        # execution
    "خطر": 0.8,          # danger
    "هشدار": 0.85,       # warning
    
    # Medium urgency
    "بازداشت": 0.7,      # arrest
    "درگیری": 0.75,      # clash
}

# Event type keywords
EVENT_TYPE_KEYWORDS = {
    "protest": [
        "تظاهرات", "اعتراض", "تجمع", "راهپیمایی", "شعار",
        "protest", "demonstration", "rally", "march",
    ],
    "clash": [
        "درگیری", "یورش", "حمله", "تیراندازی", "خشونت",
        "clash", "attack", "shooting", "violence", "riot",
    ],
    "arrest": [
        "بازداشت", "دستگیری", "زندان", "احضار", "احضاریه",
        "arrest", "detained", "prison", "custody", "summoned",
    ],
    "strike": [
        "اعتصاب", "تعطیل", "بازار", "کسبه",
        "strike", "walkout", "shutdown", "bazaar",
    ],
    "police_presence": [
        "نیروی انتظامی", "پلیس", "گشت", "ایست بازرسی", "یگان ویژه",
        "police", "security forces", "checkpoint", "riot police",
    ],
}


# ============================================================================
# IRANIAN CITIES (Persian → Coordinates)
# ============================================================================
PERSIAN_CITIES = {
    # Major cities
    "تهران": {"lat": 35.6892, "lon": 51.3890, "en": "Tehran"},
    "اصفهان": {"lat": 32.6546, "lon": 51.6680, "en": "Isfahan"},
    "مشهد": {"lat": 36.2605, "lon": 59.6168, "en": "Mashhad"},
    "تبریز": {"lat": 38.0962, "lon": 46.2919, "en": "Tabriz"},
    "شیراز": {"lat": 29.5918, "lon": 52.5837, "en": "Shiraz"},
    "کرج": {"lat": 35.8400, "lon": 50.9391, "en": "Karaj"},
    "اهواز": {"lat": 31.3183, "lon": 48.6706, "en": "Ahvaz"},
    "قم": {"lat": 34.6416, "lon": 50.8746, "en": "Qom"},
    
    # Kurdish region
    "سنندج": {"lat": 35.3145, "lon": 46.9923, "en": "Sanandaj"},
    "مهاباد": {"lat": 36.7631, "lon": 45.7222, "en": "Mahabad"},
    "ارومیه": {"lat": 37.5527, "lon": 45.0761, "en": "Urmia"},
    "کرمانشاه": {"lat": 34.3142, "lon": 47.0650, "en": "Kermanshah"},
    "سقز": {"lat": 36.2500, "lon": 46.2667, "en": "Saqqez"},
    "بوکان": {"lat": 36.5214, "lon": 46.2086, "en": "Bukan"},
    "مریوان": {"lat": 35.5167, "lon": 46.1833, "en": "Marivan"},
    "پیرانشهر": {"lat": 36.6992, "lon": 45.1458, "en": "Piranshahr"},
    "بانه": {"lat": 35.9978, "lon": 45.8858, "en": "Baneh"},
    
    # Baluchistan
    "زاهدان": {"lat": 29.4963, "lon": 60.8629, "en": "Zahedan"},
    "چابهار": {"lat": 25.2919, "lon": 60.6430, "en": "Chabahar"},
    "خاش": {"lat": 28.2211, "lon": 61.2158, "en": "Khash"},
    
    # Other major cities
    "رشت": {"lat": 37.2808, "lon": 49.5832, "en": "Rasht"},
    "کرمان": {"lat": 30.2839, "lon": 57.0834, "en": "Kerman"},
    "یزد": {"lat": 31.8974, "lon": 54.3569, "en": "Yazd"},
    "بندرعباس": {"lat": 27.1832, "lon": 56.2666, "en": "Bandar Abbas"},
    "همدان": {"lat": 34.7990, "lon": 48.5150, "en": "Hamadan"},
    "اراک": {"lat": 34.0954, "lon": 49.7013, "en": "Arak"},
    "اردبیل": {"lat": 38.2498, "lon": 48.2933, "en": "Ardabil"},
    "گرگان": {"lat": 36.8427, "lon": 54.4353, "en": "Gorgan"},
    "زنجان": {"lat": 36.6736, "lon": 48.4787, "en": "Zanjan"},
    "ساری": {"lat": 36.5633, "lon": 53.0601, "en": "Sari"},
    "قزوین": {"lat": 36.2688, "lon": 50.0041, "en": "Qazvin"},
    "خرم‌آباد": {"lat": 33.4878, "lon": 48.3558, "en": "Khorramabad"},
    "ایلام": {"lat": 33.6374, "lon": 46.4227, "en": "Ilam"},
    "بوشهر": {"lat": 28.9684, "lon": 50.8385, "en": "Bushehr"},
    "سمنان": {"lat": 35.5769, "lon": 53.3970, "en": "Semnan"},
    "شهرکرد": {"lat": 32.3256, "lon": 50.8645, "en": "Shahr-e Kord"},
    "یاسوج": {"lat": 30.6684, "lon": 51.5880, "en": "Yasuj"},
    
    # Universities (key protest locations)
    "دانشگاه شریف": {"lat": 35.7022, "lon": 51.3513, "en": "Sharif University"},
    "دانشگاه تهران": {"lat": 35.7129, "lon": 51.3981, "en": "Tehran University"},
    "دانشگاه امیرکبیر": {"lat": 35.7005, "lon": 51.4056, "en": "Amirkabir University"},
    "دانشگاه علم و صنعت": {"lat": 35.7446, "lon": 51.5111, "en": "Iran University of Science"},
}


class PersianNLPService:
    """
    Persian Natural Language Processing service for analyzing Telegram messages.
    Uses rule-based approaches for speed and reliability.
    """
    
    def __init__(self):
        # Compile regex patterns for efficiency
        self._city_pattern = self._build_city_pattern()
        self._keyword_pattern = self._build_keyword_pattern()
    
    def _build_city_pattern(self) -> re.Pattern:
        """Build regex pattern for city detection"""
        cities = list(PERSIAN_CITIES.keys())
        # Sort by length (longest first) to match "دانشگاه شریف" before "شریف"
        cities.sort(key=len, reverse=True)
        pattern = '|'.join(re.escape(city) for city in cities)
        return re.compile(pattern)
    
    def _build_keyword_pattern(self) -> re.Pattern:
        """Build regex pattern for keyword detection"""
        keywords = list(PROTEST_KEYWORDS.keys())
        keywords.sort(key=len, reverse=True)
        pattern = '|'.join(re.escape(kw) for kw in keywords)
        return re.compile(pattern, re.IGNORECASE)
    
    def analyze(self, text: str) -> Dict:
        """
        Analyze Persian/English text for protest-related content.
        
        Returns:
            Dict with keys: keywords, locations, sentiment, urgency_score, event_type
        """
        if not text:
            return self._empty_result()
        
        # Extract all features
        keywords = self.extract_keywords(text)
        locations = self.detect_locations(text)
        sentiment = self.analyze_sentiment(text)
        urgency = self.calculate_urgency(text, keywords)
        event_type = self.detect_event_type(text)
        
        return {
            "keywords": keywords,
            "locations": locations,
            "sentiment": sentiment,
            "urgency_score": urgency,
            "event_type": event_type,
        }
    
    def _empty_result(self) -> Dict:
        return {
            "keywords": [],
            "locations": [],
            "sentiment": "neutral",
            "urgency_score": 0.3,
            "event_type": None,
        }
    
    def extract_keywords(self, text: str) -> List[Dict]:
        """
        Extract protest-related keywords from text.
        
        Returns:
            List of {"keyword": str, "relevance": float}
        """
        found = []
        text_lower = text.lower()
        
        for keyword, relevance in PROTEST_KEYWORDS.items():
            if keyword in text or keyword.lower() in text_lower:
                found.append({"keyword": keyword, "relevance": relevance})
        
        # Sort by relevance
        found.sort(key=lambda x: x["relevance"], reverse=True)
        return found[:20]  # Limit to top 20
    
    def detect_locations(self, text: str) -> List[Dict]:
        """
        Detect Iranian cities mentioned in text.
        
        Returns:
            List of {"city": str, "city_en": str, "lat": float, "lon": float}
        """
        found = []
        seen = set()
        
        # Search for Persian city names
        for city_fa, data in PERSIAN_CITIES.items():
            if city_fa in text and city_fa not in seen:
                found.append({
                    "city": city_fa,
                    "city_en": data["en"],
                    "lat": data["lat"],
                    "lon": data["lon"],
                })
                seen.add(city_fa)
        
        # Also search for English city names
        text_lower = text.lower()
        for city_fa, data in PERSIAN_CITIES.items():
            en_name = data["en"].lower()
            if en_name in text_lower and city_fa not in seen:
                found.append({
                    "city": city_fa,
                    "city_en": data["en"],
                    "lat": data["lat"],
                    "lon": data["lon"],
                })
                seen.add(city_fa)
        
        return found
    
    def analyze_sentiment(self, text: str) -> str:
        """
        Analyze sentiment of text (rule-based).
        
        Returns:
            'positive', 'negative', or 'neutral'
        """
        text_lower = text.lower()
        
        negative_count = sum(1 for kw in NEGATIVE_KEYWORDS if kw in text or kw.lower() in text_lower)
        
        # Most protest content is negative in nature
        if negative_count >= 3:
            return "negative"
        elif negative_count >= 1:
            return "negative"  # Even one negative keyword is significant
        
        # Check for positive indicators (rare in this context)
        positive_indicators = ["پیروزی", "آزادی", "victory", "success", "freed"]
        positive_count = sum(1 for kw in positive_indicators if kw in text or kw.lower() in text_lower)
        
        if positive_count > negative_count:
            return "positive"
        
        return "neutral"
    
    def calculate_urgency(self, text: str, keywords: List[Dict] = None) -> float:
        """
        Calculate urgency score (0-1) based on text content.
        
        Higher scores indicate more urgent/breaking content.
        """
        if not text:
            return 0.3
        
        score = 0.3  # Base score
        text_lower = text.lower()
        
        # Check urgency keywords
        for keyword, weight in URGENCY_KEYWORDS.items():
            if keyword in text or keyword.lower() in text_lower:
                score = max(score, weight)
        
        # Boost for multiple high-relevance keywords
        if keywords:
            high_relevance = sum(1 for k in keywords if k.get("relevance", 0) >= 0.9)
            if high_relevance >= 3:
                score = min(score + 0.1, 1.0)
        
        # Boost for ALL CAPS (shouting)
        caps_words = len([w for w in text.split() if w.isupper() and len(w) > 2])
        if caps_words >= 3:
            score = min(score + 0.1, 1.0)
        
        # Boost for exclamation marks
        if text.count('!') >= 2:
            score = min(score + 0.05, 1.0)
        
        return round(score, 2)
    
    def detect_event_type(self, text: str) -> Optional[str]:
        """
        Detect the type of event described in text.
        
        Returns:
            'protest', 'clash', 'arrest', 'strike', 'police_presence', or None
        """
        if not text:
            return None
        
        text_lower = text.lower()
        scores = {}
        
        for event_type, keywords in EVENT_TYPE_KEYWORDS.items():
            count = sum(1 for kw in keywords if kw in text or kw.lower() in text_lower)
            if count > 0:
                scores[event_type] = count
        
        if not scores:
            return None
        
        # Return the event type with most matches
        return max(scores, key=scores.get)
    
    def is_relevant(self, text: str, threshold: float = 0.3) -> bool:
        """
        Check if text is relevant to Iran protests.
        
        Args:
            text: Text to check
            threshold: Minimum keyword relevance to be considered relevant
            
        Returns:
            True if text is relevant
        """
        if not text:
            return False
        
        keywords = self.extract_keywords(text)
        if not keywords:
            return False
        
        # At least one keyword with sufficient relevance
        max_relevance = max(k.get("relevance", 0) for k in keywords)
        return max_relevance >= threshold
    
    def get_summary(self, text: str) -> str:
        """
        Generate a brief summary/headline from text.
        
        Returns first 100 chars with location prefix if detected.
        """
        if not text:
            return ""
        
        locations = self.detect_locations(text)
        prefix = ""
        if locations:
            prefix = f"📍 {locations[0]['city_en']}: "
        
        # Clean text
        clean = text.replace('\n', ' ').strip()
        max_len = 100 - len(prefix)
        
        if len(clean) > max_len:
            return prefix + clean[:max_len-3] + "..."
        return prefix + clean


# Singleton instance for reuse
_nlp_service: Optional[PersianNLPService] = None


def get_nlp_service() -> PersianNLPService:
    """Get singleton NLP service instance"""
    global _nlp_service
    if _nlp_service is None:
        _nlp_service = PersianNLPService()
    return _nlp_service


def analyze_text(text: str) -> Dict:
    """Convenience function to analyze text"""
    return get_nlp_service().analyze(text)

