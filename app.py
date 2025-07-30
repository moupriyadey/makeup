import os
import json
import uuid
import qrcode
import random
from flask import Flask, render_template, request, redirect, url_for, session, flash, make_response, send_from_directory # Added send_from_directory
from flask_mail import Mail, Message
from dotenv import load_dotenv
from flask_login import LoginManager, UserMixin, login_required, login_user, logout_user, current_user
from datetime import datetime
from werkzeug.utils import secure_filename # Added secure_filename

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

# Image Upload Configuration
UPLOAD_FOLDER = os.path.join('static', 'gallery_uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True) # Ensure the upload folder exists

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

# Helper function to check allowed file extensions
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

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
        new_id = str(random.randint(100000, 99999999))
        if new_id not in existing_ids:
            return new_id

# Context processor to add enumerate to templates
@app.context_processor
def inject_enumerate():
    return dict(enumerate=enumerate)

# Context processor to make datetime available globally in templates
@app.context_processor
def inject_datetime():
    return {'datetime': datetime}

# Home route
@app.route('/')
def index():
    return render_template('index.html', datetime=datetime) # Pass datetime

# Booking route
@app.route('/book', methods=['GET', 'POST'])
def book():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        mobile = request.form['mobile']
        service = request.form['service']
        date_str = request.form['date']
        time = request.form['time']

        # Generate a numerical appointment ID
        appointment_id = generate_unique_numerical_id()

        # Try both date formats
        try:
            formatted_date = datetime.strptime(date_str, "%Y-%m-%d").strftime("%d/%m/%Y")
        except ValueError:
            try:
                formatted_date = datetime.strptime(date_str, "%d/%m/%Y").strftime("%d/%m/%Y")
            except ValueError:
                flash("Invalid date format. Please use DD/MM/YYYY or YYYY-MM-DD.", "danger")
                return redirect(url_for('book'))

        # Add creation timestamp
        created_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

        new_booking = {
            'id': appointment_id,
            'name': name,
            'email': email,
            'mobile': mobile,
            'service': service,
            'date': formatted_date,
            'time': time,
            'status': 'Pending',
            'payment_status': 'Unpaid',
            'created_at': created_at
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
Booked on: {created_at}

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

    current_date = datetime.today().strftime('%Y-%m-%d')
    return render_template('book.html', date=current_date, datetime=datetime) # Pass datetime

# Testimonials route
@app.route('/testimonials')
def testimonials():
    testimonials_data = [
        {"name": "Priya Sharma", "testimonial": "Absolutely loved my bridal look! The team was professional, punctual, and so talented.", "rating": 5, "image": "priya_sharma.jpg"},
        {"name": "Riya Dey", "testimonial": "They transformed me for my big day! Everyone complimented my hair and makeup.", "rating": 5, "image": "riya_dey.jpg"},
        {"name": "Ananya Gupta", "testimonial": "Such a relaxing experience. Great service, beautiful nail art, and amazing styling!", "rating": 4, "image": "ananya_gupta.jpg"},
        {"name": "Sneha Patel", "testimonial": "Mou's team gave me the exact look I wanted. Soft, elegant, and flawless. I highly recommend them!", "rating": 5, "image": "sneha_patel.jpg"},
        {"name": "Roshni Sen", "testimonial": "Professional, warm and extremely talented. My party makeup turned out absolutely stunning!", "rating": 5, "image": "roshni_sen.jpg"},
        {"name": "Meenakshi Roy", "testimonial": "The hair styling lasted all day and I got compliments everywhere I went. Super happy!", "rating": 4, "image": "meenakshi_roy.jpg"},
        {"name": "Reena Mallik", "testimonial": "The makeup service exceeded my expectations!", "rating": 5, "image": "reena_mallik.jpg"},
        {"name": "Chandana Paul", "testimonial": "Professional, efficient, and so talented!", "rating": 5, "image": "chandana_paul.jpg"}
    ]
    return render_template('testimonials.html', testimonials=testimonials_data, datetime=datetime) # Pass datetime

# Gallery route - UPDATED TO READ FROM UPLOAD_FOLDER
@app.route('/gallery')
def gallery():
    gallery_images = []
    for filename in os.listdir(app.config['UPLOAD_FOLDER']):
        if allowed_file(filename):
            gallery_images.append(filename)
    gallery_images.sort(reverse=True) # Sort to show newest first, optional
    return render_template('gallery.html', images=gallery_images, datetime=datetime) # Pass datetime

# Thank you page after booking
@app.route('/thank_you')
def thank_you():
    appointment_id = request.args.get('appointment_id')
    if not appointment_id:
        flash("No appointment ID provided.", "danger")
        return redirect(url_for('index'))

    bookings = load_bookings()
    booking_details = next((b for b in bookings if b['id'] == appointment_id), None)

    if not booking_details:
        flash("Appointment details not found.", "danger")
        return redirect(url_for('index'))

    upi_id = "moupriyadeys@axl"
    amount = 500
    payee_name = "MOU PRIYA DEY"
    qr_filename = f"qr_{appointment_id}.png"
    qr_path = os.path.join(QR_FOLDER, qr_filename)

    if not os.path.exists(qr_path):
        upi_url = f"upi://pay?pa={upi_id}&pn={payee_name}&am={amount}&cu=INR&tn=Payment for Makeup booking ID {appointment_id}"
        qr = qrcode.make(upi_url)
        qr.save(qr_path)

    return render_template('thank_you.html',
                           appointment_id=appointment_id,
                           qr_image_url=f"/static/qr_codes/{qr_filename}",
                           booking=booking_details,
                           payment_amount=amount,
                           datetime=datetime) # Pass datetime

# Payment confirmation route
@app.route('/confirm_payment/<appointment_id>', methods=['POST'])
def confirm_payment(appointment_id):
    bookings = load_bookings()
    for booking in bookings:
        if booking['id'] == appointment_id:
            booking['payment_status'] = 'Paid'
            save_bookings(bookings)
            flash('Payment confirmed. Thank you for your payment!', 'success')
            return redirect(url_for('payment_success', appointment_id=appointment_id))
    flash('Booking not found for payment confirmation.', 'danger')
    return redirect(url_for('index'))

# Payment success page
@app.route('/payment_success/<appointment_id>')
def payment_success(appointment_id):
    bookings = load_bookings()
    booking_details = next((b for b in bookings if b['id'] == appointment_id), None)
    if not booking_details:
        flash("Payment confirmation details not found.", "danger")
        return redirect(url_for('index'))
    return render_template('payment_success.html', booking=booking_details, datetime=datetime) # Pass datetime

# Admin dashboard
# app.py (Find your existing admin_dashboard route)

@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    status_filter = request.args.get('status')
    date_filter = request.args.get('date')
    search_filter = request.args.get('search')

    bookings = load_bookings()

    filtered_bookings = []
    for b in bookings:
        match_status = True
        match_date = True
        match_search = True

        if status_filter and b['status'] != status_filter:
            match_status = False
        # The date filter logic needs to parse the date strings to compare correctly
        if date_filter:
            try:
                filter_date_obj = datetime.strptime(date_filter, "%Y-%m-%d").date()
                booking_date_obj = datetime.strptime(b['date'], "%d/%m/%Y").date()
                if booking_date_obj != filter_date_obj:
                    match_date = False
            except ValueError:
                # Handle cases where date_filter or b['date'] might be in unexpected formats
                match_date = False # Or flash an error
        if search_filter and search_filter.lower() not in b['name'].lower() and search_filter.lower() not in b['id'].lower():
            match_search = False

        if match_status and match_date and match_search:
            filtered_bookings.append(b)

    # Manual pagination logic (if not using Flask-SQLAlchemy-Pagination)
    page = request.args.get('page', 1, type=int)
    per_page = 10  # Number of bookings per page
    total_bookings = len(filtered_bookings)
    total_pages = (total_bookings + per_page - 1) // per_page
    start_index = (page - 1) * per_page
    end_index = start_index + per_page
    paginated_bookings = filtered_bookings[start_index:end_index]

    # --- NEW ADDITION: Get gallery images here ---
    gallery_images = []
    # Ensure UPLOAD_FOLDER is configured correctly in app.py at the top
    # e.g., UPLOAD_FOLDER = os.path.join('static', 'gallery_uploads')
    # app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
    if os.path.exists(app.config['UPLOAD_FOLDER']):
        for filename in os.listdir(app.config['UPLOAD_FOLDER']):
            # Check for allowed extensions before adding to the list
            if '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS:
                gallery_images.append(filename)
    gallery_images.sort(reverse=True) # Optional: sort by newest first

    return render_template('admin_dashboard.html',
                           bookings=paginated_bookings,
                           current_page=page,
                           total_pages=total_pages,
                           datetime=datetime,
                           gallery_images=gallery_images) # <-- Pass the gallery_images list

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
Booked on: {confirmed_booking.get('created_at', 'N/A')}

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

    return render_template('admin_login.html', datetime=datetime) # Pass datetime

@app.route('/admin/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'success')
    return redirect(url_for('login'))

@app.route('/terms_of_sale')
def terms_of_sale():
    return render_template('terms_of_sale.html', datetime=datetime) # Pass datetime

# Services page
@app.route('/services')
def services():
    return render_template('services.html', datetime=datetime) # Pass datetime

# --- NEW/UPDATED GALLERY & UPLOAD ROUTES ---
# app.py (Find your existing upload_image route)

# ... (keep existing imports and code)

@app.route('/admin/upload_image', methods=['GET', 'POST'])
@login_required
def upload_image():
    if request.method == 'POST':
        # Check if the post request has the file part
        if 'files[]' not in request.files: # Changed from 'file' to 'files[]'
            flash('No file part', 'danger')
            return redirect(request.url)

        files = request.files.getlist('files[]') # Use getlist for multiple files
        uploaded_count = 0
        skipped_count = 0

        for file in files:
            # If the user does not select a file for a given input field,
            # the browser submits an empty file without a filename.
            if file.filename == '':
                skipped_count += 1
                continue # Skip empty file input

            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                try:
                    file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                    uploaded_count += 1
                except Exception as e:
                    flash(f'Error uploading "{filename}": {e}', 'warning')
                    skipped_count += 1
            else:
                flash(f'Skipped "{file.filename}": Allowed image types are png, jpg, jpeg, gif', 'warning')
                skipped_count += 1

        if uploaded_count > 0:
            flash(f'{uploaded_count} image(s) successfully uploaded!', 'success')
        if skipped_count > 0:
            flash(f'{skipped_count} image(s) skipped due to errors or invalid file types.', 'info')

        return redirect(url_for('gallery')) # Redirect to gallery to see the new images

    return render_template('admin_upload_image.html', datetime=datetime)
@app.route('/static/gallery_uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# app.py additions
# ... (keep your existing imports and code above)

import os # Ensure this is already imported at the top, if not add it.
# ...

@app.route('/admin/delete_image/<filename>', methods=['POST'])
@login_required
def delete_image(filename):
    if session.get('role') != 'admin': # Optional: additional check for admin role
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('admin_dashboard'))

    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    if os.path.exists(filepath):
        try:
            os.remove(filepath)
            flash(f'Image "{filename}" deleted successfully.', 'success')
        except Exception as e:
            flash(f'Error deleting image "{filename}": {e}', 'danger')
    else:
        flash(f'Image "{filename}" not found.', 'danger')

    return redirect(url_for('admin_dashboard')) # Redirect back to admin dashboard

# Prevent cached pages for admin panel after logout
@app.after_request
def no_cache(response):
    response.headers['Cache-Control'] = 'no-store'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

if __name__ == '__main__':
    app.run(debug=True)