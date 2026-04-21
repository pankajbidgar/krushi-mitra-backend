import sqlite3

conn = sqlite3.connect("farmers.db")
cursor = conn.cursor()
try:
    cursor.execute("ALTER TABLE yield_predictions ADD COLUMN season TEXT")
    conn.commit()
    print("✅ Column 'season' added successfully.")
except sqlite3.OperationalError as e:
    print(f"Error: {e}")
conn.close()