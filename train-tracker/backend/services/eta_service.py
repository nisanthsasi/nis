"""ETA calculation service for train tracking."""

from datetime import datetime, timedelta
from typing import Optional

from models.train import Station, ETAResult
from services.train_service import TrainService


class ETAService:
    """Calculates estimated time of arrival and remaining journey details."""

    def __init__(self, train_service: TrainService):
        self.train_service = train_service

    def calculate_eta(
        self,
        train_number: str,
        destination_code: str,
        date: Optional[str] = None,
    ) -> Optional[ETAResult]:
        """Calculate ETA to a destination station for a running train.

        Returns detailed information including:
        - Expected arrival time (adjusted for delays)
        - Remaining distance
        - Remaining stops with times
        - Time remaining in minutes
        """
        # Get live status
        live_status = self.train_service.get_live_status(train_number, date)
        if not live_status:
            return None

        # Get route
        route = self.train_service.get_train_route(train_number)
        if not route:
            return None

        destination_code = destination_code.strip().upper()

        # Find destination in route
        dest_idx = None
        for i, station in enumerate(route.stations):
            if station.code == destination_code:
                dest_idx = i
                break

        if dest_idx is None:
            return None

        dest_station = route.stations[dest_idx]

        # Find current station index
        current_idx = 0
        for i, station in enumerate(live_status.stations):
            if station.code == live_status.current_station:
                current_idx = i
                break

        # Check if already past destination
        if current_idx >= dest_idx:
            return ETAResult(
                train_number=train_number,
                train_name=route.train_name,
                destination_station=destination_code,
                destination_name=dest_station.name,
                scheduled_arrival=dest_station.arrival,
                status="already_passed",
                current_station=live_status.current_station,
                current_station_name=live_status.current_station_name,
            )

        # Calculate remaining distance
        current_distance = route.stations[current_idx].distance_km
        dest_distance = dest_station.distance_km
        remaining_distance = dest_distance - current_distance

        # Collect remaining stations
        remaining_stations = []
        for i in range(current_idx + 1, dest_idx + 1):
            stn = route.stations[i]
            live_stn = live_status.stations[i] if i < len(live_status.stations) else stn

            remaining_stations.append(Station(
                code=stn.code,
                name=stn.name,
                arrival=stn.arrival,
                departure=stn.departure,
                halt_minutes=stn.halt_minutes,
                distance_km=stn.distance_km - current_distance,
                day=stn.day,
                actual_arrival=live_stn.actual_arrival,
                actual_departure=live_stn.actual_departure,
                delay_minutes=live_stn.delay_minutes,
                has_arrived=live_stn.has_arrived,
                has_departed=live_stn.has_departed,
            ))

        # Calculate expected arrival with delay
        delay = live_status.delay_minutes
        scheduled_arrival = dest_station.arrival
        expected_arrival = None
        time_remaining = 0

        if scheduled_arrival:
            h, m = map(int, scheduled_arrival.split(":"))
            now = datetime.now()
            sched_dt = now.replace(hour=h, minute=m, second=0, microsecond=0)

            # Adjust for multi-day journey
            if dest_station.day > 1:
                sched_dt += timedelta(days=dest_station.day - 1)

            # Add delay
            expected_dt = sched_dt + timedelta(minutes=delay)
            expected_arrival = expected_dt.strftime("%H:%M")

            # Time remaining from now
            diff = expected_dt - now
            time_remaining = max(0, int(diff.total_seconds() / 60))

        # Determine status
        if live_status.not_yet_departed:
            status = "not_departed"
        elif live_status.journey_completed:
            status = "completed"
        elif delay > 15:
            status = "delayed"
        elif delay > 0:
            status = "slightly_delayed"
        else:
            status = "on_time"

        return ETAResult(
            train_number=train_number,
            train_name=route.train_name,
            destination_station=destination_code,
            destination_name=dest_station.name,
            scheduled_arrival=scheduled_arrival,
            expected_arrival=expected_arrival,
            delay_minutes=delay,
            remaining_distance_km=remaining_distance,
            remaining_stops=len(remaining_stations) - 1,  # -1 for destination itself
            remaining_stations=remaining_stations,
            current_station=live_status.current_station,
            current_station_name=live_status.current_station_name,
            time_remaining_minutes=time_remaining,
            status=status,
        )

    def get_journey_summary(
        self,
        train_number: str,
        from_station: str,
        to_station: str,
    ) -> Optional[dict]:
        """Get a journey summary between two stations on a train."""
        route = self.train_service.get_train_route(train_number)
        if not route:
            return None

        from_station = from_station.strip().upper()
        to_station = to_station.strip().upper()

        from_idx = None
        to_idx = None

        for i, station in enumerate(route.stations):
            if station.code == from_station:
                from_idx = i
            if station.code == to_station:
                to_idx = i

        if from_idx is None or to_idx is None or from_idx >= to_idx:
            return None

        from_stn = route.stations[from_idx]
        to_stn = route.stations[to_idx]

        # Calculate journey time
        journey_minutes = 0
        if from_stn.departure and to_stn.arrival:
            dep_h, dep_m = map(int, from_stn.departure.split(":"))
            arr_h, arr_m = map(int, to_stn.arrival.split(":"))
            dep_total = dep_h * 60 + dep_m
            arr_total = arr_h * 60 + arr_m

            # Handle day change
            day_diff = to_stn.day - from_stn.day
            journey_minutes = arr_total - dep_total + (day_diff * 24 * 60)
            if journey_minutes < 0:
                journey_minutes += 24 * 60

        hours = journey_minutes // 60
        minutes = journey_minutes % 60

        # Intermediate stations
        intermediate = []
        for i in range(from_idx + 1, to_idx):
            stn = route.stations[i]
            intermediate.append({
                "code": stn.code,
                "name": stn.name,
                "arrival": stn.arrival,
                "departure": stn.departure,
                "halt_minutes": stn.halt_minutes,
                "distance_from_boarding": stn.distance_km - from_stn.distance_km,
            })

        return {
            "train_number": route.train_number,
            "train_name": route.train_name,
            "from_station": {"code": from_stn.code, "name": from_stn.name},
            "to_station": {"code": to_stn.code, "name": to_stn.name},
            "departure": from_stn.departure,
            "arrival": to_stn.arrival,
            "distance_km": to_stn.distance_km - from_stn.distance_km,
            "duration": f"{hours}h {minutes}m",
            "duration_minutes": journey_minutes,
            "intermediate_stops": len(intermediate),
            "intermediate_stations": intermediate,
            "run_days": route.run_days,
        }
