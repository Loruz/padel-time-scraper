"""Shared helpers for scrapers."""

import re
from typing import Optional

from bs4 import BeautifulSoup


def _normalize_color(color: str) -> Optional[str]:
    """Normalize CSS color to lowercase hex (#rrggbb) for consistent lookup."""
    if not color:
        return None
    color = color.strip().lower()
    hex_match = re.match(r"#([0-9a-f]{6})\b", color)
    if hex_match:
        return "#" + hex_match.group(1)
    rgb_match = re.match(
        r"rgb\s*\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)", color
    )
    if rgb_match:
        r, g, b = (int(x) for x in rgb_match.groups())
        return f"#{r:02x}{g:02x}{b:02x}"
    return None


def parse_price_legend(soup: BeautifulSoup) -> dict[str, float]:
    """
    Build a color -> price (euros) map from the booking table legend.

    Looks for legend items that have a span with background-color and a price
    like "24 €" (Vienos valandos kaina style). Returns a dict mapping
    normalized hex color to price.
    """
    color_to_price: dict[str, float] = {}
    # Legend items: div.legend-item containing span[style*="background-color"] and price text
    for item in soup.select("div.legend-item"):
        span = item.find("span", style=re.compile(r"background-color", re.I))
        if not span or not span.get("style"):
            continue
        style = span["style"]
        bg_match = re.search(
            r"background-color\s*:\s*([#\w(),\s]+)", style, re.I
        )
        if not bg_match:
            continue
        color = _normalize_color(bg_match.group(1).strip())
        if not color:
            continue
        # Price is the rest of the text in the legend item (e.g. "24 €" or "38 €")
        text = item.get_text(strip=True)
        price_match = re.search(r"([\d.,]+)\s*€?", text)
        if price_match:
            price_str = price_match.group(1).replace(",", ".")
            try:
                color_to_price[color] = float(price_str)
            except ValueError:
                pass
    return color_to_price


def parse_price_from_time_descriptions(soup: BeautifulSoup) -> dict[str, float]:
    """
    Build color -> price (euros per hour) from .pricing .time-description blocks.

    Used when the page has e.g. <div class="time-description"><div class="color"
    style="background-color: #9DB0DA">...</div><div class="description">20 €/val.</div></div>.
    Returns a dict mapping normalized hex color to hourly price.
    """
    color_to_price: dict[str, float] = {}
    for item in soup.select(".time-description"):
        color_div = item.find(
            "div", class_="color", style=re.compile(r"background-color", re.I)
        )
        if not color_div or not color_div.get("style"):
            continue
        style = color_div["style"]
        bg_match = re.search(
            r"background-color\s*:\s*([#\w(),\s]+)", style, re.I
        )
        if not bg_match:
            continue
        color = _normalize_color(bg_match.group(1).strip())
        if not color:
            continue
        desc = item.find("div", class_="description")
        if not desc:
            continue
        text = desc.get_text(strip=True)
        # First "20 €/val." or "38 €/val." is the current price per hour
        price_match = re.search(r"([\d.,]+)\s*€/val", text)
        if price_match:
            price_str = price_match.group(1).replace(",", ".")
            try:
                color_to_price[color] = float(price_str)
            except ValueError:
                pass
    return color_to_price


def get_slot_price_from_style(td, color_to_price: dict[str, float]) -> Optional[float]:
    """
    Get the price for a slot cell by its background-color and the legend map.

    Legend prices are per hour; each slot is 30 minutes, so the returned value
    is half the hourly price, rounded.

    td: a BeautifulSoup element (e.g. <td>) that may have style="background-color: #hex".
    color_to_price: result of parse_price_legend(soup).
    """
    if not color_to_price:
        return None
    style = td.get("style") if hasattr(td, "get") else None
    if not style:
        return None
    bg_match = re.search(
        r"background-color\s*:\s*([#\w(),\s]+)", style, re.I
    )
    if not bg_match:
        return None
    color = _normalize_color(bg_match.group(1).strip())
    price_per_hour = color_to_price.get(color) if color else None
    if price_per_hour is None:
        return None
    # Each slot is 30 min; legend is "Vienos valandos kaina" (price per hour)
    return round(price_per_hour / 2)
