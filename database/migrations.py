# database/migrations.py
import sqlite3
from passlib.context import CryptContext

DB_PATH = "messages.db"  # adjust if your DB is in parent folder

def run_migration():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # ---- Fix delivery_fees ----
    cursor.execute("PRAGMA table_info(delivery_fees)")
    cols = [col[1] for col in cursor.fetchall()]

    if 'type' not in cols:
        cursor.execute("ALTER TABLE delivery_fees ADD COLUMN type TEXT")
        cursor.execute("ALTER TABLE delivery_fees ADD COLUMN amount REAL")
        cursor.execute("UPDATE delivery_fees SET type = location, amount = fee")
        print("Added type/amount columns")

    # Insert missing fees
    cursor.execute("INSERT OR IGNORE INTO delivery_fees (type, amount, location, fee) VALUES (?,?,?,?)", ('home',150,'home',150))
    cursor.execute("INSERT OR IGNORE INTO delivery_fees (type, amount, location, fee) VALUES (?,?,?,?)", ('express',300,'express',300))
    cursor.execute("INSERT OR IGNORE INTO delivery_fees (type, amount, location, fee) VALUES (?,?,?,?)", ('pickup',0,'pickup',0))

    # ---- Create new tables ----
    cursor.execute('''CREATE TABLE IF NOT EXISTS dashboard_users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        role TEXT NOT NULL CHECK(role IN ('admin','sales','delivery','monitor','security','auditor','pickup_staff','company_coordinator')),
        pickup_station_id INTEGER NULL,
        company_name TEXT NULL,
        active BOOLEAN DEFAULT 1,
        password_hash TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS audit_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        user_username TEXT,
        action TEXT NOT NULL,
        details TEXT,
        ip_address TEXT,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        price REAL NOT NULL,
        stock INTEGER DEFAULT 0,
        available BOOLEAN DEFAULT 1
    )''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS conversation_flags (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_id INTEGER,
        flagged_by INTEGER,
        reason TEXT,
        resolved BOOLEAN DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    # Extend orders table
    columns_to_add = [
        ("delivery_status", "TEXT DEFAULT 'pending'"),
        ("gps_location", "TEXT"),
        ("last_gps_update", "TIMESTAMP"),
        ("delivery_started_at", "TIMESTAMP"),
        ("delivered_at", "TIMESTAMP"),
        ("delivered_by", "INTEGER"),
        ("company_name", "TEXT"),
        ("company_delivery_status", "TEXT DEFAULT 'pending'"),
        ("pickup_station_ready", "BOOLEAN DEFAULT 0")
    ]

    for col, col_type in columns_to_add:
        try:
            cursor.execute(f"ALTER TABLE orders ADD COLUMN {col} {col_type}")
            print(f"Added column {col}")
        except sqlite3.OperationalError:
            print(f"Column {col} already exists")

    # Insert sample products
    cursor.execute("INSERT OR IGNORE INTO products (name, price, stock, available) VALUES (?,?,?,?)", ('Lipstick',450,20,1))
    cursor.execute("INSERT OR IGNORE INTO products (name, price, stock, available) VALUES (?,?,?,?)", ('Foundation',600,15,1))
    cursor.execute("INSERT OR IGNORE INTO products (name, price, stock, available) VALUES (?,?,?,?)", ('Eyeliner',300,10,1))

    # Create default admin user (password: admin123)
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    hashed = pwd_context.hash("admin123")
    cursor.execute("INSERT OR IGNORE INTO dashboard_users (username, name, role, password_hash) VALUES (?,?,?,?)",
                   ('admin', 'Administrator', 'admin', hashed))

    conn.commit()
    conn.close()
    print("✅ Migration completed. Default admin user: admin / admin123")

if __name__ == "__main__":
    run_migration()