from datetime import date
import json
import httpx

from ..base import BaseScraper, CourtAvailability, TimeSlot, City
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
            }
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
        time_slots = []

        # Use the desktop table (same data as mobile, clearer structure)
        table = soup.select_one("table.desktop")
        if not table:
            table = soup.find("table")
        if not table:
            return CourtAvailability(
                venue_name=self.name,
                venue_url=self.base_url,
                date=target_date,
                time_slots=[],
            )

        tbody = table.find("tbody")
        if not tbody:
            return CourtAvailability(
                venue_name=self.name,
                venue_url=self.base_url,
                date=target_date,
                time_slots=[],
            )

        for row in tbody.find_all("tr"):
            # First cell is <th> with court name (e.g. "Pirma aikštelė", "Antra aikštelė")
            th = row.find("th")
            court_name = th.get_text(strip=True) if th else None
            if not court_name:
                continue
            # Remaining cells: <td> with data-time = available slot; class "not-available" = unavailable
            for td in row.find_all("td"):
                if "not-available" in td.get("class", []):
                    continue
                slot_time = td.get("data-time")
                if not slot_time:
                    continue
                time_slots.append(TimeSlot(
                    slot_time=slot_time,
                    court_name=court_name,
                ))

        return CourtAvailability(
            venue_name=self.name,
            venue_url=self.base_url,
            date=target_date,
            time_slots=time_slots,
            venue_image="https://rezervacija.padelhouse.lt/build/images/logo-full.png",
        )
