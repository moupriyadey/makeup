import os
import json
import uuid
import random
from io import BytesIO
from datetime import datetime, timedelta

import cloudinary
import cloudinary.uploader
import cloudinary.api
import pandas as pd  # pip install pandas openpyxl
import qrcode
from dotenv import load_dotenv
from flask import (
    Flask, render_template, request, redirect, url_for,
    session, flash, make_response, send_from_directory, send_file, jsonify
)
from flask_mail import Mail, Message
from flask_login import (
    LoginManager, UserMixin, login_required, login_user,
    logout_user, current_user
)
from werkzeug.utils import secure_filename
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text

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
# Temporary line to create tables


# Cloudinary Configuration
cloudinary.config(
    cloud_name=os.getenv('CLOUDINARY_CLOUD_NAME'),
    api_key=os.getenv('CLOUDINARY_API_KEY'),
    api_secret=os.getenv('CLOUDINARY_API_SECRET')
)
# File paths and QR folder setup
QR_FOLDER = os.path.join('static', 'qr_codes')
os.makedirs(QR_FOLDER, exist_ok=True)

# Image Upload Configuration (REINTRODUCED for local storage)
UPLOAD_FOLDER = os.path.join('static', 'gallery_uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'} # Reintroduced for local file type validation

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
    

# Additive homepage appearance settings; existing business tables are unchanged.
class HomepageSettings(db.Model):
    __tablename__ = 'homepage_settings'
    id = db.Column(db.Integer, primary_key=True)
    theme = db.Column(db.String(30), nullable=False, default='royal')
    navbar_style = db.Column(db.String(30), nullable=False, default='floating')
    section_settings = db.Column(db.JSON, nullable=False, default=dict)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# REMOVED: GalleryImage Model (since images are local, not in DB metadata)
class GalleryImage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    url = db.Column(db.String(500), nullable=False)
    filename = db.Column(db.String(255), nullable=True)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)


# Invoice Model
# Invoice model for database storage
class Invoice(db.Model):
    id = db.Column(db.String(50), primary_key=True, unique=True, nullable=False)
    invoice_number = db.Column(db.String(50), unique=True, nullable=False)
    customer_name = db.Column(db.String(100), nullable=False)
    customer_address = db.Column(db.String(200), nullable=True)
    customer_phone = db.Column(db.String(20), nullable=True)
    invoice_date = db.Column(db.Date, nullable=False)
    due_date = db.Column(db.Date, nullable=True)
    total_amount = db.Column(db.Float, nullable=False)
    advance_amount = db.Column(db.Float, nullable=True, default=0.0)
    due_amount = db.Column(db.Float, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    appointment_time = db.Column(db.String(50), nullable=True)

    def __repr__(self):
        return f"<Invoice {self.invoice_number}>"

# Services model associated with an Invoice
class InvoiceService(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.String(50), db.ForeignKey('invoice.id'), nullable=False)
    description = db.Column(db.String(200), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    invoice = db.relationship('Invoice', backref=db.backref('services', lazy=True))# Function to generate unique numerical ID (checks DB)

def generate_unique_numerical_id():
    while True:
        new_id = str(random.randint(100000, 99999999))
        if not Booking.query.filter_by(id=new_id).first(): # Check if ID exists in DB
            return new_id
def cloudinary_public_id_from_url(url):
    """
    Extract the public_id from a Cloudinary URL without the file extension.
    Example:
        https://res.cloudinary.com/demo/image/upload/v1234567890/foldername/imagefile.jpg
        => foldername/imagefile
    """
    import re
    match = re.search(r'upload/(?:v\d+/)?(.+?)\.[a-zA-Z]+$', url)
    if match:
        return match.group(1)
    return None
      
# Function to convert number to words
def number_to_words(number):
    # This is a simplified version. A more robust one may be needed for very large numbers or different currencies.
    # We will use the same JS logic from the template for consistency
    num_str = "{:,.2f}".format(number)
    parts = num_str.split('.')
    integer_part = int(parts[0].replace(',', ''))
    decimal_part = int(parts[1]) if len(parts) > 1 else 0

    def in_words(num):
        a = ['', 'one ', 'two ', 'three ', 'four ', 'five ', 'six ', 'seven ', 'eight ', 'nine ', 'ten ', 'eleven ', 'twelve ', 'thirteen ', 'fourteen ', 'fifteen ', 'sixteen ', 'seventeen ', 'eighteen ', 'nineteen ']
        b = ['', '', 'twenty', 'thirty', 'forty', 'fifty', 'sixty', 'seventy', 'eighty', 'ninety']
        if num < 20:
            return a[num]
        else:
            return b[num // 10] + (a[num % 10] if num % 10 != 0 else '')

    def parse(num):
        if num == 0:
            return ''
        
        words = ''
        if num >= 10000000:
            words += in_words(num // 10000000) + 'crore '
            num %= 10000000
        if num >= 100000:
            words += in_words(num // 100000) + 'lakh '
            num %= 100000
        if num >= 1000:
            words += in_words(num // 1000) + 'thousand '
            num %= 1000
        if num >= 100:
            words += in_words(num // 100) + 'hundred '
            num %= 100
        if num > 0:
            if words: words += 'and '
            words += in_words(num)
        return words

    words = parse(integer_part)
    if decimal_part > 0:
        if words: words += ' and '
        words += in_words(decimal_part) + 'paise'

    return words.strip() or "Zero"

# Add a context processor to make the function available in all templates
@app.context_processor
def utility_processor():
    return dict(number_to_words=number_to_words)

# Add this function somewhere in your app.py, outside of any route.

# Function to generate unique sequential invoice number
# Function to generate unique sequential invoice number
def generate_invoice_number():
    current_year_suffix = datetime.utcnow().strftime('%y')
    
    # Get the last invoice number from the database, regardless of the year
    last_invoice = Invoice.query.order_by(Invoice.created_at.desc()).first()

    if last_invoice:
        try:
            # Extract the numerical part from the last invoice number
            last_number = int(last_invoice.invoice_number.split('/')[1])
            new_number = last_number + 1
        except (IndexError, ValueError):
            # Fallback in case of an unusual invoice number format
            new_number = 1
    else:
        # If no invoices exist in the database, start at 1
        new_number = 1

    return f"MDB/{new_number:03d}/{current_year_suffix}"

# Context processor to add enumerate to templates
@app.context_processor
def inject_enumerate():
    return dict(enumerate=enumerate)

# Context processor to make datetime available globally in templates
@app.context_processor
def inject_datetime():
    return {'datetime': datetime}

# Homepage appearance defaults. Admin selections are stored in one additive table.
HOMEPAGE_DEFAULT_SECTIONS = [
    {'id': 'hero', 'label': 'Hero banner', 'visible': True},
    {'id': 'rent-feature', 'label': 'Rental collection', 'visible': True},
    {'id': 'buy', 'label': 'BUY collection', 'visible': True},
    {'id': 'beauty-services', 'label': 'Beauty services', 'visible': True},
    {'id': 'featured-services', 'label': 'Featured services', 'visible': True},
    {'id': 'gallery-carousel', 'label': 'Gallery carousel', 'visible': True},
    {'id': 'gallery-links', 'label': 'Gallery and reviews links', 'visible': True},
    {'id': 'testimonials-links', 'label': 'Testimonials links', 'visible': True},
    {'id': 'youtube', 'label': 'YouTube videos', 'visible': True},
    {'id': 'address', 'label': 'Address and location', 'visible': True}
]

def get_homepage_settings():
    # Create only this new settings table if absent; do not run create_all()
    # across the application's other business tables on public page requests.
    HomepageSettings.__table__.create(bind=db.engine, checkfirst=True)
    settings = HomepageSettings.query.first()
    if settings is None:
        settings = HomepageSettings(
            theme='royal',
            navbar_style='floating',
            section_settings={'sections': HOMEPAGE_DEFAULT_SECTIONS}
        )
        db.session.add(settings)
        db.session.commit()
    return settings

# Home route
@app.route('/')
def index():
    settings = get_homepage_settings()
    section_data = settings.section_settings or {'sections': HOMEPAGE_DEFAULT_SECTIONS}
    return render_template(
        'index.html', datetime=datetime,
        homepage_theme=settings.theme,
        homepage_navbar_style=settings.navbar_style,
        homepage_sections=section_data.get('sections', HOMEPAGE_DEFAULT_SECTIONS)
    )

@app.route('/admin/homepage-settings', methods=['GET'])
@login_required
def admin_homepage_settings():
    if session.get('role') != 'admin':
        flash('Administrator access required.', 'danger')
        return redirect(url_for('login'))
    settings = get_homepage_settings()
    section_data = settings.section_settings or {'sections': HOMEPAGE_DEFAULT_SECTIONS}
    return render_template(
        'admin_homepage_settings.html', settings=settings,
        sections=section_data.get('sections', HOMEPAGE_DEFAULT_SECTIONS),
        datetime=datetime
    )

@app.route('/admin/homepage-settings/save', methods=['POST'])
@login_required
def save_admin_homepage_settings():
    if session.get('role') != 'admin':
        flash('Administrator access required.', 'danger')
        return redirect(url_for('login'))

    allowed_themes = {'royal', 'glass', 'emerald'}
    allowed_navbars = {'floating', 'glass', 'clay'}
    theme = request.form.get('theme', 'royal')
    navbar_style = request.form.get('navbar_style', 'floating')
    if theme not in allowed_themes or navbar_style not in allowed_navbars:
        flash('Invalid appearance selection.', 'danger')
        return redirect(url_for('admin_homepage_settings'))

    # Preserve only known section IDs and the admin-selected order.
    known = {item['id']: item for item in HOMEPAGE_DEFAULT_SECTIONS}
    submitted_ids = request.form.getlist('section_order')
    ordered = []
    for section_id in submitted_ids:
        if section_id in known and section_id not in [x['id'] for x in ordered]:
            ordered.append({
                'id': section_id,
                'label': known[section_id]['label'],
                'visible': request.form.get(f'show_{section_id}') == 'on'
            })
    for item in HOMEPAGE_DEFAULT_SECTIONS:
        if item['id'] not in [x['id'] for x in ordered]:
            ordered.append(dict(item))

    settings = get_homepage_settings()
    settings.theme = theme
    settings.navbar_style = navbar_style
    settings.section_settings = {'sections': ordered}
    settings.updated_at = datetime.utcnow()
    db.session.commit()
    flash('Homepage appearance and section settings saved.', 'success')
    return redirect(url_for('admin_homepage_settings'))



# 1️⃣ Backup function
def backup_invoices():
    """Create a backup JSON file of all invoices and their services in two locations."""
    try:
        invoices = Invoice.query.all()
        backup_data = []
        for inv in invoices:
            backup_data.append({
                "invoice_number": inv.invoice_number,
                "customer_name": inv.customer_name,
                "customer_address": inv.customer_address,
                "customer_phone": inv.customer_phone,
                "invoice_date": inv.invoice_date.strftime("%Y-%m-%d"),
                "due_date": inv.due_date.strftime("%Y-%m-%d") if inv.due_date else None,
                "total_amount": inv.total_amount,
                "advance_amount": inv.advance_amount,
                "due_amount": inv.due_amount,
                "services": [
                    {"description": s.description, "amount": s.amount}
                    for s in inv.services
                ]
            })

        # Timestamp for backup file name
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"invoices_backup_{timestamp}.json"

        # 1) Project's backups folder
        project_backup_folder = os.path.join("backups")
        os.makedirs(project_backup_folder, exist_ok=True)
        project_backup_path = os.path.join(project_backup_folder, filename)

        # 2) External local backup folder
        local_backup_folder = r"D:\InvoiceBackups"  # change if needed
        os.makedirs(local_backup_folder, exist_ok=True)
        local_backup_path = os.path.join(local_backup_folder, filename)

        for path in [project_backup_path, local_backup_path]:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(backup_data, f, indent=4, ensure_ascii=False)

        print(f"✅ Backup created: {project_backup_path} and {local_backup_path}")
    except Exception as e:
        print(f"❌ Backup failed: {e}")



# 3️⃣ Export to Excel route
@app.route('/admin/invoices/export')
@login_required
def export_invoices_excel():
    invoices = Invoice.query.all()
    data = []
    for inv in invoices:
        for service in inv.services:
            data.append({
                "Invoice Number": inv.invoice_number,
                "Customer Name": inv.customer_name,
                "Customer Address": inv.customer_address,
                "Customer Phone": inv.customer_phone,
                "Invoice Date": inv.invoice_date.strftime("%Y-%m-%d"),
                "Due Date": inv.due_date.strftime("%Y-%m-%d") if inv.due_date else None,
                "Service Description": service.description,
                "Service Amount": service.amount,
                "Total Amount": inv.total_amount,
                "Advance Amount": inv.advance_amount,
                "Due Amount": inv.due_amount
            })

    df = pd.DataFrame(data)
    export_folder = os.path.join("exports")
    os.makedirs(export_folder, exist_ok=True)
    file_path = os.path.join(export_folder, f"invoices_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx")
    df.to_excel(file_path, index=False)

    return send_file(file_path, as_attachment=True)


@app.route('/ping')
def ping_db():
    try:
        # A simple query to wake up the database
        db.session.execute(db.text('SELECT 1'))
        return 'Database is awake!', 200
    except Exception as e:
        return f'Database connection error: {e}', 500

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
    # Fetch images from database (Cloudinary URLs)
    gallery_images = GalleryImage.query.order_by(GalleryImage.uploaded_at.desc()).all()
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

    # --------------------------------------------------
    # EXISTING MAKEUP BOOKING LOGIC - PRESERVED
    # --------------------------------------------------
    query = Booking.query

    if status_filter:
        query = query.filter_by(status=status_filter)

    if date_filter:
        try:
            filter_date_obj = datetime.strptime(
                date_filter, "%Y-%m-%d"
            ).strftime("%d/%m/%Y")
            query = query.filter_by(date=filter_date_obj)
        except ValueError:
            flash(
                "Invalid date format for filter. Please use YYYY-MM-DD.",
                "warning"
            )

    if search_filter:
        search_pattern = f"%{search_filter}%"
        query = query.filter(
            (Booking.name.ilike(search_pattern)) |
            (Booking.id.ilike(search_pattern))
        )

    query = query.order_by(Booking.created_at.desc())

    page = request.args.get('page', 1, type=int)
    per_page = 10

    paginated_bookings = query.paginate(
        page=page,
        per_page=per_page,
        error_out=False
    )

    # Existing date conversion - preserved
    for booking in paginated_bookings.items:
        try:
            booking.date = datetime.strptime(
                booking.date, "%d/%m/%Y"
            ).date()
        except (ValueError, TypeError) as e:
            print(f"Error converting date for booking {booking.id}: {e}")
            booking.date = None

    # Existing gallery logic - preserved
    gallery_images = []

    if os.path.exists(app.config['UPLOAD_FOLDER']):
        for filename in os.listdir(app.config['UPLOAD_FOLDER']):
            if allowed_file(filename):
                gallery_images.append(filename)

    gallery_images.sort(reverse=True)

    # --------------------------------------------------
    # NEW RENTAL DASHBOARD DATA
    # --------------------------------------------------
    ensure_rental_tables()

    rental_products = RentalProduct.query.order_by(
        RentalProduct.created_at.desc()
    ).all()

    rental_orders = RentalOrder.query.order_by(
        RentalOrder.created_at.desc()
    ).all()

    # Rental order status counts
    rental_status_counts = {}

    for item in rental_orders:
        rental_status_counts[item.status] = (
            rental_status_counts.get(item.status, 0) + 1
        )

    today = datetime.utcnow().date()

    # Upcoming rental events
    upcoming_rental_events = sorted(
        [
            order for order in rental_orders
            if order.return_date >= today
            and order.status not in ('Returned', 'Cancelled')
        ],
        key=lambda order: (order.pickup_date, order.return_date)
    )[:12]

    # Calendar events: event, pickup and return dates
    rental_calendar_events = []

    for order in rental_orders:
        if order.status == 'Cancelled':
            continue

        product_name = (
            order.product.name
            if order.product else 'Rental item'
        )

        event_title = (
            f"{order.order_code} · {product_name} · "
            f"{order.customer_name}"
        )

        for event_date, event_kind in (
            (order.event_date, 'Event'),
            (order.pickup_date, 'Pickup'),
            (order.return_date, 'Return')
        ):
            if event_date:
                rental_calendar_events.append({
                    'date': event_date.isoformat(),
                    'kind': event_kind,
                    'title': event_title
                })

    # Inventory category counts
    rental_category_counts = {}

    for product in rental_products:
        rental_category_counts[product.category] = (
            rental_category_counts.get(product.category, 0) + 1
        )

    # Six-month committed rental value
    # This is NOT actual money collected.
    rental_monthly_value = {}

    for offset in range(5, -1, -1):
        month_date = today.replace(day=1)
        month_index = month_date.month - 1 - offset

        year = month_date.year + (month_index // 12)
        month = (month_index % 12) + 1

        month_key = f"{year:04d}-{month:02d}"
        rental_monthly_value[month_key] = 0.0

    for order in rental_orders:
        if (
            order.status in (
                'Confirmed',
                'Ready for pickup',
                'Rented',
                'Returned'
            )
            and order.event_date
        ):
            month_key = order.event_date.strftime('%Y-%m')

            if month_key in rental_monthly_value:
                rental_monthly_value[month_key] += float(
                    order.rental_price or 0
                )

    # Total committed rental value
    rental_active_value = sum(
        float(order.rental_price or 0)
        for order in rental_orders
        if order.status in (
            'Confirmed',
            'Ready for pickup',
            'Rented',
            'Returned'
        )
    )

    # --------------------------------------------------
    # SEND EXISTING + NEW DATA TO DASHBOARD TEMPLATE
    # --------------------------------------------------
    return render_template(
        'admin_dashboard.html',

        # Existing makeup dashboard data
        bookings=paginated_bookings.items,
        current_page=paginated_bookings.page,
        total_pages=paginated_bookings.pages,
        datetime=datetime,
        gallery_images=gallery_images,

        # New rental dashboard data
        rental_products=rental_products,
        rental_orders=rental_orders,
        rental_status_counts=rental_status_counts,
        rental_category_counts=rental_category_counts,
        rental_monthly_value=rental_monthly_value,
        upcoming_rental_events=upcoming_rental_events,
        rental_calendar_events=rental_calendar_events,
        rental_active_value=rental_active_value
    )

@app.route('/admin/invoices', methods=['GET', 'POST'])
@login_required
def manage_invoices():
    if request.method == 'POST':
        # Handle invoice creation
        customer_name = request.form['customer_name']
        customer_address = request.form['customer_address']
        customer_phone = request.form.get('customer_phone')
        due_date_str = request.form.get('due_date')
        
        # Parse services data from form
        service_descriptions = request.form.getlist('service_description[]')
        service_amounts = request.form.getlist('service_amount[]')
        
        total_amount = 0.0
        services_to_add = [] # Temporary list to hold service data
        
        for desc, amount in zip(service_descriptions, service_amounts):
            if desc and amount:
                amount_float = float(amount)
                services_to_add.append({"description": desc, "amount": amount_float})
                total_amount += amount_float
        
        advance_amount = float(request.form.get('advance_amount', 0))
        due_amount = total_amount - advance_amount

        # Generate unique invoice number and ID
        invoice_number = generate_invoice_number()
        invoice_id = str(uuid.uuid4())
        
        # Parse due date
        due_date = None
        if due_date_str:
            try:
                due_date = datetime.strptime(due_date_str, "%Y-%m-%d").date()
            except ValueError:
                flash("Invalid due date format. Please use YYYY-MM-DD.", "danger")
                return redirect(url_for('manage_invoices'))

        new_invoice = Invoice(
            id=invoice_id,
            invoice_number=invoice_number,
            customer_name=customer_name,
            customer_address=customer_address,
            customer_phone=customer_phone,
            total_amount=total_amount,
            advance_amount=advance_amount,
            due_amount=due_amount,
            due_date=due_date,
            invoice_date=datetime.utcnow(),
            appointment_time=request.form['appointment_time']
        )
        
        db.session.add(new_invoice)
        
        # Now create and link the InvoiceService entries
        for service_data in services_to_add:
            new_service = InvoiceService(
                invoice_id=new_invoice.id,
                description=service_data['description'],
                amount=service_data['amount']
            )
            db.session.add(new_service)
            
        db.session.commit()
        
        flash(f'Invoice {invoice_number} created successfully!', 'success')
        return redirect(url_for('manage_invoices'))

    # Handle GET request to display invoices
    invoices = Invoice.query.order_by(Invoice.invoice_date.desc()).all()
    
    # Calculate total revenue
    total_revenue = db.session.query(db.func.sum(Invoice.total_amount)).scalar() or 0
    
    # Data for revenue chart (last 7 days)
    revenue_data = {}
    today = datetime.utcnow().date()
    for i in range(7):
        day = today - timedelta(days=i)
        day_total = db.session.query(db.func.sum(Invoice.total_amount)).filter(db.func.date(Invoice.invoice_date) == day).scalar() or 0
        revenue_data[day.strftime('%Y-%m-%d')] = day_total
        
    # Data for schedule calendar
    schedule_data = {}
    
    # Fetch all confirmed bookings and invoices with due dates
    all_bookings = Booking.query.filter(Booking.status == 'Confirmed').all()
    all_invoices = Invoice.query.all()
    
    # Process bookings
    for booking in all_bookings:
        try:
            date_obj = datetime.strptime(booking.date, '%d/%m/%Y').date()
            date_key = date_obj.strftime('%Y-%m-%d')  # Convert to string key
            if date_key not in schedule_data:
                schedule_data[date_key] = []
            schedule_data[date_key].append({
                'type': 'Booking',
                'customer_name': booking.name,
                'details': f"Service: {booking.service}, Time: {booking.time}",
                'amount': 0
            })
        except ValueError:
            continue
    
    # Process invoices
    for invoice in all_invoices:
        if invoice.due_date:
            date_key = invoice.due_date.strftime('%Y-%m-%d')
            if date_key not in schedule_data:
                schedule_data[date_key] = []
            schedule_data[date_key].append({
                'type': 'Invoice',
                'customer_name': invoice.customer_name,
                'appointment_time': invoice.appointment_time, # <-- ADD THIS LINE
                'details': f"Invoice: {invoice.invoice_number}, Total: ₹{invoice.total_amount:,.2f}, Due: ₹{invoice.due_amount:,.2f}",
                'amount': invoice.total_amount
            })
    print("DEBUG schedule_data:", schedule_data)

    return render_template('admin_invoices.html',
                            invoices=invoices,
                            total_revenue=total_revenue,
                            revenue_data=revenue_data,
                            schedule_data=schedule_data,
                            datetime=datetime)
@app.route('/admin/invoices/backup')
@login_required
def backup_invoices_route():
    if session.get('role') != 'admin':
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('login'))
    backup_invoices()
    flash('Invoices backup created successfully in both local and project backup folders.', 'success')
    return redirect(url_for('manage_invoices'))

@app.route('/admin/delete_invoice/<invoice_id>', methods=['POST'])
@login_required
def delete_invoice(invoice_id):
    invoice = Invoice.query.get_or_404(invoice_id)
    try:
        # First, delete all services associated with the invoice
        InvoiceService.query.filter_by(invoice_id=invoice.id).delete()
        # Then, delete the invoice itself
        db.session.delete(invoice)
        db.session.commit()
        flash('Invoice deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting invoice: {str(e)}', 'danger')
    return redirect(url_for('manage_invoices'))

# Route to edit an existing invoice
@app.route('/edit_invoice/<invoice_id>', methods=['GET', 'POST'])
@login_required
def edit_invoice(invoice_id):
    invoice = Invoice.query.get_or_404(invoice_id)
    if request.method == 'POST':
        # Update invoice details from the form
        invoice.customer_name = request.form['customer_name']
        invoice.customer_address = request.form['customer_address']
        invoice.customer_phone = request.form.get('customer_phone')
        due_date_str = request.form.get('due_date')
        invoice.due_date = datetime.strptime(due_date_str, '%Y-%m-%d') if due_date_str else None
        invoice.appointment_time = request.form.get('appointment_time')

        # Calculate total, advance, and due amounts
        service_descriptions = request.form.getlist('service_description[]')
        service_amounts = request.form.getlist('service_amount[]')
        total_amount = sum(float(amount) for amount in service_amounts if amount)
        advance_amount = float(request.form.get('advance_amount', 0))
        due_amount = total_amount - advance_amount
        
        invoice.total_amount = total_amount
        invoice.advance_amount = advance_amount
        invoice.due_amount = due_amount
        
        # Clear existing services and add new ones
        InvoiceService.query.filter_by(invoice_id=invoice.id).delete()
        for desc, amount in zip(service_descriptions, service_amounts):
            if desc and amount:
                new_service = InvoiceService(invoice_id=invoice.id, description=desc, amount=float(amount))
                db.session.add(new_service)
        
        db.session.commit()
        flash('Invoice updated successfully!', 'success')
        return redirect(url_for('manage_invoices'))

    return render_template('edit_invoice.html', invoice=invoice, services=invoice.services)

@app.route('/admin/view_invoice/<invoice_id>')
@login_required
def view_invoice(invoice_id):
    invoice = Invoice.query.get(invoice_id)
    if not invoice:
        flash('Invoice not found.', 'danger')
        return redirect(url_for('manage_invoices'))
    
    # Fetch services linked to this invoice via the relationship
    services = invoice.services
    
    return render_template('view_invoice.html', invoice=invoice, services=services)

@app.route('/invoice/<invoice_id>')
def view_public_invoice(invoice_id):
    invoice = Invoice.query.get(invoice_id)
    if not invoice:
        return "Invoice not found", 404

    # Fetch services linked to this invoice via the relationship
    services = invoice.services

    return render_template('view_invoice.html', invoice=invoice, services=services)

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
@app.route('/bulk_delete_gallery', methods=['POST'])
@login_required
def bulk_delete_gallery():
    if session.get('role') != 'admin':
        flash("Unauthorized", "danger")
        return redirect(url_for('gallery'))

    ids = request.form.getlist('selected_images')
    if not ids:
        flash("No images selected", "warning")
        return redirect(url_for('gallery'))

    images = GalleryImage.query.filter(GalleryImage.id.in_(ids)).all()

    deleted = 0
    import cloudinary.uploader
    for img in images:
        # Prefer stored public_id; fall back to extracting from URL
        pid = cloudinary_public_id_from_url(img.url)

        try:
            if pid:
                cloudinary.uploader.destroy(pid)
        except Exception as e:
            # If Cloudinary deletion fails, we still remove DB record to keep UI clean.
            # (Optional) flash a warning if you want.
            print("Cloudinary deletion error:", e)

        db.session.delete(img)
        deleted += 1

    db.session.commit()
    flash(f"{deleted} image(s) deleted", "success")
    return redirect(url_for('gallery'))


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

            if file and allowed_file(file.filename):
                try:
                    # Upload to Cloudinary inside "site1/gallery_uploads"
                    upload_result = cloudinary.uploader.upload(
                        file,
                        folder="site1/gallery_uploads"
                    )
                    image_url = upload_result.get('secure_url')

                    # Save URL to Neon DB
                    new_image = GalleryImage(url=image_url, filename=file.filename)
                    db.session.add(new_image)

                    uploaded_count += 1
                except Exception as e:
                    flash(f'Error uploading "{file.filename}": {e}', 'warning')
                    skipped_count += 1
            else:
                flash(f'Skipped "{file.filename}": Allowed image types are png, jpg, jpeg, gif', 'warning')
                skipped_count += 1

        db.session.commit()

        if uploaded_count > 0:
            flash(f'{uploaded_count} image(s) successfully uploaded to Cloudinary!', 'success')
        if skipped_count > 0:
            flash(f'{skipped_count} image(s) skipped.', 'info')

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

from flask import (
    Flask, render_template, request, redirect, url_for,
    session, flash, make_response, send_from_directory, send_file, jsonify
)

@app.route('/admin/update_invoice_payment', methods=['POST'])
@login_required
def update_invoice_payment():
    invoice_id = request.json.get('invoice_id')
    if not invoice_id:
        return jsonify({'status': 'error', 'message': 'Invoice ID is required'}), 400
    
    invoice = Invoice.query.get(invoice_id)
    if not invoice:
        return jsonify({'status': 'error', 'message': 'Invoice not found'}), 404
    
    invoice.due_amount = 0.0
    try:
        db.session.commit()
        return jsonify({'status': 'success', 'message': 'Invoice updated successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500
    
@app.route('/admin/set_invoice_due_amount', methods=['POST'])
@login_required
def set_invoice_due_amount():
    invoice_id = request.json.get('invoice_id')
    new_amount = request.json.get('new_amount')

    if not invoice_id or new_amount is None:
        return jsonify({'status': 'error', 'message': 'Invoice ID and new amount are required'}), 400

    try:
        new_amount = float(new_amount)
    except (ValueError, TypeError):
        return jsonify({'status': 'error', 'message': 'Invalid amount provided'}), 400

    invoice = Invoice.query.get(invoice_id)
    if not invoice:
        return jsonify({'status': 'error', 'message': 'Invoice not found'}), 404

    invoice.due_amount = new_amount
    try:
        db.session.commit()
        return jsonify({'status': 'success', 'message': f'Invoice due amount updated to ₹{new_amount:.2f}'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500

# Prevent cached pages for admin panel after logout (no change)
@app.after_request
def no_cache(response):
    response.headers['Cache-Control'] = 'no-store'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response


# -----------------------------------------------------------------------------
# MOUPRIYA RENTAL BUSINESS MODULE
# Separate rental tables and workspace; existing makeup bookings/invoices remain.
# -----------------------------------------------------------------------------
class RentalProduct(db.Model):
    __tablename__ = 'rental_products'
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(40), unique=True, nullable=False)
    name = db.Column(db.String(160), nullable=False)
    category = db.Column(db.String(80), nullable=False)
    description = db.Column(db.Text)
    size_details = db.Column(db.String(160))
    rental_price = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    refundable_deposit = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    rental_days = db.Column(db.Integer, nullable=False, default=3)
    image_url = db.Column(db.String(700))  # legacy primary image; retained for existing products
    badge = db.Column(db.String(60))
    status = db.Column(db.String(20), nullable=False, default='Active')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class RentalProductImage(db.Model):
    __tablename__ = 'rental_product_images'
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('rental_products.id', ondelete='CASCADE'), nullable=False, index=True)
    image_url = db.Column(db.String(900), nullable=False)
    public_id = db.Column(db.String(300))
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class RentalOrder(db.Model):
    __tablename__ = 'rental_orders'
    id = db.Column(db.Integer, primary_key=True)
    order_code = db.Column(db.String(40), unique=True, nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('rental_products.id'), nullable=False)
    customer_name = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(30), nullable=False)
    email = db.Column(db.String(120))
    event_date = db.Column(db.Date, nullable=False)
    pickup_date = db.Column(db.Date, nullable=False)
    return_date = db.Column(db.Date, nullable=False)
    message = db.Column(db.Text)
    rental_price = db.Column(db.Numeric(10, 2), nullable=False)
    refundable_deposit = db.Column(db.Numeric(10, 2), nullable=False)
    status = db.Column(db.String(24), nullable=False, default='Enquiry')
    deposit_status = db.Column(db.String(24), nullable=False, default='Not received')
    return_condition = db.Column(db.String(30), default='Not returned')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    product = db.relationship('RentalProduct', backref=db.backref('orders', lazy=True))


RentalProduct.gallery_images = db.relationship('RentalProductImage', backref='product', lazy=True, cascade='all, delete-orphan', order_by='RentalProductImage.sort_order')

def ensure_rental_tables():
    # Additive rental-only schema setup; existing makeup tables and records are untouched.
    db.create_all()
    db.session.execute(text("ALTER TABLE rental_products ADD COLUMN IF NOT EXISTS badge VARCHAR(60)"))
    db.session.commit()

@app.route('/rent')
def rental_catalogue():
    ensure_rental_tables()
    category = request.args.get('category', '').strip()
    query = RentalProduct.query.filter_by(status='Active')
    if category:
        query = query.filter_by(category=category)
    products = query.order_by(RentalProduct.created_at.desc()).all()
    for item in products:
        item.gallery_urls = [x.image_url for x in sorted(item.gallery_images, key=lambda x: x.sort_order)]
        if item.image_url and item.image_url not in item.gallery_urls: item.gallery_urls.insert(0, item.image_url)
    categories = [r[0] for r in db.session.query(RentalProduct.category).filter_by(status='Active').distinct().order_by(RentalProduct.category).all()]
    return render_template('rental_catalogue.html', products=products, categories=categories, selected_category=category)


@app.route('/rent/product/<int:product_id>')
def rental_product_detail(product_id):
    ensure_rental_tables()

    product = RentalProduct.query.filter_by(
        id=product_id,
        status='Active'
    ).first_or_404()

    product.gallery_urls = [
        x.image_url
        for x in sorted(product.gallery_images, key=lambda x: x.sort_order)
    ]

    if product.image_url and product.image_url not in product.gallery_urls:
        product.gallery_urls.insert(0, product.image_url)

    # Open the photograph selected by the customer on the catalogue.
    selected_image_index = request.args.get('image', default=0, type=int)

    if not product.gallery_urls:
        selected_image_index = 0
    else:
        selected_image_index = max(
            0,
            min(selected_image_index, len(product.gallery_urls) - 1)
        )

    return render_template(
        'rental_product.html',
        product=product,
        selected_image_index=selected_image_index
    )

@app.route('/rent/enquire/<int:product_id>', methods=['POST'])
def rental_enquiry(product_id):
    ensure_rental_tables()
    product = RentalProduct.query.filter_by(id=product_id, status='Active').first_or_404()
    try:
        name = request.form.get('customer_name', '').strip()
        phone = request.form.get('phone', '').strip()
        event_date = datetime.strptime(request.form.get('event_date', ''), '%Y-%m-%d').date()
        pickup_date = datetime.strptime(request.form.get('pickup_date', ''), '%Y-%m-%d').date()
        return_date = datetime.strptime(request.form.get('return_date', ''), '%Y-%m-%d').date()
        if not name or not phone or pickup_date > return_date or event_date < pickup_date:
            raise ValueError('Please check your name, phone and dates.')
        # Enquiry is not a confirmed booking. Admin confirms availability manually.
        order = RentalOrder(
            order_code='MR-' + uuid.uuid4().hex[:8].upper(), product_id=product.id,
            customer_name=name, phone=phone, email=request.form.get('email','').strip() or None,
            event_date=event_date, pickup_date=pickup_date, return_date=return_date,
            message=request.form.get('message','').strip(), rental_price=product.rental_price,
            refundable_deposit=product.refundable_deposit, status='Enquiry')
        db.session.add(order); db.session.commit()
        flash('Your rental enquiry has been received. Our team will contact you to confirm availability. Reference: ' + order.order_code, 'success')
        return redirect(url_for('rental_product_detail', product_id=product.id))
    except ValueError as exc:
        flash(str(exc), 'danger')
    except Exception:
        db.session.rollback()
        app.logger.exception('Rental enquiry could not be saved')
        flash('We could not save the enquiry. Please try again or contact us on WhatsApp.', 'danger')
    return redirect(url_for('rental_product_detail', product_id=product.id))

@app.route('/admin/rentals')
@login_required
def rental_admin_dashboard():
    if session.get('role') != 'admin':
        flash('Please sign in as administrator.', 'warning'); return redirect(url_for('login'))
    ensure_rental_tables()
    products = RentalProduct.query.order_by(RentalProduct.created_at.desc()).all()
    orders = RentalOrder.query.order_by(RentalOrder.created_at.desc()).limit(100).all()
    return render_template('rental_admin.html', products=products, orders=orders)

@app.route('/admin/rentals/backup')
@login_required
def rental_data_backup():

    if session.get('role') != 'admin':
        flash('Administrator access required.', 'danger')
        return redirect(url_for('login'))

    ensure_rental_tables()

    products = RentalProduct.query.order_by(
        RentalProduct.id.asc()
    ).all()

    orders = RentalOrder.query.order_by(
        RentalOrder.id.asc()
    ).all()

    payload = {
        'backup_type': 'Moupriya rental data',
        'created_at_utc': datetime.utcnow().isoformat(),

        'products': [
            {
                'id': p.id,
                'code': p.code,
                'name': p.name,
                'category': p.category,
                'description': p.description,
                'size_details': p.size_details,
                'rental_price': float(p.rental_price or 0),
                'refundable_deposit': float(
                    p.refundable_deposit or 0
                ),
                'rental_days': p.rental_days,
                'image_url': p.image_url,
                'badge': p.badge,
                'status': p.status,
                'created_at': (
                    p.created_at.isoformat()
                    if p.created_at else None
                )
            }
            for p in products
        ],

        'orders': [
            {
                'id': o.id,
                'order_code': o.order_code,
                'product_id': o.product_id,
                'product_name': (
                    o.product.name if o.product else None
                ),
                'customer_name': o.customer_name,
                'phone': o.phone,
                'email': o.email,
                'event_date': o.event_date.isoformat(),
                'pickup_date': o.pickup_date.isoformat(),
                'return_date': o.return_date.isoformat(),
                'message': o.message,
                'rental_price': float(o.rental_price or 0),
                'refundable_deposit': float(
                    o.refundable_deposit or 0
                ),
                'status': o.status,
                'deposit_status': o.deposit_status,
                'return_condition': o.return_condition,
                'created_at': (
                    o.created_at.isoformat()
                    if o.created_at else None
                )
            }
            for o in orders
        ]
    }

    filename = (
        'moupriya_rental_backup_'
        + datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        + '.json'
    )

    data = json.dumps(
        payload,
        ensure_ascii=False,
        indent=2
    ).encode('utf-8')

    return send_file(
        BytesIO(data),
        mimetype='application/json',
        as_attachment=True,
        download_name=filename
    )

@app.route('/admin/rentals/product/save', methods=['POST'])
@login_required
def rental_product_save():
    if session.get('role') != 'admin': return redirect(url_for('login'))
    ensure_rental_tables()
    try:
        product_id = request.form.get('product_id', type=int)
        product = RentalProduct.query.get(product_id) if product_id else RentalProduct()
        if not product:
            flash('Product not found.', 'danger'); return redirect(url_for('rental_admin_dashboard'))
        code = request.form.get('code','').strip().upper()
        name = request.form.get('name','').strip()
        category = request.form.get('category','').strip()
        if not code or not name or not category: raise ValueError('Product code, name and category are required.')
        product.code=code; product.name=name; product.category=category
        product.description=request.form.get('description','').strip()
        product.size_details=request.form.get('size_details','').strip()
        product.rental_price=float(request.form.get('rental_price') or 0)
        product.refundable_deposit=float(request.form.get('refundable_deposit') or 0)
        product.rental_days=max(1, int(request.form.get('rental_days') or 3))
        product.status=request.form.get('status','Active')
        product.badge=request.form.get('badge','').strip()[:60] or None
        photos=request.files.getlist('images')
        photos=[f for f in photos if f and f.filename]
        if photos:
            if not all(allowed_file(f.filename) for f in photos):
                raise ValueError('Please upload only JPG, PNG or WEBP image files.')
            if not all(os.getenv(k) for k in ('CLOUDINARY_CLOUD_NAME','CLOUDINARY_API_KEY','CLOUDINARY_API_SECRET')):
                raise ValueError('Cloudinary is not configured. Check the existing Cloudinary environment variables.')
            if not product_id: db.session.add(product); db.session.flush()
            from PIL import Image, ImageOps
            for index, photo in enumerate(photos):
                image = Image.open(photo.stream)
                image = ImageOps.exif_transpose(image).convert('RGB')
                image.thumbnail((1800, 1800), Image.Resampling.LANCZOS)
                buffer = BytesIO(); image.save(buffer, format='WEBP', quality=82, method=6)
                buffer.seek(0)
                result=cloudinary.uploader.upload(buffer, folder='moupriya/rentals', resource_type='image',
                    format='webp', quality='auto:good',
                    transformation=[{'width': 1600, 'height': 1600, 'crop': 'limit'}])
                gallery=RentalProductImage(product_id=product.id, image_url=result.get('secure_url'),
                    public_id=result.get('public_id'), sort_order=RentalProductImage.query.filter_by(product_id=product.id).count())
                db.session.add(gallery)
                if not product.image_url: product.image_url=result.get('secure_url')
        if not product_id: db.session.add(product)
        db.session.commit(); flash('Rental product saved successfully.', 'success')
    except ValueError as exc:
        db.session.rollback(); flash(str(exc), 'danger')
    except Exception as exc:
        db.session.rollback(); app.logger.exception('Rental product save failed')
        flash('Could not save product. Check that the product code is unique and Cloudinary is configured.', 'danger')
    return redirect(url_for('rental_admin_dashboard'))

@app.route('/admin/rentals/product/<int:product_id>/edit')
@login_required
def rental_product_edit(product_id):
    if session.get('role') != 'admin': return redirect(url_for('login'))
    ensure_rental_tables()
    product = RentalProduct.query.get_or_404(product_id)
    product.gallery_urls = [x.image_url for x in sorted(product.gallery_images, key=lambda x: x.sort_order)]
    if product.image_url and product.image_url not in product.gallery_urls: product.gallery_urls.insert(0, product.image_url)
    return render_template('rental_product_edit.html', product=product)


@app.route('/admin/rentals/product/<int:product_id>/image/<int:image_id>/delete', methods=['POST'])
@login_required
def rental_product_image_delete(product_id, image_id):
    if session.get('role') != 'admin':
        flash('Administrator access required.', 'danger')
        return redirect(url_for('login'))

    ensure_rental_tables()

    product = RentalProduct.query.get_or_404(product_id)

    # image_id = 0 means the old/legacy primary image.
    if image_id == 0:
        if not product.image_url:
            flash('No primary image found.', 'warning')
            return redirect(url_for('rental_product_edit', product_id=product.id))

        # Remove the image reference from this product.
        # Legacy images may not have a Cloudinary public_id.
        product.image_url = None
        db.session.commit()

        flash('Primary image removed from this product.', 'success')
        return redirect(url_for('rental_product_edit', product_id=product.id))

    # Find the selected gallery image and ensure it belongs to this product.
    image = RentalProductImage.query.filter_by(
        id=image_id,
        product_id=product.id
    ).first_or_404()

    old_image_url = image.image_url
    public_id = image.public_id

    # Delete the Cloudinary asset when its public_id is available.
    cloudinary_deleted = False

    if public_id:
        try:
            result = cloudinary.uploader.destroy(
                public_id,
                resource_type='image',
                invalidate=True
            )
            cloudinary_deleted = result.get('result') == 'ok'
        except Exception:
            app.logger.exception(
                'Cloudinary image deletion failed for %s', public_id
            )

    # Remove the image record from the database.
    db.session.delete(image)

    # If this was the primary image, select another gallery image.
    if product.image_url == old_image_url:
        next_image = RentalProductImage.query.filter_by(
            product_id=product.id
        ).filter(
            RentalProductImage.id != image.id
        ).order_by(
            RentalProductImage.sort_order
        ).first()

        product.image_url = next_image.image_url if next_image else None

    db.session.commit()

    if public_id and cloudinary_deleted:
        flash('Image removed from the product and Cloudinary.', 'success')
    elif public_id:
        flash(
            'Image removed from the product, but Cloudinary deletion '
            'could not be confirmed. Please check Cloudinary.',
            'warning'
        )
    else:
        flash(
            'Image removed from the product. No Cloudinary public ID '
            'was available, so the stored Cloudinary file may remain.',
            'warning'
        )

    return redirect(url_for('rental_product_edit', product_id=product.id))

@app.route('/admin/rentals/product/<int:product_id>/status', methods=['POST'])
@login_required
def rental_product_status(product_id):
    if session.get('role') != 'admin': return redirect(url_for('login'))
    ensure_rental_tables()
    product=RentalProduct.query.get_or_404(product_id)
    product.status='Archived' if product.status == 'Active' else 'Active'
    db.session.commit(); flash('Product status updated.', 'success')
    return redirect(url_for('rental_admin_dashboard'))

@app.route('/admin/rentals/order/<int:order_id>/update', methods=['POST'])
@login_required
def rental_order_update(order_id):
    if session.get('role') != 'admin': return redirect(url_for('login'))
    ensure_rental_tables()
    order=RentalOrder.query.get_or_404(order_id)
    allowed_status={'Enquiry','Confirmed','Ready for pickup','Rented','Returned','Cancelled'}
    allowed_deposit={'Not received','Received','Refunded','Partially retained'}
    status=request.form.get('status'); deposit=request.form.get('deposit_status')
    if status in allowed_status:
        if status in {'Confirmed','Ready for pickup','Rented'}:
            conflict = RentalOrder.query.filter(
                RentalOrder.product_id == order.product_id,
                RentalOrder.id != order.id,
                RentalOrder.status.in_(['Confirmed','Ready for pickup','Rented']),
                RentalOrder.pickup_date <= order.return_date,
                RentalOrder.return_date >= order.pickup_date
            ).first()
            if conflict:
                flash('Cannot confirm: this product overlaps with ' + conflict.order_code + '.', 'danger')
                return redirect(url_for('rental_admin_dashboard'))
        order.status=status
    if deposit in allowed_deposit: order.deposit_status=deposit
    order.return_condition=request.form.get('return_condition','Not returned')[:30]
    db.session.commit(); flash('Rental order updated.', 'success')
    return redirect(url_for('rental_admin_dashboard'))


if __name__ == '__main__':
    if os.environ.get("FLASK_ENV") == "development":
        with app.app_context():
            db.create_all()

    app.run(debug=True, host='0.0.0.0', port=5000)
