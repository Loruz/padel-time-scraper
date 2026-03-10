from datetime import date

from ..base import BaseScraper, CourtAvailability, TimeSlot, City
from ..registry import scraper_registry


@scraper_registry.register
class KupolasScraper(BaseScraper):
    city = City.KLAIPEDA
    name = "Klaipėdos Kupolas"
    base_url = "http://www.kupolas.klaipedapadel.lt/Rezervacija"
    api_url = "http://www.kupolas.klaipedapadel.lt/Rezervacija.aspx/GetDayView"

    async def scrape(self, target_date: date) -> CourtAvailability:
        date_str = target_date.strftime("%Y-%m-%d")
        response = await self.client.post(
            self.api_url,
            json={"courttype": "1", "date": date_str},
            headers={"Content-Type": "application/json"},
        )
        response.raise_for_status()
        html = response.json()["d"]

        soup = self.parse_html(html)

        print(soup)

        time_slots = []
        for td in soup.select("td.available"):
            court_name = td.get("data-courtname", "").strip()
            price_raw = td.get("data-price")
            start_time = td.get("data-starttime", "")
            slot_time = start_time.replace("-", ":", 1)

            price = float(price_raw) if price_raw is not None else None

            time_slots.append(
                TimeSlot(
                    slot_time=slot_time,
                    court_name=court_name or None,
                    price=round(price),
                )
            )

        return CourtAvailability(
            venue_name=self.name,
            venue_image="http://www.kupolas.klaipedapadel.lt/Images/logoFront.png",
            venue_url=self.base_url,
            date=target_date,
            time_slots=time_slots,
        )
