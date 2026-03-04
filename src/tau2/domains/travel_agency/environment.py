import random
from pathlib import Path
from typing import Optional

from tau2.data_model.tasks import Task
from tau2.domains.travel_agency.data_model import TravelAgencyDB
from tau2.domains.travel_agency.tools import TravelAgencyTools
from tau2.domains.travel_agency.user_data_model import (
    FlightSummary,
    HotelSummary,
    RentalSummary,
    TravelAgencyUserDB,
    TripSummary,
)
from tau2.domains.travel_agency.user_tools import TravelAgencyUserTools
from tau2.domains.travel_agency.utils import (
    TRAVEL_AGENCY_DB_PATH,
    TRAVEL_AGENCY_POLICY_PATH,
    TRAVEL_AGENCY_TASK_SET_PATH,
    TRAVEL_AGENCY_USER_DB_PATH,
)
from tau2.environment.environment import Environment
from tau2.utils import load_file


class TravelAgencyEnvironment(Environment):
    tools: TravelAgencyTools
    user_tools: TravelAgencyUserTools

    def __init__(
        self,
        domain_name: str,
        policy: str,
        tools: TravelAgencyTools,
        user_tools: TravelAgencyUserTools,
    ):
        super().__init__(domain_name, policy, tools, user_tools)

    def sync_tools(self):
        """Synchronize agent-side DB state into user-visible summaries.

        Projects:
        1. Trip summaries
        2. Flight booking summaries
        3. Hotel reservation summaries
        4. Car rental summaries
        """
        if self.user_tools.db.client_id is None:
            return

        client_id = self.user_tools.db.client_id

        # 1. Sync trip summaries
        self.user_tools.db.my_trips = [
            TripSummary(
                trip_id=t.trip_id,
                destination=t.destination,
                start_date=t.start_date,
                end_date=t.end_date,
                status=t.status,
            )
            for t in self.tools.db.trips
            if t.client_id == client_id
        ]

        # 2. Sync flight summaries
        self.user_tools.db.my_flights = [
            FlightSummary(
                booking_id=f.booking_id,
                airline=f.airline,
                departure_city=f.departure_city,
                arrival_city=f.arrival_city,
                departure_date=f.departure_date,
                seat_class=f.seat_class,
                passenger_name=f.passenger_name,
                price=f.price,
            )
            for f in self.tools.db.flight_bookings
            if f.client_id == client_id
        ]

        # 3. Sync hotel summaries
        self.user_tools.db.my_hotels = [
            HotelSummary(
                reservation_id=h.reservation_id,
                hotel_name=h.hotel_name,
                check_in_date=h.check_in_date,
                check_out_date=h.check_out_date,
                room_type=h.room_type,
                total_price=h.total_price,
            )
            for h in self.tools.db.hotel_reservations
            if h.client_id == client_id
        ]

        # 4. Sync car rental summaries
        self.user_tools.db.my_rentals = [
            RentalSummary(
                rental_id=r.rental_id,
                company=r.company,
                pickup_date=r.pickup_date,
                return_date=r.return_date,
                car_type=r.car_type,
                total_price=r.total_price,
            )
            for r in self.tools.db.car_rentals
            if r.client_id == client_id
        ]


def get_environment(
    db: Optional[TravelAgencyDB] = None,
    user_db: Optional[TravelAgencyUserDB] = None,
    solo_mode: bool = False,
) -> TravelAgencyEnvironment:
    """Factory function to create the travel agency environment."""
    if db is None:
        db = TravelAgencyDB.load(TRAVEL_AGENCY_DB_PATH)
    tools = TravelAgencyTools(db)
    if user_db is None:
        user_db = TravelAgencyUserDB.load(TRAVEL_AGENCY_USER_DB_PATH)
    user_tools = TravelAgencyUserTools(user_db)
    policy = load_file(TRAVEL_AGENCY_POLICY_PATH)
    env = TravelAgencyEnvironment(
        domain_name="travel_agency",
        policy=policy,
        tools=tools,
        user_tools=user_tools,
    )
    if solo_mode:
        env.set_solo_mode(True)
    return env


def load_tasks(path: str) -> list[Task]:
    """Load tasks from a JSON file."""
    tasks = load_file(path)
    if isinstance(tasks, dict) and "tasks" in tasks:
        tasks = tasks["tasks"]
    return [Task.model_validate(task) for task in tasks]


def get_tasks(task_split_name: Optional[str] = "base") -> list[Task]:
    """Get tasks for the domain, shuffled for representative sampling."""
    if not TRAVEL_AGENCY_TASK_SET_PATH.exists():
        return []
    tasks = load_tasks(TRAVEL_AGENCY_TASK_SET_PATH)
    if task_split_name is None:
        pass
    else:
        task_splits = get_tasks_split()
        if task_splits is not None and task_split_name in task_splits:
            tasks = [task for task in tasks if task.id in task_splits[task_split_name]]
    rng = random.Random(42)
    rng.shuffle(tasks)
    return tasks


def get_tasks_split() -> Optional[dict[str, list[str]]]:
    """Load task splits from JSON if they exist."""
    split_file = (
        Path(TRAVEL_AGENCY_TASK_SET_PATH).parent
        / f"split_{Path(TRAVEL_AGENCY_TASK_SET_PATH).stem}.json"
    )
    if split_file.exists():
        return load_file(split_file)
    return None
