import sqlite3
from typing import Optional

DB_PATH = "messages.db"

def get_db_connection() -> sqlite3.Connection:
    """Return a database connection with row_factory set to sqlite3.Row."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_database():
    """Create all necessary tables for the bot (customers, cart, orders, messages, delivery_fees, pickup_stations)."""
    conn = get_db_connection()
    c = conn.cursor()

    # Customers table (permanent name storage)
    c.execute('''CREATE TABLE IF NOT EXISTS customers (
        phone_number TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        first_seen TIMESTAMP,
        last_seen TIMESTAMP
    )''')

    # Cart table (persistent cart)
    c.execute('''CREATE TABLE IF NOT EXISTS cart (
        user_id TEXT,
        product TEXT,
        quantity INTEGER,
        price REAL,
        PRIMARY KEY (user_id, product)
    )''')

    # Orders table
    c.execute('''CREATE TABLE IF NOT EXISTS orders (
        order_id TEXT PRIMARY KEY,
        user_phone TEXT,
        customer_name TEXT,
        total REAL,
        delivery_fee REAL,
        address TEXT,
        status TEXT,
        payment_method TEXT,
        receipt_url TEXT,
        created_at TIMESTAMP,
        items TEXT,
        location_lat REAL,
        location_lon REAL,
        rider_assigned TEXT
    )''')

    # Messages table (conversation history)
    c.execute('''CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT,
        role TEXT,
        content TEXT,
        timestamp TIMESTAMP
    )''')

    # Delivery fees table
    c.execute('''CREATE TABLE IF NOT EXISTS delivery_fees (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        location TEXT,
        fee REAL,
        active BOOLEAN DEFAULT 1
    )''')

    # Pickup stations table
    c.execute('''CREATE TABLE IF NOT EXISTS pickup_stations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        address TEXT NOT NULL,
        contact TEXT
    )''')

    # Indexes for performance
    c.execute("CREATE INDEX IF NOT EXISTS idx_customers_phone ON customers(phone_number)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_orders_user_phone ON orders(user_phone)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_messages_user_id ON messages(user_id)")

    conn.commit()

    # Insert default delivery fees if empty
    c.execute("SELECT COUNT(*) FROM delivery_fees")
    if c.fetchone()[0] == 0:
        default_fees = [
            ("Ikeja", 1000),
            ("Lekki", 2000),
            ("Surulere", 1500),
            ("Victoria Island", 2500),
            ("Yaba", 1200),
            ("Gbagada", 1300),
            ("Apapa", 1800),
        ]
        c.executemany("INSERT INTO delivery_fees (location, fee, active) VALUES (?, ?, 1)", default_fees)
        conn.commit()

    # Insert default pickup stations if empty
    c.execute("SELECT COUNT(*) FROM pickup_stations")
    if c.fetchone()[0] == 0:
        default_stations = [
            ("Ikeja Station", "15 Bishop Street, Ikeja, Lagos", "08012345678"),
            ("Surulere Station", "22 Adeniran Ogunsanya, Surulere, Lagos", "08023456789"),
            ("Lekki Station", "5 Admiralty Way, Lekki Phase 1, Lagos", "08034567890"),
            ("VI Station", "10 Ahmadu Bello Way, Victoria Island, Lagos", "08045678901"),
        ]
        c.executemany("INSERT INTO pickup_stations (name, address, contact) VALUES (?, ?, ?)", default_stations)
        conn.commit()

    conn.close()