from typing import List, Optional

from tau2.environment.db import DB
from tau2.utils.pydantic_utils import BaseModelNoExtra


class Client(BaseModelNoExtra):
    client_id: str
    name: str
    phone: str
    email: str
    membership_tier: str  # standard, silver, gold, platinum
    account_status: str  # active, suspended


class Trip(BaseModelNoExtra):
    trip_id: str
    client_id: str
    destination: str
    start_date: str
    end_date: str
    budget: float
    status: str  # planned, confirmed, cancelled
    travel_insurance_status: str  # active, expired, none
    discount_pct: float  # loyalty discount percentage applied


class FlightBooking(BaseModelNoExtra):
    booking_id: str
    trip_id: str
    client_id: str
    airline: str
    flight_number: str
    departure_city: str
    arrival_city: str
    departure_date: str
    seat_class: str  # economy, premium_economy, business, first
    passenger_name: str
    price: float
    status: str  # confirmed, cancelled


class HotelReservation(BaseModelNoExtra):
    reservation_id: str
    trip_id: str
    client_id: str
    hotel_name: str
    check_in_date: str
    check_out_date: str
    room_type: str  # standard, deluxe, suite
    guests: int
    price_per_night: float
    total_price: float
    status: str  # confirmed, cancelled


class CarRental(BaseModelNoExtra):
    rental_id: str
    trip_id: str
    client_id: str
    company: str
    pickup_date: str
    return_date: str
    car_type: str  # economy, compact, midsize, suv, luxury
    pickup_location: str
    daily_rate: float
    total_price: float
    status: str  # confirmed, cancelled


class TravelAgencyDB(DB):
    clients: List[Client]
    trips: List[Trip]
    flight_bookings: List[FlightBooking]
    hotel_reservations: List[HotelReservation]
    car_rentals: List[CarRental]
