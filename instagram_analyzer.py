from responses import AnalyzeResponse
from dotenv import load_dotenv
from responses import *

load_dotenv()

import os
import re
import requests
from datetime import datetime
from typing import Optional, Dict, List
from collections import defaultdict, Counter
from textblob import TextBlob

def fetch_instagram_posts(query: str, search_limit: int = 5, results_limit: int = 10):
    """
    Fetch Instagram posts using Apify API with search parameter
    """
    
    url = "https://api.apify.com/v2/acts/apify~instagram-scraper/run-sync-get-dataset-items"
    
    headers = {
        "Content-Type": "application/json"
    }
    
    # Clean query - remove # if present for hashtag search
    clean_query = query.replace('#', '') if query.startswith('#') else query
    
    payload = {
        "search": clean_query,
        "searchType": "hashtag",  # bisa juga "user" atau "place"
        "searchLimit": search_limit,
        "resultsType": "posts",
        "resultsLimit": results_limit,
        "onlyPostsNewerThan": "7 days",  # untuk analisis yang relevan
        "addParentData": False  # tidak perlu untuk analisis basic
    }
    
    load_dotenv()
    APIFY_TOKEN = os.getenv("APIFY_TOKEN")

    params = {
        "token": APIFY_TOKEN
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, params=params)
        response.raise_for_status()
        result = response.json()
        
        # Debug: print structure untuk troubleshooting
        print("API Response type:", type(result))
        if isinstance(result, dict):
            print("Response keys:", list(result.keys()) if result else "Empty dict")
        elif isinstance(result, list):
            print("Response is list with length:", len(result))
            
        return result
        
    except requests.exceptions.RequestException as e:
        return {"error": f"Failed to fetch Instagram data: {str(e)}"}
    except Exception as e:
        return {"error": f"Unexpected error: {str(e)}"}

def analyze_instagram(query: str, search_limit: int = 10, results_limit: int = 50):
    """
    Analyze Instagram posts for a given query/hashtag
    Returns AnalyzeResponse with Instagram data
    """
    
    # Fetch Instagram posts data dengan parameter yang fleksibel
    data = fetch_instagram_posts(query=query, search_limit=search_limit, results_limit=results_limit)
    
    # Handle different response structures
    if isinstance(data, dict):
        if "error" in data:
            return AnalyzeResponse(
                total_mentions=0,
                positive_sentiment_percent=0,
                avg_engagement_rate=0,
                estimated_reach=0,
                sentiment_trend={},
                top_locations=[],
                top_keywords=[],
                recent_mentions=[],
                top_influencers=[],
                error=data["error"]
            )
        # Extract posts from the hashtag data structure
        posts = []
        if isinstance(data, list) and len(data) > 0:
            hashtag_data = data[0]  # First hashtag object
            # Combine topPosts and latestPosts
            posts.extend(hashtag_data.get("topPosts", []))
            posts.extend(hashtag_data.get("latestPosts", []))
        else:
            # Fallback for other structures
            posts = data.get("data", []) or data.get("items", []) or data.get("posts", [])
    elif isinstance(data, list):
        # Handle list response - could be list of hashtag objects
        posts = []
        for item in data:
            if isinstance(item, dict):
                posts.extend(item.get("topPosts", []))
                posts.extend(item.get("latestPosts", []))
            else:
                posts.append(item)
    else:
        print("Unexpected data format:", type(data))
        posts = []
    
    print("Instagram data received:", len(posts))
    total_mentions = len(posts)

    if total_mentions == 0:
        return AnalyzeResponse(
            total_mentions=0,
            positive_sentiment_percent=0,
            avg_engagement_rate=0,
            estimated_reach=0,
            sentiment_trend={},
            top_locations=[],
            top_keywords=[],
            recent_mentions=[],
            top_influencers=[]
        )

    positive_count = 0
    trend = defaultdict(lambda: [0, 0])  # date -> [sent_sum, count]
    engagements = []
    reach_set = set()
    city_counter = Counter()
    keywords_counter = Counter()
    
    recent_posts_list = []
    user_sentiments = defaultdict(lambda: {"sentiments": [], "followers": 0, "post_count": 0, "total_engagement": 0})

    for post in posts:
        try:
            # Extract post data from the new structure
            caption = post.get("caption", "") or ""
            username = post.get("ownerUsername", "") or ""
            owner_full_name = post.get("ownerFullName", "") or ""
            owner_id = post.get("ownerId", "") or ""
            
            # Sentiment analysis on caption
            if caption:
                sentiment_blob = TextBlob(caption)
                polarity = sentiment_blob.sentiment.polarity
                sentiment_label = get_sentiment_label(polarity)
                
                # Count positive posts
                if polarity > 0:
                    positive_count += 1
            else:
                polarity = 0
                sentiment_label = "neutral"

            # Date parsing for trends
            timestamp = post.get("timestamp")
            parsed_datetime = None
            
            if timestamp:
                try:
                    # Handle ISO format timestamp
                    if isinstance(timestamp, str):
                        # Remove Z and parse ISO format
                        clean_timestamp = timestamp.rstrip("Z")
                        if "+" in clean_timestamp:
                            clean_timestamp = clean_timestamp.split("+")[0]
                        parsed_datetime = datetime.fromisoformat(clean_timestamp)
                    elif isinstance(timestamp, (int, float)):
                        parsed_datetime = datetime.fromtimestamp(timestamp)
                    
                    if parsed_datetime:
                        date = parsed_datetime.date().isoformat()
                        trend[date][0] += polarity
                        trend[date][1] += 1
                except (ValueError, TypeError) as e:
                    print(f"Date parsing error: {e}")
                    date = datetime.now().date().isoformat()
                    trend[date][0] += polarity
                    trend[date][1] += 1
            else:
                parsed_datetime = datetime.now()
                date = parsed_datetime.date().isoformat()
                trend[date][0] += polarity
                trend[date][1] += 1

            # Engagement calculation from the response structure
            likes = post.get("likesCount", 0) or 0
            comments = post.get("commentsCount", 0) or 0
            video_plays = post.get("videoPlayCount", 0) or post.get("igPlayCount", 0) or 0
            reshares = post.get("reshareCount", 0) or 0
            
            # Total engagement
            total_engagement = likes + comments + reshares
            
            # For Instagram, we don't always have follower count per post
            # Use a reasonable engagement rate calculation
            if total_engagement > 0:
                # Estimate engagement rate based on likes (assuming average account size)
                estimated_followers = max(likes * 10, 1000)  # Rough estimation
                eng_rate = (total_engagement / estimated_followers) * 100
                engagements.append(min(eng_rate, 100))  # Cap at 100%
            
            # Track unique users for reach estimation
            if owner_id:
                reach_set.add(str(owner_id))
            elif username:
                reach_set.add(username)
            
            # Track user sentiments for influencer analysis
            if username:
                user_sentiments[username]["sentiments"].append(polarity)
                user_sentiments[username]["post_count"] += 1
                user_sentiments[username]["total_engagement"] += total_engagement
                
                # Try to estimate followers from engagement
                if likes > 0:
                    estimated_followers = likes * 15  # Rough estimation
                    user_sentiments[username]["followers"] = max(
                        user_sentiments[username]["followers"], 
                        estimated_followers
                    )

            # Location extraction
            location_name = post.get("locationName")
            if location_name:
                city_name = extract_instagram_location(location_name)
                if city_name:
                    city_counter[city_name] += 1

            # Create Post object for recent mentions
            if username and caption:
                if not parsed_datetime:
                    parsed_datetime = datetime.now()
                
                formatted_username = f"@{username}" if not username.startswith('@') else username
                
                post_obj = Tweet(  # Reusing Tweet class
                    platform="instagram",
                    text=caption[:200] + "..." if len(caption) > 200 else caption,
                    time=parsed_datetime,
                    username=formatted_username,
                    sentiment=sentiment_label,
                    sentiment_score=round(polarity, 3)
                )
                recent_posts_list.append(post_obj)

            # Keywords extraction from caption and hashtags
            if caption:
                # Extract hashtags from the hashtags array if available
                hashtags_list = post.get("hashtags", [])
                for hashtag in hashtags_list[:10]:  # Limit hashtags
                    clean_hashtag = hashtag.lower() if isinstance(hashtag, str) else str(hashtag).lower()
                    if len(clean_hashtag) > 2:
                        keywords_counter[clean_hashtag] += 3  # Weight hashtags higher
                
                # Also extract hashtags from caption as fallback
                caption_hashtags = re.findall(r'#(\w+)', caption)
                for hashtag in caption_hashtags[:5]:
                    clean_hashtag = hashtag.lower()
                    if len(clean_hashtag) > 2:
                        keywords_counter[clean_hashtag] += 2
                
                # Extract regular words from caption
                clean_text = re.sub(r'#\w+|@\w+|https?://\S+', '', caption)
                words = []
                
                for word in clean_text.split():
                    clean_word = re.sub(r'[^\w]', '', word.lower()).strip()
                    
                    if (len(clean_word) >= 3 and
                        not clean_word.isdigit() and
                        clean_word.isalpha() and
                        clean_word not in STOPWORDS):
                        words.append(clean_word)
                
                keywords_counter.update(words)

        except Exception as e:
            print(f"Error processing Instagram post: {e}")
            continue

    # Calculate final metrics
    sentiment_percent = (positive_count / total_mentions * 100) if total_mentions > 0 else 0
    avg_engagement = (sum(engagements) / len(engagements)) if engagements else 0

    # Sentiment trend calculation
    sentiment_trend = {}
    for date, (sentiment_sum, post_count) in trend.items():
        if post_count > 0:
            sentiment_trend[date] = round(sentiment_sum / post_count, 3)

    # Create Location objects
    top_locations = [
        Location(location_name=city, total_mentions=count)
        for city, count in city_counter.most_common(5)
    ]

    # Create Keyword objects
    top_keywords = [
        Keyword(text=word, mentions=count)
        for word, count in keywords_counter.most_common(10)
    ]

    # Create User objects for top influencers
    top_influencers = []
    for username, data in user_sentiments.items():
        if data["post_count"] > 0:
            avg_sentiment = sum(data["sentiments"]) / len(data["sentiments"])
            formatted_username = f"@{username}" if not username.startswith('@') else username
            
            user_obj = User(
                username=formatted_username,
                followers=data["followers"],
                sentiment=get_sentiment_label(avg_sentiment),
                sentiment_score=round(avg_sentiment, 3),
                total_tweets=data["post_count"]
            )
            top_influencers.append(user_obj)

    # Sort influencers by engagement and followers
    top_influencers.sort(key=lambda x: (x.followers, x.total_tweets), reverse=True)
    top_influencers = top_influencers[:5]

    # Sort recent posts by time (most recent first)
    recent_posts_list.sort(key=lambda x: x.time, reverse=True)
    recent_mentions = recent_posts_list[:5]

    return AnalyzeResponse(
        total_mentions=total_mentions,
        positive_sentiment_percent=round(sentiment_percent, 2),
        avg_engagement_rate=round(avg_engagement, 4),
        estimated_reach=len(reach_set),
        sentiment_trend=sentiment_trend,
        top_locations=top_locations,
        top_keywords=top_keywords,
        recent_mentions=recent_mentions,
        top_influencers=top_influencers
    )

def get_sentiment_label(polarity: float) -> str:
    """Convert polarity score to sentiment label"""
    if polarity > 0.1:
        return "positive"
    elif polarity < -0.1:
        return "negative"
    else:
        return "neutral"

def extract_instagram_location(location_data) -> str:
    """Extract city name from location data"""
    if isinstance(location_data, str):
        return location_data
    elif isinstance(location_data, dict):
        return location_data.get('name', '')
    return ""

# Common stopwords to filter out
STOPWORDS = {
    'the', 'and', 'but', 'for', 'are', 'this', 'that', 'with', 'have', 'from', 
    'they', 'know', 'want', 'been', 'good', 'much', 'some', 'time', 'very', 
    'when', 'come', 'here', 'just', 'like', 'over', 'also', 'back', 'after', 
    'first', 'well', 'way', 'even', 'new', 'work', 'will', 'can', 'said', 
    'each', 'which', 'their', 'said', 'them', 'she', 'may', 'use', 'her', 
    'than', 'now', 'look', 'only', 'come', 'its', 'over', 'think', 'also', 
    'your', 'years', 'way', 'these', 'give', 'day', 'most', 'us'
}