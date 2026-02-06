import os
from datetime import date, datetime, timedelta
from collections import defaultdict
from fastapi import FastAPI, Request, Query
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from copy import deepcopy

from scrapers import scraper_registry, CourtAvailability

# Rate limiting configuration
RATE_LIMIT_MAX_REFRESHES = 5  # Max refreshes allowed in the window
RATE_LIMIT_WINDOW_SECONDS = 300  # 5 minute window
RATE_LIMIT_COOLDOWN_SECONDS = 60  # Cooldown when limit exceeded

# In-memory rate limit storage: {ip: [timestamp1, timestamp2, ...]}
refresh_timestamps: dict[str, list[datetime]] = defaultdict(list)
# Track last requested date per IP to detect date changes
last_requested_dates: dict[str, date] = {}

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
    month = LT_MONTHS[d.month][:3]
    if include_year:
        return f"{weekday}, {month} {d.day}, {d.year}"
    return f"{weekday}, {month} {d.day}"


def filter_by_time(venues: list[CourtAvailability], time_from: str | None) -> list[CourtAvailability]:
    """Filter time slots to only include those at or after time_from."""
    if not time_from:
        return venues
    
    filtered_venues = []
    for venue in venues:
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
    ip = get_client_ip(request)
    
    # Parse date or use today
    if date_str:
        try:
            target_date = date.fromisoformat(date_str)
        except ValueError:
            target_date = date.today()
    else:
        target_date = date.today()
    
    # Validate date is within allowed range
    if not is_date_allowed(target_date):
        target_date = date.today()
    
    # Check if this is a date change (different from last requested date)
    last_date = last_requested_dates.get(ip)
    is_date_change = last_date is not None and last_date != target_date
    
    # Apply rate limiting for date changes ONLY if cache doesn't exist
    # (allows free navigation when using cached data)
    rate_limited_message = None
    if is_date_change:
        # Check if cache exists for the target date
        cache_exists = scraper_registry.has_cache_for_date(target_date)
        
        if not cache_exists:
            # Cache doesn't exist - will trigger scrape, so apply rate limiting
            status = get_rate_limit_status(ip)
            if not status["allowed"]:
                # Rate limited - keep the last date instead of changing
                target_date = last_date if last_date and is_date_allowed(last_date) else date.today()
                cooldown_seconds = status.get("cooldown_seconds", 0)
                rate_limited_message = f"Per daug datų keitimų. Palaukite {cooldown_seconds}s."
            else:
                # Record date change as refresh attempt (will trigger scrape)
                record_refresh_attempt(ip)
        # If cache exists, allow free navigation without rate limiting
    
    # Update last requested date (only if not rate limited)
    if not rate_limited_message:
        last_requested_dates[ip] = target_date
    
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
        "rate_limited_message": rate_limited_message,
        "google_analytics_id": os.environ.get("GOOGLE_ANALYTICS_ID", ""),
    })


def get_client_ip(request: Request) -> str:
    """Get client IP from request, considering proxies."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def clean_old_timestamps(ip: str) -> None:
    """Remove timestamps older than the rate limit window."""
    cutoff = datetime.now() - timedelta(seconds=RATE_LIMIT_WINDOW_SECONDS)
    refresh_timestamps[ip] = [
        ts for ts in refresh_timestamps[ip] if ts > cutoff
    ]


def is_date_allowed(target_date: date) -> bool:
    """Check if date is within allowed range (today to 6 days ahead)."""
    today = date.today()
    max_date = today + timedelta(days=6)
    return today <= target_date <= max_date


def get_rate_limit_status(ip: str) -> dict:
    """Get current rate limit status for an IP."""
    clean_old_timestamps(ip)
    timestamps = refresh_timestamps[ip]
    
    used = len(timestamps)
    remaining = max(0, RATE_LIMIT_MAX_REFRESHES - used)
    
    # Check if in cooldown (exceeded limit)
    if used >= RATE_LIMIT_MAX_REFRESHES and timestamps:
        oldest = min(timestamps)
        cooldown_ends = oldest + timedelta(seconds=RATE_LIMIT_WINDOW_SECONDS)
        seconds_until_reset = (cooldown_ends - datetime.now()).total_seconds()
        
        if seconds_until_reset > 0:
            return {
                "allowed": False,
                "remaining": 0,
                "cooldown_seconds": int(seconds_until_reset),
                "max_refreshes": RATE_LIMIT_MAX_REFRESHES,
            }
    
    return {
        "allowed": True,
        "remaining": remaining,
        "cooldown_seconds": 0,
        "max_refreshes": RATE_LIMIT_MAX_REFRESHES,
    }


def record_refresh_attempt(ip: str) -> dict:
    """Record a refresh attempt and return updated status."""
    status = get_rate_limit_status(ip)
    
    if not status["allowed"]:
        return status
    
    # Record this refresh
    refresh_timestamps[ip].append(datetime.now())
    
    # Return updated status
    return get_rate_limit_status(ip)


@app.get("/refresh/status")
async def refresh_status(request: Request):
    """Get current rate limit status."""
    ip = get_client_ip(request)
    return get_rate_limit_status(ip)


@app.post("/refresh")
async def refresh_cache(request: Request):
    """Clear cache and return fresh data with rate limiting."""
    ip = get_client_ip(request)
    status = record_refresh_attempt(ip)
    
    if not status["allowed"]:
        return {
            "status": "rate_limited",
            "message": "Too many refreshes. Please wait.",
            **status
        }
    
    # Clear cache
    scraper_registry.clear_cache()
    
    return {
        "status": "cache_cleared",
        **status
    }


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