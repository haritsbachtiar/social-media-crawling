from fastapi import FastAPI, HTTPException, Query
from analyzer import analyze
from responses import AnalyzeEndpointResponse
from responses import AnalyzeResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional, List
from social_media_platform import SocialMediaPlatform
from instagram_analyzer import analyze_instagram

app = FastAPI(
    title="Social Media Analyzer"
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # in dev, allow all
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get('/')
def root():
    return {
        "message": "Welcome to Twitter Sentiment Analyzer API",
        "endpoints": {
            "/analyze": "Analyze sentiment for a search query",
            "/docs": "API documentation"
        }
    }

@app.get(
    '/analyze',
    response_model=AnalyzeEndpointResponse,
    summary="Analyze tweets for a query"
)
def analyzer_endpoint(
    query: str = Query(
        ..., 
        description = "Search query to analyze",
        example = "kopi",
        min_length = 3
        ),
    platform: SocialMediaPlatform = Query(
        SocialMediaPlatform.TWITTER,
        description="Social media platform to analyze",
        example="twitter"
        )
):
    """
    Analyze sentiment and engagement metrics for a given search query across different social media platforms.
    
    **Parameters:**
    - **query**: The search term to analyze (minimum 3 characters)
    - **platform**: The social media platform to analyze:
        - `twitter`: Analyze Twitter/X posts
        - `instagram`: Analyze Instagram posts  
        - `facebook`: Analyze Facebook posts (coming soon)
        - `all`: Analyze across all available platforms
    
    **Returns comprehensive analysis including:**
    - Total mentions count
    - Positive sentiment percentage  
    - Average engagement rate
    - Estimated reach
    - Sentiment trend over time
    - Top locations
    - Top keywords
    - Recent mentions
    - Top influencers
    """
    try:
        if not query or len(query.strip()) < 3:
            raise HTTPException(
                status_code=400, 
                detail="Query must be at least 3 characters long"
            )
        
        cleaned_query = query.strip()
        
        # Call the appropriate analyzer based on platform
        if platform == SocialMediaPlatform.TWITTER:
            result = analyze(cleaned_query)
            
        elif platform == SocialMediaPlatform.INSTAGRAM:
            result = analyze_instagram(cleaned_query)
            
        elif platform == SocialMediaPlatform.FACEBOOK:
            # Placeholder for future Facebook implementation
            raise HTTPException(
                status_code=501, 
                detail="Facebook analysis is not yet implemented"
            )
            
        elif platform == SocialMediaPlatform.ALL:
            # Analyze across all platforms and combine results
            result = analyze_all_platforms(cleaned_query)
            
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported platform: {platform}"
            )
        
        # Check if there's an error in the analysis
        if hasattr(result, 'error') and result.error:
            raise HTTPException(
                status_code=500, 
                detail=f"Analysis failed: {result.error}"
            )
        
        # Check if analysis returned no data
        if result.total_mentions == 0 and not hasattr(result, 'error'):
            return AnalyzeEndpointResponse(
                query=cleaned_query,
                platform=platform.value,
                analysis=result,
                status="success",
                message=f"No mentions found for '{cleaned_query}' on {platform.value}"
            )
        
        return AnalyzeEndpointResponse(
            query=cleaned_query,
            platform=platform.value,
            analysis=result,
            status="success",
            message=f"Successfully analyzed {result.total_mentions} mentions from {platform.value}"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Internal server error: {str(e)}"
        )

def analyze_all_platforms(query: str) -> AnalyzeResponse:
    """
    Analyze query across all available platforms and combine results
    """
    try:
        # Get results from all platforms
        twitter_result = analyze(query)
        instagram_result = analyze_instagram(query)
        
        # Handle errors - if all platforms fail, return error
        twitter_error = hasattr(twitter_result, 'error') and twitter_result.error
        instagram_error = hasattr(instagram_result, 'error') and instagram_result.error
        
        if twitter_error and instagram_error:
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
                error=f"All platforms failed. Twitter: {twitter_result.error if twitter_error else 'OK'}, Instagram: {instagram_result.error if instagram_error else 'OK'}"
            )
        
        # Use successful results only
        results = []
        if not twitter_error:
            results.append(twitter_result)
        if not instagram_error:
            results.append(instagram_result)
        
        if not results:
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
        
        # Combine results
        combined_result = combine_analysis_results(results)
        return combined_result
        
    except Exception as e:
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
            error=f"Error in multi-platform analysis: {str(e)}"
        )

def combine_analysis_results(results: List[AnalyzeResponse]) -> AnalyzeResponse:
    """
    Combine multiple AnalyzeResponse objects into one
    """
    if not results:
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
    
    # Combine basic metrics
    total_mentions = sum(r.total_mentions for r in results)
    total_positive = sum(r.positive_sentiment_percent * r.total_mentions / 100 for r in results if r.total_mentions > 0)
    avg_positive_sentiment = (total_positive / total_mentions * 100) if total_mentions > 0 else 0
    
    # Average engagement rate weighted by mentions
    total_weighted_engagement = sum(r.avg_engagement_rate * r.total_mentions for r in results if r.total_mentions > 0)
    avg_engagement_rate = (total_weighted_engagement / total_mentions) if total_mentions > 0 else 0
    
    # Sum estimated reach
    estimated_reach = sum(r.estimated_reach for r in results)
    
    # Combine sentiment trends
    combined_sentiment_trend = {}
    for result in results:
        for date, sentiment in result.sentiment_trend.items():
            if date in combined_sentiment_trend:
                # Average the sentiments for the same date
                combined_sentiment_trend[date] = (combined_sentiment_trend[date] + sentiment) / 2
            else:
                combined_sentiment_trend[date] = sentiment
    
    # Combine and re-rank locations
    location_counter = Counter()
    for result in results:
        for location in result.top_locations:
            location_counter[location.location_name] += location.total_mentions
    
    top_locations = [
        Location(location_name=name, total_mentions=count)
        for name, count in location_counter.most_common(5)
    ]
    
    # Combine and re-rank keywords
    keyword_counter = Counter()
    for result in results:
        for keyword in result.top_keywords:
            keyword_counter[keyword.text] += keyword.mentions
    
    top_keywords = [
        Keyword(text=text, mentions=count)
        for text, count in keyword_counter.most_common(10)
    ]
    
    # Combine recent mentions (sorted by time)
    all_mentions = []
    for result in results:
        all_mentions.extend(result.recent_mentions)
    
    # Sort by time and take top 10
    all_mentions.sort(key=lambda x: x.time, reverse=True)
    recent_mentions = all_mentions[:10]
    
    # Combine influencers and re-rank by followers
    all_influencers = []
    for result in results:
        all_influencers.extend(result.top_influencers)
    
    # Remove duplicates by username and keep the one with more followers
    influencer_dict = {}
    for influencer in all_influencers:
        username = influencer.username
        if username not in influencer_dict or influencer.followers > influencer_dict[username].followers:
            influencer_dict[username] = influencer
    
    # Sort by followers and take top 5
    top_influencers = sorted(influencer_dict.values(), key=lambda x: x.followers, reverse=True)[:5]
    
    return AnalyzeResponse(
        total_mentions=total_mentions,
        positive_sentiment_percent=round(avg_positive_sentiment, 2),
        avg_engagement_rate=round(avg_engagement_rate, 4),
        estimated_reach=estimated_reach,
        sentiment_trend=combined_sentiment_trend,
        top_locations=top_locations,
        top_keywords=top_keywords,
        recent_mentions=recent_mentions,
        top_influencers=top_influencers
    )

# Alternative endpoint for specific platforms (more explicit)
@app.get(
    '/analyze/{platform}',
    response_model=AnalyzeEndpointResponse,
    summary="Analyze specific platform"
)
def platform_specific_analyzer(
    platform: SocialMediaPlatform,
    query: str = Query(
        ..., 
        description="Search query to analyze",
        example="kopi",
        min_length=3
    )
):
    """
    Platform-specific analysis endpoint. Same functionality as /analyze but with platform in the URL path.
    
    **Examples:**
    - `/analyze/twitter?query=kopi`
    - `/analyze/instagram?query=food`
    - `/analyze/all?query=travel`
    """
    return analyzer_endpoint(query=query, platform=platform)