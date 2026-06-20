import sqlite3
from typing import List, Dict, Optional

def get_delivery_fee_by_location(address: str) -> float:
    """
    Calculate delivery fee based on location keywords.
    Reads from delivery_fees table; if no match, returns default fee.
    """
    address_lower = address.lower()
    conn = sqlite3.connect("messages.db")
    c = conn.cursor()
    # Fetch all active delivery fees
    c.execute("SELECT location, fee FROM delivery_fees WHERE active = 1")
    rows = c.fetchall()
    conn.close()
    for location, fee in rows:
        if location.lower() in address_lower:
            return fee
    # Default fee if no match
    return 1000  # default delivery fee

def get_all_pickup_stations() -> List[Dict]:
    """Return list of all active pickup stations."""
    conn = sqlite3.connect("messages.db")
    c = conn.cursor()
    c.execute("SELECT id, name, address FROM pickup_stations WHERE active = 1")
    rows = c.fetchall()
    conn.close()
    stations = []
    for row in rows:
        stations.append({"id": row[0], "name": row[1], "address": row[2]})
    return stations

def get_pickup_station_by_name(name: str) -> Optional[Dict]:
    """Find a pickup station by name (case-insensitive)."""
    stations = get_all_pickup_stations()
    for station in stations:
        if station["name"].lower() == name.lower():
            return station
    return None

def add_delivery_fee(location: str, fee: float) -> bool:
    """Add a new delivery fee (used by admin dashboard)."""
    try:
        conn = sqlite3.connect("messages.db")
        c = conn.cursor()
        c.execute("INSERT INTO delivery_fees (location, fee, active) VALUES (?, ?, 1)", (location, fee))
        conn.commit()
        conn.close()
        return True
    except Exception:
        return False

def update_delivery_fee(fee_id: int, new_fee: float) -> bool:
    """Update an existing delivery fee."""
    try:
        conn = sqlite3.connect("messages.db")
        c = conn.cursor()
        c.execute("UPDATE delivery_fees SET fee = ? WHERE id = ?", (new_fee, fee_id))
        conn.commit()
        conn.close()
        return True
    except Exception:
        return False

def delete_delivery_fee(fee_id: int) -> bool:
    """Soft delete a delivery fee (set active = 0)."""
    try:
        conn = sqlite3.connect("messages.db")
        c = conn.cursor()
        c.execute("UPDATE delivery_fees SET active = 0 WHERE id = ?", (fee_id,))
        conn.commit()
        conn.close()
        return True
    except Exception:
        return False