from datetime import date
import json
import httpx

from ..base import BaseScraper, CourtAvailability, TimeSlot, City
from ..helpers import (
    get_slot_price_from_style,
    parse_price_legend,
    parse_price_from_time_descriptions,
)
from ..registry import scraper_registry


@scraper_registry.register
class PadelHouseScraper(BaseScraper):
    city = City.KAUNAS
    name = "Padel House"
    base_url = "https://rezervacija.padelhouse.lt"

    async def scrape(self, target_date: date) -> CourtAvailability:
        date_str = target_date.strftime("%Y-%m-%d")  # e.g. 2026-02-16
        async with httpx.AsyncClient(
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            },
        ) as client:
            response = await client.post(
                f"{self.base_url}/lt/timetable",
                data={"dateFor": date_str},
            )
            if response.status_code != 200:
                raise Exception(f"POST failed: {response.status_code}")
            raw = response.text

        # API returns JSON: { "data": "<table class=\"desktop\">..." }
        try:
            payload = json.loads(raw)
            html = payload.get("data", raw)
        except json.JSONDecodeError:
            html = raw

        soup = self.parse_html(html)
        # Try legend (rbt-table / Vienos valandos kaina), then .time-description pricing (desktop layout)
        color_to_price = parse_price_legend(soup) or parse_price_from_time_descriptions(soup)
        if not color_to_price and soup.select_one("td.booking-slot-available"):
            color_to_price = {"#b9e5fb": 24.0, "#8dd8f8": 38.0}
        time_slots = []

        # Pattern 1: rbt-table (booking-slot-available, a[data-time], legend prices)
        for slot_td in soup.select("td.booking-slot-available"):
            link = slot_td.select_one("a[data-time]")
            if not link:
                continue
            slot_time = link.get("data-time")
            price = get_slot_price_from_style(slot_td, color_to_price)
            row = slot_td.find_parent("tr")
            court_cell = row.select_one("td.rbt-sticky-col span") if row else None
            court_name = court_cell.text.strip() if court_cell else None
            time_slots.append(
                TimeSlot(
                    slot_time=slot_time,
                    court_name=court_name,
                    price=price,
                )
            )

        # Fallback: desktop table (td with data-time, th for court name)
        if not time_slots:
            table = soup.select_one("table.desktop") or soup.find("table")
            if table and table.find("tbody"):
                for row in table.find("tbody").find_all("tr"):
                    th = row.find("th")
                    court_name = th.get_text(strip=True) if th else None
                    if not court_name:
                        continue
                    for td in row.find_all("td"):
                        if "not-available" in td.get("class", []):
                            continue
                        slot_time = td.get("data-time")
                        if not slot_time:
                            continue
                        price = get_slot_price_from_style(td, color_to_price)
                        time_slots.append(
                            TimeSlot(
                                slot_time=slot_time,
                                court_name=court_name,
                                price=price,
                            )
                        )

        return CourtAvailability(
            venue_name=self.name,
            venue_url=self.base_url,
            date=target_date,
            time_slots=time_slots,
            venue_image="https://rezervacija.padelhouse.lt/build/images/logo-full.png",
        )
