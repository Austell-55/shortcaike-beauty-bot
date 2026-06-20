# database/models.py
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List, Dict

@dataclass
class Customer:
    phone_number: str
    name: str
    first_seen: datetime
    last_seen: datetime

@dataclass
class CartItem:
    user_id: str
    product: str
    quantity: int
    price: float

@dataclass
class Order:
    order_id: str
    user_phone: str
    customer_name: str
    total: float
    delivery_fee: float
    address: str
    status: str  # pending_availability, awaiting_payment, ready_for_delivery, out_for_delivery, delivered_waiting_confirm, completed, cancelled, ready_for_pickup, picked_up
    payment_method: Optional[str]
    receipt_url: Optional[str]
    created_at: datetime
    items: str  # JSON string
    location_lat: Optional[float]
    location_lon: Optional[float]
    rider_assigned: Optional[str]

@dataclass
class ConversationMessage:
    id: int
    user_id: str
    role: str  # user or assistant
    content: str
    timestamp: datetime

@dataclass
class DeliveryFee:
    id: int
    location: str
    fee: float
    active: bool

@dataclass
class PickupStation:
    id: int
    name: str
    address: str
    contact: Optional[str]

# Helper functions to convert DB rows to dataclass instances
def dict_to_customer(row: Dict) -> Customer:
    return Customer(
        phone_number=row["phone_number"],
        name=row["name"],
        first_seen=datetime.fromisoformat(row["first_seen"]),
        last_seen=datetime.fromisoformat(row["last_seen"])
    )

def dict_to_order(row: Dict) -> Order:
    return Order(
        order_id=row["order_id"],
        user_phone=row["user_phone"],
        customer_name=row["customer_name"],
        total=row["total"],
        delivery_fee=row["delivery_fee"],
        address=row["address"],
        status=row["status"],
        payment_method=row.get("payment_method"),
        receipt_url=row.get("receipt_url"),
        created_at=datetime.fromisoformat(row["created_at"]),
        items=row["items"],
        location_lat=row.get("location_lat"),
        location_lon=row.get("location_lon"),
        rider_assigned=row.get("rider_assigned")
    )

def dict_to_message(row: Dict) -> ConversationMessage:
    return ConversationMessage(
        id=row["id"],
        user_id=row["user_id"],
        role=row["role"],
        content=row["content"],
        timestamp=datetime.fromisoformat(row["timestamp"])
    )
