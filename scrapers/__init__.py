from .base import BaseScraper, TimeSlot, CourtAvailability, CITIES, City, DEFAULT_CITY
from .registry import ScraperRegistry, scraper_registry

# Import scrapers so they register with scraper_registry (single place to add new scrapers)
from .klaipeda import (
    a1_scraper,
    bsport_scraper,
    fourpadel_scraper,
    padelspot_scraper,
    skycop_scraper,
    slenis_scraper,
)
from .kaunas import (
    kauno_padelis_scraper,
    tennis_space_scraper,
    padel_house_scraper,
)

__all__ = [
    "BaseScraper",
    "TimeSlot",
    "CourtAvailability",
    "CITIES",
    "City",
    "DEFAULT_CITY",
    "ScraperRegistry",
    "scraper_registry",
    "a1_scraper",
    "bsport_scraper",
    "fourpadel_scraper",
    "padelspot_scraper",
    "skycop_scraper",
    "slenis_scraper",
    "kauno_padelis_scraper",
    "tennis_space_scraper",
    "padel_house_scraper",
]
