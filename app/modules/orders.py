import sqlite3
import json
from datetime import datetime
from typing import List, Dict, Any, Optional

def create_order(user_id: str, cart: List[Dict], address: str, delivery_option: str, customer_name: str, phone: str, status: str = "pending_payment") -> str:
    """
    Create a new order in the database.
    - status: can be 'pending_payment', 'ready_for_delivery', 'completed', etc.
    - Does NOT send any WhatsApp message (that's handled by the caller).
    """
    order_id = f"SBS-{int(datetime.utcnow().timestamp())}"
    total = sum(item["price"] * item["quantity"] for item in cart)
    items_json = json.dumps(cart)
    conn = sqlite3.connect("messages.db")
    c = conn.cursor()
    c.execute("""
        INSERT INTO orders (order_id, customer_phone, customer_name, items, total, address, delivery_type, status, payment_status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (order_id, phone, customer_name, items_json, total, address, delivery_option, status, "unpaid", datetime.utcnow().isoformat()))
    conn.commit()
    conn.close()
    return order_id

def update_order_status(order_id: str, new_status: str, payment_status: str = None) -> bool:
    """Update the status of an order, optionally also payment_status."""
    conn = sqlite3.connect("messages.db")
    c = conn.cursor()
    if payment_status:
        c.execute("UPDATE orders SET status = ?, payment_status = ? WHERE order_id = ?", (new_status, payment_status, order_id))
    else:
        c.execute("UPDATE orders SET status = ? WHERE order_id = ?", (new_status, order_id))
    updated = c.rowcount > 0
    conn.commit()
    conn.close()
    return updated

def get_order_by_id(order_id: str) -> Optional[Dict]:
    """Retrieve order details as a dictionary."""
    conn = sqlite3.connect("messages.db")
    c = conn.cursor()
    c.execute("SELECT * FROM orders WHERE order_id = ?", (order_id,))
    row = c.fetchone()
    conn.close()
    if row:
        # Convert to dictionary (assuming column names are accessible)
        return {col[0]: row[idx] for idx, col in enumerate(c.description)} if c.description else None
    return None

def get_orders_by_phone(phone: str) -> List[Dict]:
    """Retrieve all orders for a given phone number."""
    conn = sqlite3.connect("messages.db")
    c = conn.cursor()
    c.execute("SELECT * FROM orders WHERE customer_phone = ? ORDER BY created_at DESC", (phone,))
    rows = c.fetchall()
    conn.close()
    if rows and c.description:
        return [{col[0]: row[idx] for idx, col in enumerate(c.description)} for row in rows]
    return []

def update_order_gps(order_id: str, lat: float, lng: float, eta: str = None) -> bool:
    """Update GPS coordinates and ETA for tracking."""
    conn = sqlite3.connect("messages.db")
    c = conn.cursor()
    if eta:
        c.execute("UPDATE orders SET gps_lat = ?, gps_lng = ?, eta = ? WHERE order_id = ?", (lat, lng, eta, order_id))
    else:
        c.execute("UPDATE orders SET gps_lat = ?, gps_lng = ? WHERE order_id = ?", (lat, lng, order_id))
    updated = c.rowcount > 0
    conn.commit()
    conn.close()
    return updated