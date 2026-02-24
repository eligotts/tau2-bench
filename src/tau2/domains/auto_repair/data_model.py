from typing import List, Optional

from tau2.environment.db import DB
from tau2.utils.pydantic_utils import BaseModelNoExtra


class Customer(BaseModelNoExtra):
    customer_id: str
    name: str
    phone: str
    email: str
    account_status: str  # active, suspended, flagged


class Vehicle(BaseModelNoExtra):
    vehicle_id: str
    customer_id: str
    make: str
    model: str
    year: int
    vin: str
    mileage: int
    registration_status: str  # current, expired
    # Diagnostic fields — only visible through run_diagnostic(), not get_vehicles()
    brake_pad_thickness: float  # mm, healthy >= 3.0
    brake_fluid_level: str  # normal, low
    oil_life_pct: int  # percent, healthy >= 20
    air_filter_status: str  # clean, clogged
    tire_pressure_psi: int  # psi, healthy >= 30
    wheel_alignment: str  # aligned, misaligned
    battery_voltage: float  # volts, healthy >= 12.4
    alternator_output: str  # normal, faulty


class ServiceOrder(BaseModelNoExtra):
    order_id: str
    vehicle_id: str
    customer_id: str
    service_type: str  # routine_maintenance, brake_service, tire_service, etc.
    scheduled_date: str
    technician: str
    status: str  # open, in_progress, completed, cancelled
    notes: str


class Invoice(BaseModelNoExtra):
    invoice_id: str
    order_id: str
    customer_id: str
    labor_hours: float
    labor_rate: float
    parts_cost: float
    discount_pct: float
    total: float
    status: str  # pending, paid, credited
    description: str


class WarrantyPlan(BaseModelNoExtra):
    warranty_id: str
    vehicle_id: str
    customer_id: str
    coverage_type: str  # basic, extended, premium
    status: str  # active, expired
    expiry_date: str


class AutoRepairDB(DB):
    customers: List[Customer]
    vehicles: List[Vehicle]
    service_orders: List[ServiceOrder]
    invoices: List[Invoice]
    warranty_plans: List[WarrantyPlan]
