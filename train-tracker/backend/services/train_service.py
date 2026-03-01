"""Service for fetching train data from Indian Railways APIs."""

import json
import os
import random
from datetime import datetime, timedelta
from typing import Optional

import requests

from models.train import Station, TrainRoute, LiveStatus

# Base URLs for Indian Railway APIs
CONFIRMTKT_API = "https://indian-railway-api.cyclic.app/trains"
RAILWAYAPI_SEARCH = "https://indian-railway-api.cyclic.app/trains/search"

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")


class TrainService:
    """Service to fetch and manage train data.

    Uses a local dataset of popular trains as fallback and can optionally
    connect to live Indian Railways APIs when available.
    """

    def __init__(self):
        self._trains_cache = {}
        self._stations_cache = {}
        self._load_sample_data()

    def _load_sample_data(self):
        """Load sample train data from JSON file."""
        data_file = os.path.join(DATA_DIR, "sample_trains.json")
        with open(data_file) as f:
            data = json.load(f)

        self._stations_cache = data.get("stations", {})

        for train_data in data.get("trains", []):
            number = train_data["number"]
            stations = []
            for s in train_data["stations"]:
                stations.append(Station(
                    code=s["code"],
                    name=s["name"],
                    arrival=s.get("arrival"),
                    departure=s.get("departure"),
                    halt_minutes=s.get("halt", 0),
                    distance_km=s.get("distance", 0),
                    day=s.get("day", 1),
                ))

            route = TrainRoute(
                train_number=number,
                train_name=train_data["name"],
                run_days=train_data.get("run_days", []),
                source_station=train_data.get("source"),
                destination_station=train_data.get("destination"),
                stations=stations,
            )
            self._trains_cache[number] = route

    def search_trains(self, query: str) -> list:
        """Search trains by number or name."""
        query = query.strip().lower()
        results = []

        for number, route in self._trains_cache.items():
            if (query in number.lower() or
                    query in route.train_name.lower()):
                results.append({
                    "train_number": route.train_number,
                    "train_name": route.train_name,
                    "source": route.source_station,
                    "source_name": self._stations_cache.get(
                        route.source_station, route.source_station
                    ),
                    "destination": route.destination_station,
                    "destination_name": self._stations_cache.get(
                        route.destination_station, route.destination_station
                    ),
                    "run_days": route.run_days,
                })

        # Also try external API
        try:
            external = self._search_external(query)
            if external:
                results.extend(external)
        except Exception:
            pass

        return results

    def _search_external(self, query: str) -> list:
        """Attempt to search trains via an external API."""
        try:
            resp = requests.get(
                RAILWAYAPI_SEARCH,
                params={"query": query},
                timeout=5,
            )
            if resp.status_code == 200:
                data = resp.json()
                return data.get("trains", [])
        except Exception:
            pass
        return []

    def get_train_route(self, train_number: str) -> Optional[TrainRoute]:
        """Get the full route/schedule for a train."""
        train_number = train_number.strip()
        if train_number in self._trains_cache:
            return self._trains_cache[train_number]

        # Try external API
        try:
            route = self._fetch_route_external(train_number)
            if route:
                self._trains_cache[train_number] = route
                return route
        except Exception:
            pass

        return None

    def _fetch_route_external(self, train_number: str) -> Optional[TrainRoute]:
        """Fetch route from external API."""
        try:
            resp = requests.get(
                f"{CONFIRMTKT_API}/{train_number}/schedule",
                timeout=5,
            )
            if resp.status_code == 200:
                data = resp.json()
                stations = []
                for s in data.get("schedule", []):
                    stations.append(Station(
                        code=s.get("stationCode", ""),
                        name=s.get("stationName", ""),
                        arrival=s.get("arrivalTime"),
                        departure=s.get("departureTime"),
                        halt_minutes=s.get("haltTime", 0),
                        distance_km=s.get("distance", 0),
                        day=s.get("dayCount", 1),
                    ))
                if stations:
                    return TrainRoute(
                        train_number=train_number,
                        train_name=data.get("trainName", f"Train {train_number}"),
                        stations=stations,
                    )
        except Exception:
            pass
        return None

    def get_live_status(self, train_number: str, date: Optional[str] = None) -> Optional[LiveStatus]:
        """Get live running status of a train.

        Simulates realistic live status based on current time and the
        train's schedule when external APIs are unavailable.
        """
        route = self.get_train_route(train_number)
        if not route or not route.stations:
            return None

        # Try external API first
        try:
            live = self._fetch_live_external(train_number, date)
            if live:
                return live
        except Exception:
            pass

        # Simulate live status based on current time
        return self._simulate_live_status(route)

    def _fetch_live_external(self, train_number: str, date: Optional[str] = None) -> Optional[LiveStatus]:
        """Fetch live status from external API."""
        try:
            today = date or datetime.now().strftime("%Y%m%d")
            resp = requests.get(
                f"{CONFIRMTKT_API}/{train_number}/live/{today}",
                timeout=5,
            )
            if resp.status_code == 200:
                data = resp.json()
                stations = []
                for s in data.get("stations", []):
                    stations.append(Station(
                        code=s.get("stationCode", ""),
                        name=s.get("stationName", ""),
                        arrival=s.get("scheduledArrival"),
                        departure=s.get("scheduledDeparture"),
                        actual_arrival=s.get("actualArrival"),
                        actual_departure=s.get("actualDeparture"),
                        delay_minutes=s.get("delayInArrival", 0),
                        has_departed=s.get("hasDeparted", False),
                        has_arrived=s.get("hasArrived", False),
                        distance_km=s.get("distance", 0),
                    ))

                return LiveStatus(
                    train_number=train_number,
                    train_name=data.get("trainName", ""),
                    current_station=data.get("currentStation", {}).get("code"),
                    current_station_name=data.get("currentStation", {}).get("name"),
                    delay_minutes=data.get("delay", 0),
                    status_message=data.get("statusMessage", ""),
                    stations=stations,
                )
        except Exception:
            pass
        return None

    def _simulate_live_status(self, route: TrainRoute) -> LiveStatus:
        """Simulate live status for demo/offline mode.

        Creates a realistic simulation based on the train's scheduled
        times and a random delay factor.
        """
        now = datetime.now()
        stations = route.stations

        # Add a small random delay (0-30 min) for realism
        delay = random.randint(0, 30)

        # Determine which station the train is at based on current time
        current_idx = 0
        for i, station in enumerate(stations):
            sched_time = station.departure or station.arrival
            if not sched_time:
                continue

            hour, minute = map(int, sched_time.split(":"))
            station_time = now.replace(hour=hour, minute=minute, second=0)

            # Adjust for multi-day journeys
            if station.day > 1:
                station_time += timedelta(days=station.day - 1)

            # Add delay
            station_time += timedelta(minutes=delay)

            if station_time <= now:
                current_idx = i

        # Build station list with live info
        live_stations = []
        for i, station in enumerate(stations):
            s = Station(
                code=station.code,
                name=station.name,
                arrival=station.arrival,
                departure=station.departure,
                halt_minutes=station.halt_minutes,
                distance_km=station.distance_km,
                day=station.day,
                delay_minutes=delay if i <= current_idx else delay,
                has_arrived=i <= current_idx,
                has_departed=i < current_idx,
            )

            # Calculate actual times with delay
            if station.arrival:
                h, m = map(int, station.arrival.split(":"))
                actual = datetime(now.year, now.month, now.day, h, m) + timedelta(minutes=delay)
                s.actual_arrival = actual.strftime("%H:%M")

            if station.departure:
                h, m = map(int, station.departure.split(":"))
                actual = datetime(now.year, now.month, now.day, h, m) + timedelta(minutes=delay)
                s.actual_departure = actual.strftime("%H:%M")

            live_stations.append(s)

        current_station = stations[current_idx]
        next_idx = min(current_idx + 1, len(stations) - 1)
        next_station = stations[next_idx]

        # Check edge cases
        not_departed = current_idx == 0
        journey_completed = current_idx == len(stations) - 1

        if not_departed:
            status_msg = f"Train has not yet departed from {current_station.name}"
        elif journey_completed:
            status_msg = f"Train has arrived at {current_station.name}"
        else:
            if delay > 0:
                status_msg = f"Running {delay} min late. Last seen at {current_station.name}"
            else:
                status_msg = f"Running on time. Last seen at {current_station.name}"

        # Calculate ETA to next station
        eta_next = None
        if next_station.arrival and not journey_completed:
            h, m = map(int, next_station.arrival.split(":"))
            eta = datetime(now.year, now.month, now.day, h, m) + timedelta(minutes=delay)
            if next_station.day > current_station.day:
                eta += timedelta(days=next_station.day - current_station.day)
            eta_next = eta.strftime("%H:%M")

        return LiveStatus(
            train_number=route.train_number,
            train_name=route.train_name,
            current_station=current_station.code,
            current_station_name=current_station.name,
            last_updated=now.strftime("%Y-%m-%d %H:%M:%S"),
            delay_minutes=delay,
            status_message=status_msg,
            next_station=next_station.code if not journey_completed else None,
            next_station_name=next_station.name if not journey_completed else None,
            eta_next_station=eta_next,
            stations=live_stations,
            journey_completed=journey_completed,
            not_yet_departed=not_departed,
        )

    def search_stations(self, query: str) -> list:
        """Search stations by code or name."""
        query = query.strip().lower()
        results = []
        for code, name in self._stations_cache.items():
            if query in code.lower() or query in name.lower():
                results.append({"code": code, "name": name})
        return results

    def get_trains_between_stations(self, from_station: str, to_station: str) -> list:
        """Find trains running between two stations."""
        from_station = from_station.strip().upper()
        to_station = to_station.strip().upper()
        results = []

        for number, route in self._trains_cache.items():
            station_codes = [s.code for s in route.stations]
            if from_station in station_codes and to_station in station_codes:
                from_idx = station_codes.index(from_station)
                to_idx = station_codes.index(to_station)
                if from_idx < to_idx:  # Train must go in the right direction
                    from_stn = route.stations[from_idx]
                    to_stn = route.stations[to_idx]
                    results.append({
                        "train_number": route.train_number,
                        "train_name": route.train_name,
                        "departure": from_stn.departure or from_stn.arrival,
                        "arrival": to_stn.arrival or to_stn.departure,
                        "duration_km": to_stn.distance_km - from_stn.distance_km,
                        "stops": to_idx - from_idx - 1,
                        "run_days": route.run_days,
                    })

        return results
