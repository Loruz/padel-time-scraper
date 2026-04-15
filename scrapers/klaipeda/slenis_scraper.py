from datetime import date
import httpx

from ..base import BaseScraper, CourtAvailability, TimeSlot, City
from ..helpers import get_slot_price_from_style, parse_price_legend
from ..registry import scraper_registry


@scraper_registry.register
class SlenisScraper(BaseScraper):
    city = City.KLAIPEDA
    name = "Padelio namai"
    base_url = "https://savitarna.padelionamai.lt"

    async def _login(self, client: httpx.AsyncClient) -> None:
        login_page_url = f"{self.base_url}/user/login"
        login_page_response = await client.get(login_page_url)
        if login_page_response.status_code != 200:
            raise Exception(
                f"Failed to open login page: {login_page_response.status_code}"
            )

        soup = self.parse_html(login_page_response.text)
        csrf_input = soup.select_one("input[name='YII_CSRF_TOKEN']")
        csrf_token = csrf_input.get("value") if csrf_input else None
        if not csrf_token:
            csrf_token = client.cookies.get("YII_CSRF_TOKEN")

        if not csrf_token:
            raise Exception("Missing CSRF token for login")

        login_data = {
            "YII_CSRF_TOKEN": csrf_token,
            "LoginForm[var_login]": "svecias",
            "LoginForm[var_password]": "svecias",
        }
        common_headers = {
            "Origin": self.base_url,
            "Referer": login_page_url,
            "Content-Type": "application/x-www-form-urlencoded",
        }

        # Some Yii setups accept login POST only on specific routes.
        login_urls = [login_page_url, self.base_url]
        login_response = None
        for login_url in login_urls:
            login_response = await client.post(
                login_url,
                data=login_data,
                headers=common_headers,
            )
            if login_response.status_code == 200:
                break

        if login_response is None or login_response.status_code != 200:
            status = login_response.status_code if login_response else "unknown"
            raise Exception(f"Login failed: {status}")

    async def scrape(self, target_date: date) -> CourtAvailability:
        async with httpx.AsyncClient(
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
            },
        ) as client:
            await self._login(client)

            date_str = f"{target_date.year}-{target_date.month}-{target_date.day}"
            booking_url = (
                f"{self.base_url}/reservation/short?iPlaceId=2&sDate={date_str}"
            )
            response = await client.get(booking_url)
            html = response.text

        soup = self.parse_html(html)
        color_to_price = parse_price_legend(soup)

        time_slots = []
        for slot_td in soup.select("td.booking-slot-available"):
            link = slot_td.select_one("a[data-time]")
            if not link:
                continue

            slot_time = link.get("data-time")
            price = get_slot_price_from_style(slot_td, color_to_price)

            row = slot_td.find_parent("tr")
            court_cell = row.select_one("td.rbt-sticky-col span")
            court_name = court_cell.text.strip() if court_cell else None

            time_slots.append(
                TimeSlot(
                    slot_time=slot_time,
                    court_name=court_name,
                    price=price,
                )
            )

        return CourtAvailability(
            venue_name=self.name,
            venue_image="https://padelionamai.lt/wp-content/uploads/2021/05/main-logo.png",
            venue_url=f"{self.base_url}/reservation/short",
            date=target_date,
            time_slots=time_slots,
        )
