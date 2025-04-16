import os
from flask import Flask, render_template, request, redirect, url_for, jsonify
from flask_mail import Mail, Message
from dotenv import load_dotenv
import json
import uuid

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)

# Configure Flask-Mail
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 465
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')  # Load email from .env
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')  # Load password from .env
app.config['MAIL_USE_TLS'] = False
app.config['MAIL_USE_SSL'] = True

# Initialize Flask-Mail
mail = Mail(app)

# Load bookings from JSON file (updated bookings_cleaned.json)
def load_bookings():
    with open('bookings_cleaned.json', 'r') as f:
        return json.load(f)

# Save bookings to JSON file
def save_bookings(bookings):
    with open('bookings_cleaned.json', 'w') as f:
        json.dump(bookings, f, indent=4)

# Route for Home Page (index)
@app.route('/')
def index():
    return render_template('index.html')

# Route for booking appointments
@app.route('/book', methods=['GET', 'POST'])
def book():
    if request.method == 'POST':
        # Get form data
        name = request.form['name']
        email = request.form['email']
        service = request.form['service']
        date = request.form['date']
        time = request.form['time']

        # Generate unique appointment ID
        appointment_id = str(uuid.uuid4())

        # Create a booking entry
        new_booking = {
            'id': appointment_id,
            'name': name,
            'email': email,
            'service': service,
            'date': date,
            'time': time,
            'status': 'Pending'
        }

        # Load existing bookings and add new booking
        bookings = load_bookings()
        bookings.append(new_booking)

        # Save updated bookings
        save_bookings(bookings)

        # Send confirmation email
        msg = Message(
            subject="Appointment Confirmation - Mou's Nail & Makeup",
            sender=app.config['MAIL_USERNAME'],  # Sender from config
            recipients=[email]  # Recipient from form
        )

        msg.body = f"""
        Dear {name},

        Your appointment for {service} on {date} at {time} has been confirmed.
        Your appointment ID is: {appointment_id}

        Best regards,
        Mou's Nail & Makeup
        """

        try:
            mail.send(msg)
            return redirect(url_for('thank_you', appointment_id=appointment_id))
        except Exception as e:
            return f"Error sending email: {str(e)}"

    return render_template('book.html')

# Route for Thank You page
@app.route('/thank_you')
def thank_you():
    appointment_id = request.args.get('appointment_id')
    return render_template('thank_you.html', appointment_id=appointment_id)

# Route for Viewing Testimonials (Page 1)
@app.route('/testimonials')
def testimonials():
    return render_template('testimonials.html')

# Route for Viewing Testimonials (Page 2)
@app.route('/testimonials2')
def testimonials2():
    return render_template('testimonials2.html')

# Route for Admin Login
@app.route('/admin')
def admin():
    return render_template('login.html')

# Admin Dashboard Route
@app.route('/admin/dashboard')
def admin_dashboard():
    # Load the bookings from the cleaned JSON file
    bookings = load_bookings()

    # Display all bookings on the admin dashboard
    return render_template('admin_dashboard.html', bookings=bookings)

# Route for confirming a booking in admin panel
@app.route('/admin/confirm_booking', methods=['POST'])
def confirm_booking():
    appointment_id = request.form.get('appointment_id')

    # Load current bookings
    bookings = load_bookings()

    # Find the booking by ID and update status
    for booking in bookings:
        if booking['id'] == appointment_id:
            booking['status'] = 'Confirmed'
            break

    # Save the updated bookings
    save_bookings(bookings)

    # Send confirmation email to client
    client_email = booking['email']
    client_name = booking['name']

    msg = Message(
        subject="Your Appointment is Confirmed",
        sender=app.config['MAIL_USERNAME'],
        recipients=[client_email]
    )
    msg.body = f"""
    Dear {client_name},

    Your appointment has been successfully confirmed.

    Best regards,
    Mou's Nail & Makeup
    """
    
    try:
        mail.send(msg)
        return redirect(url_for('admin_dashboard'))
    except Exception as e:
        return f"Error sending confirmation email: {str(e)}"

# Route for handling login (simplified for this example)
@app.route('/login', methods=['POST'])
def login():
    username = request.form['username']
    password = request.form['password']
    
    # Example check (this should be enhanced with proper authentication)
    if username == 'admin' and password == 'password':
        return redirect(url_for('admin_dashboard'))
    
    return 'Login Failed', 403

# Run the Flask app
if __name__ == '__main__':
    app.run(debug=True)
