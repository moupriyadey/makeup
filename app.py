import os
import json
import uuid
import qrcode
import random
from flask import Flask, render_template, request, redirect, url_for, session, flash, make_response, send_from_directory # send_from_directory is back for local files
from flask_mail import Mail, Message
from dotenv import load_dotenv
from flask_login import LoginManager, UserMixin, login_required, login_user, logout_user, current_user
from datetime import datetime
from werkzeug.utils import secure_filename
from flask_sqlalchemy import SQLAlchemy # For database integration

# REMOVED: Cloudinary imports

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

# Flask-SQLAlchemy Configuration (for Neon DB for bookings)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# REMOVED: Cloudinary Configuration

# File paths and QR folder setup
QR_FOLDER = os.path.join('static', 'qr_codes')
os.makedirs(QR_FOLDER, exist_ok=True)

# Image Upload Configuration (REINTRODUCED for local storage)
UPLOAD_FOLDER = os.path.join('static', 'gallery_uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'} # Reintroduced for local file type validation

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True) # Ensure the upload folder exists

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

# Helper function to check allowed file extensions (now using ALLOWED_EXTENSIONS)
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Define the Booking Model (for Neon DB)
class Booking(db.Model):
    id = db.Column(db.String(50), primary_key=True, unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), nullable=False)
    mobile = db.Column(db.String(20), nullable=False)
    service = db.Column(db.String(100), nullable=False)
    date = db.Column(db.String(20), nullable=False) # Store as string "DD/MM/YYYY" for now
    time = db.Column(db.String(10), nullable=False)
    status = db.Column(db.String(20), default='Pending')
    payment_status = db.Column(db.String(20), default='Unpaid')
    created_at = db.Column(db.DateTime, default=datetime.utcnow) # Store as datetime object

    def __repr__(self):
        return f"<Booking {self.id}>"

# REMOVED: GalleryImage Model (since images are local, not in DB metadata)

# Function to generate unique numerical ID (checks DB)
def generate_unique_numerical_id():
    while True:
        new_id = str(random.randint(100000, 99999999))
        if not Booking.query.filter_by(id=new_id).first(): # Check if ID exists in DB
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
    return render_template('index.html', datetime=datetime)

# Booking route - UPDATED FOR DB (no change from previous DB integration)
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

        # Create new booking object and add to DB
        new_booking = Booking(
            id=appointment_id,
            name=name,
            email=email,
            mobile=mobile,
            service=service,
            date=formatted_date,
            time=time,
            status='Pending',
            payment_status='Unpaid',
            created_at=datetime.utcnow() # Store as datetime object
        )
        db.session.add(new_booking)
        db.session.commit() # Commit to save to database

        # Send confirmation email
        msg = Message(
            subject="Appointment Confirmation - Mou's Makeup & Nails",
            recipients=[email]
        )
        msg.body = f"""Dear {name},

Your appointment for {service} on {formatted_date} at {time} has been received.
Appointment ID: {appointment_id}
Booked on: {new_booking.created_at.strftime("%Y-%m-%d %H:%M:%S")}

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
    return render_template('book.html', date=current_date, datetime=datetime)

# Testimonials route (no change)
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
    return render_template('testimonials.html', testimonials=testimonials_data, datetime=datetime)

# Gallery route - REVERTED TO READ FROM LOCAL UPLOAD_FOLDER
@app.route('/gallery')
def gallery():
    gallery_images = []
    # This now reads from the local filesystem (UPLOAD_FOLDER)
    if os.path.exists(app.config['UPLOAD_FOLDER']): # Check if folder exists
        for filename in os.listdir(app.config['UPLOAD_FOLDER']):
            if allowed_file(filename): # Use allowed_file for validation
                gallery_images.append(filename)
    gallery_images.sort(reverse=True) # Sort to show newest first
    return render_template('gallery.html', images=gallery_images, datetime=datetime)

# Thank you page after booking - UPDATED FOR DB (no change from previous DB integration)
@app.route('/thank_you')
def thank_you():
    appointment_id = request.args.get('appointment_id')
    if not appointment_id:
        flash("No appointment ID provided.", "danger")
        return redirect(url_for('index'))

    booking_details = Booking.query.get(appointment_id) # Fetch from DB

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
                           datetime=datetime)

# Payment confirmation route - UPDATED FOR DB (no change from previous DB integration)
@app.route('/confirm_payment/<appointment_id>', methods=['POST'])
def confirm_payment(appointment_id):
    booking = Booking.query.get(appointment_id) # Fetch from DB
    if booking:
        booking.payment_status = 'Paid' # Update status
        db.session.commit() # Commit to save
        flash('Payment confirmed. Thank you for your payment!', 'success')
        return redirect(url_for('payment_success', appointment_id=appointment_id))
    flash('Booking not found for payment confirmation.', 'danger')
    return redirect(url_for('index'))

# Payment success page - UPDATED FOR DB (no change from previous DB integration)
@app.route('/payment_success/<appointment_id>')
def payment_success(appointment_id):
    booking_details = Booking.query.get(appointment_id) # Fetch from DB
    if not booking_details:
        flash("Payment confirmation details not found.", "danger")
        return redirect(url_for('index'))
    return render_template('payment_success.html', booking=booking_details, datetime=datetime)

# Admin dashboard - UPDATED FOR DB & REVERTED FOR LOCAL IMAGES
@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    status_filter = request.args.get('status')
    date_filter = request.args.get('date')
    search_filter = request.args.get('search')

    # Query all bookings from the database (no change from previous DB integration)
    query = Booking.query

    if status_filter:
        query = query.filter_by(status=status_filter)

    if date_filter:
        try:
            # Convert date_filter to the same format as stored in DB (DD/MM/YYYY)
            filter_date_obj = datetime.strptime(date_filter, "%Y-%m-%d").strftime("%d/%m/%Y")
            query = query.filter_by(date=filter_date_obj)
        except ValueError:
            flash("Invalid date format for filter. Please use YYYY-MM-DD.", "warning")

    if search_filter:
        search_pattern = f"%{search_filter}%" # For LIKE queries
        query = query.filter(
            (Booking.name.ilike(search_pattern)) | # Case-insensitive LIKE for name
            (Booking.id.ilike(search_pattern))    # Case-insensitive LIKE for id
        )

    # Order by creation date descending
    query = query.order_by(Booking.created_at.desc())

    # Manual pagination logic (using Flask-SQLAlchemy's paginate)
    page = request.args.get('page', 1, type=int)
    per_page = 10
    paginated_bookings = query.paginate(page=page, per_page=per_page, error_out=False)

    # REVERTED: Get gallery images from local UPLOAD_FOLDER
    gallery_images = []
    if os.path.exists(app.config['UPLOAD_FOLDER']):
        for filename in os.listdir(app.config['UPLOAD_FOLDER']):
            if allowed_file(filename):
                gallery_images.append(filename)
    gallery_images.sort(reverse=True)

    return render_template('admin_dashboard.html',
                           bookings=paginated_bookings.items,
                           current_page=paginated_bookings.page,
                           total_pages=paginated_bookings.pages,
                           datetime=datetime,
                           gallery_images=gallery_images) # Now passes filenames again

@app.route('/admin/confirm_booking', methods=['POST'])
@login_required
def confirm_booking():
    appointment_id = request.form.get('appointment_id')
    booking = Booking.query.get(appointment_id) # Fetch from DB

    if booking:
        booking.status = 'Confirmed' # Update status
        db.session.commit() # Commit to save

        msg = Message(
            subject="Your Appointment is Confirmed",
            recipients=[booking.email]
        )
        msg.body = f"""Dear {booking.name},

Your appointment has been confirmed.

Details:
Service: {booking.service}
Date: {booking.date}
Time: {booking.time}
Appointment ID: {booking.id}
Payment Status: {booking.payment_status}
Booked on: {booking.created_at.strftime("%Y-%m-%d %H:%M:%S")}

Best regards,
Mou's Makeup & Nails
"""
        try:
            mail.send(msg)
        except Exception as e:
            print(f"❌ Error sending confirmation email: {str(e)}")
        flash('Booking Confirmed.', 'success')
    else:
        flash('Booking not found.', 'danger')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/delete_booking', methods=['POST'])
@login_required
def delete_booking():
    appointment_id = request.form.get('appointment_id')
    booking = Booking.query.get(appointment_id) # Fetch from DB

    if booking:
        db.session.delete(booking) # Delete from DB
        db.session.commit() # Commit to save
        flash('Booking deleted successfully.', 'success')
    else:
        flash('Booking not found.', 'danger')
    return redirect(url_for('admin_dashboard'))

# Admin login and logout (no change)
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

    return render_template('admin_login.html', datetime=datetime)

@app.route('/admin/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'success')
    return redirect(url_for('login'))

@app.route('/terms_of_sale')
def terms_of_sale():
    return render_template('terms_of_sale.html', datetime=datetime)

# Services page (no change)
@app.route('/services')
def services():
    return render_template('services.html', datetime=datetime)

# REVERTED: Upload Image Route (to local UPLOAD_FOLDER)
@app.route('/admin/upload_image', methods=['GET', 'POST'])
@login_required
def upload_image():
    if request.method == 'POST':
        if 'files[]' not in request.files:
            flash('No file part', 'danger')
            return redirect(request.url)

        files = request.files.getlist('files[]')
        uploaded_count = 0
        skipped_count = 0

        for file in files:
            if file.filename == '':
                skipped_count += 1
                continue

            if file and allowed_file(file.filename): # Use allowed_file check
                filename = secure_filename(file.filename)
                try:
                    file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename)) # Save to local folder
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

        return redirect(url_for('gallery'))

    return render_template('admin_upload_image.html', datetime=datetime)

# REINTRODUCED: Route to serve uploaded files from local folder
@app.route('/static/gallery_uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# REVERTED: Delete Image Route (from local UPLOAD_FOLDER)
@app.route('/admin/delete_image/<filename>', methods=['POST'])
@login_required
def delete_image(filename):
    if session.get('role') != 'admin':
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('admin_dashboard'))

    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename) # Path to local file
    if os.path.exists(filepath):
        try:
            os.remove(filepath) # Delete local file
            flash(f'Image "{filename}" deleted successfully.', 'success')
        except Exception as e:
            flash(f'Error deleting image "{filename}": {e}', 'danger')
    else:
        flash(f'Image "{filename}" not found.', 'danger')

    return redirect(url_for('admin_dashboard'))

# Prevent cached pages for admin panel after logout (no change)
@app.after_request
def no_cache(response):
    response.headers['Cache-Control'] = 'no-store'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

if __name__ == '__main__':
    # Create database tables if they don't exist
    with app.app_context():
        db.create_all() # This creates the Booking table (GalleryImage is removed)

    app.run(debug=True)