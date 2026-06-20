# cart.py
from typing import List, Dict, Optional
from database.db import get_db_connection
from products import get_product_price

def get_user_cart(user_id: str) -> List[Dict]:
    """Fetch all items in a user's cart."""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT product, quantity, price FROM cart WHERE user_id = ?", (user_id,))
    rows = c.fetchall()
    conn.close()
    return [{"product": row["product"], "quantity": row["quantity"], "price": row["price"]} for row in rows]

def add_to_cart(user_id: str, product_name: str, quantity: int = 1) -> bool:
    """Add a product to the cart (upsert). Returns True if successful, False if product not found."""
    price = get_product_price(product_name)
    if price == 0:
        return False
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT quantity FROM cart WHERE user_id = ? AND product = ?", (user_id, product_name))
    existing = c.fetchone()
    if existing:
        new_qty = existing["quantity"] + quantity
        c.execute("UPDATE cart SET quantity = ? WHERE user_id = ? AND product = ?", (new_qty, user_id, product_name))
    else:
        c.execute("INSERT INTO cart (user_id, product, quantity, price) VALUES (?, ?, ?, ?)",
                  (user_id, product_name, quantity, price))
    conn.commit()
    conn.close()
    return True

def add_to_cart_batch(user_id: str, items: List[Dict]) -> List[str]:
    """
    Add multiple items to cart at once.
    items = [{"product": "face cream", "quantity": 2}, ...]
    Returns list of errors (empty if all succeeded).
    """
    errors = []
    for item in items:
        product = item.get("product")
        qty = item.get("quantity", 1)
        if not product:
            errors.append("Missing product name")
            continue
        if not add_to_cart(user_id, product, qty):
            errors.append(f"Product '{product}' not found")
    return errors

def remove_from_cart(user_id: str, product_name: str, quantity: Optional[int] = None) -> bool:
    """Remove a product or reduce quantity. If quantity is None, remove entirely."""
    conn = get_db_connection()
    c = conn.cursor()
    if quantity is None:
        c.execute("DELETE FROM cart WHERE user_id = ? AND product = ?", (user_id, product_name))
    else:
        c.execute("SELECT quantity FROM cart WHERE user_id = ? AND product = ?", (user_id, product_name))
        row = c.fetchone()
        if row:
            new_qty = row["quantity"] - quantity
            if new_qty <= 0:
                c.execute("DELETE FROM cart WHERE user_id = ? AND product = ?", (user_id, product_name))
            else:
                c.execute("UPDATE cart SET quantity = ? WHERE user_id = ? AND product = ?",
                          (new_qty, user_id, product_name))
    conn.commit()
    affected = c.rowcount
    conn.close()
    return affected > 0

def clear_cart(user_id: str) -> bool:
    """Remove all items from user's cart."""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("DELETE FROM cart WHERE user_id = ?", (user_id,))
    conn.commit()
    affected = c.rowcount
    conn.close()
    return affected > 0

def get_cart_total(user_id: str) -> float:
    """Calculate total price of items in cart (price × quantity)."""
    cart = get_user_cart(user_id)
    return sum(item["price"] * item["quantity"] for item in cart)