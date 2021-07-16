from typing import Optional
import datetime

import click
import notifypy

import sepaq_crawler


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
    def park_filter(p: sepaq_crawler.Park) -> bool:
        if parks is not None:
            return p.name in parks.split(",")
        elif distance is not None:
            return p.distance_km_from(current_location()) < distance
        return True

    # Restrict Cabins to search
    def cabin_filter(c: sepaq_crawler.Cabin) -> bool:
        return c.is_available(arriving, leaving)

    notify = notifypy.Notify(
        default_notification_title="SEPAQ Cabin",
        default_application_name="SEPAQ Crawler",
    )

    def alert(c: sepaq_crawler.Cabin) -> None:
        print(f"Found Cabin {c.name}: {c.url}")
        notify.message = f"Found Cabin in {c.park.name}"
        notify.send()


    sepaq_crawler.search(park_filter=park_filter, cabin_filter=cabin_filter, alert=alert)


if __name__ == "__main__":
    cli()
