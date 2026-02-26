from typing import Dict, List, Optional

from tau2.environment.db import DB
from tau2.utils.pydantic_utils import BaseModelNoExtra


class OrderSummary(BaseModelNoExtra):
    order_id: str
    product_name: str
    total: float
    status: str
    shipping_method: str


class ReturnSummary(BaseModelNoExtra):
    return_id: str
    product_name: str
    status: str
    refund_amount: float


class OnlineShoppingUserDB(DB):
    customer_id: Optional[str] = None
    customer_name: Optional[str] = None
    my_orders: List[OrderSummary] = []
    my_returns: List[ReturnSummary] = []
    resolution_acknowledged: Dict[str, bool] = {}
    pricing_update_confirmed: Dict[str, bool] = {}
    shipping_update_confirmed: Dict[str, bool] = {}
    tracking_update_confirmed: Dict[str, bool] = {}
    return_resolution_confirmed: Dict[str, bool] = {}
    payment_info_updated: Dict[str, bool] = {}
    payment_update_confirmed: Dict[str, bool] = {}
    membership_renewal_confirmed: Dict[str, bool] = {}
    billing_correction_confirmed: Dict[str, bool] = {}
