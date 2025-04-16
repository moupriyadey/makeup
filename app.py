from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file
from markupsafe import Markup

from flask_mail import Mail, Message
from flask_paginate import Pagination
import json
import os
import uuid
from io import BytesIO
import qrcode
from dotenv import load_dotenv

app = Flask(__name__)
app.secret_key = 'your_secret_key'

# ===== Flask Mail Configuration =====
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'covcorresl@gmail.com'  # Your Gmail address
app.config['MAIL_PASSWORD'] = 'cmam wswb irws bjor'  # App password generated from Google

mail = Mail(app)

# Load environment variables from .env file
load_dotenv()

# ===== Routes =====

@app.route('/')
def home():
    return render_template('index.html')


@app.route('/submit', methods=['POST'])
def submit():
    name = request.form['name']
    email = request.form['email']
    service = request.form['service']
    date = request.form['date']
    time = request.form['time']

    appointment_id = str(uuid.uuid4())

    # Email Confirmation
    msg = Message(
        subject="Appointment Confirmation - Mou's Nail & Makeup",
        sender=app.config['MAIL_USERNAME'],
        recipients=[email]
    )
    msg.body = f"""Dear {name},

Your appointment for {service} has been booked successfully!

📅 Date: {date}
🕒 Time: {time}

We look forward to glamming you up! 💄✨

Warm regards,  
Mou's Nail & Makeup Team
"""
    mail.send(msg)

    new_booking = {
        "id": appointment_id,
        "name": name,
        "email": email,
        "service": service,
        "date": date,
        "time": time,
        "status": "Pending"
    }

    try:
        with open('bookings.json', 'r+') as f:
            data = json.load(f)
            data.append(new_booking)
            f.seek(0)
            json.dump(data, f, indent=2)
    except FileNotFoundError:
        with open('bookings.json', 'w') as f:
            json.dump([new_booking], f, indent=2)

    return render_template('thank_you.html', name=name)


@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        if username == 'admin' and password == 'admin123':
            session['admin_logged_in'] = True
            return redirect(url_for('admin_panel'))
        else:
            flash('Invalid username or password')

    return render_template('admin_login.html')


@app.route('/admin/panel')
def admin_panel():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))

    try:
        with open('bookings.json', 'r') as f:
            bookings = json.load(f)
    except FileNotFoundError:
        bookings = []

    return render_template('admin_panel.html', bookings=bookings)


@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    return redirect(url_for('home'))


# ===== UPI Payment =====

def generate_upi_qr(payment_amount, upi_id):
    upi_link = f"upi://pay?pa={upi_id}&pn=Mou's Nail & Makeup&mc=1234&tid=1234567890&tn=Payment+for+Appointment&am={payment_amount}&cu=INR"
    img = qrcode.make(upi_link)
    img_io = BytesIO()
    img.save(img_io, 'PNG')
    img_io.seek(0)
    return img_io


@app.route('/payment/<appointment_id>', methods=['GET'])
def payment(appointment_id):
    payment_amount = 500  # Example
    upi_id = "your_upi_id@upi"
    qr_image = generate_upi_qr(payment_amount, upi_id)
    return send_file(qr_image, mimetype='image/png')


@app.route('/confirm_payment/<appointment_id>', methods=['GET'])
def confirm_payment(appointment_id):
    try:
        with open('bookings.json', 'r') as f:
            bookings = json.load(f)

        appointment = next((b for b in bookings if b["id"] == appointment_id), None)
        if appointment:
            msg = Message(
                'Payment Confirmation - Mou\'s Nail & Makeup',
                sender=app.config['MAIL_USERNAME'],
                recipients=[appointment['email']]
            )
            msg.body = f"Dear {appointment['name']},\n\nYour payment has been successfully received. Your appointment is confirmed for {appointment['date']} at {appointment['time']}.\n\nThank you!"
            mail.send(msg)

            appointment['status'] = 'Confirmed'
            with open('bookings.json', 'w') as f:
                json.dump(bookings, f, indent=2)

            return render_template('payment_success.html', appointment_id=appointment_id)
        else:
            return "Appointment not found", 404
    except FileNotFoundError:
        return "Bookings file not found", 404


# ===== Admin Dashboard with Filters & Pagination =====

@app.route('/admin/dashboard', methods=['GET'])
def admin_dashboard():
    search_query = request.args.get('search', '')
    status_filter = request.args.get('status', '')
    date_filter = request.args.get('date', '')
    page = request.args.get('page', 1, type=int)

    try:
        with open('bookings.json', 'r') as f:
            bookings = json.load(f)
    except FileNotFoundError:
        bookings = []

    filtered_bookings = [b for b in bookings if
                         (not search_query or search_query.lower() in b['name'].lower() or search_query.lower() in b['service'].lower()) and
                         (not status_filter or b.get('status') == status_filter) and
                         (not date_filter or b['date'] == date_filter)]

    per_page = 10
    start = (page - 1) * per_page
    end = start + per_page
    paginated_bookings = filtered_bookings[start:end]
    pagination = Pagination(page=page, total=len(filtered_bookings), per_page=per_page, css_framework='bootstrap4')

    return render_template('admin_dashboard.html', bookings=paginated_bookings, pagination=pagination)


@app.route('/update_status/<int:appointment_id>/<status>', methods=['POST'])
def update_status(appointment_id, status):
    try:
        with open('bookings.json', 'r+') as f:
            bookings = json.load(f)

        appointment = next((b for b in bookings if b["id"] == appointment_id), None)
        if appointment:
            appointment['status'] = status
            f.seek(0)
            json.dump(bookings, f, indent=2)
            return '', 200
        else:
            return 'Appointment not found', 404
    except FileNotFoundError:
        return 'Bookings file not found', 404


if __name__ == '__main__':
    app.run(debug=True)

