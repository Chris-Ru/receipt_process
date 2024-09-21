import os
import re
import io
import sqlite3
import PIL.ImageFilter
import cv2
import PIL

from datetime import datetime

import pytesseract
from pdf2image import convert_from_path
from PIL import Image

from app import Receipt, Item, session

pytesseract.pytesseract.tesseract_cmd = '/usr/bin/tesseract'

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'pdf'}

# Function to check allowed file types
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def convert_pdf_to_images(pdf_path):
    """Convert a PDF file into images (one per page)."""
    images = convert_from_path(pdf_path)
    return images

# Function to perform OCR on images
def perform_ocr(image):
    text = pytesseract.image_to_string(image)
    print(text)
    return text

def extract_text(image):
    """Extract text from the preprocessed image using Tesseract OCR."""
    return pytesseract.image_to_string(image)

def parse_receipt(text):
    """Parse relevant information from the extracted text."""
    lines = text.split('\n')

    data = {
        "store_name": None,
        "date": None,
        "items": [],
        "total": None
    }

    for line in lines:
        date_match = re.search(r'\d{1,2}/\d{1,2}/\d{2,4}', line)
        if date_match:
            data["date"] = date_match.group()

        total_match = re.search(r'Total:\s*\$?(\d+\.\d{2})', line, re.IGNORECASE)
        if total_match:
            data["total"] = float(total_match.group(1))

        if data["store_name"] is None:
            data["store_name"] = line.strip()

        item_match = re.search(r'(.+?)\s+\$?(\d+\.\d{2})', line)
        if item_match:
            item = item_match.group(1).strip()
            price = float(item_match.group(2))
            data["items"].append({"item": item, "price": price})

    return data

# Function to process uploaded files
def process_receipt(file_path):
    # Check if the file exists before processing
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"The file does not exist: {file_path}")

    # Your OCR processing code here
    # Example:
    extracted_text = ""
    if file_path.lower().endswith('.pdf'):
        images = convert_from_path(file_path)
        for image in images:
            extracted_text += perform_ocr(image)
    else:
        image = Image.open(file_path)
        extracted_text = perform_ocr(image)

    parse_text = parse_receipt(extracted_text)
    
    # Process and save to the database
    store_name = parse_text.get('store_name', '')
    date = parse_text.get('date', '')
    time = parse_text.get('time', '')
    items = parse_text.get('items', [])
    total = parse_text.get('total_due', '')
    payment_method = parse_text.get('payment_method', '')
    filepath = file_path.strip('uploads/')
    
    receipt = Receipt(store_name=store_name, date=date, time=time, total=total, payment_method=payment_method, filepath=filepath)
    
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
        r'\b(\d{4}/\d{2}/\d{2})\b',           # YYYY/MM/DD
        r'\b(\d{2}/\d{2}/\d{2})\b',           # MM/DD/YY
        r'\b(\d{2}/\d{2}/\d{4})\b',           # MM/DD/YYYY (edge case)
        r'\b(\d{4}-\d{2}-\d{2})\b',           # YYYY-MM-DD
        r'\b(\d{2}/\d{2}/\d{2,4})\b',         # MM/DD/YY or DD/MM/YYYY
        r'\b(\d{2}-[A-Za-z]{3}-\d{2,4})\b',   # DD-MON-YYYY
        r'\b(\d{1,2}\s[A-Za-z]{3}\s\d{4})\b', # DD MON YYYY
    ]

    # Extract date
    date_str = None
    for pattern in date_patterns:
        date_match = re.search(pattern, text)
        if date_match:
            date_str = date_match.group(1)
            # print("######   date_str => ", date_str, '\n')
            break
    
    # Format the date
    if date_str:
        try:
            # Try parsing various formats
            for fmt in ('%Y/%m/%d', '%m/%d/%Y', '%m/%d/%Y', '%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y', '%d-%m-%Y', '%d %m %Y'):
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
        r'\b(\d{1,2}:\d{2}:\d{2}[\w]{1})\b',  # HH:MM:SS A/P
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

def convert_pdf_to_image(pdf_path):
    images = convert_from_path(pdf_path)
    # For simplicity, just use the first page
    image = images[0]
    image_bytes = io.BytesIO()
    image.save(image_bytes, format='JPEG')
    image_bytes.seek(0)
    return image_bytes

def get_filepath_by_id(receipt_id):
    # Connect to the SQLite database
    conn = sqlite3.connect('receipts.db')  # Replace with your actual database file name
    cursor = conn.cursor()
    
    try:
        # SQL query to get the filepath from the receipts table based on the given id
        cursor.execute('SELECT filepath FROM receipts WHERE id = ?', (receipt_id,))
        result = cursor.fetchone()
        
        # If a result is found, return the filepath
        if result:
            return result[0]  # The filepath is in the first column of the result
        
    except sqlite3.Error as e:
        print(f"An error occurred: {e}")
    
    finally:
        # Close the database connection
        conn.close()
    
    # If no result is found, return None
    return None

