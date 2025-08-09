from fastapi import FastAPI, HTTPException, Query
from analyzer import analyze
from responses import AnalyzeEndpointResponse
from fastapi.middleware.cors import CORSMiddleware

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
        )
    ):
    """
    Analyze Twitter sentiment and engagement metrics for a given search query.
    
    - **query**: The search term to analyze on Twitter
    - **max_results**: Number of tweets to analyze (1-100)
    
    Returns comprehensive analysis including:
    - Total mentions count
    - Positive sentiment percentage
    - Average engagement rate
    - Estimated reach
    - Sentiment trend over time
    - Top locations
    - Top keywords
    - Recent mentions
    """
    try:
        if not query or len(query.strip()) < 3:
            raise HTTPException(status_code=400, detail="Query must be at least 2 characters long")
        
        # Call the analyze function with the query parameter
        result = analyze(query.strip())
        
        # Check if there's an error in the analysis
        if "error" in result and result.get("total_mentions", 0) == 0:
            raise HTTPException(status_code=500, detail=f"Analysis failed: {result['error']}")
        
        return AnalyzeEndpointResponse(
            query=query.strip(),
            analysis=result,
            status="success"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")