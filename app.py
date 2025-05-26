import os
import json
import uuid
import qrcode
import random # Import the random module
from flask import Flask, render_template, request, redirect, url_for, session, flash, make_response
from flask_mail import Mail, Message
from dotenv import load_dotenv
from flask_login import LoginManager, UserMixin, login_required, login_user, logout_user, current_user
from datetime import datetime

# Load environment variables
load_dotenv()

# Initialize the Flask app
app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'your_super_secret_key_here')

# Flask-Mail configuration
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 465
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = app.config['MAIL_USERNAME']
app.config['MAIL_USE_TLS'] = False
app.config['MAIL_USE_SSL'] = True

mail = Mail(app)

# File paths and QR folder setup
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

# Load and save bookings
def load_bookings():
    with open(BOOKINGS_FILE, 'r') as f:
        return json.load(f)

def save_bookings(bookings):
    with open(BOOKINGS_FILE, 'w') as f:
        json.dump(bookings, f, indent=4)

# Function to generate unique numerical ID
def generate_unique_numerical_id():
    bookings = load_bookings()
    existing_ids = {booking['id'] for booking in bookings}
    while True:
        # Generate a random 6-8 digit number
        new_id = str(random.randint(100000, 99999999))
        if new_id not in existing_ids:
            return new_id

# Context processor to add enumerate to templates
@app.context_processor
def inject_enumerate():
    return dict(enumerate=enumerate)

# New context processor to make datetime available globally in templates
@app.context_processor
def inject_datetime():
    return {'datetime': datetime}

# Home route
@app.route('/')
def index():
    return render_template('index.html')

# Booking route
@app.route('/book', methods=['GET', 'POST'])
def book():
    if request.method == 'POST':
        # Handle form submission
        name = request.form['name']
        email = request.form['email']
        mobile = request.form['mobile']
        service = request.form['service']
        date_str = request.form['date']
        time = request.form['time']

        # Generate a numerical appointment ID
        appointment_id = generate_unique_numerical_id() # Use the new function

        # TRY both date formats
        try:
            formatted_date = datetime.strptime(date_str, "%Y-%m-%d").strftime("%d/%m/%Y")
        except ValueError:
            try:
                formatted_date = datetime.strptime(date_str, "%d/%m/%Y").strftime("%d/%m/%Y")
            except ValueError:
                flash("Invalid date format. Please use DD/MM/YYYY or YYYY-MM-DD.", "danger")
                return redirect(url_for('book'))

        new_booking = {
            'id': appointment_id,
            'name': name,
            'email': email,
            'mobile': mobile,
            'service': service,
            'date': formatted_date,
            'time': time,
            'status': 'Pending',
            'payment_status': 'Unpaid' # Initialize payment status
        }

        bookings = load_bookings()
        bookings.append(new_booking)
        save_bookings(bookings)

        # Send confirmation email
        msg = Message(
            subject="Appointment Confirmation - Mou's Makeup & Nails",
            recipients=[email]
        )
        msg.body = f"""Dear {name},

Your appointment for {service} on {formatted_date} at {time} has been received.
Appointment ID: {appointment_id}

Please note: A partial payment of INR 500 is required to confirm your booking. Please scan the QR code on the payment page.

We'll contact you if there are any changes.

Best,
Mou's Makeup & Nails
"""
        try:
            mail.send(msg)
        except Exception as e:
            print(f"❌ Error sending email: {e}")
            flash(f"Error sending confirmation email. Please ensure your email is correct: {e}", "warning")


        return redirect(url_for('thank_you', appointment_id=appointment_id))

    # If GET request, pass current date to template
    current_date = datetime.today().strftime('%Y-%m-%d')
    return render_template('book.html', date=current_date)

# Testimonials route
@app.route('/testimonials')
def testimonials():
    # Combine all testimonials into one list
    testimonials_data = [
        {"name": "Priya Sharma", "testimonial": "Absolutely loved my bridal look! The team was professional, punctual, and so talented.", "rating": 5, "image": "priya_sharma.jpg"},
        {"name": "Riya Dey", "testimonial": "They transformed me for my big day! Everyone complimented my hair and makeup.", "rating": 5, "image": "riya_dey.jpg"},
        {"name": "Ananya Gupta", "testimonial": "Such a relaxing experience. Great service, beautiful nail art, and amazing styling!", "rating": 4, "image": "ananya_gupta.jpg"},
        {"name": "Sneha Patel", "testimonial": "Mou's team gave me the exact look I wanted. Soft, elegant, and flawless. I highly recommend them!", "rating": 5, "image": "sneha_patel.jpg"},
        {"name": "Roshni Sen", "testimonial": "Professional, warm and extremely talented. My party makeup turned out absolutely stunning!", "rating": 5, "image": "roshni_sen.jpg"},
        {"name": "Meenakshi Roy", "testimonial": "The hair styling lasted all day and I got compliments everywhere I went. Super happy!", "rating": 4, "image": "meenakshi_roy.jpg"},
        {"name": "Reena Mallik", "testimonial": "The makeup service exceeded my expectations!", "rating": 5, "image": "reena_mallik.jpg"},
        {"name": "Chandana Paul", "testimonial": "Professional, efficient, and so talented!", "rating": 5, "image": "chandana_paul.jpg"}
        # Add more testimonials here as your business grows!
    ]
    # You can sort testimonials here if you want them in a specific order
    return render_template('testimonials.html', testimonials=testimonials_data) # Removed datetime=datetime here

# !!! IMPORTANT: Remove or comment out the testimonials2 route from your app.py
# @app.route('/testimonials2')
# def testimonials2():
#    ... (delete this entire route) ...

# Gallery route
@app.route('/gallery')
def gallery():
    gallery_images = ["image1.jpg", "image2.jpg", "image3.jpg"] # Update with actual image paths
    return render_template('gallery.html', images=gallery_images)

# Thank you page after booking (now also handling payment QR)
@app.route('/thank_you')
def thank_you():
    appointment_id = request.args.get('appointment_id')
    if not appointment_id:
        flash("No appointment ID provided.", "danger")
        return redirect(url_for('index'))

    # Retrieve booking details for displaying on the page
    bookings = load_bookings()
    booking_details = next((b for b in bookings if b['id'] == appointment_id), None)

    if not booking_details:
        flash("Appointment details not found.", "danger")
        return redirect(url_for('index'))

    upi_id = "moupriyadeys@axl" # Replace with actual UPI ID
    amount = 500 # Fixed partial payment amount
    payee_name = "MOU PRIYA DEY"
    qr_filename = f"qr_{appointment_id}.png" # Prefix with 'qr_' to avoid conflicts
    qr_path = os.path.join(QR_FOLDER, qr_filename)

    # Generate QR code only if it doesn't exist
    if not os.path.exists(qr_path):
        upi_url = f"upi://pay?pa={upi_id}&pn={payee_name}&am={amount}&cu=INR&tn=Payment for Makeup booking ID {appointment_id}"
        qr = qrcode.make(upi_url)
        qr.save(qr_path)

    return render_template('thank_you.html',
                           appointment_id=appointment_id,
                           qr_image_url=f"/static/qr_codes/{qr_filename}",
                           booking=booking_details,
                           payment_amount=amount)

# Payment confirmation route
@app.route('/confirm_payment/<appointment_id>', methods=['POST'])
def confirm_payment(appointment_id):
    bookings = load_bookings()
    for booking in bookings:
        if booking['id'] == appointment_id:
            booking['payment_status'] = 'Paid'
            save_bookings(bookings) # Save after updating status
            flash('Payment confirmed. Thank you for your payment!', 'success')
            return redirect(url_for('payment_success', appointment_id=appointment_id))
    flash('Booking not found for payment confirmation.', 'danger')
    return redirect(url_for('index')) # Fallback if booking not found

# New route for payment success page
@app.route('/payment_success/<appointment_id>')
def payment_success(appointment_id):
    bookings = load_bookings()
    booking_details = next((b for b in bookings if b['id'] == appointment_id), None)
    if not booking_details:
        flash("Payment confirmation details not found.", "danger")
        return redirect(url_for('index'))
    return render_template('payment_success.html', booking=booking_details)


# Admin routes
@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    status_filter = request.args.get('status')
    date_filter = request.args.get('date')
    search_filter = request.args.get('search')

    bookings = load_bookings()

    # Filter bookings by status and date
    filtered_bookings = []
    for b in bookings:
        match_status = True
        match_date = True
        match_search = True

        if status_filter and b['status'] != status_filter:
            match_status = False
        if date_filter and b['date'] != date_filter:
            match_date = False
        if search_filter and search_filter.lower() not in b['name'].lower() and search_filter.lower() not in b['id'].lower():
            match_search = False # Also search by ID

        if match_status and match_date and match_search:
            filtered_bookings.append(b)

    return render_template('admin_dashboard.html', bookings=filtered_bookings)


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

Details:
Service: {confirmed_booking['service']}
Date: {confirmed_booking['date']}
Time: {confirmed_booking['time']}
Appointment ID: {confirmed_booking['id']}
Payment Status: {confirmed_booking.get('payment_status', 'N/A')}

Best regards,
Mou's Makeup & Nails
"""
        try:
            mail.send(msg)
        except Exception as e:
            print(f"❌ Error sending confirmation email: {str(e)}")

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

# Admin login and logout
@app.route('/admin/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = os.getenv('ADMIN_USERNAME')
        password = os.getenv('ADMIN_PASSWORD')

        if request.form['username'] == username and request.form['password'] == password:
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


@app.route('/terms_of_sale')
def terms_of_sale():
    return render_template('terms_of_sale.html')

# Services page
@app.route('/services')
def services():
    return render_template('services.html')

# Prevent cached pages for admin panel after logout
@app.after_request
def no_cache(response):
    response.headers['Cache-Control'] = 'no-store'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

if __name__ == '__main__':
    app.run(debug=True)