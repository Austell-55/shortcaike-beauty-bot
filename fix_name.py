import sqlite3
conn = sqlite3.connect('messages.db')
cursor = conn.cursor()
cursor.execute("DELETE FROM customers WHERE name = 'yes pls two'")
conn.commit()
print(f"Deleted {cursor.rowcount} record(s)")
conn.close()
