"""
Twitter/X Feed Service

Fetches tweets via Twitter API v2 and stores them for the live feed.
Similar to telegram_feed.py but for Twitter.
"""

import os
import requests
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import desc

from .. import models
from .persian_nlp import get_nlp_service

# Twitter Bearer Token
TWITTER_BEARER_TOKEN = os.getenv("TWITTER_BEARER_TOKEN", "")

# Search queries for Iran-related content
SEARCH_QUERIES = [
    "#Iran",
    "#IranProtests",
    "#IranRevolution2026",
    "#IranMassacer"
]


class TwitterFeedService:
    """
    Service to fetch and process Twitter messages for the live feed.
    """
    
    API_URL = "https://api.twitter.com/2/tweets/search/recent"
    
    def __init__(self, db: Session):
        self.db = db
        self.nlp = get_nlp_service()
        self.bearer_token = TWITTER_BEARER_TOKEN
    
    def fetch_tweets(self, query: str = "#Iran", max_results: int = 10) -> List[Dict]:
        """
        Fetch recent tweets matching a query.
        
        Args:
            query: Search query
            max_results: Maximum tweets to fetch (10-100)
            
        Returns:
            List of tweet dictionaries
        """
        if not self.bearer_token:
            print("  ⚠ Twitter: TWITTER_BEARER_TOKEN not configured - skipping fetch")
            print(f"    Set TWITTER_BEARER_TOKEN environment variable to enable Twitter feed")
            return []
        
        print(f"  Twitter: Fetching tweets for query '{query}'...")
        
        tweets = []
        
        try:
            headers = {
                "Authorization": f"Bearer {self.bearer_token}",
            }
            
            params = {
                "query": f"{query} -is:retweet",
                "max_results": min(max_results, 100),
                "tweet.fields": "created_at,text,author_id,public_metrics,attachments",
                "expansions": "author_id,attachments.media_keys",
                "user.fields": "username,name",
                "media.fields": "url,preview_image_url,type"
            }
            
            resp = requests.get(self.API_URL, headers=headers, params=params, timeout=15)
            
            if resp.status_code == 200:
                data = resp.json()
                raw_tweets = data.get("data", [])
                includes = data.get("includes", {})
                users = {u["id"]: u for u in includes.get("users", [])}
                # Build media lookup by media_key
                media_map = {m["media_key"]: m for m in includes.get("media", [])}
                
                print(f"    ✓ Got {len(raw_tweets)} tweets from Twitter API")
                
                for tweet in raw_tweets:
                    author_id = tweet.get("author_id", "")
                    user_info = users.get(author_id, {})
                    
                    # Extract media from attachments
                    media_url = None
                    media_type = None
                    attachments = tweet.get("attachments", {})
                    media_keys = attachments.get("media_keys", [])
                    
                    if media_keys:
                        # Get first media item
                        first_media = media_map.get(media_keys[0], {})
                        media_type = first_media.get("type")  # photo, video, animated_gif
                        # For photos, use 'url'; for videos, use 'preview_image_url'
                        media_url = first_media.get("url") or first_media.get("preview_image_url")
                    
                    tweets.append({
                        "tweet_id": tweet.get("id"),
                        "text": tweet.get("text", ""),
                        "username": user_info.get("username", "unknown"),
                        "author_name": user_info.get("name", ""),
                        "author_id": author_id,
                        "timestamp": tweet.get("created_at"),
                        "metrics": tweet.get("public_metrics", {}),
                        "media_url": media_url,
                        "media_type": media_type,
                    })
            elif resp.status_code == 401:
                print(f"    ✗ Twitter API 401: Invalid or expired bearer token")
            elif resp.status_code == 403:
                print(f"    ✗ Twitter API 403: Forbidden - check API access level")
            elif resp.status_code == 429:
                print(f"    ✗ Twitter API 429: Rate limit exceeded - try again later")
            else:
                print(f"    ✗ Twitter API error: {resp.status_code} - {resp.text[:200]}")
                
        except requests.exceptions.Timeout:
            print(f"    ✗ Twitter fetch timeout for query '{query}'")
        except requests.exceptions.ConnectionError as e:
            print(f"    ✗ Twitter connection error: {e}")
        except Exception as e:
            print(f"    ✗ Twitter fetch error: {e}")
        
        return tweets
    
    def process_and_store(self, tweets: List[Dict]) -> int:
        """
        Process tweets with NLP and store in database.
        
        Args:
            tweets: List of tweet dictionaries
            
        Returns:
            Number of new tweets stored
        """
        count = 0
        
        for tweet in tweets:
            try:
                tweet_id = tweet.get("tweet_id")
                if not tweet_id:
                    continue
                
                # Check for duplicate
                existing = self.db.query(models.TwitterMessage).filter(
                    models.TwitterMessage.tweet_id == tweet_id
                ).first()
                
                if existing:
                    continue
                
                text = tweet.get("text", "")
                
                # Skip replies (tweets starting with @)
                if text.strip().startswith("@"):
                    continue
                
                # NLP analysis
                nlp_result = self.nlp.analyze(text)
                
                # Parse timestamp
                ts_str = tweet.get("timestamp")
                if ts_str:
                    try:
                        timestamp = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                    except:
                        timestamp = datetime.now(timezone.utc)
                else:
                    timestamp = datetime.now(timezone.utc)
                
                # Extract metrics
                metrics = tweet.get("metrics", {})
                
                # Create message
                msg = models.TwitterMessage(
                    tweet_id=tweet_id,
                    username=tweet.get("username", "unknown"),
                    author_id=tweet.get("author_id"),
                    text=text,
                    text_translated=nlp_result.get("translation"),
                    timestamp=timestamp,
                    sentiment=nlp_result.get("sentiment"),
                    keywords=str(nlp_result.get("keywords", [])),
                    locations_mentioned=str(nlp_result.get("locations", [])),
                    event_type_detected=nlp_result.get("event_type"),
                    urgency_score=nlp_result.get("urgency", 0.5),
                    retweet_count=metrics.get("retweet_count", 0),
                    like_count=metrics.get("like_count", 0),
                    reply_count=metrics.get("reply_count", 0),
                    is_relevant=nlp_result.get("is_relevant", True),
                    media_url=tweet.get("media_url"),
                    media_type=tweet.get("media_type"),
                )
                
                self.db.add(msg)
                count += 1
                
            except Exception as e:
                print(f"  Twitter: Error processing tweet - {e}")
                continue
        
        if count > 0:
            self.db.commit()
            print(f"  Twitter: Stored {count} new tweets")
        
        return count
    
    def fetch_and_process_all(self) -> int:
        """Fetch from all queries and store"""
        total = 0
        
        for query in SEARCH_QUERIES[:3]:  # Limit queries to avoid rate limits
            tweets = self.fetch_tweets(query=query, max_results=10)
            stored = self.process_and_store(tweets)
            total += stored
        
        return total
    
    def get_feed(
        self,
        limit: int = 50,
        hours: int = 24,
        min_urgency: float = 0,
        relevant_only: bool = True,
    ) -> Tuple[List[models.TwitterMessage], int]:
        """
        Get Twitter messages from database for feed display.
        
        Args:
            limit: Maximum messages to return
            hours: Time window in hours
            min_urgency: Minimum urgency score (0-1)
            relevant_only: Only show relevant messages
            
        Returns:
            Tuple of (messages, total_count)
        """
        try:
            cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
            
            query = self.db.query(models.TwitterMessage).filter(
                models.TwitterMessage.timestamp >= cutoff
            )
            
            if relevant_only:
                query = query.filter(models.TwitterMessage.is_relevant == True)
            
            if min_urgency > 0:
                query = query.filter(models.TwitterMessage.urgency_score >= min_urgency)
            
            total = query.count()
            
            messages = query.order_by(
                desc(models.TwitterMessage.urgency_score),
                desc(models.TwitterMessage.timestamp)
            ).limit(limit).all()
            
            return messages, total
            
        except Exception as e:
            print(f"  Twitter feed error: {e}")
            return [], 0


def fetch_twitter_feed(db: Session) -> int:
    """Convenience function for scheduled fetching"""
    service = TwitterFeedService(db)
    return service.fetch_and_process_all()

