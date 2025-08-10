import requests
import urllib.parse
import os
import re
from datetime import datetime
from collections import defaultdict, Counter
from textblob import TextBlob
from dotenv import load_dotenv
from responses import *
from typing import Optional
# from indo_bert_sentiment import IndoBERTSentiment

# indobert_sentiment = IndoBERTSentiment()

def fetch_recent_tweets(query: str):
    try:
        max_results = 10
        url = "https://api.x.com/2/tweets/search/recent"
        
        # Your bearer token
        # load_dotenv()
        bearer_token = os.getenv("BEARER_TOKEN")
        if not bearer_token:
            return {"error": "Authentication Failed"}

        headers = {
            "Authorization": f"Bearer {bearer_token.strip()}"
        }
        
        # FIX: Match exact parameter order and format from curl
        params = {
            "max_results": max_results,
            "query": query,
            "tweet.fields": "created_at,public_metrics,author_id,geo",
            "expansions": "author_id,geo.place_id", 
            "user.fields": "username,public_metrics,verified,location",
            "place.fields": "full_name,country,place_type"
        }
        
        # Debug: Print the full URL being called
        print("🔗 Request URL:", url)
        print("📋 Request params:", params)
        print("🔑 Authorization header:", headers.get("Authorization", "")[:50] + "...")
        
        # Make request with timeout
        response = requests.get(url, headers=headers, params=params, timeout=10)
        
        # Debug: Print response details
        print(f"📊 Response status: {response.status_code}")
        print(f"🌐 Full URL called: {response.url}")

        # Handle HTTP errors
        if response.status_code != 200:
            print(f"❌ Error response: {response.text}")
            return {
                "error": f"Failed to fetch tweets (status {response.status_code})",
                "details": response.text
            }

        # Try parsing JSON
        try:
            json_response = response.json()
            print(f"✅ Successfully got {len(json_response.get('data', []))} tweets")
            return json_response
        except ValueError as e:
            print(f"❌ JSON parsing error: {e}")
            return {
                "error": "Invalid JSON response",
                "details": response.text
            }

    except requests.exceptions.Timeout:
        return {"error": "Request timed out"}
    except requests.exceptions.ConnectionError:
        return {"error": "Network connection error"}
    except Exception as e:
        return {"error": f"Unexpected error: {str(e)}"}

def extract_indonesian_city(location_string: str) -> Optional[str]:
    """
    Extract Indonesian city name from location string with Indonesia-specific optimizations.
    Handles various Indonesian location formats like:
    - "Jakarta, Indonesia" -> "Jakarta"
    - "Kota Bandung, Jawa Barat" -> "Bandung"
    - "Surabaya, Jawa Timur, Indonesia" -> "Surabaya"
    - "📍 Yogyakarta" -> "Yogyakarta"
    - "Tinggal di Medan" -> "Medan"
    """
    if not location_string or not location_string.strip():
        return None
    
    # Clean the location string
    location = location_string.strip()
    
    # Remove emojis and special characters at the beginning
    location = re.sub(r'^[^\w\s]+', '', location).strip()
    
    # Indonesian-specific prefixes to remove
    prefixes_to_remove = [
        'tinggal di', 'domisili', 'asal', 'dari', 'di', 'kota', 'kabupaten',
        'living in', 'based in', 'from', 'in', 'at', 'currently in',
        'located in', 'residing in', 'home:', 'location:', 'here:'
    ]
    
    location_lower = location.lower()
    for prefix in prefixes_to_remove:
        if location_lower.startswith(prefix):
            location = location[len(prefix):].strip()
            break
    
    # Indonesian city name mappings and aliases
    city_aliases = {
        'dki jakarta': 'Jakarta',
        'jakarta pusat': 'Jakarta',
        'jakarta selatan': 'Jakarta',
        'jakarta utara': 'Jakarta',
        'jakarta barat': 'Jakarta',
        'jakarta timur': 'Jakarta',
        'jogja': 'Yogyakarta',
        'yogya': 'Yogyakarta',
        'jogjakarta': 'Yogyakarta',
        'bandung raya': 'Bandung',
        'kota bandung': 'Bandung',
        'solo': 'Surakarta',
        'semarang': 'Semarang',
        'surabaya': 'Surabaya',
        'medan': 'Medan',
        'palembang': 'Palembang',
        'makassar': 'Makassar',
        'denpasar': 'Denpasar',
        'bali': 'Denpasar',
        'malang': 'Malang',
        'bogor': 'Bogor',
        'tangerang': 'Tangerang',
        'bekasi': 'Bekasi',
        'depok': 'Depok',
        'pontianak': 'Pontianak',
        'balikpapan': 'Balikpapan',
        'banjarmasin': 'Banjarmasin',
        'manado': 'Manado',
        'pekanbaru': 'Pekanbaru',
        'padang': 'Padang',
        'batam': 'Batam',
        'samarinda': 'Samarinda'
    }
    
    # Check for direct city alias matches first
    location_clean = location.lower().strip()
    if location_clean in city_aliases:
        return city_aliases[location_clean]
    
    # Split by common separators and take the first part (usually the city)
    separators = [',', '|', '-', '•', '·', '/']
    
    for sep in separators:
        if sep in location:
            parts = location.split(sep)
            city_candidate = parts[0].strip().lower()
            
            # Check if first part matches any Indonesian city
            if city_candidate in city_aliases:
                return city_aliases[city_candidate]
            
            # Clean and format the city name
            city_candidate = re.sub(r'[^\w\s]', '', city_candidate).strip()
            if len(city_candidate) > 2 and not city_candidate.isdigit():
                # Remove "kota" or "kabupaten" prefix if present
                if city_candidate.startswith(('kota ', 'kabupaten ')):
                    city_candidate = city_candidate.split(' ', 1)[1]
                return city_candidate.title()
    
    # If no separator found, check whole string
    if location_clean in city_aliases:
        return city_aliases[location_clean]
    
    # Clean and return the whole string
    city_candidate = re.sub(r'[^\w\s]', '', location).strip().lower()
    if len(city_candidate) > 2 and not city_candidate.isdigit():
        # Remove "kota" or "kabupaten" prefix if present
        if city_candidate.startswith(('kota ', 'kabupaten ')):
            city_candidate = city_candidate.split(' ', 1)[1]
        return city_candidate.title()
    
    return None
    
def extract_city_name(location_string: str) -> Optional[str]:
    """
    Extract city name from location string.
    Handles various location formats like:
    - "Jakarta, Indonesia" -> "Jakarta"
    - "New York, NY, USA" -> "New York"
    - "London, England" -> "London"
    - "📍 Bandung" -> "Bandung"
    - "Living in Paris" -> "Paris"
    """
    if not location_string or not location_string.strip():
        return None
    
    # Clean the location string
    location = location_string.strip()
    
    # Remove emojis and special characters at the beginning
    location = re.sub(r'^[^\w\s]+', '', location).strip()
    
    # Remove common prefixes
    prefixes_to_remove = [
        'living in', 'based in', 'from', 'in', 'at', 'currently in',
        'located in', 'residing in', 'home:', 'location:', 'here:'
    ]
    
    location_lower = location.lower()
    for prefix in prefixes_to_remove:
        if location_lower.startswith(prefix):
            location = location[len(prefix):].strip()
            break
    
    # Split by common separators and take the first part (usually the city)
    separators = [',', '|', '-', '•', '·', '/']
    
    for sep in separators:
        if sep in location:
            parts = location.split(sep)
            city_candidate = parts[0].strip()
            if city_candidate:
                # Additional cleaning for the city name
                city_candidate = re.sub(r'[^\w\s]', '', city_candidate).strip()
                if len(city_candidate) > 1 and not city_candidate.isdigit():
                    return city_candidate.title()
    
    # If no separator found, clean and return the whole string
    city_candidate = re.sub(r'[^\w\s]', '', location).strip()
    if len(city_candidate) > 1 and not city_candidate.isdigit():
        return city_candidate.title()
    
    return None


def get_sentiment_label(polarity: float) -> str:
        """Convert sentiment polarity to label"""
        if polarity > 0.1:
            return "positive"
        elif polarity < -0.1:
            return "negative"
        else:
            return "neutral"

def analyze(query: str):
    data = fetch_recent_tweets(query=query)
    print(data)
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
    
    tweets = data.get("data", [])
    includes = data.get("includes", {})
    users = {u["id"]: u for u in includes.get("users", [])}
    places = {p["id"]: p for p in includes.get("places", [])}

    total_mentions = len(tweets)

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

    recent_tweets_list = []
    user_sentiments = defaultdict(lambda: {"sentiments": [], "followers": 0, "tweet_count": 0})

    for t in tweets:
        try:
            text = t.get("text", "")
            author_id = t.get("author_id")

            # Sentiment (More Acurate But Takes Time) Will Change To This When Available
            # sentiment_result = indobert_sentiment.get_detailed_sentiment(text)
            # polarity = sentiment_result['polarity']
            # sentiment_label = sentiment_result['label']

            # Sentiment (Simpler Version)
            sentiment_blob = TextBlob(text)
            polarity = sentiment_blob.sentiment.polarity
            sentiment_label = get_sentiment_label(polarity)

            # Count positive tweets
            if polarity > 0:
                positive_count += 1

            # Date parsing for trends
            created_at = t.get("created_at")
            parsed_datetime = None
            if created_at:
                try:
                    parsed_datetime = datetime.fromisoformat(created_at.rstrip("Z"))
                    date = parsed_datetime.date().isoformat()
                    trend[date][0] += polarity
                    trend[date][1] += 1
                except ValueError:
                    date = datetime.now().date().isoformat()
                    trend[date][0] += polarity
                    trend[date][1] += 1

            # Get author information
            author = users.get(author_id)
            username = ""
            if author:
                username = f"@{author.get('username', 'unknown')}"
                followers = author.get("public_metrics", {}).get("followers_count", 0)
                location = author.get("location")
                
                # Track user sentiments for influencer analysis
                user_sentiments[author_id]["sentiments"].append(polarity)
                user_sentiments[author_id]["followers"] = followers
                user_sentiments[author_id]["tweet_count"] += 1
                
                # Engagement calculation
                metrics = t.get("public_metrics", {})
                like_count = metrics.get("like_count", 0)
                retweet_count = metrics.get("retweet_count", 0)
                reply_count = metrics.get("reply_count", 0)
                
                # Calculate engagement rate (avoid division by zero)
                if followers > 0:
                    eng = (like_count + retweet_count + reply_count) / followers * 100
                else:
                    # For users with 0 followers, use raw engagement count
                    eng = like_count + retweet_count + reply_count
                engagements.append(eng)
                
                reach_set.add(author_id)

                # Profile location as fallback (since geo data is rare)
                if location and location.strip():
                    # Try Indonesian city extraction first
                    city_name = extract_indonesian_city(location)
                    if not city_name:
                        # Fallback to general city extraction
                        city_name = extract_city_name(location)
                    
                    if city_name:
                        city_counter[city_name] += 1
            
            # Indonesian city extraction from GEO DATA ONLY
            geo_data = t.get("geo")
            if geo_data and geo_data.get("place_id"):
                place = places.get(geo_data["place_id"])
                if place:
                    place_country = place.get("country", "").lower()
                    place_name = place.get("full_name", "")
                    place_type = place.get("place_type", "")
                    
                    city_from_geo = None

                    # If it's Indonesia, use Indonesian-specific extraction
                    if place_country == "indonesia" or "indonesia" in place_country:
                        if place_type in ["city", "admin"]:
                            city_from_geo = extract_indonesian_city(place_name)
                        elif place_name:
                            city_from_geo = extract_indonesian_city(place_name)
                    
                    # For non-Indonesian locations, use global city extraction
                    else:
                        if place_type in ["city", "admin"]:
                            city_from_geo = extract_city_name(place_name)
                        elif place_name:
                            city_from_geo = extract_city_name(place_name)
                    
                    if city_from_geo:
                        city_counter[city_from_geo] += 1

            # Create Tweet object for recent mentions
            if username:
                if not parsed_datetime:
                    parsed_datetime = datetime.now()

            # if parsed_datetime and username:
                tweet_obj = Tweet(
                    platform="twitter",
                    text=text,
                    time=parsed_datetime,
                    username=username,
                    sentiment=sentiment_label,
                    sentiment_score=round(polarity, 3)
                )
                recent_tweets_list.append(tweet_obj)

            # Keywords extraction 
            words = []
            # Remove mentions and URLs first
            clean_text = re.sub(r'@\w+|https?://\S+', '', text)

            for word in clean_text.split():
                # Remove punctuation but keep the word
                clean_word = re.sub(r'[^\w]', '', word.lower()).strip()
            
                # More lenient filtering
                if (len(clean_word) >= 2 and  # Allow 2+ character words
                    not clean_word.isdigit() and  # Exclude pure numbers
                    clean_word.isalpha() and  # Only alphabetic characters
                    clean_word not in ['rt', 'the', 'and', 'or', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by']):  # Exclude common stop words
                    words.append(clean_word)
            
            keywords_counter.update(words)

        except Exception as e:
            print(f"Error processing tweet: {e}")
            continue

    # Calculate final metrics
    sentiment_percent = (positive_count / total_mentions * 100) if total_mentions > 0 else 0
    avg_engagement = (sum(engagements) / len(engagements)) if engagements else 0

    # Sentiment trend calculation
    sentiment_trend = {}
    for date, (sentiment_sum, tweet_count) in trend.items():
        if tweet_count > 0:
            sentiment_trend[date] = round(sentiment_sum / tweet_count, 3)

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
    for author_id, data in user_sentiments.items():
        if data["tweet_count"] > 0:  # Only users with some influence
            avg_sentiment = sum(data["sentiments"]) / len(data["sentiments"])
            author = users.get(author_id)
            if author:
                username = f"@{author.get('username', 'unknown')}"
                user_obj = User(
                    username=username,
                    followers=data["followers"],
                    sentiment=get_sentiment_label(avg_sentiment),
                    sentiment_score=round(avg_sentiment, 3),
                    total_tweets=data["tweet_count"]
                )
                top_influencers.append(user_obj)

    # Sort influencers by followers count
    top_influencers.sort(key=lambda x: x.followers, reverse=True)
    top_influencers = top_influencers[:5]  # Top 5 influencers

    # Sort recent tweets by time (most recent first)
    recent_tweets_list.sort(key=lambda x: x.time, reverse=True)
    recent_mentions = recent_tweets_list[:5]  # Top 5 recent mentions

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