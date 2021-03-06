from typing import Optional
import datetime

import click
import notifypy

import sepaq_crawler


@click.command()
@click.option("--arriving", required=True, type=datetime.date.fromisoformat, help="Arriving date.")
@click.option("--leaving", required=True, type=datetime.date.fromisoformat, help="Departure date.")
@click.option("--min-capacity", default=None, type=int, help="Minimum capacity of the cabin to rent")
@click.option("--parks", "-p", default=None, type=str, help="Comma separated list of parks in which to search.")
@click.option("--distance", "-d", default=None, type=float, help="Distance from current location.")
@click.option("--retries", "-r", default=None, type=int, help="Number of times to retry all cabins.")
@click.option("--sleep", default=60, type=int, help="Time in second to wait between two iterations.")
@click.option("--notify", "-n", is_flag=True, help="Send notification when a cabin is found.")
def cli(
    arriving: datetime.date,
    leaving: datetime.date,
    min_capacity: Optional[int],
    parks: Optional[str],
    distance: Optional[float],
    retries: Optional[int],
    sleep: int,
    notify: bool,
):
    # Callback to restrict parks to search
    def park_filter(p: sepaq_crawler.Park) -> bool:
        if parks is not None:
            return p.name in parks.split(",")
        elif distance is not None:
            return p.distance_km_from(sepaq_crawler.current_location()) < distance
        return True

    # Callback to restrict cabins to search
    def cabin_filter(c: sepaq_crawler.Cabin) -> bool:
        if min_capacity is not None:
            return c.capacity >= min_capacity
        return True

    # Callback to assert whether a cabin is available
    def cabin_available(c: sepaq_crawler.Cabin) -> bool:
        return c.is_available(arriving, leaving)

    notifier = notifypy.Notify(
        default_notification_title="SEPAQ Cabin",
        default_application_name="SEPAQ Crawler",
    )

    def alert(c: sepaq_crawler.Cabin) -> None:
        print(f"  - Found Cabin {c.name}: {c.url}")
        if notify:
            notify.message = f"Found Cabin in {c.park.name}"
            notify.send()

    sepaq_crawler.search(
        park_filter=park_filter,
        cabin_filter=cabin_filter,
        cabin_available=cabin_available,
        alert=alert,
        retries=retries,
        sleep=sleep,
    )


if __name__ == "__main__":
    cli()
