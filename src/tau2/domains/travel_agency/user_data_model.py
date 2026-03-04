from typing import Dict, List, Optional

from tau2.environment.db import DB
from tau2.utils.pydantic_utils import BaseModelNoExtra


class TripSummary(BaseModelNoExtra):
    trip_id: str
    destination: str
    start_date: str
    end_date: str
    status: str


class FlightSummary(BaseModelNoExtra):
    booking_id: str
    airline: str
    departure_city: str
    arrival_city: str
    departure_date: str
    seat_class: str
    passenger_name: str
    price: float


class HotelSummary(BaseModelNoExtra):
    reservation_id: str
    hotel_name: str
    check_in_date: str
    check_out_date: str
    room_type: str
    total_price: float


class RentalSummary(BaseModelNoExtra):
    rental_id: str
    company: str
    pickup_date: str
    return_date: str
    car_type: str
    total_price: float


class TravelAgencyUserDB(DB):
    client_id: Optional[str] = None
    client_name: Optional[str] = None
    my_trips: List[TripSummary] = []
    my_flights: List[FlightSummary] = []
    my_hotels: List[HotelSummary] = []
    my_rentals: List[RentalSummary] = []
    flight_change_confirmed: Dict[str, bool] = {}  # booking_id -> bool
    hotel_change_confirmed: Dict[str, bool] = {}  # reservation_id -> bool
    rental_change_confirmed: Dict[str, bool] = {}  # rental_id -> bool
    insurance_renewal_confirmed: Dict[str, bool] = {}  # trip_id -> bool
    resolution_acknowledged: Dict[str, bool] = {}  # client_id -> bool
    trip_modification_authorized: Dict[str, bool] = {}  # trip_id -> bool
