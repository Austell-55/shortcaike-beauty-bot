import sqlite3
import hashlib

conn = sqlite3.connect('messages.db')
cursor = conn.cursor()

# Drop existing table (safe – no important data yet)
cursor.execute("DROP TABLE IF EXISTS dashboard_users")

# Recreate with correct schema
cursor.execute('''
CREATE TABLE dashboard_users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('admin','sales','delivery','monitor','security','auditor','pickup_staff','company_coordinator')),
    pickup_station_id INTEGER NULL,
    company_name TEXT NULL,
    active BOOLEAN DEFAULT 1,
    password_hash TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
''')

# Simple password hash (for demo only – use bcrypt in production)
password = "admin123"
hash_obj = hashlib.sha256(password.encode())
hashed = hash_obj.hexdigest()

# Insert admin user
cursor.execute('''
INSERT OR IGNORE INTO dashboard_users (username, name, role, password_hash)
VALUES (?, ?, ?, ?)
''', ('admin', 'Administrator', 'admin', hashed))

conn.commit()
conn.close()
print("✅ Fixed dashboard_users table. Admin user: admin / admin123")
