import sqlite3
import hashlib
import json
from datetime import datetime

# Connect to the database (or create it if it doesn't exist)
conn = sqlite3.connect('todo.db')
c = conn.cursor()

print("Setting up database...")

# --- Drop existing tables for a clean setup ---
c.execute("DROP TABLE IF EXISTS tasks")
c.execute("DROP TABLE IF EXISTS users")
print("Dropped old tables.")

# --- User Table ---
# Stores user accounts and their preferences (e.g., dark mode)
c.execute("""
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    preferences TEXT
)
""")
print("Created 'users' table.")

# --- Tasks Table ---
# Stores individual tasks, linked to a user by user_id
c.execute("""
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL,
    content TEXT NOT NULL,
    category TEXT,
    created_date DATETIME NOT NULL,
    due_date DATETIME,
    status TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users (id)
)
""")
print("Created 'tasks' table.")


# --- Sample User (for testing) ---
try:
    # Add a sample user 'test' with password 'test'
    default_prefs = json.dumps({"dark_mode": False})
    hashed_password = hashlib.sha256("test".encode()).hexdigest()
    c.execute("INSERT INTO users (username, password, preferences) VALUES (?, ?, ?)",
              ("test", hashed_password, default_prefs))
    
    # Get the new user's ID
    user_id = c.lastrowid
    
    # --- Sample Tasks ---
    now = datetime.now()
    
    c.execute("INSERT INTO tasks (user_id, content, category, created_date, due_date, status) VALUES (?, ?, ?, ?, ?, ?)",
              (user_id, "Complete project report", "Work", now, datetime(2025, 12, 1, 17, 0), "upcoming"))
    
    c.execute("INSERT INTO tasks (user_id, content, category, created_date, due_date, status) VALUES (?, ?, ?, ?, ?, ?)",
              (user_id, "Review PR #123", "Work", now, datetime(2025, 11, 20, 12, 0), "in_process"))
              
    c.execute("INSERT INTO tasks (user_id, content, category, created_date, status) VALUES (?, ?, ?, ?, ?)",
              (user_id, "Buy groceries", "Personal", now, "completed"))

    print("Sample user 'test' (password 'test') and tasks created.")

except sqlite3.IntegrityError:
    print("Sample user 'test' already exists.")
except Exception as e:
    print(f"An error occurred: {e}")


# Commit the changes and close the connection
conn.commit()
conn.close()
print("Database setup complete and connection closed.")

