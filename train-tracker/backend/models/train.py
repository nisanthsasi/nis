"""Data models for train tracking."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Station:
    code: str
    name: str
    arrival: Optional[str] = None
    departure: Optional[str] = None
    halt_minutes: int = 0
    distance_km: float = 0.0
    day: int = 1
    platform: Optional[str] = None
    # Live status fields
    actual_arrival: Optional[str] = None
    actual_departure: Optional[str] = None
    delay_minutes: int = 0
    has_departed: bool = False
    has_arrived: bool = False

    def to_dict(self):
        return {
            "code": self.code,
            "name": self.name,
            "arrival": self.arrival,
            "departure": self.departure,
            "halt_minutes": self.halt_minutes,
            "distance_km": self.distance_km,
            "day": self.day,
            "platform": self.platform,
            "actual_arrival": self.actual_arrival,
            "actual_departure": self.actual_departure,
            "delay_minutes": self.delay_minutes,
            "has_departed": self.has_departed,
            "has_arrived": self.has_arrived,
        }


@dataclass
class TrainRoute:
    train_number: str
    train_name: str
    run_days: list = field(default_factory=list)
    source_station: Optional[str] = None
    destination_station: Optional[str] = None
    stations: list = field(default_factory=list)

    def to_dict(self):
        return {
            "train_number": self.train_number,
            "train_name": self.train_name,
            "run_days": self.run_days,
            "source_station": self.source_station,
            "destination_station": self.destination_station,
            "stations": [s.to_dict() for s in self.stations],
        }


@dataclass
class LiveStatus:
    train_number: str
    train_name: str
    current_station: Optional[str] = None
    current_station_name: Optional[str] = None
    last_updated: Optional[str] = None
    delay_minutes: int = 0
    status_message: str = ""
    next_station: Optional[str] = None
    next_station_name: Optional[str] = None
    eta_next_station: Optional[str] = None
    stations: list = field(default_factory=list)
    journey_completed: bool = False
    not_yet_departed: bool = False

    def to_dict(self):
        return {
            "train_number": self.train_number,
            "train_name": self.train_name,
            "current_station": self.current_station,
            "current_station_name": self.current_station_name,
            "last_updated": self.last_updated,
            "delay_minutes": self.delay_minutes,
            "status_message": self.status_message,
            "next_station": self.next_station,
            "next_station_name": self.next_station_name,
            "eta_next_station": self.eta_next_station,
            "stations": [s.to_dict() for s in self.stations],
            "journey_completed": self.journey_completed,
            "not_yet_departed": self.not_yet_departed,
        }


@dataclass
class ETAResult:
    train_number: str
    train_name: str
    destination_station: str
    destination_name: str
    scheduled_arrival: Optional[str] = None
    expected_arrival: Optional[str] = None
    delay_minutes: int = 0
    remaining_distance_km: float = 0.0
    remaining_stops: int = 0
    remaining_stations: list = field(default_factory=list)
    current_station: Optional[str] = None
    current_station_name: Optional[str] = None
    time_remaining_minutes: int = 0
    status: str = ""

    def to_dict(self):
        return {
            "train_number": self.train_number,
            "train_name": self.train_name,
            "destination_station": self.destination_station,
            "destination_name": self.destination_name,
            "scheduled_arrival": self.scheduled_arrival,
            "expected_arrival": self.expected_arrival,
            "delay_minutes": self.delay_minutes,
            "remaining_distance_km": self.remaining_distance_km,
            "remaining_stops": self.remaining_stops,
            "remaining_stations": [s.to_dict() for s in self.remaining_stations],
            "current_station": self.current_station,
            "current_station_name": self.current_station_name,
            "time_remaining_minutes": self.time_remaining_minutes,
            "status": self.status,
        }
