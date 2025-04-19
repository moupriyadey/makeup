import os
import json
import uuid
import qrcode
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_mail import Mail, Message
from dotenv import load_dotenv
from flask_login import LoginManager, UserMixin, login_required, login_user, logout_user, current_user

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = 'your_super_secret_key_here'

# Flask-Mail configuration
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 465
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = app.config['MAIL_USERNAME']
app.config['MAIL_USE_TLS'] = False
app.config['MAIL_USE_SSL'] = True

mail = Mail(app)

BOOKINGS_FILE = 'bookings_cleaned.json'
QR_FOLDER = os.path.join('static', 'qr_codes')
os.makedirs(QR_FOLDER, exist_ok=True)

if not os.path.exists(BOOKINGS_FILE):
    with open(BOOKINGS_FILE, 'w') as f:
        json.dump([], f)

# Initialize the LoginManager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

# User class for login
class User(UserMixin):
    def __init__(self, id):
        self.id = id

@login_manager.user_loader
def load_user(user_id):
    return User(user_id)

def load_bookings():
    with open(BOOKINGS_FILE, 'r') as f:
        return json.load(f)

def save_bookings(bookings):
    with open(BOOKINGS_FILE, 'w') as f:
        json.dump(bookings, f, indent=4)

@app.context_processor
def inject_enumerate():
    return dict(enumerate=enumerate)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/book', methods=['GET', 'POST'])
def book():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        mobile = request.form['mobile']
        service = request.form['service']
        date = request.form['date']
        time = request.form['time']
        appointment_id = str(uuid.uuid4())

        new_booking = {
            'id': appointment_id,
            'name': name,
            'email': email,
            'mobile': mobile,
            'service': service,
            'date': date,
            'time': time,
            'status': 'Pending'
        }

        bookings = load_bookings()
        bookings.append(new_booking)
        save_bookings(bookings)

        msg = Message(
            subject="Appointment Confirmation - Mou's Makeup & Nails",
            recipients=[email]
        )
        msg.body = f"""Dear {name},

Your appointment for {service} on {date} at {time} has been received.
Appointment ID: {appointment_id}

We'll contact you if there are any changes.

Best,
Mou's Makeup & Nails
"""
        try:
            mail.send(msg)
        except Exception as e:
            print(f"❌ Error sending email: {e}")

        return redirect(url_for('thank_you', appointment_id=appointment_id))

    return render_template('book.html')

@app.route('/testimonials')
def testimonials():
    testimonials_data = [
        {"name": "Riya Dey", "testimonial": "Amazing service! My makeup was flawless."},
        {"name": "Shraboni RoyChoudhary", "testimonial": "Highly recommend! Very professional and skilled."},
        {"name": "Lolita Halder", "testimonial": "I loved the whole experience. Best makeup artist ever!"}
    ]
    return render_template('testimonials.html', testimonials=testimonials_data)

@app.route('/testimonials2')
def testimonials2():
    testimonials_data2 = [
        {"name": "Reena Mallik", "testimonial": "The makeup service exceeded my expectations!"},
        {"name": "Chandana Paul", "testimonial": "Professional, efficient, and so talented!"}
    ]
    return render_template('testimonials2.html', testimonials=testimonials_data2)

@app.route('/gallery')
def gallery():
    gallery_images = ["image1.jpg", "image2.jpg", "image3.jpg"]
    return render_template('gallery.html', images=gallery_images)

@app.route('/thank_you')
def thank_you():
    appointment_id = request.args.get('appointment_id')
    upi_id = "smarasada@okaxis"
    amount = 1
    payee_name = "Mou's Makeup and Nails"
    qr_filename = f"{appointment_id}.png"
    qr_path = os.path.join(QR_FOLDER, qr_filename)

    if not os.path.exists(qr_path):
        upi_url = f"upi://pay?pa={upi_id}&pn={payee_name}&am={amount}&cu=INR&tn=Payment for Makeup booking ID {appointment_id}"
        qr = qrcode.make(upi_url)
        qr.save(qr_path)

    return render_template('thank_you.html', appointment_id=appointment_id, qr_image_url=f"/static/qr_codes/{qr_filename}")

@app.route('/payment_done/<appointment_id>', methods=['POST'])
def payment_done(appointment_id):
    return redirect(url_for('index'))

@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    status_filter = request.args.get('status')
    date_filter = request.args.get('date')

    with open('bookings_cleaned.json') as f:
        bookings = json.load(f)

    if status_filter:
        bookings = [b for b in bookings if b['status'] == status_filter]
    if date_filter:
        bookings = [b for b in bookings if b['date'] == date_filter]

    search_filter = request.args.get('search')
    if search_filter:
        bookings = [b for b in bookings if search_filter.lower() in b['name'].lower()]

    return render_template('admin_dashboard.html', bookings=bookings)

@app.route('/admin/confirm_booking', methods=['POST'])
@login_required
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
Mou's Makeup & Nails
"""
        try:
            mail.send(msg)
        except Exception as e:
            return f"❌ Error sending confirmation email: {str(e)}"

    flash('Booking Confirmed.', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/delete_booking', methods=['POST'])
@login_required
def delete_booking():
    appointment_id = request.form.get('appointment_id')
    bookings = load_bookings()
    bookings = [b for b in bookings if b['id'] != appointment_id]
    save_bookings(bookings)

    flash('Booking deleted successfully.', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        if username == os.getenv('ADMIN_USERNAME') and password == os.getenv('ADMIN_PASSWORD'):
            user = User(username)
            login_user(user)
            session['role'] = 'admin'
            flash('Login successful!', 'success')
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Invalid credentials. Please try again.', 'danger')
            return redirect(url_for('login'))

    return render_template('admin_login.html')

@app.route('/admin/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'success')
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)
