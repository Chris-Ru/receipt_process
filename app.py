import os

from flask import Flask, request, render_template, redirect, url_for, flash, jsonify, send_file, abort
from werkzeug.utils import secure_filename
from werkzeug.security import check_password_hash, generate_password_hash

from sqlalchemy import create_engine, Column, Integer, String, Float, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship

from receipt_processor import *

app = Flask(__name__)
app.secret_key = os.urandom(24)  # Generates a random 24-byte secret key

# Password setup (replace 'your_password' with your actual password)
password_hash = generate_password_hash('asdf1234')

# File upload configuration
UPLOAD_FOLDER = 'uploads/'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

DATABASE_URL = 'sqlite:///receipts.db'

Base = declarative_base()

class Item(Base):
    __tablename__ = 'items'
    item_id = Column(Integer, primary_key=True)
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
    filepath = Column(String)

    items = relationship("Item", back_populates="receipt", cascade="all, delete-orphan")

engine = create_engine(DATABASE_URL)
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)
session = Session()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'files' not in request.files:
        flash('No files part')
        return redirect(request.url)
    
    files = request.files.getlist('files')
    
    if len(files) == 0 or all(file.filename == '' for file in files):
        flash('No selected files')
        return redirect(request.url)
    
    for file in files:
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)

            # Debugging: print the path to ensure it's correct
            print("Saving file to:", file_path)

            try:
                file.save(file_path)
            except Exception as e:
                flash(f"Error saving file: {str(e)}")
                return redirect(request.url)

            # Process the uploaded file with OCR
            process_receipt(file_path)
        else:
            flash(f"Invalid file type: {file.filename}")
            return redirect(request.url)

    flash("All files processed successfully!")
    return redirect(url_for('show_receipts'))

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


# API for displaying image
@app.route('/file/<path:filepath>')
def serve_file(filepath):
    # Construct the full file path
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filepath)

    # Check if the file exists
    if not os.path.exists(file_path):
        flash('File not found')
        return redirect(url_for('show_receipts'))

    # Serve the file directly
    return send_file(file_path)

@app.route('/display_image/<int:receipt_id>')
def display_image(receipt_id):
    # Get the image URL based on the ID
    print("URL = " + get_filepath_by_id(receipt_id))
    image_url = "http://127.0.0.1:5000/file/" + get_filepath_by_id(receipt_id)
    
    if not image_url:
        abort(404)  # Return 404 error if no URL is found
    
    file_extension = image_url.split('.')[-1].lower()  # Get file extension
    # Pass the image URL to the template
    return render_template('display_receipt.html', image_url=image_url, file_extension=file_extension)

if __name__ == '__main__':
    app.run(debug=True)
