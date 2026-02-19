from datetime import date, timedelta
from typing import Optional
from cachetools import TTLCache
import asyncio

from .base import BaseScraper, CourtAvailability, DEFAULT_CITY


class ScraperRegistry:
    """Registry for all scrapers with caching support. Scrapers are grouped by city; only one city is scraped at a time."""

    def __init__(self, cache_ttl: int = 300):
        """
        Initialize registry.

        Args:
            cache_ttl: Cache time-to-live in seconds (default: 5 minutes)
        """
        # (city, scraper_name) -> scraper class
        self._scrapers: dict[tuple[str, str], type[BaseScraper]] = {}
        self._cache: TTLCache = TTLCache(maxsize=100, ttl=cache_ttl)
        self._cache_ttl = cache_ttl

    def register(self, scraper_class: type[BaseScraper]) -> type[BaseScraper]:
        """Register a scraper class. Can be used as decorator. City is taken from scraper_class.city."""
        key = (scraper_class.city, scraper_class.name)
        self._scrapers[key] = scraper_class
        return scraper_class

    def get_cities(self) -> list[str]:
        """Get list of cities that have at least one registered scraper."""
        return sorted(set(city for city, _ in self._scrapers))

    def get_scraper_names(self, city: Optional[str] = None) -> list[str]:
        """Get list of registered scraper names, optionally filtered by city. If city is None, uses DEFAULT_CITY."""
        target = city if city is not None else DEFAULT_CITY
        return sorted(name for c, name in self._scrapers if c == target)

    def _cache_key(self, city: str, scraper_name: str, target_date: date) -> str:
        """Generate cache key (city-scoped so different cities do not share cache)."""
        return f"{city}:{scraper_name}:{target_date.isoformat()}"

    def _get_scraper_class(
        self, city: str, scraper_name: str
    ) -> Optional[type[BaseScraper]]:
        """Get scraper class by city and name."""
        return self._scrapers.get((city, scraper_name))

    async def scrape_one(
        self,
        scraper_name: str,
        target_date: date,
        city: Optional[str] = None,
        use_cache: bool = True,
    ) -> Optional[CourtAvailability]:
        """Scrape a single venue. city defaults to DEFAULT_CITY."""
        target_city = city if city is not None else DEFAULT_CITY
        scraper_class = self._get_scraper_class(target_city, scraper_name)
        if scraper_class is None:
            return None

        cache_key = self._cache_key(target_city, scraper_name, target_date)

        if use_cache and cache_key in self._cache:
            return self._cache[cache_key]

        async with scraper_class() as scraper:
            result = await scraper.scrape_safe(target_date)

        self._cache[cache_key] = result
        return result

    async def scrape_all(
        self,
        target_date: date,
        city: Optional[str] = None,
        use_cache: bool = True,
    ) -> list[CourtAvailability]:
        """Scrape all registered venues for the given city concurrently. Only one city is scraped at a time."""
        target_city = city if city is not None else DEFAULT_CITY
        names = self.get_scraper_names(target_city)
        tasks = [
            self.scrape_one(name, target_date, city=target_city, use_cache=use_cache)
            for name in names
        ]
        results = await asyncio.gather(*tasks)
        return [r for r in results if r is not None]

    async def scrape_date_range(
        self,
        start_date: date,
        days: int = 7,
        city: Optional[str] = None,
        use_cache: bool = True,
    ) -> dict[date, list[CourtAvailability]]:
        """Scrape all venues for a range of dates for the given city."""
        results = {}
        for i in range(days):
            target_date = start_date + timedelta(days=i)
            results[target_date] = await self.scrape_all(
                target_date, city=city, use_cache=use_cache
            )
        return results

    def has_cache_for_date(self, target_date: date, city: Optional[str] = None) -> bool:
        """Check if cache exists for all scrapers for the given city and date."""
        target_city = city if city is not None else DEFAULT_CITY
        names = self.get_scraper_names(target_city)
        if not names:
            return False
        for scraper_name in names:
            cache_key = self._cache_key(target_city, scraper_name, target_date)
            if cache_key not in self._cache:
                return False
        return True

    def clear_cache(self):
        """Clear all cached data."""
        self._cache.clear()


# Global registry instance
scraper_registry = ScraperRegistry(cache_ttl=600)  # 10 minute cache
