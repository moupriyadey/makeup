from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import os
import json

app = Flask(__name__)
app.secret_key = 'your_secret_key'

# Home route
@app.route('/')
def home():
    return render_template('index.html')

# Booking form submission route
@app.route('/submit', methods=['POST'])
def submit_form():
    # Getting data from the form
    name = request.form.get('name')
    email = request.form.get('email')
    service = request.form.get('service')
    date = request.form.get('date')
    time = request.form.get('time')

    # Debugging output
    print("Form Data Received:", name, email, service, date, time)

    # Validating data
    if not all([name, email, service, date, time]):
        return "Missing form fields", 400  # Return a helpful error message

    # Creating a new booking entry
    new_booking = {
        "name": name,
        "email": email,
        "service": service,
        "date": date,
        "time": time
    }

    # Saving the booking to a JSON file
    try:
        with open('bookings.json', 'r+') as f:
            data = json.load(f)
            data.append(new_booking)
            f.seek(0)
            json.dump(data, f, indent=2)
    except FileNotFoundError:
        with open('bookings.json', 'w') as f:
            json.dump([new_booking], f, indent=2)

    # Redirecting to thank you page with the name passed as context
    return render_template('thank_you.html', name=name)

# Admin login route
@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        # Check credentials
        if username == 'admin' and password == 'admin123':
            session['admin_logged_in'] = True
            return redirect(url_for('admin_panel'))
        else:
            flash('Invalid username or password')

    return render_template('admin_login.html')

# Admin panel route
@app.route('/admin/panel')
def admin_panel():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))

    # Fetching booking data from JSON file
    try:
        with open('bookings.json', 'r') as f:
            bookings = json.load(f)
    except FileNotFoundError:
        bookings = []

    return render_template('admin_panel.html', bookings=bookings)

# Admin logout route
@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    return redirect(url_for('home'))

# Temporary data for demo purposes (optional, for getting booked slots)
sample_bookings = [
    {"date": "2025-04-15", "time": "10:00"},
    {"date": "2025-04-15", "time": "14:00"},
    {"date": "2025-04-16", "time": "18:00"},
]

# Get booked slots based on date
@app.route('/get_booked_slots', methods=['GET'])
def get_booked_slots():
    selected_date = request.args.get('date')
    booked_times = [b["time"] for b in sample_bookings if b["date"] == selected_date]
    return jsonify(booked_times)

if __name__ == '__main__':
    app.run(debug=True)
