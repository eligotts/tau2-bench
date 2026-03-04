from datetime import datetime
from typing import Any, Dict, List, Optional

from tau2.domains.travel_agency.data_model import (
    CarRental,
    Client,
    FlightBooking,
    HotelReservation,
    TravelAgencyDB,
    Trip,
)
from tau2.environment.toolkit import ToolKitBase, ToolType, is_tool


class TravelAgencyTools(ToolKitBase):
    db: TravelAgencyDB

    def __init__(self, db: TravelAgencyDB):
        super().__init__(db)

    # =============================================
    # PRIVATE HELPERS
    # =============================================

    def _find_client(self, client_id: str) -> Client:
        for c in self.db.clients:
            if c.client_id == client_id:
                return c
        raise ValueError(f"Client '{client_id}' not found.")

    def _find_client_by_name(self, name: str) -> Optional[Client]:
        name_lower = name.strip().lower()
        for c in self.db.clients:
            if c.name.lower() == name_lower:
                return c
        return None

    def _find_trip(self, trip_id: str) -> Trip:
        for t in self.db.trips:
            if t.trip_id == trip_id:
                return t
        raise ValueError(f"Trip '{trip_id}' not found.")

    def _find_flight(self, booking_id: str) -> FlightBooking:
        for f in self.db.flight_bookings:
            if f.booking_id == booking_id:
                return f
        raise ValueError(f"Flight booking '{booking_id}' not found.")

    def _find_hotel(self, reservation_id: str) -> HotelReservation:
        for h in self.db.hotel_reservations:
            if h.reservation_id == reservation_id:
                return h
        raise ValueError(f"Hotel reservation '{reservation_id}' not found.")

    def _find_rental(self, rental_id: str) -> CarRental:
        for r in self.db.car_rentals:
            if r.rental_id == rental_id:
                return r
        raise ValueError(f"Car rental '{rental_id}' not found.")

    def _days_between(self, start_date: str, end_date: str) -> int:
        d1 = datetime.strptime(start_date, "%Y-%m-%d")
        d2 = datetime.strptime(end_date, "%Y-%m-%d")
        return (d2 - d1).days

    # =============================================
    # READ TOOLS — transparent (Archetype C)
    # =============================================

    @is_tool(ToolType.READ)
    def get_client_by_name(self, name: str) -> Dict[str, Any]:
        """
        Look up a client by name.

        Args:
            name: Client's full name.

        Returns:
            Client details including ID, contact info, membership tier, and account status.
        """
        client = self._find_client_by_name(name)
        if client is None:
            raise ValueError(f"No client found with name '{name}'.")
        return {
            "client_id": client.client_id,
            "name": client.name,
            "phone": client.phone,
            "email": client.email,
            "membership_tier": client.membership_tier,
            "account_status": client.account_status,
        }

    @is_tool(ToolType.READ)
    def get_client_by_id(self, client_id: str) -> Dict[str, Any]:
        """
        Look up a client by their client ID.

        Args:
            client_id: The unique client identifier.

        Returns:
            Client details including name, contact info, membership tier, and account status.
        """
        client = self._find_client(client_id)
        return {
            "client_id": client.client_id,
            "name": client.name,
            "phone": client.phone,
            "email": client.email,
            "membership_tier": client.membership_tier,
            "account_status": client.account_status,
        }

    @is_tool(ToolType.READ)
    def get_trips(self, client_id: str) -> Any:
        """
        Get all trips for a client.

        Args:
            client_id: The client's unique identifier.

        Returns:
            List of trips with destination, dates, budget, and status.
            Returns an error message if the account is suspended.
        """
        client = self._find_client(client_id)
        # GATE: account status blocks trip access
        if client.account_status == "suspended":
            return (
                f"Account {client_id} is currently suspended. "
                "Reactivate the account before accessing trip records."
            )
        trips = [t for t in self.db.trips if t.client_id == client_id]
        return [
            {
                "trip_id": t.trip_id,
                "destination": t.destination,
                "start_date": t.start_date,
                "end_date": t.end_date,
                "budget": t.budget,
                "status": t.status,
                "travel_insurance_status": t.travel_insurance_status,
                "discount_pct": t.discount_pct,
            }
            for t in trips
        ]

    @is_tool(ToolType.READ)
    def get_flight_bookings(self, trip_id: str) -> List[Dict[str, Any]]:
        """
        Get all flight bookings for a trip.

        Args:
            trip_id: The trip's unique identifier.

        Returns:
            List of flight bookings with airline, dates, seat class, and price.
        """
        self._find_trip(trip_id)
        flights = [f for f in self.db.flight_bookings if f.trip_id == trip_id]
        return [
            {
                "booking_id": f.booking_id,
                "airline": f.airline,
                "flight_number": f.flight_number,
                "departure_city": f.departure_city,
                "arrival_city": f.arrival_city,
                "departure_date": f.departure_date,
                "seat_class": f.seat_class,
                "passenger_name": f.passenger_name,
                "price": f.price,
                "status": f.status,
            }
            for f in flights
        ]

    @is_tool(ToolType.READ)
    def get_hotel_reservations(self, trip_id: str) -> List[Dict[str, Any]]:
        """
        Get all hotel reservations for a trip.

        Args:
            trip_id: The trip's unique identifier.

        Returns:
            List of hotel reservations with dates, room type, and pricing.
        """
        self._find_trip(trip_id)
        hotels = [h for h in self.db.hotel_reservations if h.trip_id == trip_id]
        return [
            {
                "reservation_id": h.reservation_id,
                "hotel_name": h.hotel_name,
                "check_in_date": h.check_in_date,
                "check_out_date": h.check_out_date,
                "room_type": h.room_type,
                "guests": h.guests,
                "price_per_night": h.price_per_night,
                "total_price": h.total_price,
                "status": h.status,
            }
            for h in hotels
        ]

    @is_tool(ToolType.READ)
    def get_car_rentals(self, trip_id: str) -> List[Dict[str, Any]]:
        """
        Get all car rentals for a trip.

        Args:
            trip_id: The trip's unique identifier.

        Returns:
            List of car rentals with dates, car type, and pricing.
        """
        self._find_trip(trip_id)
        rentals = [r for r in self.db.car_rentals if r.trip_id == trip_id]
        return [
            {
                "rental_id": r.rental_id,
                "company": r.company,
                "pickup_date": r.pickup_date,
                "return_date": r.return_date,
                "car_type": r.car_type,
                "pickup_location": r.pickup_location,
                "daily_rate": r.daily_rate,
                "total_price": r.total_price,
                "status": r.status,
            }
            for r in rentals
        ]

    @is_tool(ToolType.READ)
    def review_trip_costs(self, trip_id: str) -> Dict[str, Any]:
        """
        Review the cost breakdown for a trip, flagging any pricing discrepancies.
        Computes expected totals from per-night and daily rates.

        Args:
            trip_id: The trip's unique identifier.

        Returns:
            Cost breakdown with expected vs actual totals and any discrepancies found.
        """
        trip = self._find_trip(trip_id)
        flights = [f for f in self.db.flight_bookings if f.trip_id == trip_id]
        hotels = [h for h in self.db.hotel_reservations if h.trip_id == trip_id]
        rentals = [r for r in self.db.car_rentals if r.trip_id == trip_id]

        discrepancies = []
        flight_total = sum(f.price for f in flights)
        hotel_total = 0.0
        rental_total = 0.0

        for h in hotels:
            nights = self._days_between(h.check_in_date, h.check_out_date)
            expected = round(h.price_per_night * nights, 2)
            hotel_total += h.total_price
            if abs(h.total_price - expected) > 0.01:
                discrepancies.append(
                    f"Hotel {h.reservation_id} ({h.hotel_name}): "
                    f"charged ${h.total_price:.2f} but expected "
                    f"${expected:.2f} ({nights} nights x ${h.price_per_night:.2f}/night)"
                )

        for r in rentals:
            days = self._days_between(r.pickup_date, r.return_date)
            expected = round(r.daily_rate * days, 2)
            rental_total += r.total_price
            if abs(r.total_price - expected) > 0.01:
                discrepancies.append(
                    f"Car rental {r.rental_id} ({r.company}): "
                    f"charged ${r.total_price:.2f} but expected "
                    f"${expected:.2f} ({days} days x ${r.daily_rate:.2f}/day)"
                )

        total_cost = flight_total + hotel_total + rental_total
        client = self._find_client(trip.client_id)

        return {
            "trip_id": trip_id,
            "destination": trip.destination,
            "budget": trip.budget,
            "flight_total": flight_total,
            "hotel_total": hotel_total,
            "rental_total": rental_total,
            "total_cost": round(total_cost, 2),
            "over_budget": total_cost > trip.budget,
            "membership_tier": client.membership_tier,
            "discount_pct": trip.discount_pct,
            "discrepancies": discrepancies,
            "discrepancy_count": len(discrepancies),
        }

    # =============================================
    # WRITE TOOLS — account fixes
    # =============================================

    @is_tool(ToolType.WRITE)
    def reactivate_account(self, client_id: str) -> str:
        """
        Reactivate a suspended client account.

        Args:
            client_id: The client's unique identifier.

        Returns:
            Confirmation message.
        """
        client = self._find_client(client_id)
        if client.account_status != "suspended":
            return f"Account {client_id} is not suspended (status: {client.account_status}). No changes made."
        client.account_status = "active"
        return f"Account {client_id} has been reactivated."

    # =============================================
    # WRITE TOOLS — flight fixes
    # =============================================

    @is_tool(ToolType.WRITE)
    def change_flight_date(self, booking_id: str, new_date: str) -> str:
        """
        Change the departure date on a flight booking.

        Args:
            booking_id: The flight booking identifier.
            new_date: The new departure date (YYYY-MM-DD).

        Returns:
            Confirmation message.
        """
        flight = self._find_flight(booking_id)
        old_date = flight.departure_date
        flight.departure_date = new_date
        return f"Flight {booking_id} departure changed from {old_date} to {new_date}."

    @is_tool(ToolType.WRITE)
    def change_seat_class(self, booking_id: str, seat_class: str) -> str:
        """
        Change the seat class on a flight booking.

        Args:
            booking_id: The flight booking identifier.
            seat_class: The new seat class (economy, premium_economy, business, first).

        Returns:
            Confirmation message.
        """
        flight = self._find_flight(booking_id)
        old_class = flight.seat_class
        flight.seat_class = seat_class
        return f"Flight {booking_id} seat class changed from {old_class} to {seat_class}."

    @is_tool(ToolType.WRITE)
    def update_passenger_name(self, booking_id: str, passenger_name: str) -> str:
        """
        Update the passenger name on a flight booking.

        Args:
            booking_id: The flight booking identifier.
            passenger_name: The correct passenger name.

        Returns:
            Confirmation message.
        """
        flight = self._find_flight(booking_id)
        old_name = flight.passenger_name
        flight.passenger_name = passenger_name
        return f"Flight {booking_id} passenger name updated from '{old_name}' to '{passenger_name}'."

    # =============================================
    # WRITE TOOLS — hotel fixes
    # =============================================

    @is_tool(ToolType.WRITE)
    def change_hotel_dates(self, reservation_id: str, check_in_date: str, check_out_date: str) -> str:
        """
        Change the check-in and check-out dates on a hotel reservation.
        Automatically recalculates the total price.

        Args:
            reservation_id: The hotel reservation identifier.
            check_in_date: The new check-in date (YYYY-MM-DD).
            check_out_date: The new check-out date (YYYY-MM-DD).

        Returns:
            Confirmation message with updated total.
        """
        hotel = self._find_hotel(reservation_id)
        hotel.check_in_date = check_in_date
        hotel.check_out_date = check_out_date
        nights = self._days_between(check_in_date, check_out_date)
        hotel.total_price = round(hotel.price_per_night * nights, 2)
        return (
            f"Hotel {reservation_id} dates changed to {check_in_date} - {check_out_date}. "
            f"New total: ${hotel.total_price:.2f} ({nights} nights x ${hotel.price_per_night:.2f}/night)."
        )

    @is_tool(ToolType.WRITE)
    def change_room_type(self, reservation_id: str, room_type: str) -> str:
        """
        Change the room type on a hotel reservation.

        Args:
            reservation_id: The hotel reservation identifier.
            room_type: The new room type (standard, deluxe, suite).

        Returns:
            Confirmation message.
        """
        hotel = self._find_hotel(reservation_id)
        old_type = hotel.room_type
        hotel.room_type = room_type
        return f"Hotel {reservation_id} room type changed from {old_type} to {room_type}."

    @is_tool(ToolType.WRITE)
    def adjust_hotel_price(self, reservation_id: str, correct_total: float) -> str:
        """
        Adjust the total price on a hotel reservation to the correct amount.

        Args:
            reservation_id: The hotel reservation identifier.
            correct_total: The correct total price.

        Returns:
            Confirmation message.
        """
        hotel = self._find_hotel(reservation_id)
        old_total = hotel.total_price
        hotel.total_price = correct_total
        return (
            f"Hotel {reservation_id} total adjusted from ${old_total:.2f} "
            f"to ${correct_total:.2f}."
        )

    # =============================================
    # WRITE TOOLS — car rental fixes
    # =============================================

    @is_tool(ToolType.WRITE)
    def change_car_type(self, rental_id: str, car_type: str) -> str:
        """
        Change the car type on a car rental.

        Args:
            rental_id: The car rental identifier.
            car_type: The new car type (economy, compact, midsize, suv, luxury).

        Returns:
            Confirmation message.
        """
        rental = self._find_rental(rental_id)
        old_type = rental.car_type
        rental.car_type = car_type
        return f"Car rental {rental_id} type changed from {old_type} to {car_type}."

    @is_tool(ToolType.WRITE)
    def change_rental_dates(self, rental_id: str, pickup_date: str, return_date: str) -> str:
        """
        Change the pickup and return dates on a car rental.
        Automatically recalculates the total price.

        Args:
            rental_id: The car rental identifier.
            pickup_date: The new pickup date (YYYY-MM-DD).
            return_date: The new return date (YYYY-MM-DD).

        Returns:
            Confirmation message with updated total.
        """
        rental = self._find_rental(rental_id)
        rental.pickup_date = pickup_date
        rental.return_date = return_date
        days = self._days_between(pickup_date, return_date)
        rental.total_price = round(rental.daily_rate * days, 2)
        return (
            f"Car rental {rental_id} dates changed to {pickup_date} - {return_date}. "
            f"New total: ${rental.total_price:.2f} ({days} days x ${rental.daily_rate:.2f}/day)."
        )

    # =============================================
    # WRITE TOOLS — trip-level fixes
    # =============================================

    @is_tool(ToolType.WRITE)
    def update_trip_destination(self, trip_id: str, destination: str) -> str:
        """
        Update the destination on a trip.

        Args:
            trip_id: The trip identifier.
            destination: The correct destination.

        Returns:
            Confirmation message.
        """
        trip = self._find_trip(trip_id)
        old_dest = trip.destination
        trip.destination = destination
        return f"Trip {trip_id} destination updated from '{old_dest}' to '{destination}'."

    @is_tool(ToolType.WRITE)
    def apply_loyalty_discount(self, trip_id: str, discount_pct: float) -> str:
        """
        Apply a loyalty membership discount to a trip.

        Args:
            trip_id: The trip identifier.
            discount_pct: The discount percentage to apply (0-100).

        Returns:
            Confirmation message.
        """
        trip = self._find_trip(trip_id)
        if trip.discount_pct > 0:
            return (
                f"Trip {trip_id} already has a {trip.discount_pct}% discount applied. "
                "No changes made."
            )
        trip.discount_pct = discount_pct
        return f"Trip {trip_id} loyalty discount set to {discount_pct}%."

    @is_tool(ToolType.WRITE)
    def renew_travel_insurance(self, trip_id: str) -> str:
        """
        Renew expired travel insurance on a trip.

        Args:
            trip_id: The trip identifier.

        Returns:
            Confirmation message.
        """
        trip = self._find_trip(trip_id)
        if trip.travel_insurance_status != "expired":
            return (
                f"Trip {trip_id} insurance is not expired "
                f"(status: {trip.travel_insurance_status}). No changes made."
            )
        trip.travel_insurance_status = "active"
        return f"Travel insurance renewed for trip {trip_id}."

    # =============================================
    # GENERIC TOOLS
    # =============================================

    @is_tool(ToolType.GENERIC)
    def transfer_to_human(self, summary: str) -> str:
        """
        Transfer the call to a human travel specialist.

        Args:
            summary: Brief description of the issue for the specialist.

        Returns:
            Confirmation of transfer.
        """
        return f"Call transferred to human travel specialist. Summary: {summary}"

    # =============================================
    # SETUP HELPERS — called by scenarios init
    # =============================================

    def set_account_status(self, client_id: str, status: str) -> None:
        client = self._find_client(client_id)
        client.account_status = status

    def set_flight_date(self, booking_id: str, date: str) -> None:
        flight = self._find_flight(booking_id)
        flight.departure_date = date

    def set_seat_class(self, booking_id: str, seat_class: str) -> None:
        flight = self._find_flight(booking_id)
        flight.seat_class = seat_class

    def set_passenger_name(self, booking_id: str, name: str) -> None:
        flight = self._find_flight(booking_id)
        flight.passenger_name = name

    def set_hotel_check_in(self, reservation_id: str, date: str) -> None:
        hotel = self._find_hotel(reservation_id)
        hotel.check_in_date = date

    def set_hotel_check_out(self, reservation_id: str, date: str) -> None:
        hotel = self._find_hotel(reservation_id)
        hotel.check_out_date = date

    def set_room_type(self, reservation_id: str, room_type: str) -> None:
        hotel = self._find_hotel(reservation_id)
        hotel.room_type = room_type

    def set_hotel_total_price(self, reservation_id: str, total: float) -> None:
        hotel = self._find_hotel(reservation_id)
        hotel.total_price = total

    def set_car_type(self, rental_id: str, car_type: str) -> None:
        rental = self._find_rental(rental_id)
        rental.car_type = car_type

    def set_rental_pickup_date(self, rental_id: str, date: str) -> None:
        rental = self._find_rental(rental_id)
        rental.pickup_date = date

    def set_rental_return_date(self, rental_id: str, date: str) -> None:
        rental = self._find_rental(rental_id)
        rental.return_date = date

    def set_insurance_status(self, trip_id: str, status: str) -> None:
        trip = self._find_trip(trip_id)
        trip.travel_insurance_status = status

    def set_trip_destination(self, trip_id: str, destination: str) -> None:
        trip = self._find_trip(trip_id)
        trip.destination = destination

    def set_trip_discount_pct(self, trip_id: str, pct: float) -> None:
        trip = self._find_trip(trip_id)
        trip.discount_pct = pct

    # =============================================
    # ASSERTION HELPERS — called by verification
    # =============================================

    def assert_account_status(self, client_id: str, expected: str) -> bool:
        client = self._find_client(client_id)
        return client.account_status == expected

    def assert_flight_date(self, booking_id: str, expected_date: str) -> bool:
        flight = self._find_flight(booking_id)
        return flight.departure_date == expected_date

    def assert_seat_class(self, booking_id: str, expected: str) -> bool:
        flight = self._find_flight(booking_id)
        return flight.seat_class == expected

    def assert_passenger_name(self, booking_id: str, expected_name: str) -> bool:
        flight = self._find_flight(booking_id)
        return flight.passenger_name == expected_name

    def assert_hotel_check_in(self, reservation_id: str, expected_date: str) -> bool:
        hotel = self._find_hotel(reservation_id)
        return hotel.check_in_date == expected_date

    def assert_room_type(self, reservation_id: str, expected: str) -> bool:
        hotel = self._find_hotel(reservation_id)
        return hotel.room_type == expected

    def assert_hotel_total_price(self, reservation_id: str, expected_total: float) -> bool:
        hotel = self._find_hotel(reservation_id)
        return abs(hotel.total_price - expected_total) < 0.01

    def assert_car_type(self, rental_id: str, expected: str) -> bool:
        rental = self._find_rental(rental_id)
        return rental.car_type == expected

    def assert_rental_pickup_date(self, rental_id: str, expected_date: str) -> bool:
        rental = self._find_rental(rental_id)
        return rental.pickup_date == expected_date

    def assert_insurance_status(self, trip_id: str, expected: str) -> bool:
        trip = self._find_trip(trip_id)
        return trip.travel_insurance_status == expected

    def assert_trip_destination(self, trip_id: str, expected: str) -> bool:
        trip = self._find_trip(trip_id)
        return trip.destination == expected

    def assert_hotel_check_out(self, reservation_id: str, expected_date: str) -> bool:
        hotel = self._find_hotel(reservation_id)
        return hotel.check_out_date == expected_date

    def assert_rental_return_date(self, rental_id: str, expected_date: str) -> bool:
        rental = self._find_rental(rental_id)
        return rental.return_date == expected_date

    def assert_trip_discount_pct(self, trip_id: str, expected_pct: float) -> bool:
        trip = self._find_trip(trip_id)
        return abs(trip.discount_pct - expected_pct) < 0.01
