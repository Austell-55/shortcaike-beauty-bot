import json
import sqlite3
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

# In-memory session store
_sessions: Dict[str, Dict[str, Any]] = {}

def get_session(user_id: str) -> Dict[str, Any]:
    """Retrieve or create a session for the user, with timeout protection."""
    now = datetime.utcnow()
    if user_id not in _sessions:
        # Create fresh session
        _sessions[user_id] = {
            "step": "idle",
            "customer_name": None,
            "cart_prompt_sent": False,
            "last_suggested_product": None,
            "delivery_option": None,
            "address": None,
            "pending_order_id": None,
            "payment_method": None,
            "temp_address": None,
            "temp_delivery_fee": 0,
            "temp_total": 0,
            "last_active": now,
            "cart": [],  # this is the actual cart list (in-memory only)
            "order_completed": False
        }
    else:
        # Check timeout: reset only if inactive >30 minutes AND no active cart AND no pending order
        last_active = _sessions[user_id].get("last_active", now)
        has_cart = bool(_sessions[user_id].get("cart"))
        has_pending_order = bool(_sessions[user_id].get("pending_order_id"))
        if now - last_active > timedelta(minutes=30) and not has_cart and not has_pending_order:
            # Reset session to idle
            _sessions[user_id] = {
                "step": "idle",
                "customer_name": _sessions[user_id].get("customer_name"),  # keep name? optional
                "cart_prompt_sent": False,
                "last_suggested_product": None,
                "delivery_option": None,
                "address": None,
                "pending_order_id": None,
                "payment_method": None,
                "temp_address": None,
                "temp_delivery_fee": 0,
                "temp_total": 0,
                "last_active": now,
                "cart": [],
                "order_completed": False
            }
        else:
            # Update last active time
            _sessions[user_id]["last_active"] = now
    return _sessions[user_id]

def update_session(user_id: str, **kwargs) -> None:
    """Update specific fields in the user's session."""
    session = get_session(user_id)
    for key, value in kwargs.items():
        session[key] = value
    # Ensure last_active is updated on any write
    session["last_active"] = datetime.utcnow()
    _sessions[user_id] = session

def clear_session(user_id: str) -> None:
    """Reset the session to initial state (lose cart, temp data, but keep name)."""
    if user_id in _sessions:
        name = _sessions[user_id].get("customer_name")
        _sessions[user_id] = {
            "step": "idle",
            "customer_name": name,
            "cart_prompt_sent": False,
            "last_suggested_product": None,
            "delivery_option": None,
            "address": None,
            "pending_order_id": None,
            "payment_method": None,
            "temp_address": None,
            "temp_delivery_fee": 0,
            "temp_total": 0,
            "last_active": datetime.utcnow(),
            "cart": [],
            "order_completed": False
        }
    else:
        get_session(user_id)  # creates fresh

def session_exists(user_id: str) -> bool:
    return user_id in _sessions

def get_all_sessions() -> Dict[str, Dict[str, Any]]:
    """Return all active sessions (for admin/debugging)."""
    return _sessions.copy()