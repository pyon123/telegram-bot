import sqlite3

# Connect to the SQLite database (or create it if it doesn't exist)
conn = sqlite3.connect('leakix_results.db')

# Create a cursor object using the cursor() method
cursor = conn.cursor()

# Create the results_table
cursor.execute('''
CREATE TABLE IF NOT EXISTS results_table (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    resource_id TEXT,
    events_summary TEXT,
    ip TEXT,
    event_source TEXT,
    host TEXT,
    fingerprints TEXT UNIQUE
);
''')

# Create the search_terms table
cursor.execute('''
CREATE TABLE IF NOT EXISTS search_terms (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    term TEXT UNIQUE,
    active INTEGER DEFAULT 1
);
''')

# Commit the changes
conn.commit()

# Close the connection
conn.close()

print("Database setup complete.")
