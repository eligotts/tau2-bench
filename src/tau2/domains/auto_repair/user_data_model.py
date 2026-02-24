from typing import Dict, List, Optional

from tau2.environment.db import DB
from tau2.utils.pydantic_utils import BaseModelNoExtra


class VehicleSummary(BaseModelNoExtra):
    vehicle_id: str
    make: str
    model: str
    year: int


class ServiceOrderSummary(BaseModelNoExtra):
    order_id: str
    service_type: str
    scheduled_date: str
    status: str


class InvoiceSummary(BaseModelNoExtra):
    invoice_id: str
    total: float
    status: str
    description: str


class AutoRepairUserDB(DB):
    customer_id: Optional[str] = None
    customer_name: Optional[str] = None
    my_vehicles: List[VehicleSummary] = []
    my_orders: List[ServiceOrderSummary] = []
    my_invoices: List[InvoiceSummary] = []
    repair_approved: Dict[str, bool] = {}  # order_id -> bool
    payment_made: Dict[str, bool] = {}  # invoice_id -> bool
    resolution_acknowledged: Dict[str, bool] = {}  # customer_id -> bool
    warranty_renewal_confirmed: Dict[str, bool] = {}  # warranty_id -> bool
