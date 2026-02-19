from datetime import date
import httpx

from ..base import BaseScraper, CourtAvailability, TimeSlot, City
from ..registry import scraper_registry


@scraper_registry.register
class TennisSpaceScraper(BaseScraper):
    city = City.KAUNAS
    name = "Tennis Space"
    base_url = "https://savitarna.tennisspace.lt"

    async def scrape(self, target_date: date) -> CourtAvailability:
        async with httpx.AsyncClient(
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
            }
        ) as client:
            login_response = await client.post(
                f"{self.base_url}/user/login",
                data={
                    "LoginForm[var_login]": "anonimas",
                    "LoginForm[var_password]": "F;293nj`yA-mVaQ."
                }
            )

            if login_response.status_code != 200:
                raise Exception(f"Login failed: {login_response.status_code}")

            date_str = f"{target_date.year}-{target_date.month}-{target_date.day}"
            booking_url = f"{self.base_url}/reservation/short?iPlaceId=4&sDate={date_str}"
            response = await client.get(booking_url)
            html = response.text

        soup = self.parse_html(html)

        time_slots = []
        for slot_td in soup.select("td.booking-slot-available"):
            link = slot_td.select_one("a[data-time]")
            if not link:
                continue

            slot_time = link.get("data-time")

            row = slot_td.find_parent("tr")
            court_cell = row.select_one("td.rbt-sticky-col span")
            court_name = court_cell.text.strip() if court_cell else None

            time_slots.append(TimeSlot(
                slot_time=slot_time,
                court_name=court_name,
            ))

        return CourtAvailability(
            venue_name=self.name,
            venue_image="https://savitarna.tennisspace.lt/themes/tennis_space/images/logo-colored.svg",
            venue_url=f"{self.base_url}/reservation/short",
            date=target_date,
            time_slots=time_slots
        )
