"""Travel agency scenario definitions using the Recipe Engine.

8 fault groups (transaction processor archetype):
  - Account status (suspended) gates trip access
  - Flight details (date, seat class), passenger name
  - Hotel details (dates, room type), pricing
  - Car rental details (type, dates)
  - Travel insurance, trip itinerary, loyalty discount

Cartesian product produces substantial combos/entity.
2 unfixable layers in a separate transfer config.
"""

from pathlib import Path
from typing import Any, Callable, Optional

from tau2.domains.travel_agency.data_model import TravelAgencyDB
from tau2.domains.travel_agency.environment import get_environment
from tau2.domains.travel_agency.utils import (
    TRAVEL_AGENCY_DB_PATH,
    TRAVEL_AGENCY_POLICY_PATH,
    TRAVEL_AGENCY_TASK_SET_PATH,
)
from tau2.generators.recipe import (
    ActionSpec,
    AssertionSpec,
    FaultAtom,
    FaultLayer,
    FaultLayerConfig,
    FaultLayerGroup,
    InitCall,
    RecipeBook,
    generate_recipe_tasks,
    verify_completion_fragments,
    verify_fault_atoms,
)
from tau2.generators.types import Persona, UserTemplate
from tau2.generators.verify import verify_tasks
from tau2.generators.verify_authoring import (
    collect_authored_files,
    verify_authoring,
    verify_authoring_with_llm,
)
from tau2.utils import dump_file


# ===================================================================
# Personas
# ===================================================================

PERSONAS = [
    Persona(
        name="organized_traveler",
        description=(
            "You are a well-organized traveler who has carefully planned your trip. "
            "You describe booking issues clearly and provide specific details like "
            "dates, booking IDs, and preferences. You cooperate with the agent "
            "and follow instructions promptly."
        ),
    ),
    Persona(
        name="overwhelmed_traveler",
        description=(
            "You are feeling overwhelmed by all the travel planning details. You "
            "describe your issues in general terms and sometimes mix up specific "
            "dates or booking references. You cooperate but occasionally need the "
            "agent to help you identify exactly which booking has the problem."
        ),
    ),
]


# ===================================================================
# User Template
# ===================================================================

USER_TEMPLATE = UserTemplate(
    domain="travel_agency",
    reason_for_call=(
        "You are contacting Horizon Travel Agency because you have "
        "issues with your upcoming trip bookings."
    ),
    known_info=(
        "You are {client_name} (client ID: {client_id}). "
        "Your trip is to {destination} from {trip_start_date} to {trip_end_date}. "
        "{fault_descriptions}"
    ),
    task_instructions=(
        "Follow the agent's instructions throughout the conversation. "
        "When the agent asks you to perform an action or use one of your tools, do so. "
        "You must actually call the tool — describing the action in words is not sufficient. "
        "You will consider your issues resolved when the agent confirms all problems have been addressed."
    ),
    ticket=(
        "Client {client_name} (ID: {client_id}), "
        "trip to {destination} ({trip_start_date} to {trip_end_date}). "
        "{fault_descriptions}"
    ),
    purpose=(
        "Test resolution of travel agency support issues including account access, "
        "flight modifications, hotel changes, car rental updates, insurance renewal, "
        "itinerary corrections, and pricing adjustments."
    ),
)


# ===================================================================
# Entity construction
# ===================================================================

def _build_entities(db: TravelAgencyDB) -> list[dict[str, Any]]:
    """Build entity dicts: one per client, joining trip + flight + hotel + rental."""
    trip_by_client = {}
    for t in db.trips:
        if t.client_id not in trip_by_client and t.status != "cancelled":
            trip_by_client[t.client_id] = t

    flight_by_trip = {}
    for f in db.flight_bookings:
        if f.trip_id not in flight_by_trip and f.status == "confirmed":
            flight_by_trip[f.trip_id] = f

    hotel_by_trip = {}
    for h in db.hotel_reservations:
        if h.trip_id not in hotel_by_trip and h.status == "confirmed":
            hotel_by_trip[h.trip_id] = h

    rental_by_trip = {}
    for r in db.car_rentals:
        if r.trip_id not in rental_by_trip and r.status == "confirmed":
            rental_by_trip[r.trip_id] = r

    entities = []
    for client in db.clients:
        trip = trip_by_client.get(client.client_id)
        if trip is None:
            continue
        flight = flight_by_trip.get(trip.trip_id)
        if flight is None:
            continue
        hotel = hotel_by_trip.get(trip.trip_id)
        if hotel is None:
            continue
        rental = rental_by_trip.get(trip.trip_id)

        # Compute correct hotel total for pricing fault
        from datetime import datetime
        ci = datetime.strptime(hotel.check_in_date, "%Y-%m-%d")
        co = datetime.strptime(hotel.check_out_date, "%Y-%m-%d")
        nights = (co - ci).days
        correct_hotel_total = round(hotel.price_per_night * nights, 2)

        # Compute loyalty discount based on tier
        tier_discounts = {"standard": 0.0, "silver": 5.0, "gold": 10.0, "platinum": 15.0}
        expected_discount = tier_discounts.get(client.membership_tier, 0.0)

        entity: dict[str, Any] = {
            # Client
            "client_id": client.client_id,
            "client_name": client.name,
            "client_phone": client.phone,
            "client_email": client.email,
            "membership_tier": client.membership_tier,
            # Trip
            "trip_id": trip.trip_id,
            "destination": trip.destination,
            "trip_start_date": trip.start_date,
            "trip_end_date": trip.end_date,
            "trip_budget": trip.budget,
            "trip_status": trip.status,
            "original_destination": trip.destination,
            # Flight
            "booking_id": flight.booking_id,
            "airline": flight.airline,
            "flight_number": flight.flight_number,
            "departure_city": flight.departure_city,
            "arrival_city": flight.arrival_city,
            "original_departure_date": flight.departure_date,
            "original_seat_class": flight.seat_class,
            "original_passenger_name": flight.passenger_name,
            "flight_price": flight.price,
            # Hotel
            "reservation_id": hotel.reservation_id,
            "hotel_name": hotel.hotel_name,
            "original_check_in_date": hotel.check_in_date,
            "original_check_out_date": hotel.check_out_date,
            "original_room_type": hotel.room_type,
            "hotel_guests": hotel.guests,
            "hotel_price_per_night": hotel.price_per_night,
            "correct_hotel_total": correct_hotel_total,
            "hotel_nights": nights,
            # Car rental (optional)
            "rental_id": rental.rental_id if rental else "N/A",
            "rental_company": rental.company if rental else "N/A",
            "original_pickup_date": rental.pickup_date if rental else "N/A",
            "original_return_date": rental.return_date if rental else "N/A",
            "original_car_type": rental.car_type if rental else "N/A",
            "rental_daily_rate": rental.daily_rate if rental else "N/A",
            # Predicate flags
            "has_rental": rental is not None,
            "has_insurance": trip.travel_insurance_status == "active",
            "has_loyalty_tier": client.membership_tier != "standard",
            # Pricing
            "expected_discount_pct": expected_discount,
        }
        entities.append(entity)

    return entities


# ===================================================================
# Fault Layers
# ===================================================================

# --- Group 1: Account Issues (1 layer) ---
# UPSTREAM GATE: blocks get_trips()

suspended_account = FaultLayer(
    name="suspended_account",
    known_info_fragment=(
        "My account appears to be suspended — I cannot access any of my trip information online."
    ),
    completion_fragment="your account is active and your trip information is accessible",
    atoms=[
        FaultAtom(
            init=InitCall(
                env_type="assistant",
                func_name="set_account_status",
                args={"client_id": "{client_id}", "status": "suspended"},
            ),
            fix=ActionSpec(
                tool_name="reactivate_account",
                args={"client_id": "{client_id}"},
                compare_args=["client_id"],
            ),
            check=AssertionSpec(
                func_name="assert_account_status",
                args={"client_id": "{client_id}", "expected": "active"},
                env_type="assistant",
                message_template="Account {client_id} should be active.",
            ),
        ),
        FaultAtom(
            fix=ActionSpec(
                tool_name="acknowledge_resolution",
                args={"client_id": "{client_id}"},
                requestor="user",
                compare_args=[],
            ),
            check=AssertionSpec(
                func_name="assert_resolution_acknowledged",
                args={"client_id": "{client_id}"},
                env_type="user",
            ),
        ),
    ],
    resource_scope="account:{client_id}",
)

account_group = FaultLayerGroup(
    name="account_issues",
    layers=[suspended_account],
    resolution_category="account",
)


# --- Group 2: Flight Details (2 mutually exclusive) ---

wrong_flight_date = FaultLayer(
    name="wrong_flight_date",
    known_info_fragment=(
        "My flight to {arrival_city} is scheduled for the wrong date. "
        "It should be departing on {original_departure_date}."
    ),
    completion_fragment="your flight to {arrival_city} shows the correct departure date of {original_departure_date}",
    atoms=[
        FaultAtom(
            init=InitCall(
                env_type="assistant",
                func_name="set_flight_date",
                args={"booking_id": "{booking_id}", "date": "2025-12-31"},
            ),
            fix=ActionSpec(
                tool_name="change_flight_date",
                args={
                    "booking_id": "{booking_id}",
                    "new_date": "{original_departure_date}",
                },
                compare_args=["booking_id"],
            ),
            check=AssertionSpec(
                func_name="assert_flight_date",
                args={
                    "booking_id": "{booking_id}",
                    "expected_date": "{original_departure_date}",
                },
                env_type="assistant",
                message_template="Flight {booking_id} should depart on {original_departure_date}.",
            ),
        ),
        FaultAtom(
            fix=ActionSpec(
                tool_name="confirm_flight_change",
                args={"booking_id": "{booking_id}"},
                requestor="user",
                compare_args=[],
            ),
            check=AssertionSpec(
                func_name="assert_flight_change_confirmed",
                args={"booking_id": "{booking_id}"},
                env_type="user",
            ),
        ),
    ],
    resource_scope="flight_date:{booking_id}",
)

wrong_seat_class = FaultLayer(
    name="wrong_seat_class",
    known_info_fragment=(
        "My flight to {arrival_city} has the wrong seat class. "
        "I booked {original_seat_class} but it shows something else."
    ),
    completion_fragment="your flight to {arrival_city} shows {original_seat_class} class seating",
    atoms=[
        FaultAtom(
            init=InitCall(
                env_type="assistant",
                func_name="set_seat_class",
                args={"booking_id": "{booking_id}", "seat_class": "unassigned"},
            ),
            fix=ActionSpec(
                tool_name="change_seat_class",
                args={
                    "booking_id": "{booking_id}",
                    "seat_class": "{original_seat_class}",
                },
                compare_args=["booking_id"],
            ),
            check=AssertionSpec(
                func_name="assert_seat_class",
                args={
                    "booking_id": "{booking_id}",
                    "expected": "{original_seat_class}",
                },
                env_type="assistant",
                message_template="Flight {booking_id} should have {original_seat_class} class.",
            ),
        ),
        FaultAtom(
            fix=ActionSpec(
                tool_name="confirm_flight_change",
                args={"booking_id": "{booking_id}"},
                requestor="user",
                compare_args=[],
            ),
            check=AssertionSpec(
                func_name="assert_flight_change_confirmed",
                args={"booking_id": "{booking_id}"},
                env_type="user",
            ),
        ),
    ],
    resource_scope="flight_class:{booking_id}",
)

flight_group = FaultLayerGroup(
    name="flight_details",
    layers=[wrong_flight_date, wrong_seat_class],
    resolution_category="booking",
)


# --- Group 3: Passenger Name (1 layer) ---

wrong_passenger_name = FaultLayer(
    name="wrong_passenger_name",
    known_info_fragment=(
        "The passenger name on my flight ticket to {arrival_city} is wrong. "
        "My name is {client_name} but the ticket shows a different name."
    ),
    completion_fragment="your flight ticket to {arrival_city} shows the correct passenger name {client_name}",
    atoms=[
        FaultAtom(
            init=InitCall(
                env_type="assistant",
                func_name="set_passenger_name",
                args={"booking_id": "{booking_id}", "name": "John Doe"},
            ),
            fix=ActionSpec(
                tool_name="update_passenger_name",
                args={
                    "booking_id": "{booking_id}",
                    "passenger_name": "{client_name}",
                },
                compare_args=["booking_id"],
            ),
            check=AssertionSpec(
                func_name="assert_passenger_name",
                args={
                    "booking_id": "{booking_id}",
                    "expected_name": "{client_name}",
                },
                env_type="assistant",
                message_template="Flight {booking_id} should have passenger name {client_name}.",
            ),
        ),
        FaultAtom(
            fix=ActionSpec(
                tool_name="confirm_flight_change",
                args={"booking_id": "{booking_id}"},
                requestor="user",
                compare_args=[],
            ),
            check=AssertionSpec(
                func_name="assert_flight_change_confirmed",
                args={"booking_id": "{booking_id}"},
                env_type="user",
            ),
        ),
    ],
    resource_scope="passenger:{booking_id}",
)

passenger_group = FaultLayerGroup(
    name="passenger_info",
    layers=[wrong_passenger_name],
    resolution_category="booking",
)


# --- Group 4: Hotel Details (2 mutually exclusive) ---

wrong_check_in_date = FaultLayer(
    name="wrong_check_in_date",
    known_info_fragment=(
        "My hotel reservation at {hotel_name} has the wrong check-in date. "
        "It should be {original_check_in_date}, not what is listed."
    ),
    completion_fragment="your hotel reservation at {hotel_name} shows the correct check-in date of {original_check_in_date}",
    atoms=[
        FaultAtom(
            init=InitCall(
                env_type="assistant",
                func_name="set_hotel_check_in",
                args={"reservation_id": "{reservation_id}", "date": "2025-12-25"},
            ),
            fix=ActionSpec(
                tool_name="change_hotel_dates",
                args={
                    "reservation_id": "{reservation_id}",
                    "check_in_date": "{original_check_in_date}",
                    "check_out_date": "{original_check_out_date}",
                },
                compare_args=["reservation_id"],
            ),
            check=AssertionSpec(
                func_name="assert_hotel_check_in",
                args={
                    "reservation_id": "{reservation_id}",
                    "expected_date": "{original_check_in_date}",
                },
                env_type="assistant",
                message_template="Hotel {reservation_id} should check in on {original_check_in_date}.",
            ),
        ),
        FaultAtom(
            fix=ActionSpec(
                tool_name="confirm_hotel_change",
                args={"reservation_id": "{reservation_id}"},
                requestor="user",
                compare_args=[],
            ),
            check=AssertionSpec(
                func_name="assert_hotel_change_confirmed",
                args={"reservation_id": "{reservation_id}"},
                env_type="user",
            ),
        ),
    ],
    resource_scope="hotel_dates:{reservation_id}",
)

wrong_room_type = FaultLayer(
    name="wrong_room_type",
    known_info_fragment=(
        "My hotel reservation at {hotel_name} has the wrong room type. "
        "I booked a {original_room_type} room but it shows something different."
    ),
    completion_fragment="your hotel reservation at {hotel_name} shows a {original_room_type} room",
    atoms=[
        FaultAtom(
            init=InitCall(
                env_type="assistant",
                func_name="set_room_type",
                args={"reservation_id": "{reservation_id}", "room_type": "unassigned"},
            ),
            fix=ActionSpec(
                tool_name="change_room_type",
                args={
                    "reservation_id": "{reservation_id}",
                    "room_type": "{original_room_type}",
                },
                compare_args=["reservation_id"],
            ),
            check=AssertionSpec(
                func_name="assert_room_type",
                args={
                    "reservation_id": "{reservation_id}",
                    "expected": "{original_room_type}",
                },
                env_type="assistant",
                message_template="Hotel {reservation_id} should have {original_room_type} room.",
            ),
        ),
        FaultAtom(
            fix=ActionSpec(
                tool_name="confirm_hotel_change",
                args={"reservation_id": "{reservation_id}"},
                requestor="user",
                compare_args=[],
            ),
            check=AssertionSpec(
                func_name="assert_hotel_change_confirmed",
                args={"reservation_id": "{reservation_id}"},
                env_type="user",
            ),
        ),
    ],
    resource_scope="hotel_room:{reservation_id}",
)

overcharged_hotel = FaultLayer(
    name="overcharged_hotel",
    known_info_fragment=(
        "The total on my hotel reservation at {hotel_name} seems wrong. "
        "I am being charged for {hotel_nights} nights at ${hotel_price_per_night} "
        "per night but the total doesn't add up."
    ),
    completion_fragment="your hotel reservation at {hotel_name} shows the correct total of ${correct_hotel_total}",
    atoms=[
        FaultAtom(
            init=InitCall(
                env_type="assistant",
                func_name="set_hotel_total_price",
                args={"reservation_id": "{reservation_id}", "total": 9999.99},
            ),
            fix=ActionSpec(
                tool_name="adjust_hotel_price",
                args={
                    "reservation_id": "{reservation_id}",
                    "correct_total": "{correct_hotel_total}",
                },
                compare_args=["reservation_id"],
            ),
            check=AssertionSpec(
                func_name="assert_hotel_total_price",
                args={
                    "reservation_id": "{reservation_id}",
                    "expected_total": "{correct_hotel_total}",
                },
                env_type="assistant",
                message_template="Hotel {reservation_id} total should be ${correct_hotel_total}.",
            ),
        ),
        FaultAtom(
            fix=ActionSpec(
                tool_name="confirm_hotel_change",
                args={"reservation_id": "{reservation_id}"},
                requestor="user",
                compare_args=[],
            ),
            check=AssertionSpec(
                func_name="assert_hotel_change_confirmed",
                args={"reservation_id": "{reservation_id}"},
                env_type="user",
            ),
        ),
    ],
    resource_scope="hotel_price:{reservation_id}",
)

hotel_group = FaultLayerGroup(
    name="hotel_details",
    layers=[wrong_check_in_date, wrong_room_type, overcharged_hotel],
    resolution_category="booking",
)


# --- Group 5: Car Rental Details (2 mutually exclusive, predicated) ---

wrong_car_type = FaultLayer(
    name="wrong_car_type",
    known_info_fragment=(
        "My car rental with {rental_company} has the wrong vehicle type. "
        "I booked a {original_car_type} but it shows something different."
    ),
    completion_fragment="your car rental with {rental_company} shows a {original_car_type} vehicle",
    atoms=[
        FaultAtom(
            init=InitCall(
                env_type="assistant",
                func_name="set_car_type",
                args={"rental_id": "{rental_id}", "car_type": "unassigned"},
            ),
            fix=ActionSpec(
                tool_name="change_car_type",
                args={
                    "rental_id": "{rental_id}",
                    "car_type": "{original_car_type}",
                },
                compare_args=["rental_id"],
            ),
            check=AssertionSpec(
                func_name="assert_car_type",
                args={
                    "rental_id": "{rental_id}",
                    "expected": "{original_car_type}",
                },
                env_type="assistant",
                message_template="Rental {rental_id} should be {original_car_type}.",
            ),
        ),
        FaultAtom(
            fix=ActionSpec(
                tool_name="confirm_rental_change",
                args={"rental_id": "{rental_id}"},
                requestor="user",
                compare_args=[],
            ),
            check=AssertionSpec(
                func_name="assert_rental_change_confirmed",
                args={"rental_id": "{rental_id}"},
                env_type="user",
            ),
        ),
    ],
    predicate_field="has_rental",
    resource_scope="rental_type:{rental_id}",
)

wrong_pickup_date = FaultLayer(
    name="wrong_pickup_date",
    known_info_fragment=(
        "My car rental with {rental_company} has the wrong pickup date. "
        "It should be {original_pickup_date}, not what is listed."
    ),
    completion_fragment="your car rental with {rental_company} shows the correct pickup date of {original_pickup_date}",
    atoms=[
        FaultAtom(
            init=InitCall(
                env_type="assistant",
                func_name="set_rental_pickup_date",
                args={"rental_id": "{rental_id}", "date": "2025-12-31"},
            ),
            fix=ActionSpec(
                tool_name="change_rental_dates",
                args={
                    "rental_id": "{rental_id}",
                    "pickup_date": "{original_pickup_date}",
                    "return_date": "{original_return_date}",
                },
                compare_args=["rental_id"],
            ),
            check=AssertionSpec(
                func_name="assert_rental_pickup_date",
                args={
                    "rental_id": "{rental_id}",
                    "expected_date": "{original_pickup_date}",
                },
                env_type="assistant",
                message_template="Rental {rental_id} should pick up on {original_pickup_date}.",
            ),
        ),
        FaultAtom(
            fix=ActionSpec(
                tool_name="confirm_rental_change",
                args={"rental_id": "{rental_id}"},
                requestor="user",
                compare_args=[],
            ),
            check=AssertionSpec(
                func_name="assert_rental_change_confirmed",
                args={"rental_id": "{rental_id}"},
                env_type="user",
            ),
        ),
    ],
    predicate_field="has_rental",
    resource_scope="rental_dates:{rental_id}",
)

rental_group = FaultLayerGroup(
    name="car_rental_details",
    layers=[wrong_car_type, wrong_pickup_date],
    resolution_category="booking",
)


# --- Group 6: Travel Insurance (1 layer, predicated) ---

expired_insurance = FaultLayer(
    name="expired_insurance",
    known_info_fragment=(
        "The travel insurance on my trip to {destination} has expired. "
        "I need it renewed before my travel dates."
    ),
    completion_fragment="your travel insurance for the trip to {destination} shows as active",
    atoms=[
        FaultAtom(
            init=InitCall(
                env_type="assistant",
                func_name="set_insurance_status",
                args={"trip_id": "{trip_id}", "status": "expired"},
            ),
            fix=ActionSpec(
                tool_name="renew_travel_insurance",
                args={"trip_id": "{trip_id}"},
                compare_args=["trip_id"],
            ),
            check=AssertionSpec(
                func_name="assert_insurance_status",
                args={"trip_id": "{trip_id}", "expected": "active"},
                env_type="assistant",
                message_template="Trip {trip_id} insurance should be active.",
            ),
        ),
        FaultAtom(
            fix=ActionSpec(
                tool_name="confirm_insurance_renewal",
                args={"trip_id": "{trip_id}"},
                requestor="user",
                compare_args=[],
            ),
            check=AssertionSpec(
                func_name="assert_insurance_renewal_confirmed",
                args={"trip_id": "{trip_id}"},
                env_type="user",
            ),
        ),
    ],
    predicate_field="has_insurance",
    resource_scope="insurance:{trip_id}",
)

insurance_group = FaultLayerGroup(
    name="travel_insurance",
    layers=[expired_insurance],
    resolution_category="insurance",
)


# --- Group 7: Trip Itinerary (1 layer) ---

wrong_destination = FaultLayer(
    name="wrong_destination",
    known_info_fragment=(
        "My trip has the wrong destination recorded. "
        "It should be {original_destination}, not what is shown in the system."
    ),
    completion_fragment="your trip shows the correct destination of {original_destination}",
    atoms=[
        FaultAtom(
            init=InitCall(
                env_type="assistant",
                func_name="set_trip_destination",
                args={"trip_id": "{trip_id}", "destination": "Unknown City"},
            ),
            fix=ActionSpec(
                tool_name="update_trip_destination",
                args={
                    "trip_id": "{trip_id}",
                    "destination": "{original_destination}",
                },
                compare_args=["trip_id"],
            ),
            check=AssertionSpec(
                func_name="assert_trip_destination",
                args={
                    "trip_id": "{trip_id}",
                    "expected": "{original_destination}",
                },
                env_type="assistant",
                message_template="Trip {trip_id} destination should be {original_destination}.",
            ),
        ),
        FaultAtom(
            fix=ActionSpec(
                tool_name="authorize_trip_modification",
                args={"trip_id": "{trip_id}"},
                requestor="user",
                compare_args=[],
            ),
            check=AssertionSpec(
                func_name="assert_trip_modification_authorized",
                args={"trip_id": "{trip_id}"},
                env_type="user",
            ),
        ),
    ],
    resource_scope="destination:{trip_id}",
)

itinerary_group = FaultLayerGroup(
    name="trip_itinerary",
    layers=[wrong_destination],
    resolution_category="booking",
)


# --- Group 8: Pricing Issues (loyalty discount only) ---

missing_loyalty_discount = FaultLayer(
    name="missing_loyalty_discount",
    known_info_fragment=(
        "I am a {membership_tier} tier member and my trip to {destination} "
        "does not have my loyalty discount applied."
    ),
    completion_fragment="your trip to {destination} shows your {membership_tier} tier loyalty discount",
    atoms=[
        FaultAtom(
            init=InitCall(
                env_type="assistant",
                func_name="set_trip_discount_pct",
                args={"trip_id": "{trip_id}", "pct": 0.0},
            ),
            fix=ActionSpec(
                tool_name="apply_loyalty_discount",
                args={
                    "trip_id": "{trip_id}",
                    "discount_pct": "{expected_discount_pct}",
                },
                compare_args=["trip_id"],
            ),
            check=AssertionSpec(
                func_name="assert_trip_discount_pct",
                args={
                    "trip_id": "{trip_id}",
                    "expected_pct": "{expected_discount_pct}",
                },
                env_type="assistant",
                message_template="Trip {trip_id} should have {expected_discount_pct}% discount.",
            ),
        ),
        FaultAtom(
            fix=ActionSpec(
                tool_name="authorize_trip_modification",
                args={"trip_id": "{trip_id}"},
                requestor="user",
                compare_args=[],
            ),
            check=AssertionSpec(
                func_name="assert_trip_modification_authorized",
                args={"trip_id": "{trip_id}"},
                env_type="user",
            ),
        ),
    ],
    predicate_field="has_loyalty_tier",
    resource_scope="discount:{trip_id}",
)

pricing_group = FaultLayerGroup(
    name="pricing_issues",
    layers=[missing_loyalty_discount],
    resolution_category="pricing",
)


# ===================================================================
# Unfixable layers (separate transfer config)
# ===================================================================

visa_restriction = FaultLayer(
    name="visa_restriction",
    unfixable=True,
    known_info_fragment=(
        "I need to travel to {destination} but I just realized I may need a visa "
        "that I cannot get in time before my departure on {original_departure_date}."
    ),
    completion_fragment=(
        "your visa for {destination} has been arranged and your trip can proceed as planned"
    ),
    atoms=[],
    resource_scope="visa:{trip_id}",
)

fully_booked_destination = FaultLayer(
    name="fully_booked_destination",
    unfixable=True,
    known_info_fragment=(
        "I want to change my trip destination to Santorini, Greece but I have heard "
        "it might be fully booked for my dates."
    ),
    completion_fragment=(
        "your trip has been rebooked to Santorini, Greece with flights and hotel confirmed"
    ),
    atoms=[],
    resource_scope="availability:{trip_id}",
)

unfixable_group = FaultLayerGroup(
    name="unfixable_issues",
    layers=[visa_restriction, fully_booked_destination],
    resolution_category="booking",
)


# ===================================================================
# FaultLayerConfigs
# ===================================================================

FIXABLE_CONFIG = FaultLayerConfig(
    name="travel_agency",
    entity_query=lambda db: _build_entities(db),
    groups=[
        account_group,      # Group 1: account (1 layer) — upstream gate
        flight_group,       # Group 2: flight details (2 layers)
        passenger_group,    # Group 3: passenger name (1 layer)
        hotel_group,        # Group 4: hotel details (2 layers)
        rental_group,       # Group 5: car rental (2 layers, predicated)
        insurance_group,    # Group 6: insurance (1 layer, predicated)
        itinerary_group,    # Group 7: trip itinerary (1 layer)
        pricing_group,      # Group 8: pricing (2 layers)
    ],
    base_init_calls=[
        InitCall(
            env_type="user",
            func_name="set_client_info",
            args={"name": "{client_name}", "client_id": "{client_id}"},
        ),
    ],
    base_known_info_template=(
        "You are {client_name}. Your client ID is {client_id}. "
        "Your trip (ID: {trip_id}) is to {destination} from {trip_start_date} to {trip_end_date}. "
        "Your flight booking ID is {booking_id}. "
        "Your hotel reservation ID is {reservation_id}. "
        "Your car rental ID is {rental_id}. "
        "{fault_descriptions}"
    ),
    base_ticket_template=(
        "Client {client_name} (ID: {client_id}), "
        "trip {trip_id} to {destination} ({trip_start_date} to {trip_end_date}). "
        "Flight: {booking_id}, Hotel: {reservation_id}, Car: {rental_id}. "
        "{fault_descriptions}"
    ),
    reason_for_call=(
        "You are contacting Horizon Travel Agency because you have "
        "issues with your upcoming trip bookings."
    ),
    purpose=(
        "Test resolution of travel agency support issues with transparent "
        "READ tools and protocol-driven WRITE tools."
    ),
    entity_id_field="client_id",
    min_faults=1,
    max_faults=8,
    max_total_tasks=1200,
    tool_grounding_block=(
        "Whenever the agent asks you about your bookings or trip status, "
        "always ground your responses on the results of tool calls. "
        "Never make up the results of tool calls, always ground your "
        "responses on the results of tool calls. If you are unsure about "
        "whether an action is necessary, always ask the agent for "
        "clarification."
    ),
)

TRANSFER_CONFIG = FaultLayerConfig(
    name="travel_agency_transfer",
    entity_query=lambda db: _build_entities(db),
    groups=[unfixable_group],
    base_init_calls=[
        InitCall(
            env_type="user",
            func_name="set_client_info",
            args={"name": "{client_name}", "client_id": "{client_id}"},
        ),
    ],
    base_known_info_template=(
        "You are {client_name}. Your client ID is {client_id}. "
        "Your trip is to {destination} from {trip_start_date} to {trip_end_date}. "
        "{fault_descriptions}"
    ),
    base_ticket_template=(
        "Client {client_name} (ID: {client_id}), "
        "trip to {destination} ({trip_start_date} to {trip_end_date}). "
        "{fault_descriptions}"
    ),
    reason_for_call=(
        "You are contacting Horizon Travel Agency about a trip issue."
    ),
    purpose="Test transfer-to-human for issues outside travel agency scope.",
    entity_id_field="client_id",
    min_faults=1,
    max_faults=1,
    max_total_tasks=16,
)


# ===================================================================
# RecipeBook
# ===================================================================

RECIPE_BOOK = RecipeBook(
    fault_layer_configs=[FIXABLE_CONFIG, TRANSFER_CONFIG],
    resolution_instruction=(
        "your trip booking details are correct and any account, pricing, "
        "or insurance issues have been resolved"
    ),
)


# ===================================================================
# Task generation entry point
# ===================================================================

def create_tasks(
    verify: bool = True,
    save: bool = False,
    seed: int = 42,
    llm_verify: bool = False,
    llm_call_fn: Optional[Callable[[str], str]] = None,
) -> list:
    """Generate tasks from the recipe book, optionally verify and save."""
    def get_db():
        return TravelAgencyDB.load(TRAVEL_AGENCY_DB_PATH)

    if verify:
        authoring_issues = verify_authoring(RECIPE_BOOK, get_environment, get_db)
        auth_errors = [i for i in authoring_issues if i.startswith("ERROR:")]
        auth_warnings = [i for i in authoring_issues if i.startswith("WARNING:")]
        print(f"Authoring verification: {len(auth_errors)} error(s), {len(auth_warnings)} warning(s)")
        for i in authoring_issues:
            print(f"  {i}")
        if auth_errors:
            raise ValueError(f"Authoring verification failed: {len(auth_errors)} error(s)")

        if llm_verify and llm_call_fn:
            authored_files = collect_authored_files(
                file_paths={
                    "tools.py": str(Path(__file__).parent / "tools.py"),
                    "scenarios.py": str(Path(__file__).parent / "scenarios.py"),
                    "data_model.py": str(Path(__file__).parent / "data_model.py"),
                    "user_tools.py": str(Path(__file__).parent / "user_tools.py"),
                    "environment.py": str(Path(__file__).parent / "environment.py"),
                    "policy.md": str(TRAVEL_AGENCY_POLICY_PATH),
                },
                db_path=str(TRAVEL_AGENCY_DB_PATH),
            )
            verify_authoring_with_llm(
                RECIPE_BOOK, authored_files, authoring_issues, llm_call_fn
            )

    tasks = generate_recipe_tasks(
        recipe_book=RECIPE_BOOK,
        build_indexes=lambda db: db,
        get_db=get_db,
        user_template=USER_TEMPLATE,
        personas=PERSONAS,
        seed=seed,
    )

    print(f"Generated {len(tasks)} tasks.")

    if verify:
        atom_issues = verify_fault_atoms(
            FIXABLE_CONFIG, get_environment, get_db, sample_size=2
        )
        if atom_issues:
            raise ValueError(
                f"Atom verification failed: {len(atom_issues)} issue(s)."
            )

        policy_text = Path(TRAVEL_AGENCY_POLICY_PATH).read_text()
        report = verify_tasks(tasks, get_environment, policy_text=policy_text)
        errors = {}
        warnings_count = 0
        for task_id, issues in report.items():
            errs = [i for i in issues if i.startswith("ERROR:")]
            warns = [i for i in issues if i.startswith("WARNING:")]
            warnings_count += len(warns)
            if errs:
                errors[task_id] = errs
        print(f"Verification: {len(errors)} tasks with errors, {warnings_count} warnings.")
        if errors:
            for task_id, errs in list(errors.items())[:10]:
                print(f"\n  Task {task_id}:")
                for e in errs:
                    print(f"    {e}")
            raise ValueError(
                f"Verification failed: {len(errors)} task(s) have errors."
            )

    if save:
        task_dicts = [t.model_dump() for t in tasks]
        dump_file(TRAVEL_AGENCY_TASK_SET_PATH, task_dicts)
        print(f"Saved {len(tasks)} tasks to {TRAVEL_AGENCY_TASK_SET_PATH}")

    return tasks
