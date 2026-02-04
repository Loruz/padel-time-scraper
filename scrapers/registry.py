from datetime import date, datetime, timedelta
from typing import Optional
from cachetools import TTLCache
import asyncio

from .base import BaseScraper, CourtAvailability


class ScraperRegistry:
    """Registry for all scrapers with caching support."""
    
    def __init__(self, cache_ttl: int = 300):
        """
        Initialize registry.
        
        Args:
            cache_ttl: Cache time-to-live in seconds (default: 5 minutes)
        """
        self._scrapers: dict[str, type[BaseScraper]] = {}
        self._cache: TTLCache = TTLCache(maxsize=100, ttl=cache_ttl)
        self._cache_ttl = cache_ttl
    
    def register(self, scraper_class: type[BaseScraper]) -> type[BaseScraper]:
        """Register a scraper class. Can be used as decorator."""
        self._scrapers[scraper_class.name] = scraper_class
        return scraper_class
    
    def get_scraper_names(self) -> list[str]:
        """Get list of registered scraper names."""
        return list(self._scrapers.keys())
    
    def _cache_key(self, scraper_name: str, target_date: date) -> str:
        """Generate cache key."""
        return f"{scraper_name}:{target_date.isoformat()}"
    
    async def scrape_one(
        self, 
        scraper_name: str, 
        target_date: date,
        use_cache: bool = True
    ) -> Optional[CourtAvailability]:
        """Scrape a single venue."""
        if scraper_name not in self._scrapers:
            return None
        
        cache_key = self._cache_key(scraper_name, target_date)
        
        # Check cache
        if use_cache and cache_key in self._cache:
            return self._cache[cache_key]
        
        # Scrape
        scraper_class = self._scrapers[scraper_name]
        async with scraper_class() as scraper:
            result = await scraper.scrape_safe(target_date)
        
        # Cache result
        self._cache[cache_key] = result
        return result
    
    async def scrape_all(
        self, 
        target_date: date,
        use_cache: bool = True
    ) -> list[CourtAvailability]:
        """Scrape all registered venues concurrently."""
        tasks = [
            self.scrape_one(name, target_date, use_cache)
            for name in self._scrapers
        ]
        results = await asyncio.gather(*tasks)
        return [r for r in results if r is not None]
    
    async def scrape_date_range(
        self,
        start_date: date,
        days: int = 7,
        use_cache: bool = True
    ) -> dict[date, list[CourtAvailability]]:
        """Scrape all venues for a range of dates."""
        results = {}
        for i in range(days):
            target_date = start_date + timedelta(days=i)
            results[target_date] = await self.scrape_all(target_date, use_cache)
        return results
    
    def clear_cache(self):
        """Clear all cached data."""
        self._cache.clear()


# Global registry instance
scraper_registry = ScraperRegistry(cache_ttl=300)  # 5 minute cache
