from flask import Flask, render_template, request, redirect, flash
from flask_sqlalchemy import SQLAlchemy
import smtplib, ssl
from email.message import EmailMessage

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///appointments.db'
app.config['SECRET_KEY'] = 'secret'
db = SQLAlchemy(app)

class Appointment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    email = db.Column(db.String(100))
    date = db.Column(db.String(20))
    time = db.Column(db.String(10))

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/book', methods=['POST'])
def book():
    name = request.form['name']
    email = request.form['email']
    date = request.form['date']
    time = request.form['time']

    # Check if slot is already booked
    existing = Appointment.query.filter_by(date=date, time=time).first()
    if existing:
        flash('Selected time slot is already booked. Please choose another.', 'danger')
        return redirect('/')

    # Book the slot
    appt = Appointment(name=name, email=email, date=date, time=time)
    db.session.add(appt)
    db.session.commit()

    send_email(name, email, date, time)
    flash('Appointment booked and confirmation email sent!', 'success')
    return redirect('/')

def send_email(name, email, date, time):
    msg = EmailMessage()
    msg['Subject'] = 'Appointment Confirmation'
    msg['From'] = 'your-email@example.com'  # Replace with your email
    msg['To'] = email
    msg.set_content(f'Hi {name},\n\nYour appointment for {date} at {time} has been confirmed.\n\nThank you!')

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL('smtp.gmail.com', 465, context=context) as server:
            server.login('covcorres@gmail.com', 'mpvx cbqu lgsd khsb')  # Replace with your credentials
            server.send_message(msg)
    except Exception as e:
        print('Email failed:', e)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
