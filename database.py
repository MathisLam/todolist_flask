#Code to create the data base
#import
import sqlite3
import json

# Connect to the database (or create it if it doesn't exist)
conn = sqlite3.connect('todo.db')  # Warning: This file is created in the current directory

# Enable fetching rows as dictionaries
conn.row_factory = sqlite3.Row

# Create a cursor object
c = conn.cursor()

# Create the users table with a task column as a JSON dictionary
c.execute("""
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    task TEXT  -- This will store JSON data
)
""")

# Insert sample data into the users table
sample_tasks = {"id": 1, "content": "Read A-byte-of-python to get a good introduction into Python", "status": 0},
#    {"id": 2, "content": "Visit the Python website", "status": 1},
#   {"id": 3, "content": "Test various editors for and check the syntax highlighting", "status": 1},
#  {"id": 4, "content": "Choose your favorite WSGI-Framework", "status": 0}




#c.execute("INSERT INTO users (username, password, task) VALUES (?, ?, ?)", 
 #         ('sample_user', 'sample_password', json.dumps(sample_tasks)))

import sqlite3
import json

def insert_task(username, task):
    # Connect to the database
    conn = sqlite3.connect('todo.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    # Retrieve the current tasks for the user
    c.execute("SELECT task FROM users WHERE username = ?", (username,))
    user_tasks = c.fetchone()
    tasks = json.loads(user_tasks['task']) if user_tasks and user_tasks['task'] else []

    # Append the new task
    tasks.append(task)

    # Update the user's tasks in the database
    c.execute("UPDATE users SET task = ? WHERE username = ?", (json.dumps(tasks), username))

    # Commit the changes and close the connection
    conn.commit()
    conn.close()

def delete_task(username, task_id):
    # Connect to the database
    conn = sqlite3.connect('todo.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    # Retrieve the current tasks for the user
    c.execute("SELECT task FROM users WHERE username = ?", (username,))
    user_tasks = c.fetchone()
    tasks = json.loads(user_tasks['task']) if user_tasks and user_tasks['task'] else []

    # Remove the task with the given id
    tasks = [task for task in tasks if task['id'] != task_id]

    # Update the user's tasks in the database
    c.execute("UPDATE users SET task = ? WHERE username = ?", (json.dumps(tasks), username))

    # Commit the changes and close the connection
    conn.commit()
    conn.close()



 
# Commit the changes and close the connection
conn.commit()
conn.close()