import requests
from datetime import datetime
from requests.auth import HTTPBasicAuth
import base64
import time

MPESA_CONSUMER_KEY = 'AvnO2hFOvgnTjC3DhjjsPvSZg43wx2pKR7mppwnEpXcofgXq'
MPESA_CONSUMER_SECRET = '79BL7sZjAfsK6ffS7NzgOpnglJhS11Vh2FAaxleIZRkaKXMfQ2l9qbk0R39CuOrD'
MPESA_BUSINESS_SHORT_CODE = '174379'
MPESA_PASSKEY = 'bfb279f9aa9bdbcf158e97dd71a467cd2e0c893059b10f78e6b72ada1ed2c919'
MPESA_CALLBACK_URL = 'https://mydomain.com/path'
MPESA_ACCOUNT_REFERENCE = 'DejAir'
MPESA_TRANSACTION_DESC = 'Payment for DejAir'

def get_mpesa_access_token():
    url = "https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials"
    response = requests.get(url, auth=HTTPBasicAuth(MPESA_CONSUMER_KEY, MPESA_CONSUMER_SECRET))
    if response.status_code == 200:
        return response.json()['access_token']
    else:
        raise Exception("Failed to fetch access token")

def generate_password(business_short_code, passkey, timestamp):
    data_to_encode = business_short_code + passkey + timestamp
    encoded_string = base64.b64encode(data_to_encode.encode())
    return encoded_string.decode('utf-8')

def format_phone_number(phone_number):
    if phone_number.startswith('0'):
        return '254' + phone_number[1:]
    elif not phone_number.startswith('254'):
        return '254' + phone_number
    return phone_number

def initiate_mpesa_payment(amount, phone_number):
    phone_number = format_phone_number(phone_number)
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    password = generate_password(MPESA_BUSINESS_SHORT_CODE, MPESA_PASSKEY, timestamp)

    payload = {
        "BusinessShortCode": MPESA_BUSINESS_SHORT_CODE,
        "Password": password,
        "Timestamp": timestamp,
        "TransactionType": "CustomerPayBillOnline",
        "Amount": str(amount), 
        "PartyA": str(phone_number),
        "PartyB": MPESA_BUSINESS_SHORT_CODE,
        "PhoneNumber": str(phone_number),
        "CallBackURL": MPESA_CALLBACK_URL,
        "AccountReference": MPESA_ACCOUNT_REFERENCE,
        "TransactionDesc": MPESA_TRANSACTION_DESC
    }

    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {get_mpesa_access_token()}'
    }

    response = requests.post('https://sandbox.safaricom.co.ke/mpesa/stkpush/v1/processrequest', json=payload, headers=headers)
    return response.json()

def verify_mpesa_payment(checkout_request_id):
    url = "https://sandbox.safaricom.co.ke/mpesa/stkpushquery/v1/query"
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    password = generate_password(MPESA_BUSINESS_SHORT_CODE, MPESA_PASSKEY, timestamp)
    
    payload = {
        "BusinessShortCode": MPESA_BUSINESS_SHORT_CODE,
        "Password": password,
        "Timestamp": timestamp,
        "CheckoutRequestID": checkout_request_id
    }

    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {get_mpesa_access_token()}'
    }

    response = requests.post(url, json=payload, headers=headers)
    return response.json()

def wait_for_payment_confirmation(checkout_request_id, max_retries=10, delay=10):
    for _ in range(max_retries):
        payment_status = verify_mpesa_payment(checkout_request_id)
        result_code = payment_status.get('ResultCode')

        if result_code == '0':
            return {'status': 'confirmed', 'details': payment_status}
        elif result_code is not None:  
            return {'status': 'canceled', 'details': payment_status}

        time.sleep(delay)

    return {'status': 'canceled', 'details': 'Payment status could not be confirmed'}

