from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_mail import Mail, Message
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from datetime import datetime
import json
import os

# Flask app setup
app = Flask(__name__)
app.secret_key = os.urandom(24)

# Flask-Mail setup
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 465
app.config['MAIL_USERNAME'] = 'your-email@gmail.com'  # Replace with your email
app.config['MAIL_PASSWORD'] = 'your-email-password'  # Replace with your email password
app.config['MAIL_USE_TLS'] = False
app.config['MAIL_USE_SSL'] = True
mail = Mail(app)

# Flask-Login setup
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

# User Class for Flask-Login
class User(UserMixin):
    def __init__(self, id):
        self.id = id

# Dummy user (to be replaced with actual admin user in production)
users = {'admin': {'password': 'admin123'}}  # Replace with your actual user credentials

@login_manager.user_loader
def load_user(user_id):
    return User(user_id)

# Booking data storage
BOOKINGS_FILE = 'bookings_cleaned.json'

def load_bookings():
    if os.path.exists(BOOKINGS_FILE):
        with open(BOOKINGS_FILE, 'r') as f:
            return json.load(f)
    return []

def save_bookings(bookings):
    with open(BOOKINGS_FILE, 'w') as f:
        json.dump(bookings, f, indent=4)

# Routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/book', methods=['GET', 'POST'])
def book():
    if request.method == 'POST':
        name = request.form['name']
        phone = request.form['phone']
        service = request.form['service']
        date = request.form['date']
        time = request.form['time']

        # Validate input data
        if not name or not phone or not service or not date or not time:
            flash("All fields are required!", 'danger')
            return redirect(url_for('book'))

        # Save booking data
        bookings = load_bookings()
        booking = {
            'name': name,
            'phone': phone,
            'service': service,
            'date': date,
            'time': time,
            'status': 'Pending'
        }
        bookings.append(booking)
        save_bookings(bookings)

        # Send email confirmation
        msg = Message('Booking Confirmation', recipients=[phone + '@example.com'])
        msg.body = f"Dear {name},\n\nYour booking for {service} on {date} at {time} is confirmed. Thank you!"
        mail.send(msg)

        flash("Your booking has been successfully submitted!", 'success')
        return redirect(url_for('index'))

    return render_template('book.html')

@app.route('/admin')
@login_required
def admin():
    bookings = load_bookings()
    return render_template('admin.html', bookings=bookings)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        if username in users and users[username]['password'] == password:
            user = User(username)
            login_user(user)
            return redirect(url_for('admin'))
        else:
            flash("Invalid login credentials.", 'danger')

    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", 'info')
    return redirect(url_for('index'))

@app.route('/delete_booking/<int:booking_id>', methods=['GET'])
@login_required
def delete_booking(booking_id):
    bookings = load_bookings()
    if 0 <= booking_id < len(bookings):
        del bookings[booking_id]
        save_bookings(bookings)
        flash("Booking deleted successfully.", 'success')
    else:
        flash("Invalid booking ID.", 'danger')
    return redirect(url_for('admin'))

# Error Handling
@app.errorhandler(404)
def page_not_found(error):
    return render_template('404.html'), 404

if __name__ == '__main__':
    app.run(debug=True)
