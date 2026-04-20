# Redis connection singleton used across the application for caching and index sync.
"""
app/data/redis_client.py
Redis connection singleton.
Exports: get_redis() -> Redis
Used by: IndexService, upload rate-limit checks.
"""
import redis
from app.core.config import get_settings
 
_redis_client: redis.Redis | None = None
 
 
def get_redis() -> redis.Redis:
    """
    Returns a singleton Redis client.
    decode_responses=True so all values are strings (JSON).
    """
    global _redis_client
    if _redis_client is None:
        settings = get_settings()
        _redis_client = redis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
        )
    return _redis_client
