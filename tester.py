import re
from datetime import datetime

def convert_to_12_hour_format(time_str):
    """Converts 24-hour format time to 12-hour format with AM/PM."""
    try:
        # Parse the 24-hour format time
        time_obj = datetime.strptime(time_str, '%H:%M')
        # Convert to 12-hour format with AM/PM
        return time_obj.strftime('%I:%M %p')
    except ValueError:
        return None

def extract_date_and_time(text):
    # Define patterns for various date formats
    date_patterns = [
        r'\b(\d{4}/\d{2}/\d{2})\b',    # YYYY/MM/DD
        r'\b(\d{2}/\d{2}/\d{2})\b',    # MM/DD/YY
        r'\b(\d{2}/\d{2}/\d{4})\b',    # MM/DD/YYYY
        r'\b(\d{4}-\d{2}-\d{2})\b',    # YYYY-MM-DD
        r'\b(\d{1,2}/\d{1,2}/\d{2,4})\b'  # MM/DD/YY or DD/MM/YYYY
    ]

    # Define patterns for time formats
    time_patterns = [
        r'\b(\d{2}:\d{2})\b',         # HH:MM (24-hour format)
        r'\b(\d{1,2}:\d{2} [APM]{2})\b' # HH:MM AM/PM (12-hour format)
    ]

    # Extract date
    date_str = None
    for pattern in date_patterns:
        date_match = re.search(pattern, text)
        if date_match:
            date_str = date_match.group(1)
            break
    
    # Extract time
    time_str = None
    for pattern in time_patterns:
        time_match = re.search(pattern, text)
        if time_match:
            time_str = time_match.group(1)
            break

    # Convert 24-hour format to 12-hour format if needed
    if time_str and ':' in time_str and not any(char in time_str for char in ['AM', 'PM']):
        time_str = convert_to_12_hour_format(time_str)
    
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

    return formatted_date, time_str

# Example usage:
text1 = """
ARCO GASOLINE
ARCO AM/PM 42598
41891 RANCHO BERNARD
SAN-DIEGO CA

DATE 8/23/24 19:04

TRAN#9015169

PUMP# 01

SERVICE LEVEL: SELF

PRODUCT; UNLD

GALLONS : 4,591

PRICE/G: $4.359

FUEL SALE $20.01

debitfee $0.35
DEBIT $20.36

FinalSale Receipt
DEBIT $20.36
Payment fron’ Primary
Account

Bayon TRO OTS

Auth #: 181354

Resp Code: 000

Stan: 20678928114
Reference:65777
APPNAME US DEBIT
ALD : AQOOOO0O980840
APP CRYPTOGRAM ;
ARQC B38738/75E6A6A36
B

ENTRY ; Tap

PIN USED

SITE ID: ARCO4259800
1

THANK YOU
FOR CHOOSING ARCO
COMMENTS?
1-800-322-2726

A
"""

text2 = """
YOUR GUEST NUMBER TS
94
IN-N-OUT CARMEL MOUNTAIN
NB? 2 772 2255

‘SPneceUnRIrNNeU ead casey
Cashier: NICOLE BR
Check : 94

1 Db1-Db1 Animal 5.90
1 Lg Neapolitan Shk 3.85 |
COUNTER-Eat In 9.75
TAX 7.75% 16
Amount Due $10.51
Tender Vises, $10.51
Change $.00

CHARGE DETATL.
Card Type: Visa
Account: RRAREAAEAKBO 7()
Capture: Contact less
PIN: Not verified
Auth Code; 092780
Auth Ref; 093b887e~9eda-4bd?-B500- caa lec
hebaf9
Trans #: 2255
AID: ANGOVODGUGO3 1010
AUTH AMT: $10.51
THANK YOU!
QUESTIONS/COMMENTS: Call 800-786-1000

2024-08-15 Lille 12:13 AM
"""

date1, time1 = extract_date_and_time(text1)
date2, time2 = extract_date_and_time(text2)
print("Extracted Date 1:", date1)
print("Extracted Time 1:", time1)
print("Extracted Date 2:", date2)
print("Extracted Time 2:", time2)

# Example values for other fields
store_name1 = "ARCO GASOLINE"
store_name2 = "IN-N-OUT CARMEL MOUNTAIN"
total1 = 20.01
total2 = 10.51
payment_method1 = "Debit"
payment_method2 = "Visa"

print(store_name1, date1, time1, total1, payment_method1)
print(store_name2, date2, time2, total2, payment_method2)
