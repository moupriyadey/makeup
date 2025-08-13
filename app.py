import os
import json
import uuid
import random
from datetime import datetime, timedelta

import cloudinary
import cloudinary.uploader
import cloudinary.api
import pandas as pd  # pip install pandas openpyxl
import qrcode
from dotenv import load_dotenv
from flask import (
    Flask, render_template, request, redirect, url_for,
    session, flash, make_response, send_from_directory, send_file
)
from flask_mail import Mail, Message
from flask_login import (
    LoginManager, UserMixin, login_required, login_user,
    logout_user, current_user
)
from werkzeug.utils import secure_filename
from flask_sqlalchemy import SQLAlchemy

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
    
    # Check for the last invoice from the current year
    last_invoice = Invoice.query.filter(Invoice.invoice_number.ilike(f'%/{current_year_suffix}')).order_by(Invoice.created_at.desc()).first()

    if last_invoice:
        last_number = int(last_invoice.invoice_number.split('/')[1])
        new_number = last_number + 1
    else:
        # Check if the current year is 25 to start at 23, otherwise start at 1
        if current_year_suffix == '25':
            new_number = 23
        else:
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

# Home route
@app.route('/')
def index():
    return render_template('index.html', datetime=datetime)



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
# Admin dashboard - UPDATED FOR DB & REVERTED FOR LOCAL IMAGES
@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    status_filter = request.args.get('status')
    date_filter = request.args.get('date')
    search_filter = request.args.get('search')

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

    query = query.order_by(Booking.created_at.desc())

    page = request.args.get('page', 1, type=int)
    per_page = 10
    paginated_bookings = query.paginate(page=page, per_page=per_page, error_out=False)

    # **CRITICAL FIX: CONVERT DATE STRINGS TO DATETIME OBJECTS**
    # The 'date' column is stored as a string in the DB, so we must convert it
    # to a datetime object before passing it to the template for strftime().
    for booking in paginated_bookings.items:
        try:
            # The date is stored as "DD/MM/YYYY", so we parse it with that format.
            booking.date = datetime.strptime(booking.date, "%d/%m/%Y").date()
        except (ValueError, TypeError) as e:
            # Handle cases where the date string is malformed or None
            print(f"Error converting date for booking {booking.id}: {e}")
            booking.date = None
    # End of critical fix

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
                           gallery_images=gallery_images)
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
            invoice_date=datetime.utcnow()
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
    invoices = Invoice.query.order_by(Invoice.created_at.desc()).all()
    
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
            date_key = invoice.due_date.strftime('%Y-%m-%d')  # Convert to string key
            if date_key not in schedule_data:
                schedule_data[date_key] = []
            schedule_data[date_key].append({
                'type': 'Invoice',
                'customer_name': invoice.customer_name,
                'details': f"Invoice: {invoice.invoice_number}, Total: ₹{invoice.total_amount:,.2f}, Due: ₹{invoice.due_amount:,.2f}",
                'amount': invoice.total_amount
            })
    
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

# Prevent cached pages for admin panel after logout (no change)
@app.after_request
def no_cache(response):
    response.headers['Cache-Control'] = 'no-store'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

if __name__ == '__main__':
    with app.app_context():
        # This will create tables if they don't exist, but will not delete existing data.
        db.create_all()
    app.run(debug=True, host='0.0.0.0', port=5000)