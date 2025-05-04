from flask import Flask, render_template, request, send_from_directory, redirect, url_for, session
import os
import re
import mysql.connector
from fpdf import FPDF
import io
import base64
import matplotlib.pyplot as plt
import datetime
from twilio.rest import Client
from random import *
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'fallback_secret_key')  # Required for session handling

# Twilio Credentials from environment
account_sid = os.environ.get('TWILIO_ACCOUNT_SID')
auth_token = os.environ.get('TWILIO_AUTH_TOKEN')
twilio_from = os.environ.get('TWILIO_PHONE_NUMBER')
client = Client(account_sid, auth_token)

# Dictionary to store OTPs temporarily
otp_store = {}

# MySQL Database Configuration from environment
db_config = {
    'host': os.environ.get('DB_HOST', 'localhost'),
    'user': os.environ.get('DB_USER', 'root'),
    'password': os.environ.get('DB_PASSWORD', ''),
    'database': os.environ.get('DB_NAME', 'parking_system')
}

# Initialize parking slots
slots = {i: None for i in range(1, 21)}  # None indicates available slots
daily_revenue = 0  # Tracks total revenue for the day in ₹

# Directory for storing generated PDFs
PDF_DIR = "generated_pdfs"
os.makedirs(PDF_DIR, exist_ok=True)

def get_db_connection():
    """Create a new connection to the MySQL database with error handling."""
    try:
        conn = mysql.connector.connect(**db_config)
        return conn
    except mysql.connector.Error as err:
        print(f"Database connection failed: {err}")
        raise

def calculate_cost(hours):
    """Calculate parking cost based on hours."""
    if hours <= 1:
        return 50
    elif 1 < hours <= 5:
        return 50 + (hours - 1) * 40
    else:
        return 210 + (hours - 5) * 30


def generate_pdf(slot, car_number, check_in, check_out, cost):
    """Generate PDF receipt for the checkout."""
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)

    pdf.cell(200, 10, txt="Car Parking Receipt", ln=True, align="C")
    pdf.ln(10)

    pdf.cell(200, 10, txt=f"Slot: {slot}", ln=True)
    pdf.cell(200, 10, txt=f"Car Number: {car_number}", ln=True)
    pdf.cell(200, 10, txt=f"Check-in Time: {check_in.strftime('%Y-%m-%d %H:%M:%S')}", ln=True)
    pdf.cell(200, 10, txt=f"Check-out Time: {check_out.strftime('%Y-%m-%d %H:%M:%S')}", ln=True)
    pdf.cell(200, 10, txt=f"Total Duration: {int((check_out - check_in).total_seconds() // 3600)} hour(s)", ln=True)
    pdf.cell(200, 10, txt=f"Total Cost: INR {cost}", ln=True)

    pdf_name = f"{PDF_DIR}/receipt_{car_number}_{slot}.pdf"
    pdf.output(pdf_name)
    return pdf_name

def load_parked_slots():
    """Load parked slot data from the database into the slots dictionary."""
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    cursor.execute("SELECT slot, car_number FROM user_info WHERE check_out IS NULL")
    parked_data = cursor.fetchall()
    cursor.close()
    connection.close()
    for data in parked_data:
        slots[data['slot']] = data['car_number']

@app.route('/')
def index():
    load_parked_slots()
    return render_template('index.html', slots=slots)


@app.route('/park', methods=['POST'])
def park_car():
    car_number = request.form['car_number']
    for slot, details in slots.items():
        if details is None:  # Slot available
            check_in_time = datetime.datetime.now()
            slots[slot] = f"{car_number}"  # Simplified display

            # Insert car park info into the database
            connection = get_db_connection()
            cursor = connection.cursor()
            cursor.execute("INSERT INTO user_info (car_number, slot, check_in, date) VALUES (%s, %s, %s, %s)",
                           (car_number, slot, check_in_time, check_in_time.strftime('%Y-%m-%d')))
            connection.commit()
            cursor.close()
            connection.close()

            return f"""
                <script>
                    alert('Slot {slot} has been allotted successfully.');
                    window.location.href = '/';  // Redirect to home page
                </script>
            """

    return """
        <script>
            alert('No available slots. Please try again later.');
            window.location.href = '/';
        </script>
    """



@app.route('/checkout', methods=['POST'])
def checkout_car():
    global daily_revenue
    car_number = request.form['car_number']
    for slot, details in slots.items():
        if details and f"{car_number}" == details:
            # Fetch check-in time from the database
            connection = get_db_connection()
            cursor = connection.cursor(dictionary=True)
            cursor.execute(
                "SELECT check_in FROM user_info WHERE car_number = %s AND slot = %s AND check_out IS NULL",
                (car_number, slot)
            )
            record = cursor.fetchone()
            cursor.close()
            connection.close()

            if not record:
                return """
                    <script>
                        alert('Car not found in the system.');
                        window.location.href = '/';
                    </script>
                """

            check_in_time = record['check_in']
            check_out_time = datetime.datetime.now()

            # Calculate duration and cost
            duration_seconds = (check_out_time - check_in_time).total_seconds()
            hours = int(duration_seconds // 3600)
            minutes = int((duration_seconds % 3600) // 60)
            cost = calculate_cost(hours + (minutes / 60))
            daily_revenue += cost

            # Generate PDF receipt
            pdf_path = generate_pdf(slot, car_number, check_in_time, check_out_time, cost)
            pdf_filename = pdf_path.split('/')[-1]  # Extract just the file name

            # Update the database with checkout details
            connection = get_db_connection()
            cursor = connection.cursor()
            cursor.execute("""
                UPDATE user_info
                SET check_out = %s, cost = %s, pdf_path = %s
                WHERE car_number = %s AND slot = %s AND check_out IS NULL
            """, (check_out_time, cost, pdf_path, car_number, slot))

            # Update the daily_revenue table
            today_date = check_out_time.date()
            cursor.execute("SELECT * FROM daily_revenue WHERE date = %s", (today_date,))
            if cursor.fetchone():
                cursor.execute(
                    "UPDATE daily_revenue SET revenue = revenue + %s WHERE date = %s",
                    (cost, today_date)
                )
            else:
                cursor.execute(
                    "INSERT INTO daily_revenue (date, revenue) VALUES (%s, %s)",
                    (today_date, cost)
                )

            connection.commit()
            cursor.close()
            connection.close()

            # Free the slot
            slots[slot] = None

            return f"""
                <script>
                    alert('Checkout successful! Duration: {hours} hour(s) and {minutes} minute(s). Cost: ₹{cost}.');
                    window.open('/pdf/{pdf_filename}', '_blank');  // Open PDF in new tab
                    setTimeout(function() {{
                        window.location.href = '/';  // Redirect to home page after 2 seconds
                    }}, 2000);
                </script>
            """

    return """
        <script>
            alert('Car not found.');
            window.location.href = '/';
        </script>
    """

@app.route('/pdf/<path:filename>')
def download_pdf(filename):
    """Serve the generated PDF file."""
    return send_from_directory(PDF_DIR, filename, as_attachment=True)

@app.route('/admin', methods=['GET', 'POST'])
def admin_view():
    error_message = None
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT * FROM admin_info WHERE username = %s AND password = %s", (username, password))
        admin = cursor.fetchone()
        cursor.close()
        connection.close()

        if admin:
            booked_slots = {slot: details for slot, details in slots.items() if details}
            available_slots = [slot for slot, details in slots.items() if details is None]

            connection = get_db_connection()
            cursor = connection.cursor(dictionary=True)

            # Fetch daily revenue records
            cursor.execute("SELECT date, revenue FROM daily_revenue ORDER BY date ASC")
            revenue_records = cursor.fetchall()

            # Fetch historical parked data (car number, slot, check-in and check-out times)
            cursor.execute("SELECT car_number, slot, check_in, check_out, cost FROM user_info WHERE check_out IS NOT NULL ORDER BY check_in DESC")
            parked_history = cursor.fetchall()

            # Format datetime fields
            for entry in parked_history:
                if entry['check_in']:
                    entry['check_in'] = entry['check_in'].strftime('%Y-%m-%d %H:%M:%S')
                if entry['check_out']:
                    entry['check_out'] = entry['check_out'].strftime('%Y-%m-%d %H:%M:%S')

            cursor.close()
            # Extract dates and revenues for the graph
            dates = [record['date'] for record in revenue_records]  # Access using the dictionary key
            revenues = [record['revenue'] for record in revenue_records]

            # Create a plot for daily revenue up to today
            plt.figure(figsize=(10, 5))
            plt.plot(dates, revenues, marker='o', linestyle='-', color='b')
            plt.title('Daily Revenue Trend (All Days up to Today)')
            plt.xlabel('Dates')
            plt.ylabel('Revenue (₹)')
            plt.xticks(rotation=45)
            plt.tight_layout()

            # Save the plot as an image
            img = io.BytesIO()
            plt.savefig(img, format='png')
            img.seek(0)
            graph_url = base64.b64encode(img.getvalue()).decode('utf-8')
            plt.close()


            connection.close()

            return render_template('admin_dashboard.html', booked_slots=booked_slots, available_slots=available_slots,
                                   daily_revenue=revenues[-1] if revenues else 0, graph_url=graph_url,
                                   parked_history=parked_history)  # Pass the parked history here
        else:
            error_message = "Invalid username or password. Please try again."

    return render_template('admin_login.html', error=error_message)



@app.route('/signup', methods=['GET', 'POST'])
def signup():

    """Sign up user after OTP verification"""
    phone = session.get('phone')

    if not phone:
        return redirect(url_for('verify_otp'))  # If no phone, go back to OTP

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        # Simplified password validation regex
        password_regex = r"^(?=.*[A-Za-z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{6,}$"

        if not re.match(password_regex, password):
            error = "Password must be at least 6 characters long, include a letter, a special symbol and a number."
            return render_template('signup.html', error=error)

        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute("INSERT INTO admin_info (username, password) VALUES (%s, %s)", (username, password))
        connection.commit()
        cursor.close()
        connection.close()

        session.pop('phone', None)  # Remove phone from session after signup
        return redirect(url_for('admin_view'))
    return render_template('signup.html')

# ----------------------- OTP Verification -----------------------

@app.route('/verify_otp', methods=['GET', 'POST'])
def verify_otp():
    """Take phone number and send OTP"""
    if request.method == 'POST':
        phone = request.form['phone']

        # Generate and store OTP
        res = str(randint(100000, 999999))
        otp_store[phone] = res

        # Send OTP via Twilio
        message = client.messages.create(
            body='Your ParkNGo OTP is: '+res+'. Do not share this OTP with anyone else.',
            from_=twilio_from,
            to= "+919499817172"
        )

        # Store phone in session to pass between pages
        session['phone'] = phone

        return redirect(url_for('enter_otp'))  # Redirect to OTP entry page

    return render_template('verify_otp.html')  # Page to enter phone number

@app.route('/enter_otp', methods=['GET', 'POST'])
def enter_otp():
    """Verify OTP before proceeding to signup"""
    phone = session.get('phone')

    if not phone:
        return redirect(url_for('verify_otp'))  # If phone not found, restart OTP process

    if request.method == 'POST':
        otp_entered = request.form['otp']

        if phone in otp_store and otp_store[phone] == otp_entered.strip():
            del otp_store[phone]  # Clear OTP after successful verification
            return redirect(url_for('signup'))  # Redirect to signup page

        return "Invalid OTP. Please try again.", 400

    return render_template('enter_otp.html', phone=phone)  # Page to enter OTP

if __name__ == '__main__':
    load_parked_slots()
    app.run(debug=True)
