from flask import Flask, render_template,request,redirect,url_for,flash,session
import sqlite3, hashlib  



app = Flask(__name__)
app.secret_key ='24' #Change this to a random secret key
db_locale = 'users.db'
 
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/signup',methods=['GET','POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        password = hashlib.sha256(request.form['password'].encode()).hexdigest()
        connection = sqlite3.connect(db_locale)
        cursor = connection.cursor()
        try:
            cursor.execute("INSERT INTO users(username, password) VALUES(?, ?)", (username, password))
            connection.commit()
            # Debug: print all users after signup
            cursor.execute("SELECT username FROM users")
            users = cursor.fetchall()
            print('Current users in database:', users)
            flash('Signup successful! Please log in')
            return redirect(url_for('login'))  # Redirect to login page after signup
        except sqlite3.IntegrityError:
            flash('Username already exists.')
            return redirect (url_for('signup'))
        finally:
            connection.close()
    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = hashlib.sha256(request.form['password'].encode()).hexdigest()
        connection = sqlite3.connect(db_locale)
        cursor = connection.cursor()
        cursor.execute("SELECT * FROM users WHERE username=? AND password=?", (username, password))
        user = cursor.fetchone()
        connection.close()

        if user:
            session['username'] = username
            flash('Login successful!')
            return redirect(url_for('dashboard'))  # Redirect to dashboard after login

        else:
            flash('Invalid username or password.')
            return redirect(url_for('login'))
    return render_template('login.html')  # Make sure there's a return for GET method as well


@app.route('/dashboard')

def dashboard():

    if 'username' in session:

        return render_template('dashboard.html', username=session['username'])

    else:

        flash('Please log in first.')

        return redirect(url_for('login'))


@app.route('/logout')

def logout():

    session.pop('username', None)

    flash('Logged out.')

    return redirect(url_for('index'))

@app.route('/book', methods=['GET', 'POST'])
def book():
    if 'username' not in session:
        flash('Please log in to book a session.')
        return redirect(url_for('login'))

    connection = sqlite3.connect(db_locale)
    cursor = connection.cursor()

    # Ensure bookings table exists and has optional session_id
    cursor.execute('''CREATE TABLE IF NOT EXISTS bookings (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        username TEXT,
                        date TEXT,
                        time TEXT
                    )''')
    # attempt to add session_id column if missing
    try:
        cursor.execute("ALTER TABLE bookings ADD COLUMN session_id INTEGER")
        connection.commit()
    except sqlite3.OperationalError:
        # column probably already exists
        pass

    # also ensure sessions table exists
    cursor.execute('''CREATE TABLE IF NOT EXISTS sessions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        title TEXT,
                        date TEXT,
                        time TEXT,
                        capacity INTEGER DEFAULT 0,
                        created_by TEXT
                    )''')
    connection.commit()

    if request.method == 'POST':
        name = session['username']
        # if a session_id was selected use its date/time
        session_id = request.form.get('session_id')
        if session_id:
            cursor.execute("SELECT date, time FROM sessions WHERE id = ?", (session_id,))
            s = cursor.fetchone()
            if s:
                date = s[0]
                time = s[1]
            else:
                flash('Selected session not found.', 'error')
                connection.close()
                return redirect(url_for('book'))

            # --- capacity check: count existing bookings for this session ---
            cursor.execute("SELECT capacity FROM sessions WHERE id = ?", (session_id,))
            cap_row = cursor.fetchone()
            capacity = int(cap_row[0]) if cap_row and cap_row[0] is not None else 0
            if capacity > 0:
                cursor.execute("SELECT COUNT(*) FROM bookings WHERE session_id = ?", (session_id,))
                booked_count = cursor.fetchone()[0]
                if booked_count >= capacity:
                    flash('Selected session is full. Please choose another session.', 'error')
                    connection.close()
                    return redirect(url_for('book'))
        else:
            date = request.form.get('date')
            time = request.form.get('time')

        cursor.execute("INSERT INTO bookings (username, date, time, session_id) VALUES (?, ?, ?, ?)",
                       (name, date, time, session_id))
        connection.commit()
        flash('Your session has been booked successfully!', 'success')
        # after insert, fall through to GET logic to show updated list

    # GET (or after POST): load bookings for current user
    cursor.execute("SELECT id, date, time FROM bookings WHERE username=? ORDER BY date, time", (session['username'],))
    user_bookings = cursor.fetchall()

    # load upcoming sessions created by organisers (only future or today)
    try:
        cursor.execute("SELECT id, title, date, time, capacity FROM sessions WHERE date >= date('now') ORDER BY date, time")
    except sqlite3.OperationalError:
        cursor.execute("SELECT id, title, date, time, capacity FROM sessions ORDER BY date, time")
    sessions_list = cursor.fetchall()

    connection.close()

    return render_template('book.html', username=session['username'], bookings=user_bookings, sessions=sessions_list)

@app.route('/contact')
def contact():
    return render_template('contact.html')

@app.route('/info')
def info():
    return render_template('info.html')

@app.route('/cancel_booking/<int:booking_id>', methods=['POST'])
def cancel_booking(booking_id):
    if 'username' not in session:
        flash('Please log in to manage bookings.')
        return redirect(url_for('login'))

    connection = sqlite3.connect(db_locale)
    cursor = connection.cursor()
    # Only delete if the booking belongs to the current user
    cursor.execute("DELETE FROM bookings WHERE id = ? AND username = ?", (booking_id, session['username']))
    connection.commit()
    deleted = cursor.rowcount
    connection.close()

    if deleted:
        flash('Booking cancelled.', 'success')
    else:
        flash('Booking not found or you are not authorised to cancel it.', 'error')

    return redirect(url_for('book'))

@app.route('/organiser', methods=['GET', 'POST'])
def organiser():
    # only allow logged-in users to create sessions — simple check
    if 'username' not in session:
        flash('Please log in to manage sessions.')
        return redirect(url_for('login'))

    connection = sqlite3.connect(db_locale)
    cursor = connection.cursor()

    # Create sessions table if it doesn't exist
    cursor.execute('''CREATE TABLE IF NOT EXISTS sessions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        title TEXT,
                        date TEXT,
                        time TEXT,
                        capacity INTEGER DEFAULT 0,
                        created_by TEXT
                    )''')
    connection.commit()

    if request.method == 'POST':
        title = request.form.get('title')
        date = request.form.get('date')
        time = request.form.get('time')
        capacity = request.form.get('capacity') or 0
        created_by = session.get('username')

        cursor.execute("INSERT INTO sessions (title, date, time, capacity, created_by) VALUES (?, ?, ?, ?, ?)",
                       (title, date, time, capacity, created_by))
        connection.commit()
        flash('Session created.', 'success')
        # fall through to show organiser page with updated list

    # list sessions for organiser user (or all)
    cursor.execute("SELECT id, title, date, time, capacity FROM sessions ORDER BY date, time")
    sessions_list = cursor.fetchall()
    connection.close()

    return render_template('organiser.html', sessions=sessions_list)


@app.route('/sessions')
def sessions_api():
    # returns sessions for a given date as JSON
    date = request.args.get('date')
    connection = sqlite3.connect(db_locale)
    cursor = connection.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS sessions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        title TEXT,
                        date TEXT,
                        time TEXT,
                        capacity INTEGER DEFAULT 0,
                        created_by TEXT
                    )''')
    connection.commit()

    if date:
        cursor.execute("SELECT id, title, date, time, capacity FROM sessions WHERE date = ? ORDER BY time", (date,))
    else:
        cursor.execute("SELECT id, title, date, time, capacity FROM sessions ORDER BY date, time")
    rows = cursor.fetchall()
    connection.close()

    # convert to list of dicts
    out = []
    for r in rows:
        out.append({'id': r[0], 'title': r[1], 'date': r[2], 'time': r[3], 'capacity': r[4]})
    from flask import jsonify
    return jsonify(out)

if __name__ == '__main__':
    app.run(debug=True)









