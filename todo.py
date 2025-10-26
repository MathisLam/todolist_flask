from flask import Flask, render_template, request, redirect, url_for, make_response, flash, g
import sqlite3
import hashlib
import json
from datetime import datetime
from functools import wraps

app = Flask(__name__)
# Make sure to set a real secret key in production
app.secret_key = 'your_very_secret_key_here_12345'
DATABASE = 'todo.db'

# --- Database Helper Functions ---

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def parse_datetime(dt_str):
    """Safely parse datetime strings from DB."""
    if not dt_str:
        return None
    try:
        # Try parsing with microseconds first
        return datetime.fromisoformat(dt_str)
    except ValueError:
        try:
            # Fallback for formats without microseconds
            return datetime.strptime(dt_str, '%Y-%m-%d %H:%M:%S')
        except ValueError:
            return None # Or handle as error

# --- Auth & User Functions ---

def get_user_id():
    """Gets the user ID from the cookie."""
    return request.cookies.get('user_id')

def get_user_prefs():
    """Gets the user's preferences (like dark mode) from the DB."""
    user_id = get_user_id()
    if not user_id:
        return {"dark_mode": False}
        
    try:
        db = get_db()
        c = db.cursor()
        c.execute("SELECT preferences FROM users WHERE id = ?", (user_id,))
        prefs_row = c.fetchone()
        if prefs_row and prefs_row['preferences']:
            return json.loads(prefs_row['preferences'])
        return {"dark_mode": False}
    except Exception as e:
        print(f"Error getting user prefs: {e}")
        return {"dark_mode": False}


# Login decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user_id = get_user_id()
        if not user_id:
            flash("You must be logged in to view this page.", "error")
            return redirect(url_for('auth', action='login'))
        g.user_id = user_id
        g.user_prefs = get_user_prefs() # Load prefs for templates
        return f(*args, **kwargs)
    return decorated_function

@app.route('/auth', methods=['GET', 'POST'])
def auth():
    action = request.args.get('action', 'login')
    
    if request.method == 'POST':
        action = request.form.get('action')
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        
        if not username or not password:
            flash("Username and password are required.", "error")
            return render_template('auth.html', action=action, user_prefs=get_user_prefs())

        hashed_password = hashlib.sha256(password.encode()).hexdigest()
        db = get_db()
        c = db.cursor()

        if action == 'signup':
            try:
                # Default preferences
                default_prefs = json.dumps({"dark_mode": False})
                c.execute("INSERT INTO users (username, password, preferences) VALUES (?, ?, ?)", 
                         (username, hashed_password, default_prefs))
                db.commit()
                flash("Signup successful! Please log in.", "success")
                return redirect(url_for('auth', action='login'))
            except sqlite3.IntegrityError:
                flash("Username already exists.", "error")
                return render_template('auth.html', action='signup', user_prefs=get_user_prefs())
            
        elif action == 'login':
            c.execute("SELECT id FROM users WHERE username = ? AND password = ?", 
                     (username, hashed_password))
            user = c.fetchone()
            if user:
                response = make_response(redirect(url_for('home')))
                # Set cookie to expire in 30 days
                response.set_cookie('user_id', str(user['id']), max_age=60*60*24*30)
                flash("Logged in successfully.", "success")
                return response
            else:
                flash("Invalid username or password.", "error")
                return render_template('auth.html', action='login', user_prefs=get_user_prefs())
    
    # Pass user_prefs even for GET request
    return render_template('auth.html', action=action, user_prefs=get_user_prefs())

@app.route('/logout')
def logout():
    response = make_response(redirect(url_for('auth', action='login')))
    response.set_cookie('user_id', '', expires=0) # Delete the cookie
    flash("You have been logged out.", "success")
    return response

# --- Core App Routes ---

@app.route('/')
@login_required
def index():
    # Redirect to home, this is just a landing page.
    return redirect(url_for('home'))

@app.route('/home')
@login_required
def home():
    db = get_db()
    c = db.cursor()
    
    # Use the more efficient single query
    c.execute("SELECT * FROM tasks WHERE user_id = ? ORDER BY created_date DESC", (g.user_id,))
    all_tasks = c.fetchall()
    
    upcoming_tasks = []
    in_process_tasks = []
    completed_tasks = []
    
    for task_row in all_tasks:
        # Convert row to a mutable dictionary
        task = dict(task_row)
        
        # Convert date/time strings back into Python datetime objects
        task['created_date'] = parse_datetime(task['created_date'])
        task['due_date'] = parse_datetime(task['due_date'])
        
        if task['status'] == 'upcoming':
            upcoming_tasks.append(task)
        elif task['status'] == 'in_process':
            in_process_tasks.append(task)
        elif task['status'] == 'completed':
            completed_tasks.append(task)
            
    # Sort lists
    upcoming_tasks.sort(key=lambda x: x['due_date'] if x['due_date'] else datetime.max)
    in_process_tasks.sort(key=lambda x: x['due_date'] if x['due_date'] else datetime.max)
    
    return render_template('home.html', 
                           upcoming=upcoming_tasks, 
                           in_process=in_process_tasks, 
                           completed=completed_tasks,
                           user_prefs=g.user_prefs)

@app.route('/new_task', methods=['GET', 'POST'])
@login_required
def new_task():
    if request.method == 'POST':
        content = request.form.get('content', '').strip()
        category = request.form.get('category', '').strip()
        due_date_str = request.form.get('due_date', '').strip()
        
        if not content:
            flash("Task content cannot be empty.", "error")
            return render_template('new_task.html', user_prefs=g.user_prefs)
            
        due_date = None
        if due_date_str:
            try:
                # Format matches 'datetime-local' input
                due_date = datetime.strptime(due_date_str, '%Y-%m-%dT%H:%M')
            except ValueError:
                flash("Invalid date format. Please use the date picker.", "error")
                return render_template('new_task.html', user_prefs=g.user_prefs)
        
        db = get_db()
        c = db.cursor()
        c.execute("""
            INSERT INTO tasks (user_id, content, category, created_date, due_date, status) 
            VALUES (?, ?, ?, ?, ?, ?)
        """, (g.user_id, content, category, datetime.now(), due_date, 'upcoming'))
        db.commit()
        
        flash("New task created.", "success")
        return redirect(url_for('home'))
        
    return render_template('new_task.html', user_prefs=g.user_prefs)

@app.route('/edit_task/<int:task_id>', methods=['GET', 'POST'])
@login_required
def edit_task(task_id):
    db = get_db()
    c = db.cursor()
    
    # Check if task exists and belongs to the user
    c.execute("SELECT * FROM tasks WHERE id = ? AND user_id = ?", (task_id, g.user_id))
    task = c.fetchone()
    if not task:
        flash("Task not found or you don't have permission.", "error")
        return redirect(url_for('home'))

    if request.method == 'POST':
        content = request.form.get('content', '').strip()
        category = request.form.get('category', '').strip()
        status = request.form.get('status', '').strip()
        due_date_str = request.form.get('due_date', '').strip()
        
        due_date = None # Default to None
        
        # Safely handle date conversion
        if due_date_str:
            try:
                due_date = datetime.strptime(due_date_str, '%Y-%m-%dT%H:%M')
            except ValueError:
                flash("Invalid date format. Please use the date picker.", "error")
                return render_template('edit_task.html', task=task, user_prefs=g.user_prefs)
        
        if not content:
            flash("Content cannot be empty.", "error")
            return render_template('edit_task.html', task=task, user_prefs=g.user_prefs)
        
        if status not in ['upcoming', 'in_process', 'completed']:
            flash("Invalid status.", "error")
            return render_template('edit_task.html', task=task, user_prefs=g.user_prefs)
            
        c.execute("""
            UPDATE tasks SET content = ?, category = ?, due_date = ?, status = ?
            WHERE id = ? AND user_id = ?
        """, (content, category, due_date, status, task_id, g.user_id))
        db.commit()
        
        flash("Task updated.", "success")
        return redirect(url_for('home'))

    return render_template('edit_task.html', task=task, user_prefs=g.user_prefs)

@app.route('/delete_task/<int:task_id>', methods=['POST'])
@login_required
def delete_task(task_id):
    db = get_db()
    c = db.cursor()
    # Delete tasks properly
    c.execute("DELETE FROM tasks WHERE id = ? AND user_id = ?", (task_id, g.user_id))
    db.commit()
    
    if c.rowcount > 0:
        flash("Task deleted.", "success")
    else:
        flash("Task not found or you don't have permission.", "error")
        
    return redirect(url_for('home'))

@app.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    if request.method == 'POST':
        action = request.form.get('action')
        db = get_db()
        c = db.cursor()
        
        if action == 'toggle_dark_mode':
            new_prefs = g.user_prefs
            new_prefs['dark_mode'] = not new_prefs.get('dark_mode', False)
            c.execute("UPDATE users SET preferences = ? WHERE id = ?", 
                      (json.dumps(new_prefs), g.user_id))
            db.commit()
            flash("Settings updated.", "success")
            # Update prefs in g for the current request
            g.user_prefs = new_prefs
            
        elif action == 'delete_account':
            # Delete user's tasks first
            c.execute("DELETE FROM tasks WHERE user_id = ?", (g.user_id,))
            # Then delete user
            c.execute("DELETE FROM users WHERE id = ?", (g.user_id,))
            db.commit()
            
            flash("Account deleted. We're sad to see you go.", "success")
            # Log the user out
            response = make_response(redirect(url_for('auth', action='login')))
            response.set_cookie('user_id', '', expires=0)
            return response
            
    return render_template('settings.html', user_prefs=g.user_prefs)

# --- BUG: "Search Bar Not Reaching Database" (Incorrectly) ---
# This is one of the bugs you liked.
@app.route('/search', methods=['GET'])
@login_required
def search():
    query = request.args.get('query', '').strip().lower()
    
    if not query:
        return redirect(url_for('home'))
        
    db = get_db()
    c = db.cursor()
    
    c.execute("SELECT * FROM tasks WHERE user_id = ? AND lower(content) = ?", 
              (g.user_id, query))
    
    results = c.fetchall()
    
    # We must still parse dates for the template
    tasks = []
    for task_row in results:
        task = dict(task_row)
        task['created_date'] = parse_datetime(task['created_date'])
        task['due_date'] = parse_datetime(task['due_date'])
        tasks.append(task)
    
    flash(f"Found {len(tasks)} results for '{query}'", "success")
    return render_template('search_results.html', tasks=tasks, query=query, user_prefs=g.user_prefs)


if __name__ == '__main__':
    # You should run the 'database.py' script once first
    # to set up the database.
    print("Running database.py to ensure schema is up to date...")
    import database # This will execute the database.py script
    print("Starting Flask app...")
    app.run(debug=True)

