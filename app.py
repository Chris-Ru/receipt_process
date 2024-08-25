import os
import re

from flask import Flask, request, render_template, redirect, url_for, flash
from werkzeug.utils import secure_filename
from werkzeug.security import check_password_hash, generate_password_hash

from datetime import datetime
import datefinder

from sqlalchemy import create_engine, Column, Integer, String, Float, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship

import pytesseract
from pdf2image import convert_from_path
from PIL import Image


app = Flask(__name__)
app.secret_key = os.urandom(24)  # Generates a random 24-byte secret key

# Password setup (replace 'your_password' with your actual password)
password_hash = generate_password_hash('asdf1234')

# File upload configuration
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'pdf'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

DATABASE_URL = 'sqlite:///receipts.db'

Base = declarative_base()

class Item(Base):
    __tablename__ = 'items'
    id = Column(Integer, primary_key=True)
    receipt_id = Column(Integer, ForeignKey('receipts.id'))
    name = Column(String)
    quantity = Column(Integer)
    price = Column(Float)

    receipt = relationship("Receipt", back_populates="items")

class Receipt(Base):
    __tablename__ = 'receipts'
    id = Column(Integer, primary_key=True)
    store_name = Column(String)
    date = Column(String)
    time = Column(String)
    total = Column(Float)
    payment_method = Column(String)

    items = relationship("Item", back_populates="receipt", cascade="all, delete-orphan")

engine = create_engine(DATABASE_URL)
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)
session = Session()

# Function to check allowed file types
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Function to perform OCR on images
def perform_ocr(image):
    text = pytesseract.image_to_string(image)
    return text

# Function to process uploaded files
def process_receipt(file_path):
    extracted_text = ""
    if file_path.lower().endswith('.pdf'):
        # Convert PDF pages to images
        images = convert_from_path(file_path)
        for image in images:
            extracted_text += perform_ocr(image)
    else:
        # Process image files directly
        image = Image.open(file_path)
        extracted_text = perform_ocr(image)

    # print("Extracted Text: ", extracted_text)
    parse_text = parse_receipt(extracted_text)

    # Example: Extracting dummy data (for actual implementation, parse the text)
    store_name = parse_text['store_name']
    date = parse_text['date']
    time = parse_text['time']
    items = parse_text['items']
    total = parse_text['total_due']
    payment_method = parse_text['payment_method']

    # Save to database
    receipt = Receipt(store_name=store_name, date=date, time=time, total=total, payment_method=payment_method)
    # Add items to the receipt
    for item in items:
        item_obj = Item(
            name=item['name'],
            quantity=item['quantity'],
            price=item['price']
        )
        receipt.items.append(item_obj)

    session.add(receipt)
    session.commit()

def parse_date(text):
    # Define patterns for various date formats
    date_patterns = [
        r'\b(\d{4}/\d{2}/\d{2})\b',         # YYYY/MM/DD
        r'\b(\d{2}/\d{2}/\d{2})\b',         # MM/DD/YY
        r'\b(\d{2}/\d{2}/\d{4})\b',         # MM/DD/YYYY (edge case)
        r'\b(\d{4}-\d{2}-\d{2})\b',         # YYYY-MM-DD
        r'\b(\d{1,2}/\d{1,2}/\d{2,4})\b',   # MM/DD/YY or DD/MM/YYYY
        r'\b(\d{1,2}-[A-Za-z]{3}-\d{4})\b'  # DD-MON-YYYY
    ]

    # Extract date
    date_str = None
    for pattern in date_patterns:
        date_match = re.search(pattern, text)
        if date_match:
            date_str = date_match.group(1)
            break
    
    # Format the date
    if date_str:
        try:
            # Try parsing various formats
            for fmt in ('%Y/%m/%d', '%m/%d/%y', '%m/%d/%Y', '%Y-%m-%d', '%m/%d/%y', '%d/%m/%Y'):
                try:
                    date_obj = datetime.strptime(date_str, fmt)
                    formatted_date = date_obj.strftime('%Y-%m-%d')
                    break
                except ValueError:
                    continue
            else:
                formatted_date = None
        except Exception:
            formatted_date = None
    else:
        formatted_date = None

    return formatted_date

def parse_time(text):
    # Define patterns for time formats
    time_patterns = [
        r'\b(\d{1,2}:\d{2} [APM]{2})\b',    # HH:MM AM/PM (12-hour format)
        r'\b(\d{2}:\d{2})\b'                # HH:MM (24-hour format)
        r'\b(\d{1,2}:\d{2}:\d{2} [APM]{2})\b',  # H:MM:SS AM/PM
    ]
    
    # Extract time
    time_str = None
    for pattern in time_patterns:
        time_match = re.search(pattern, text)
        if time_match:
            time_str = time_match.group(1)
            # Check if it's already in AM/PM format
            if 'AM' not in time_str and 'PM' not in time_str:
                # Convert 24-hour format to 12-hour format
                time_str = convert_to_12_hour_format(time_str)
            break
    
    return time_str

def convert_to_12_hour_format(time_str):
    """Converts 24-hour format time to 12-hour format with AM/PM."""
    try:
        # Parse the 24-hour format time
        time_obj = datetime.strptime(time_str, '%H:%M')
        # Convert to 12-hour format with AM/PM
        return time_obj.strftime('%I:%M %p')
    except ValueError:
        return time_str

def find_total(text):
    lines = text.splitlines()
    total = 0.0
    for line in reversed(lines):
        match = re.search(r'[$€£]?\s*(\d+\.\d{2})', line)
        if match:
            total = float(match.group(1))
            break
    return total

def parse_payment_method(text):
    payment_methods = ['Visa', 'MasterCard', 'Amex', 'Debit', 'Credit']
    for method in payment_methods:
        if re.search(method, text, re.IGNORECASE):
            return method
    return "Unknown"

def parse_items(receipt_text):
    # Define a regular expression pattern to match item lines
    item_pattern = re.compile(r'(\d+)\s+([A-Za-z\s\-]+)\s+(\d+\.\d{2})')

    # Find all matches in the receipt text
    matches = item_pattern.findall(receipt_text)

    # Convert matches into a list of dictionaries
    items = []
    for match in matches:
        quantity = int(match[0])
        name = match[1].strip()
        price = float(match[2])
        items.append({
            'name': name,
            'quantity': quantity,
            'price': price
        })
    
    print("Parsed Items: ", items)  # Debug print
    return items

def parse_receipt(text):
    receipt_data = {}

    # Extract Store Name (assuming first uppercase line is store name)
    store_name_match = re.search(r'^([A-Z\s\-]+)$', text, re.MULTILINE)
    receipt_data['store_name'] = store_name_match.group(0).strip() if store_name_match else "Unknown"

    # Extract Date and Time (multiple formats)
    receipt_data['date'] = parse_date(text)
    receipt_data['time'] = parse_time(text)

    # Extract Items (assuming lines with qcuantity, description, and price)
    receipt_data['items'] = parse_items(text)

    # Extract Total Amount
    receipt_data['total_due'] = find_total(text)

    # Extract Payment Method
    receipt_data['payment_method'] = parse_payment_method(text)

    return receipt_data

def update_receipt(receipt_id, store_name=None, date=None, time=None, total=None, payment_method=None):
    try:
        # Fetch the record by its ID
        receipt = session.query(Receipt).filter_by(id=receipt_id).one()

        # Update the fields if new values are provided
        if store_name is not None:
            receipt.store_name = store_name
        if date is not None:
            receipt.date = date
        if time is not None:
            receipt.time = time
        if total is not None:
            receipt.total = total
        if payment_method is not None:
            receipt.payment_method = payment_method

        # Commit the changes to the database
        session.commit()

        print("Receipt updated successfully.")

    except NoResultFound:
        print(f"No receipt found with ID: {receipt_id}")
    except Exception as e:
        print(f"An error occurred: {e}")
        session.rollback()




@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        flash('No file part')
        return redirect(request.url)
    
    file = request.files['file']
    
    if file.filename == '':
        flash('No selected file')
        return redirect(request.url)
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)

        # Process the uploaded file with OCR
        process_receipt(file_path)

        flash("File processed successfully!")
        return redirect(url_for('show_receipts'))
    else:
        flash("Invalid file type.")
        return redirect(request.url)

@app.route('/receipts')
def show_receipts():
    receipts = session.query(Receipt).all()
    return render_template('results.html', receipts=receipts)

@app.route('/delete/', methods=['POST'])
def delete_receipt():
    if request.method == 'POST':
        password = request.form.get('password')
        receipt_id = request.form.get('receipt_id')

    if password is None:
        flash("Error: Password is required.", "error")
        return redirect(url_for('show_receipts'))

    if check_password_hash(password_hash, password):
        receipt = session.query(Receipt).get(receipt_id)
        if receipt:
            # Capture the details of the receipt before deletion
            receipt_details = {
                "store_name": receipt.store_name,
                "date": receipt.date,
                "total": receipt.total
            }
            session.delete(receipt)
            session.commit()
            flash(f"200 Success: Receipt for {receipt_details['store_name']} that took place on {receipt_details['date']} with a total of {receipt_details['total']} was deleted.", "success")
            return redirect(url_for('show_receipts'))
        else:
            flash("Error: Receipt not found.", "error")
            return redirect(url_for('show_receipts'))
    else:
        flash("Error: Unauthorized access.", "error")
        return redirect(url_for('show_receipts'))
    
@app.route('/update_receipt', methods=['POST'])
def update_receipt_endpoint():
    data = request.json
    receipt_id = data.get('id')
    store_name = data.get('store_name')
    date = data.get('date')
    time = data.get('time')
    total = data.get('total')
    payment_method = data.get('payment_method')

    update_receipt(receipt_id, store_name, date, time, total, payment_method)

    return jsonify({"message": "Receipt updated successfully."})


"""
@app.route('/delete/<int:receipt_id>', methods=['POST', 'GET'])
def delete_receipt(receipt_id):
    if request.method == 'POST':
        password = request.form.get('password')
    elif request.method == 'GET':
        password = request.args.get('password')

    if password is None:
        return jsonify({"error": "Password is required."}), 400

    if check_password_hash(password_hash, password):
        print("receipt id is ", receipt_id)
        receipt = session.query(Receipt).get(receipt_id)
        if receipt:
            session.delete(receipt)
            session.commit()
            flash("200 success: Receipt deleted successfully.")
            return redirect(url_for('receipts'))
        else:
            return jsonify({"error": "Receipt not found."}), 404
    else:
        return jsonify({"error": "Unauthorized access."}), 401
"""

if __name__ == '__main__':
    app.run(debug=True)
