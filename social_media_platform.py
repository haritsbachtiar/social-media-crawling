
from enum import Enum

class SocialMediaPlatform(str, Enum):
    """Supported social media platforms"""
    TWITTER = "twitter"
    INSTAGRAM = "instagram"
    FACEBOOK = "facebook"  # For future implementation
    ALL = "all"  # Analyze across all platforms