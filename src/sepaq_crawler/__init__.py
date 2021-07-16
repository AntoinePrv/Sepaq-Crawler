from __future__ import annotations

import json
import datetime
import dataclasses
import functools
import itertools
import time
from typing import Dict, List, Any, Callable

import click
import geopy
import geopy.distance
import requests


SEPAQ_BASE_URL = "https://www.sepaq.com"


def stateful_json_request(page_url: str, api_url: str) -> Any:
    """Query SEPAQ API.

    SEPAQ API requires to get a cookie from a main page to disambiguate
    the API (park, cabin, ...).
    """
    # Aquire cookies on main page
    page_response = requests.get(page_url)
    # Json API to query
    api_response = requests.get(api_url, cookies=page_response.cookies)
    return json.loads(api_response.content)


def date_time_range(start: datetime.date, stop: datetime.date) -> List[datetime.date]:
    """List all days in a range."""
    n_days = (stop - start).days
    return [start + datetime.timedelta(i) for i in range(n_days)]


@functools.lru_cache
def geocoder() -> geopy.geocoders.Nominatim:
    """Geocoder object to find locations."""
    return geopy.geocoders.Nominatim(user_agent="Sepaq-Crawler")


@functools.lru_cache
def current_location() -> geopy.Location:
    """The current location according to IP."""
    r = requests.get("https://ipinfo.io/loc")
    lat, long = [float(coo) for coo in r.text.split(",")]
    return geocoder().reverse((lat, long))


def distance_km(a: geopy.Location, b: geopy.Location) -> float:
    """Flighing distance in km between two locations."""
    return geopy.distance.distance((a.latitude, a.longitude), (b.latitude, b.longitude)).km


@dataclasses.dataclass
class Park:
    """A SEPAQ park."""

    data: Dict[str, Any]

    @classmethod
    def get_all(cls) -> List[Park]:
        parks = stateful_json_request(
            f"{SEPAQ_BASE_URL}/en/reservation/chalet",
            f"{SEPAQ_BASE_URL}/en/reservation/carte/resultats",
        )
        # Some redirect to an external website
        return [cls(p) for p in parks if p["url"].startswith("/")]

    @property
    def name(self) -> str:
        return self.data["nom"]

    @property
    def url(self) -> str:
        return SEPAQ_BASE_URL + self.data["url"]

    @property
    def location(self) -> geopy.Location:
        return geocoder().reverse(self.data["coordonnees"].values())

    def distance_km_from(self, location: geopy.Location) -> float:
        return distance_km(location, self.location)

    def cabins(self) -> List[Cabin]:
        cabins = stateful_json_request(
            self.url,
            f"{SEPAQ_BASE_URL}/en/reservation/carte/resultats",
        )
        return [Cabin(c, park=self) for c in cabins]


@dataclasses.dataclass
class Cabin:
    """A SEPAQ Cabin."""

    data: Dict[str, Any]
    park: Park

    @property
    def name(self) -> str:
        return self.data["nom"]

    @property
    def url(self) -> str:
        return SEPAQ_BASE_URL + self.data["url"]

    def dates(self) -> List[CabinDate]:
        dates = stateful_json_request(
            self.url,
            f"{SEPAQ_BASE_URL}/en/reservation/availabilities/",
        )
        return [CabinDate(a) for a in dates]

    def is_available(self, start: datetime.date, stop: datetime.date) -> bool:
        free_dates = {d.date for d in self.dates() if d.is_available}
        needed_dates = date_time_range(start, stop)
        return all((d in free_dates) for d in needed_dates)


@dataclasses.dataclass
class CabinDate:
    """A SEPAQ Cabin on a given date."""

    data: Dict[str, Any]

    @property
    def date(self) -> datetime.date:
        return datetime.date.fromisoformat(self.data["dateAsStandardString"])

    @property
    def is_available(self) -> bool:
        return self.data["availability"]


def search(
    park_filter: Callable[[Park], bool] = lambda p: True,
    cabin_filter: Callable[[Cabin], bool] = lambda c: True,
    cabin_available: Callable[[Cabin], bool] = lambda c: True,
    alert: Callable[[Cabin], None] = lambda c: None,
    retries: Optional[int] = None,
    sleep: int = 60,
):
    """Search for available cabins.

    Parameters
    ----------
    park_filter:
        A callback function to filter park to search into.
    cabin_filter:
        A callback function to filter valid cabins.
    cabin_available:
        A callback evaluated on each retry to check if new cabins are available.
    alert:
        A callback to alert when a cabin is found.
    retries:
        Number of times to retry, or infinitly.
    sleep:
        Number of seconds to sleep between two iterations.

    """
    # Get list of park that validate conditions
    parks = [p for p in Park.get_all() if park_filter(p)]
    print("Searching following parks:")
    for p in parks:
        print(f"  - {p.name}")

    # Get list of cabins that validate conditions
    cabins = [c for p in parks for c in p.cabins() if cabin_filter(c)]

    # Potentially iyerate forever if retries is None
    for i in itertools.count():
        if i == retries:
            break
        else:
            print(f"Iteration {i}")
            for c in cabins:
                if cabin_available(c):
                    alert(c)
            else:
                print("  Found nothing")
        time.sleep(sleep)
