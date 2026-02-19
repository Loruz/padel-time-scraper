from datetime import date
import httpx

from ..base import BaseScraper, CourtAvailability, TimeSlot, City
from ..registry import scraper_registry


@scraper_registry.register
class FourPadelScraper(BaseScraper):
    name = "4Padel Arena"
    city = City.KLAIPEDA
    base_url = "https://activezone.fun"
    venue_page = "https://4padelarena.lt"
    location_id = 189
    city_id = 3

    async def scrape(self, target_date: date) -> CourtAvailability:
        async with httpx.AsyncClient(
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
            }
        ) as client:
            # Build API URL with dynamic date
            date_str = target_date.isoformat()  # "2026-02-05"
            api_url = f"{self.base_url}/api/v1/settings/tickets/user"

            response = await client.get(
                api_url,
                params={
                    "page": 0,
                    "size": 2000,
                    "ticketFrom": f"{date_str} 00:00:00",
                    "ticketTo": f"{date_str} 23:59:00",
                    "locationIds": self.location_id,
                    "sportTypes": "padel",
                    "isAuthorized": "true",
                    "isAllCity": "false",
                    "showSingle": "false",
                    "cityId": self.city_id,
                    "isTrainer": "false",
                },
            )

            if response.status_code != 200:
                raise Exception(f"API request failed: {response.status_code}")

            data = response.json()

            # Extract slots from JSON response
            time_slots = []
            for item in data.get("content", []):
                # Only include free slots
                if item.get("status") == "free":
                    # Extract time from "06:00:00" format -> "06:00"
                    ticket_time = item.get("ticketTime", "")
                    slot_time = ticket_time[:5] if ticket_time else None

                    # Get court name
                    court = item.get("court", {})
                    court_name = court.get("name", "").strip()

                    # Price is in cents, convert to euros
                    price_cents = item.get("price", 0)
                    price = round(price_cents / 100) if price_cents else None

                    if slot_time:
                        time_slots.append(
                            TimeSlot(
                                slot_time=slot_time,
                                court_name=court_name,
                                price=price,
                            )
                        )

            return CourtAvailability(
                venue_name=self.name,
                venue_url=self.venue_page,
                venue_image="https://4padelarena.lt/wp-content/uploads/2024/02/4-PADEL-ARENA_logo_2023_B-2-166x73.png",
                date=target_date,
                time_slots=time_slots,
            )
