import sqlite3

conn = sqlite3.connect('messages.db')
c = conn.cursor()

c.execute("PRAGMA table_info(orders)")
existing = [col[1] for col in c.fetchall()]

columns = [
    ("concern", "TEXT"),
    ("tracking_status", "TEXT DEFAULT 'processing'"),
    ("gps_lat", "REAL"),
    ("gps_lng", "REAL"),
    ("eta", "TEXT")
]

for col_name, col_type in columns:
    if col_name not in existing:
        try:
            c.execute(f"ALTER TABLE orders ADD COLUMN {col_name} {col_type}")
            print(f"Added column: {col_name}")
        except sqlite3.OperationalError as e:
            print(f"Error adding {col_name}: {e}")
    else:
        print(f"Column already exists: {col_name}")

conn.commit()
conn.close()
print("✅ Done.")
