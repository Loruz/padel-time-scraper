from datetime import date, datetime, timedelta
from fastapi import FastAPI, Request, Query
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from copy import deepcopy

from scrapers import scraper_registry, CourtAvailability

# Import scrapers to register them
from scrapers import a1_scraper  # noqa: F401
from scrapers import slenis_scraper  # noqa: F401
from scrapers import skycop_scraper  # noqa: F401
from scrapers import fourpadel_scraper  # noqa: F401
from scrapers import  padelspot_scraper #noqa: F401           
from scrapers import  bsport_scraper #noqa: F401           

app = FastAPI(title="Padel Time", description="Padel court availability aggregator")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


def get_current_hour_filter() -> str:
    """Get the current hour as a filter string (e.g., '14:00')."""
    now = datetime.now()
    return f"{now.hour:02d}:00"


# Lithuanian day and month names
LT_WEEKDAYS = ["Pirmadienis", "Antradienis", "Trečiadienis", "Ketvirtadienis", "Penktadienis", "Šeštadienis", "Sekmadienis"]
LT_WEEKDAYS_SHORT = ["Pr", "An", "Tr", "Kt", "Pn", "Št", "Sk"]
LT_MONTHS = ["", "Sausio", "Vasario", "Kovo", "Balandžio", "Gegužės", "Birželio", "Liepos", "Rugpjūčio", "Rugsėjo", "Spalio", "Lapkričio", "Gruodžio"]


def format_date_lt(d: date, include_year: bool = False) -> str:
    """Format date in Lithuanian (e.g., 'Pirmadienis, Vas 4')."""
    weekday = LT_WEEKDAYS[d.weekday()]
    month = LT_MONTHS[d.month][:3]  # First 3 letters
    if include_year:
        return f"{weekday}, {month} {d.day}, {d.year}"
    return f"{weekday}, {month} {d.day}"


def filter_by_time(venues: list[CourtAvailability], time_from: str | None) -> list[CourtAvailability]:
    """Filter time slots to only include those at or after time_from."""
    if not time_from:
        return venues
    
    filtered_venues = []
    for venue in venues:
        # Create a copy to avoid modifying cached data
        filtered_venue = deepcopy(venue)
        filtered_venue.time_slots = [
            slot for slot in venue.time_slots
            if slot.slot_time >= time_from
        ]
        filtered_venues.append(filtered_venue)
    
    return filtered_venues


def prepare_venue_table_data(venues: list[CourtAvailability]) -> list[dict]:
    """Prepare venue data for table display with availability lookup."""
    result = []
    for venue in venues:
        # Get unique courts
        courts = list(dict.fromkeys(
            slot.court_name for slot in venue.time_slots if slot.court_name
        ))
        
        availability = {
            (slot.court_name, slot.slot_time): True
            for slot in venue.time_slots
        }
        
        result.append({
            "venue": venue,
            "courts": courts,
            "venue_image": venue.venue_image,
            "availability": availability,
        })
    
    return result


# Time options for the filter dropdown (hourly)
TIME_OPTIONS = [f"{h:02d}:00" for h in range(6, 23)]

# Time columns for the table view (30-min intervals)
TIME_COLUMNS = [f"{h:02d}:{m:02d}" for h in range(6, 23) for m in (0, 30)]


@app.get("/")
async def home(
    request: Request,
    date_str: str = Query(default=None, alias="date"),
    time_from: str = Query(default=None, alias="from")
):
    # Parse date or use today
    if date_str:
        try:
            target_date = date.fromisoformat(date_str)
        except ValueError:
            target_date = date.today()
    else:
        target_date = date.today()
    
    # Generate date options for next 7 days
    date_options = []
    for i in range(7):
        opt_date = date.today() + timedelta(days=i)
        if i == 0:
            label = "Šiandien"
        elif i == 1:
            label = "Rytoj"
        else:
            label = format_date_lt(opt_date)
        date_options.append({
            "date": opt_date,
            "label": label,
            "is_selected": opt_date == target_date
        })
    
    show_all_times = time_from == "all"
    is_today = target_date == date.today()
    
    if show_all_times:
        # User explicitly selected "all times"
        effective_time_filter = None
        time_auto_selected = False
    elif time_from:
        # User selected a specific time
        effective_time_filter = time_from
        time_auto_selected = False
    elif is_today:
        # Auto-filter to current hour for today
        effective_time_filter = get_current_hour_filter()
        time_auto_selected = True
    else:
        # Future date - show all times by default
        effective_time_filter = None
        time_auto_selected = False
    
    # Scrape all venues for the selected date
    venues = await scraper_registry.scrape_all(target_date)
    
    # Filter by effective time
    venues = filter_by_time(venues, effective_time_filter)
    
    # Filter time columns based on effective time
    time_columns = [t for t in TIME_COLUMNS if not effective_time_filter or t >= effective_time_filter]
    
    # Prepare table data with availability lookup
    venue_tables = prepare_venue_table_data(venues)
    
    # Format selected date label in Lithuanian
    if is_today:
        selected_date_label = "Šiandien"
    elif target_date == date.today() + timedelta(days=1):
        selected_date_label = "Rytoj"
    else:
        selected_date_label = format_date_lt(target_date)
    
    return templates.TemplateResponse("index.html", {
        "request": request,
        "venues": venues,
        "venue_tables": venue_tables,
        "selected_date": target_date,
        "selected_date_label": selected_date_label,
        "date_options": date_options,
        "time_options": TIME_OPTIONS,   
        "time_columns": time_columns,
        "selected_time": effective_time_filter,
        "time_auto_selected": time_auto_selected,
        "show_all_times": show_all_times,
        "is_today": is_today,
        "scraper_names": scraper_registry.get_scraper_names(),
    })


@app.post("/refresh")
async def refresh_cache():
    """Clear cache and return fresh data."""
    scraper_registry.clear_cache()
    return {"status": "cache_cleared"}


@app.get("/api/availability")
async def api_availability(
    date_str: str = Query(alias="date", default=None),
    time_from: str = Query(alias="from", default=None),
    venue: str = Query(default=None)
):
    """API endpoint for programmatic access."""
    target_date = date.fromisoformat(date_str) if date_str else date.today()
    
    if venue:
        result = await scraper_registry.scrape_one(venue, target_date)
        venues = [result] if result else []
    else:
        venues = await scraper_registry.scrape_all(target_date)
    
    # Filter by start time if provided
    venues = filter_by_time(venues, time_from)
    
    return {
        "date": target_date.isoformat(),
        "time_from": time_from,
        "venues": [
            {
                "name": v.venue_name,
                "url": v.venue_url,
                "available_slots": v.available_count,
                "error": v.error,
                "slots": [
                    {
                        "time": s.slot_time,
                        "court": s.court_name,
                        "price": s.price,
                    }
                    for s in v.time_slots
                ]
            }
            for v in venues
        ]
    }