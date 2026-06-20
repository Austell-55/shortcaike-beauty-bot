import bcrypt
import sqlite3
from typing import Optional, Dict, List
from datetime import datetime
from database.db import get_db_connection

# ==================== Password Hashing ====================
def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def verify_password(password: str, hashed: str) -> bool:
    """Verify a password against its hash."""
    return bcrypt.checkpw(password.encode(), hashed.encode())

# ==================== User Management ====================
def create_user(username: str, full_name: str, role: str, password: str) -> int:
    """
    Create a new dashboard user.
    Returns user ID.
    Raises ValueError if username already exists.
    """
    conn = get_db_connection()
    c = conn.cursor()
    hashed = hash_password(password)
    try:
        c.execute("""
            INSERT INTO dashboard_users (username, full_name, role, password_hash, created_at, active)
            VALUES (?, ?, ?, ?, ?, 1)
        """, (username, full_name, role, hashed, datetime.utcnow().isoformat()))
        conn.commit()
        user_id = c.lastrowid
        return user_id
    except sqlite3.IntegrityError:
        raise ValueError(f"User with username '{username}' already exists")
    finally:
        conn.close()

def get_user_by_username(username: str) -> Optional[Dict]:
    """Fetch user by username."""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM dashboard_users WHERE username = ?", (username,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None

def get_user_by_id(user_id: int) -> Optional[Dict]:
    """Fetch user by ID."""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM dashboard_users WHERE id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None

def get_all_users(active_only: bool = False) -> List[Dict]:
    """Fetch all dashboard users. If active_only=True, only active users."""
    conn = get_db_connection()
    c = conn.cursor()
    if active_only:
        c.execute("SELECT id, username, full_name, role, active, created_at FROM dashboard_users WHERE active = 1")
    else:
        c.execute("SELECT id, username, full_name, role, active, created_at FROM dashboard_users")
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def deactivate_user(user_id: int) -> bool:
    """Deactivate a user (they cannot log in)."""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("UPDATE dashboard_users SET active = 0 WHERE id = ?", (user_id,))
    conn.commit()
    affected = c.rowcount
    conn.close()
    return affected > 0

def activate_user(user_id: int) -> bool:
    """Reactivate a user."""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("UPDATE dashboard_users SET active = 1 WHERE id = ?", (user_id,))
    conn.commit()
    affected = c.rowcount
    conn.close()
    return affected > 0

def delete_user(user_id: int) -> bool:
    """Permanently delete a user. Returns True if deleted."""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("DELETE FROM dashboard_users WHERE id = ?", (user_id,))
    conn.commit()
    affected = c.rowcount
    conn.close()
    return affected > 0

def authenticate_user(username: str, password: str) -> Optional[Dict]:
    """Verify credentials for dashboard login."""
    user = get_user_by_username(username)
    if user and user["active"] and verify_password(password, user["password_hash"]):
        return user
    return None