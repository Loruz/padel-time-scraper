from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, date
from typing import Optional
import httpx
from bs4 import BeautifulSoup


@dataclass
class TimeSlot:
    """Represents a single available time slot."""
    slot_time: str  # Format: "HH:MM"
    court_name: Optional[str] = None
    price: Optional[float] = None
    
    def __str__(self) -> str:
        slot = self.slot_time
        if self.court_name:
            slot = f"{self.court_name}: {slot}"
        if self.price:
            slot += f" ({self.price}€)"
        return slot


@dataclass
class CourtAvailability:
    """Availability data for a single venue."""
    venue_name: str
    venue_url: str
    date: date
    venue_image: Optional[str] = None
    time_slots: list[TimeSlot] = field(default_factory=list)
    scraped_at: datetime = field(default_factory=datetime.now)
    error: Optional[str] = None
    
    @property
    def has_availability(self) -> bool:
        return len(self.time_slots) > 0 and self.error is None
    
    @property
    def available_count(self) -> int:
        return len(self.time_slots)


class BaseScraper(ABC):
    """Base class for all padel court scrapers."""
    
    # Override in subclasses
    name: str = "Unknown"
    base_url: str = ""
    
    def __init__(self):
        self.client = httpx.AsyncClient(
            timeout=30.0,
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
        )
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
    
    async def close(self):
        await self.client.aclose()
    
    async def fetch_page(self, url: str) -> str:
        """Fetch HTML content from URL."""
        response = await self.client.get(url)
        response.raise_for_status()
        return response.text
    
    def parse_html(self, html: str) -> BeautifulSoup:
        """Parse HTML string into BeautifulSoup object."""
        return BeautifulSoup(html, "lxml")
    
    @abstractmethod
    async def scrape(self, target_date: date) -> CourtAvailability:
        """
        Scrape availability for a specific date.
        Must be implemented by each venue scraper.
        """
        pass
    
    async def scrape_safe(self, target_date: date) -> CourtAvailability:
        """Scrape with error handling."""
        try:
            return await self.scrape(target_date)
        except Exception as e:
            return CourtAvailability(
                venue_name=self.name,
                venue_url=self.base_url,
                date=target_date,
                error=str(e)
            )
