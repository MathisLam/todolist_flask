from flask import Flask, render_template, request, redirect, url_for, make_response
import sqlite3
import hashlib
import json
from functools import wraps

app = Flask(__name__)
app.secret_key = 'some-secret-key'  # Replace with your secret key

# Login decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user_id = request.cookies.get('account')
        if not user_id:
            return redirect(url_for('auth', action='login'))
        return f(*args, **kwargs)
    return decorated_function

def get_db():
    return sqlite3.connect('todo.db')

# Auth routes
@app.route('/')
@app.route('/auth', methods=['GET', 'POST'])
def auth():
    error = None
    action = request.args.get('action', 'login')
    
    if request.method == 'POST':
        action = request.form.get('action')
        username = request.form.get('username').strip()
        password = request.form.get('password').strip()
        hashed_password = hashlib.sha256(password.encode()).hexdigest()

        conn = get_db()
        conn.row_factory = sqlite3.Row
        c = conn.cursor()

        if action == 'signup':
            try:
                c.execute("INSERT INTO users (username, password, task) VALUES (?, ?, ?)", 
                         (username, hashed_password, json.dumps([])))
                conn.commit()
                return redirect(url_for('auth', action='login'))
            except sqlite3.IntegrityError:
                return render_template('auth.html', error="Username already exists.", action='signup')
            finally:
                conn.close()
        elif action == 'login':
            c.execute("SELECT id FROM users WHERE username = ? AND password = ?", 
                     (username, hashed_password))
            user = c.fetchone()
            conn.close()

            if user:
                response = make_response(redirect(url_for('home')))
                response.set_cookie('account', str(user[0]))
                return response
            else:
                return render_template('auth.html', error="Invalid username or password.", action='login')
    
    return render_template('auth.html', action=action, error=error)

@app.route('/home')
@login_required
def home():
    return render_template('home.html')

@app.route('/todo')
@login_required
def todo_list():
    user_id = request.cookies.get('account')
    conn = get_db()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT task FROM users WHERE id = ?", (user_id,))
    user_tasks = c.fetchone()
    conn.close()

    tasks = json.loads(user_tasks['task']) if user_tasks else []
    open_tasks = [task for task in tasks if task['status'] == 1]
    return render_template('make_table.html', rows=open_tasks)

@app.route('/new', methods=['GET', 'POST'])
@login_required
def new_item():
    if request.args.get('save'):
        new_task_content = request.args.get('task', '').strip()
        if not new_task_content:
            return render_template('new_task.html', error="Task content cannot be empty")
        
        user_id = request.cookies.get('account')
        conn = get_db()
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT task FROM users WHERE id = ?", (user_id,))
        user_tasks = c.fetchone()
        tasks = json.loads(user_tasks['task']) if user_tasks and user_tasks['task'] else []

        new_task = {"id": len(tasks) + 1, "content": new_task_content, "status": 1}
        tasks.append(new_task)
        c.execute("UPDATE users SET task = ? WHERE id = ?", (json.dumps(tasks), user_id))
        conn.commit()
        conn.close()
        
        return redirect(url_for('todo_list'))
    return render_template('new_task.html')

@app.route('/edit/<int:no>', methods=['GET', 'POST'])
@login_required
def edit_item(no):
    conn = get_db()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    if request.args.get('save'):
        edit_content = request.args.get('task', '').strip()
        status = request.args.get('status', '').strip()
        status = 1 if status == 'open' else 0

        user_id = request.cookies.get('account')
        c.execute("SELECT task FROM users WHERE id = ?", (user_id,))
        user_tasks = c.fetchone()
        tasks = json.loads(user_tasks['task']) if user_tasks else []

        for task in tasks:
            if task['id'] == no:
                task['content'] = edit_content
                task['status'] = status
                break

        c.execute("UPDATE users SET task = ? WHERE id = ?", (json.dumps(tasks), user_id))
        conn.commit()
        conn.close()
        return redirect(url_for('todo_list'))
    else:
        user_id = request.cookies.get('account')
        c.execute("SELECT task FROM users WHERE id = ?", (user_id,))
        user_tasks = c.fetchone()
        tasks = json.loads(user_tasks['task']) if user_tasks else []

        task_to_edit = next((task for task in tasks if task['id'] == no), None)
        conn.close()
        return render_template('edit_task.html', old=task_to_edit, no=no)

if __name__ == '__main__':
    app.run(debug=True)