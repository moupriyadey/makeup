import os
import json
import uuid
import qrcode
from flask import Flask, render_template, request, redirect, url_for
from flask_mail import Mail, Message
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Configure Flask-Mail
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 465
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = app.config['MAIL_USERNAME']
app.config['MAIL_USE_TLS'] = False
app.config['MAIL_USE_SSL'] = True

mail = Mail(app)

# Constants
BOOKINGS_FILE = 'bookings_cleaned.json'
QR_FOLDER = os.path.join('static', 'qr_codes')

# Ensure directories exist
os.makedirs(QR_FOLDER, exist_ok=True)
if not os.path.exists(BOOKINGS_FILE):
    with open(BOOKINGS_FILE, 'w') as f:
        json.dump([], f)

# Load bookings
def load_bookings():
    with open(BOOKINGS_FILE, 'r') as f:
        return json.load(f)

# Save bookings
def save_bookings(bookings):
    with open(BOOKINGS_FILE, 'w') as f:
        json.dump(bookings, f, indent=4)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/book', methods=['GET', 'POST'])
def book():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        service = request.form['service']
        date = request.form['date']
        time = request.form['time']
        appointment_id = str(uuid.uuid4())

        new_booking = {
            'id': appointment_id,
            'name': name,
            'email': email,
            'service': service,
            'date': date,
            'time': time,
            'status': 'Pending'
        }

        bookings = load_bookings()
        bookings.append(new_booking)
        save_bookings(bookings)

        # Send confirmation email
        msg = Message(
            subject="Appointment Confirmation - Mou's Nail & Makeup",
            recipients=[email]
        )
        msg.body = f"""Dear {name},

Your appointment for {service} on {date} at {time} has been received.
Appointment ID: {appointment_id}

We'll contact you if there are any changes.

Best,
Mou's Nail & Makeup
"""
        try:
            mail.send(msg)
        except Exception as e:
            print(f"❌ Error sending email: {e}")

        return redirect(url_for('thank_you', appointment_id=appointment_id))

    return render_template('book.html')

@app.route('/thank_you')
def thank_you():
    appointment_id = request.args.get('appointment_id')

    # Customizable UPI ID and Amount (can also be loaded from environment variables or a form)
    upi_id = "smarasada@okaxis"  # Change this to your own UPI ID
    amount = 1  # Specify the amount here
    payee_name = "Mou's Makeup and Nail"  # Payee name

    qr_filename = f"{appointment_id}.png"
    qr_path = os.path.join(QR_FOLDER, qr_filename)

    # Generate QR if not already created
    if not os.path.exists(qr_path):
        upi_url = f"upi://pay?pa={upi_id}&pn={payee_name}&am={amount}&cu=INR&tn=Payment for Makeup booking ID {appointment_id}"
        qr = qrcode.make(upi_url)
        qr.save(qr_path)

    return render_template('thank_you.html', appointment_id=appointment_id, qr_image_url=f"/static/qr_codes/{qr_filename}")

@app.route('/payment_done/<appointment_id>', methods=['POST'])
def payment_done(appointment_id):
    return redirect(url_for('index'))

@app.route('/testimonials')
def testimonials():
    return render_template('testimonials.html')

@app.route('/testimonials2')
def testimonials2():
    return render_template('testimonials2.html')

@app.route('/gallery')
def gallery():
    return render_template('gallery.html')


@app.route('/admin')
def admin():
    return render_template('login.html')

@app.route('/admin/dashboard')
def admin_dashboard():
    bookings = load_bookings()
    return render_template('admin_dashboard.html', bookings=bookings)

@app.route('/admin/confirm_booking', methods=['POST'])
def confirm_booking():
    appointment_id = request.form.get('appointment_id')
    bookings = load_bookings()
    confirmed_booking = None

    for booking in bookings:
        if booking['id'] == appointment_id:
            booking['status'] = 'Confirmed'
            confirmed_booking = booking
            break

    save_bookings(bookings)

    if confirmed_booking:
        msg = Message(
            subject="Your Appointment is Confirmed",
            recipients=[confirmed_booking['email']]
        )
        msg.body = f"""Dear {confirmed_booking['name']},

Your appointment has been confirmed.

Best regards,
Mou's Nail & Makeup
"""
        try:
            mail.send(msg)
        except Exception as e:
            return f"❌ Error sending confirmation email: {str(e)}"

    return redirect(url_for('admin_dashboard'))

@app.route('/login', methods=['POST'])
def login():
    username = request.form['username']
    password = request.form['password']

    if username == 'admin' and password == 'password':
        return redirect(url_for('admin_dashboard'))

    return 'Login Failed', 403

if __name__ == '__main__':
    app.run(debug=True)
