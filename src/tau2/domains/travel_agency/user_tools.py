from typing import Any, Dict, List

from tau2.domains.travel_agency.user_data_model import TravelAgencyUserDB
from tau2.environment.toolkit import ToolKitBase, ToolType, is_tool


class TravelAgencyUserTools(ToolKitBase):
    db: TravelAgencyUserDB

    def __init__(self, db: TravelAgencyUserDB):
        super().__init__(db)

    # =============================================
    # READ TOOLS — user's view of their bookings
    # =============================================

    @is_tool(ToolType.READ)
    def view_my_trips(self) -> List[Dict[str, Any]]:
        """View my trip summaries."""
        return [t.model_dump() for t in self.db.my_trips]

    @is_tool(ToolType.READ)
    def view_my_bookings(self) -> Dict[str, Any]:
        """View all my booking details including flights, hotels, and car rentals."""
        return {
            "flights": [f.model_dump() for f in self.db.my_flights],
            "hotels": [h.model_dump() for h in self.db.my_hotels],
            "rentals": [r.model_dump() for r in self.db.my_rentals],
        }

    # =============================================
    # WRITE TOOLS — user confirmations
    # =============================================

    @is_tool(ToolType.WRITE)
    def confirm_flight_change(self, booking_id: str) -> str:
        """
        Confirm a flight booking modification.

        Args:
            booking_id: The flight booking to confirm changes for.

        Returns:
            Confirmation of acceptance.
        """
        self.db.flight_change_confirmed[booking_id] = True
        return f"Flight change confirmed for booking {booking_id}."

    @is_tool(ToolType.WRITE)
    def confirm_hotel_change(self, reservation_id: str) -> str:
        """
        Confirm a hotel reservation modification.

        Args:
            reservation_id: The hotel reservation to confirm changes for.

        Returns:
            Confirmation of acceptance.
        """
        self.db.hotel_change_confirmed[reservation_id] = True
        return f"Hotel change confirmed for reservation {reservation_id}."

    @is_tool(ToolType.WRITE)
    def confirm_rental_change(self, rental_id: str) -> str:
        """
        Confirm a car rental modification.

        Args:
            rental_id: The car rental to confirm changes for.

        Returns:
            Confirmation of acceptance.
        """
        self.db.rental_change_confirmed[rental_id] = True
        return f"Car rental change confirmed for rental {rental_id}."

    @is_tool(ToolType.WRITE)
    def confirm_insurance_renewal(self, trip_id: str) -> str:
        """
        Confirm travel insurance renewal.

        Args:
            trip_id: The trip ID for the insurance renewal.

        Returns:
            Confirmation of acceptance.
        """
        self.db.insurance_renewal_confirmed[trip_id] = True
        return f"Insurance renewal confirmed for trip {trip_id}."

    @is_tool(ToolType.WRITE)
    def acknowledge_resolution(self, client_id: str) -> str:
        """
        Acknowledge that an account or administrative issue has been resolved.

        Args:
            client_id: Your client ID.

        Returns:
            Confirmation of acknowledgment.
        """
        self.db.resolution_acknowledged[client_id] = True
        return "Resolution acknowledged. Thank you."

    @is_tool(ToolType.WRITE)
    def authorize_trip_modification(self, trip_id: str) -> str:
        """
        Authorize a modification to a trip's itinerary or budget.

        Args:
            trip_id: The trip ID to authorize changes for.

        Returns:
            Confirmation of authorization.
        """
        self.db.trip_modification_authorized[trip_id] = True
        return f"Trip modification authorized for trip {trip_id}."

    # =============================================
    # SETUP HELPERS — called by scenarios init
    # =============================================

    def set_client_info(self, name: str, client_id: str) -> None:
        """Set the user's identity for this scenario."""
        self.db.client_name = name
        self.db.client_id = client_id

    # =============================================
    # ASSERTION HELPERS — called by verification
    # =============================================

    def assert_flight_change_confirmed(self, booking_id: str) -> bool:
        return self.db.flight_change_confirmed.get(booking_id, False)

    def assert_hotel_change_confirmed(self, reservation_id: str) -> bool:
        return self.db.hotel_change_confirmed.get(reservation_id, False)

    def assert_rental_change_confirmed(self, rental_id: str) -> bool:
        return self.db.rental_change_confirmed.get(rental_id, False)

    def assert_insurance_renewal_confirmed(self, trip_id: str) -> bool:
        return self.db.insurance_renewal_confirmed.get(trip_id, False)

    def assert_resolution_acknowledged(self, client_id: str) -> bool:
        return self.db.resolution_acknowledged.get(client_id, False)

    def assert_trip_modification_authorized(self, trip_id: str) -> bool:
        return self.db.trip_modification_authorized.get(trip_id, False)
