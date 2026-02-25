from typing import List, Optional

from tau2.environment.db import DB
from tau2.utils.pydantic_utils import BaseModelNoExtra


class Customer(BaseModelNoExtra):
    customer_id: str
    name: str
    email: str
    phone: str
    account_status: str  # active, locked, restricted
    membership_tier: str  # standard, silver, gold, platinum
    membership_expiry: str  # YYYY-MM-DD


class Order(BaseModelNoExtra):
    order_id: str
    customer_id: str
    product_name: str
    quantity: int
    unit_price: float
    shipping_cost: float
    tax_amount: float
    promo_code: Optional[str] = None
    promo_discount_pct: float = 0.0
    total: float
    status: str  # pending, processing, shipped, delivered, cancelled
    order_date: str
    shipping_method: str  # standard, express, overnight
    shipping_address: str
    tracking_number: str  # empty string if not assigned
    payment_method_id: str
    payment_reprocessed: bool = False


class ReturnRequest(BaseModelNoExtra):
    return_id: str
    order_id: str
    customer_id: str
    product_name: str
    quantity: int
    unit_price: float
    reason: str
    status: str  # pending, approved, denied, completed
    refund_amount: float
    refund_method: str  # original_payment, store_credit


class PaymentMethod(BaseModelNoExtra):
    payment_id: str
    customer_id: str
    card_type: str  # visa, mastercard, amex
    last_four: str
    is_default: bool
    status: str  # active, expired, suspended


class OnlineShoppingDB(DB):
    customers: List[Customer]
    orders: List[Order]
    return_requests: List[ReturnRequest]
    payment_methods: List[PaymentMethod]
