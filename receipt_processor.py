import cv2
from PIL import Image
import pytesseract
import re
from pdf2image import convert_from_path

pytesseract.pytesseract.tesseract_cmd = '/usr/bin/tesseract'

def convert_pdf_to_images(pdf_path):
    """Convert a PDF file into images (one per page)."""
    images = convert_from_path(pdf_path)
    return images

def preprocess_image(image_path):
    """Preprocess the image for better OCR results."""
    image = cv2.imread(image_path)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY_INV)
    denoised = cv2.medianBlur(thresh, 3)
    return denoised

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
