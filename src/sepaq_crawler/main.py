from __future__ import annotations

import json
import datetime
import dataclasses
import functools
from typing import Optional, Dict, List, Any, Callable

import click
import geopy
import geopy.distance
import requests


SEPAQ_BASE_URL = "https://www.sepaq.com"

Cabin = Dict[str, Any]
CabinDate = Dict[str, Any]


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
    n_days = (stop - start).days
    return [start + datetime.timedelta(i) for i in range(n_days)]


@functools.lru_cache
def geocoder() -> geopy.geocoders.Nominatim:
    return geopy.geocoders.Nominatim(user_agent="Sepaq-Crawler")


@functools.lru_cache
def current_location() -> geopy.Location:
    r = requests.get("https://ipinfo.io/loc")
    lat, long = [float(coo) for coo in r.text.split(",")]
    return geocoder().reverse((lat, long))


def distance_km(a: geopy.Location, b: geopy.Location) -> float:
    return geopy.distance.distance((a.latitude, a.longitude), (b.latitude, b.longitude)).km


@dataclasses.dataclass
class Park:
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
        return [Cabin(c) for c in cabins]


@dataclasses.dataclass
class Cabin:
    data: Dict[str, Any]

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
):
    # Get list of park that validate conditions
    parks = [p for p in Park.get_all() if park_filter(p)]
    print("Searching following parks:")
    for p in parks:
        print(f"  - {p.name}")

    # Get list of cabins that validate conditions
    for p in parks:
        cabins = [c for c in p.cabins() if cabin_filter(c)]
        for c in cabins:
            print(f"Found Cabin {c.name}: {c.url}")
    else:
        print("Found nothing")


@click.command()
@click.option("--arriving", required=True, type=datetime.date.fromisoformat, help="Arriving date")
@click.option("--leaving", required=True, type=datetime.date.fromisoformat, help="Departure date")
@click.option("--parks", "-p", default=None, type=str, help="Comma separated list of parks in which to search")
@click.option("--distance", "-d", default=None, type=float, help="Distance from current location")
def cli(
    arriving: datetime.date,
    leaving: datetime.date,
    parks: Optional[str],
    distance: Optional[float],
):
    # Restrict parks to search
    def park_filter(p: Park) -> bool:
        if parks is not None:
            return p.name in parks.split(",")
        elif distance is not None:
            return p.distance_km_from(current_location()) < distance
        return True

    # Restrict Cabins to search
    def cabin_filter(c: Cabin) -> bool:
        return c.is_available(arriving, leaving)

    search(park_filter=park_filter, cabin_filter=cabin_filter)


if __name__ == "__main__":
    cli()
