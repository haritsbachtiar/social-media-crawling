from typing import List, Dict, Optional
from datetime import datetime, date
from pydantic import BaseModel

class Location(BaseModel):
    location_name: str
    total_mentions: int

class Tweet(BaseModel):
    platform: str = "twitter"
    text: str
    time: datetime
    username: str
    sentiment: str
    sentiment_score: float

class User(BaseModel):
    username: str
    followers: int
    sentiment: str
    sentiment_score: float
    total_tweets: int

class Keyword(BaseModel):
    text: str
    mentions: int

class AnalyzeResponse(BaseModel):
    total_mentions: int
    positive_sentiment_percent: float
    avg_engagement_rate: float
    estimated_reach: int
    sentiment_trend: Dict[str, float]  # date -> average sentiment
    top_locations: List[Location]
    top_keywords: List[Keyword]
    recent_mentions: List[Tweet]
    top_influencers: List[User]
    error: Optional[str] = None

class AnalyzeEndpointResponse(BaseModel):
    query: str
    analysis: AnalyzeResponse
    status: str