# Save as insert_users.py and run
import sqlite3
from passlib.context import CryptContext
pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")
users = [
    ('admin', 'Administrator', 'admin', 'admin123'),
    ('sales1', 'Sales Person', 'sales', 'sales123'),
    ('delivery1', 'Delivery Rider', 'delivery', 'delivery123'),
    ('monitor1', 'Customer Care Monitor', 'monitor', 'monitor123'),
    ('security1', 'Security Officer', 'security', 'security123'),
    ('auditor1', 'Auditor', 'auditor', 'auditor123'),
    ('pickup1', 'Pickup Station Staff', 'pickup_staff', 'pickup123'),
    ('company1', 'Company Coordinator', 'company_coordinator', 'company123')
]
conn = sqlite3.connect('messages.db')
cur = conn.cursor()
for u, full, role, pw in users:
    hashed = pwd.hash(pw)
    cur.execute("INSERT OR IGNORE INTO dashboard_users (username, full_name, role, password_hash) VALUES (?,?,?,?)",
                (u, full, role, hashed))
conn.commit()
conn.close()
print("8 users inserted.")