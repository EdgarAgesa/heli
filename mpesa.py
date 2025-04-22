import requests
import json
import base64
import datetime
import time
import logging
from requests.exceptions import RequestException, Timeout

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants
REQUEST_TIMEOUT = 30  # seconds
MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds
MAX_VERIFICATION_ATTEMPTS = 15  # Try for up to 2 minutes (24*5s)
VERIFICATION_RETRY_DELAY = 5    # seconds

# M-Pesa credentials
CONSUMER_KEY = 'AvnO2hFOvgnTjC3DhjjsPvSZg43wx2pKR7mppwnEpXcofgXq'
CONSUMER_SECRET = '79BL7sZjAfsK6ffS7NzgOpnglJhS11Vh2FAaxleIZRkaKXMfQ2l9qbk0R39CuOrD'
SHORTCODE = '174379'
PASSKEY = 'bfb279f9aa9bdbcf158e97dd71a467cd2e0c893059b10f78e6b72ada1ed2c919'
CALLBACK_URL = 'https://mydomain.com/path'
ACCOUNT_REFERENCE = 'DejAir'
TRANSACTION_DESC = 'Payment for DejAir'

def get_mpesa_access_token():
    """Get M-Pesa access token with retry mechanism"""
    url = 'https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials'
    auth = base64.b64encode(f'{CONSUMER_KEY}:{CONSUMER_SECRET}'.encode()).decode()
    
    for attempt in range(MAX_RETRIES):
        try:
            logger.info(f"Attempting to get M-Pesa access token (attempt {attempt + 1}/{MAX_RETRIES})")
            response = requests.get(url, headers={'Authorization': f'Basic {auth}'}, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            token = response.json()['access_token']
            logger.info("Successfully obtained M-Pesa access token")
            return token
        except Timeout:
            logger.warning(f"Timeout getting access token (attempt {attempt + 1}/{MAX_RETRIES})")
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY * (attempt + 1))
            else:
                raise Exception("Failed to get access token after multiple attempts")
        except RequestException as e:
            logger.error(f"Error getting access token: {str(e)}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY * (attempt + 1))
            else:
                raise Exception(f"Failed to get access token: {str(e)}")

def generate_password():
    """Generate M-Pesa password"""
    timestamp = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
    data_to_encode = f"{SHORTCODE}{PASSKEY}{timestamp}"
    return base64.b64encode(data_to_encode.encode()).decode(), timestamp

def format_phone_number(phone):
    """Format phone number for M-Pesa"""
    # Remove any non-digit characters
    phone = ''.join(filter(str.isdigit, phone))
    
    # Add country code if not present
    if not phone.startswith('254'):
        if phone.startswith('0'):
            phone = '254' + phone[1:]
        else:
            phone = '254' + phone
    
    logger.info(f"Formatted phone number: {phone}")
    return phone

def initiate_mpesa_payment(amount, phone_number, business_short_code=SHORTCODE, callback_url=CALLBACK_URL):
    """Initiate M-Pesa payment with retry mechanism"""
    try:
        logger.info(f"Initiating M-Pesa payment for amount {amount} to phone {phone_number}")
        access_token = get_mpesa_access_token()
        password, timestamp = generate_password()
        formatted_phone = format_phone_number(phone_number)
        
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }
        
        payload = {
            'BusinessShortCode': business_short_code,
            'Password': password,
            'Timestamp': timestamp,
            'TransactionType': 'CustomerPayBillOnline',
            'Amount': int(amount),
            'PartyA': formatted_phone,
            'PartyB': business_short_code,
            'PhoneNumber': formatted_phone,
            'CallBackURL': callback_url,
            'AccountReference': ACCOUNT_REFERENCE,
            'TransactionDesc': TRANSACTION_DESC
        }
        
        logger.info(f"M-Pesa payment payload: {json.dumps(payload, indent=2)}")
        
        url = 'https://sandbox.safaricom.co.ke/mpesa/stkpush/v1/processrequest'
        
        for attempt in range(MAX_RETRIES):
            try:
                logger.info(f"Sending payment request to M-Pesa (attempt {attempt + 1}/{MAX_RETRIES})")
                response = requests.post(url, json=payload, headers=headers, timeout=REQUEST_TIMEOUT)
                logger.info(f"M-Pesa response status: {response.status_code}")
                logger.info(f"M-Pesa response content: {response.text}")
                response.raise_for_status()
                result = response.json()
                if result.get('ResponseCode') != '0':
                    error_msg = result.get('ResponseDescription', 'Unknown M-Pesa error')
                    logger.error(f"M-Pesa error: {error_msg}")
                    raise Exception(f"M-Pesa error: {error_msg}")
                logger.info(f"Payment initiated successfully: {json.dumps(result, indent=2)}")
                return result
            except Timeout:
                logger.warning(f"Timeout initiating payment (attempt {attempt + 1}/{MAX_RETRIES})")
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_DELAY * (attempt + 1))
                else:
                    raise Exception("Payment initiation timed out after multiple attempts")
            except RequestException as e:
                logger.error(f"Error initiating payment: {str(e)}")
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_DELAY * (attempt + 1))
                else:
                    raise Exception(f"Failed to initiate payment: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error in initiate_mpesa_payment: {str(e)}")
        raise

def verify_mpesa_payment(checkout_request_id):
    """Verify M-Pesa payment with improved processing state handling"""
    try:
        logger.info(f"Verifying M-Pesa payment for checkout request ID: {checkout_request_id}")
        access_token = get_mpesa_access_token()
        password, timestamp = generate_password()
        
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }
        
        payload = {
            'BusinessShortCode': SHORTCODE,
            'Password': password,
            'Timestamp': timestamp,
            'CheckoutRequestID': checkout_request_id
        }
        
        logger.info(f"M-Pesa verification payload: {json.dumps(payload, indent=2)}")
        
        url = 'https://sandbox.safaricom.co.ke/mpesa/stkpushquery/v1/query'
        
        for attempt in range(MAX_RETRIES):
            try:
                logger.info(f"Sending verification request to M-Pesa (attempt {attempt + 1}/{MAX_RETRIES})")
                response = requests.post(url, json=payload, headers=headers, timeout=REQUEST_TIMEOUT)
                
                logger.info(f"M-Pesa verification response status: {response.status_code}")
                logger.info(f"M-Pesa verification response content: {response.text}")
                
                # Handle 500 responses with processing message
                if response.status_code == 500:
                    error_data = response.json()
                    if error_data.get('errorCode') == '500.001.1001':
                        logger.info("Transaction is still being processed")
                        return {
                            'status': 'pending',
                            'details': 'Transaction is being processed',
                            'response': error_data
                        }
                
                response.raise_for_status()
                result = response.json()
                
                # Handle successful verification
                if result.get('ResultCode') == '0':
                    logger.info("Payment successfully verified")
                    return {
                        'status': 'success',
                        'details': 'Payment confirmed',
                        'response': result
                    }
                # Handle failed payment
                elif result.get('ResultCode') in ['1032', '1037']:  # 1032 = request cancelled, 1037 = timeout
                    logger.warning(f"Payment failed with code {result.get('ResultCode')}")
                    return {
                        'status': 'failed',
                        'details': result.get('ResultDesc'),
                        'response': result
                    }
                # Handle other error cases
                else:
                    logger.error(f"Payment verification error: {result.get('ResultDesc')}")
                    return {
                        'status': 'error',
                        'details': result.get('ResultDesc', 'Unknown error'),
                        'response': result
                    }
                    
            except Timeout:
                logger.warning(f"Timeout verifying payment (attempt {attempt + 1}/{MAX_RETRIES})")
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_DELAY * (attempt + 1))
                else:
                    return {
                        'status': 'error',
                        'details': 'Payment verification timed out'
                    }
            except RequestException as e:
                logger.error(f"Error verifying payment: {str(e)}")
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_DELAY * (attempt + 1))
                else:
                    return {
                        'status': 'error',
                        'details': str(e)
                    }
    except Exception as e:
        logger.error(f"Unexpected error in verify_mpesa_payment: {str(e)}")
        return {
            'status': 'error',
            'details': str(e)
        }

def wait_for_payment_confirmation(checkout_request_id, max_attempts=MAX_VERIFICATION_ATTEMPTS, delay=VERIFICATION_RETRY_DELAY):
    """Wait for payment confirmation with better state handling"""
    logger.info(f"Waiting for payment confirmation for checkout request ID: {checkout_request_id}")
    
    for attempt in range(max_attempts):
        try:
            logger.info(f"Payment verification attempt {attempt + 1}/{max_attempts}")
            result = verify_mpesa_payment(checkout_request_id)
            
            # Handle different status cases
            if result.get('status') == 'success':
                logger.info("Payment confirmed successfully")
                return result
            elif result.get('status') == 'pending':
                logger.info(f"Payment still processing, waiting {delay} seconds before retry")
                time.sleep(delay)
                continue
            elif result.get('status') == 'failed':
                logger.warning(f"Payment failed: {result.get('details')}")
                return result
            else:
                logger.error(f"Payment verification error: {result.get('details')}")
                if attempt < max_attempts - 1:
                    time.sleep(delay)
                    continue
                else:
                    return {
                        'status': 'error',
                        'details': 'Maximum attempts reached without confirmation'
                    }
        except Exception as e:
            logger.error(f"Error checking payment status: {str(e)}")
            if attempt < max_attempts - 1:
                time.sleep(delay)
                continue
            else:
                return {
                    'status': 'error',
                    'details': str(e)
                }
    
    logger.warning("Payment status could not be confirmed after maximum attempts")
    return {
        'status': 'failed',
        'details': 'Maximum attempts reached without confirmation'
    }

# Example usage of initiate_mpesa_payment and database integration
def process_payment(amount, phone_number, db, Payment):
    """Process payment and save to database"""
    try:
        formatted_phone = format_phone_number(phone_number)
        mpesa_response = initiate_mpesa_payment(amount, formatted_phone)
        checkout_request_id = mpesa_response.get('CheckoutRequestID')
        payment = Payment(
            amount=amount,
            phone_number=formatted_phone,
            checkout_request_id=checkout_request_id,
            status='pending'
        )
        db.session.add(payment)
        db.session.commit()
        logger.info("Payment record saved to database")
        return payment
    except Exception as e:
        logger.error(f"Error processing payment: {str(e)}")
        raise

def confirm_payment(payment_id, Payment):
    """Confirm payment status and update database"""
    try:
        payment = Payment.query.get(payment_id)
        checkout_request_id = payment.checkout_request_id  # This is the string from M-Pesa, not an integer!
        payment_verification = wait_for_payment_confirmation(checkout_request_id)
        return payment_verification
    except Exception as e:
        logger.error(f"Error confirming payment: {str(e)}")
        raise
