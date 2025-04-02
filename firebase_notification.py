import firebase_admin
from firebase_admin import credentials, messaging
from flask import current_app
import uuid
import os
from dotenv import load_dotenv
import logging
import json
import base64

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
try:
    env_path = os.path.join(os.getcwd(), '.env')
    if os.path.exists(env_path):
        load_dotenv(env_path, override=True)
    else:
        env_path = os.path.join(os.path.dirname(os.getcwd()), '.env')
        if os.path.exists(env_path):
            load_dotenv(env_path, override=True)
        else:
            logger.error("Could not find .env file in current or parent directory")
except Exception as e:
    logger.error(f"Error loading .env file: {str(e)}")

# Flag to track Firebase initialization
firebase_initialized = False

def get_required_env_var(var_name):
    """Get a required environment variable or raise an error"""
    value = os.getenv(var_name)
    if not value:
        error_msg = f"Missing required environment variable: {var_name}"
        logger.error(error_msg)
        raise ValueError(error_msg)
    return value

def format_private_key(private_key):
    """Format the private key to ensure proper newline handling"""
    if not private_key:
        logger.error("Private key is empty")
        return None
    
    try:
        # Remove any existing quotes and whitespace
        private_key = private_key.strip().strip('"').strip("'")
        
        # If the key is base64 encoded, decode it
        if not private_key.startswith('-----BEGIN PRIVATE KEY-----'):
            try:
                decoded_key = base64.b64decode(private_key).decode('utf-8')
                if decoded_key.startswith('-----BEGIN PRIVATE KEY-----'):
                    private_key = decoded_key
            except Exception:
                pass
        
        # Replace literal \n with actual newlines
        private_key = private_key.replace('\\n', '\n')
        
        # Split into lines and clean up
        lines = [line.strip() for line in private_key.split('\n') if line.strip()]
        
        # If we only have the markers, try to extract the key content
        if len(lines) <= 2:
            start_idx = private_key.find('-----BEGIN PRIVATE KEY-----')
            end_idx = private_key.find('-----END PRIVATE KEY-----')
            
            if start_idx != -1 and end_idx != -1:
                content = private_key[start_idx + len('-----BEGIN PRIVATE KEY-----'):end_idx].strip()
                if content:
                    chunks = [content[i:i+64] for i in range(0, len(content), 64)]
                    private_key = '-----BEGIN PRIVATE KEY-----\n' + '\n'.join(chunks) + '\n-----END PRIVATE KEY-----'
                else:
                    logger.error("No key content found between BEGIN and END markers")
                    return None
            else:
                logger.error("Could not find BEGIN or END markers in the key")
                return None
        
        # Ensure proper line breaks
        if '\n' not in private_key:
            chunks = [private_key[i:i+64] for i in range(0, len(private_key), 64)]
            private_key = '\n'.join(chunks)
        
        # Ensure the key starts and ends with proper markers
        if not private_key.startswith('-----BEGIN PRIVATE KEY-----'):
            private_key = '-----BEGIN PRIVATE KEY-----\n' + private_key
        if not private_key.endswith('-----END PRIVATE KEY-----'):
            private_key = private_key + '\n-----END PRIVATE KEY-----'
        
        # Validate key content
        lines = private_key.split('\n')
        if len(lines) <= 2:
            logger.error("Private key is missing content between BEGIN and END markers")
            return None
            
        # Check if the key content looks valid (should be base64-like)
        key_content = ''.join(lines[1:-1])  # Exclude BEGIN and END markers
        if not all(c in 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=' for c in key_content):
            logger.error("Private key content contains invalid characters")
            return None
            
        return private_key
        
    except Exception as e:
        logger.error(f"Error formatting private key: {str(e)}")
        return None

def initialize_firebase(app):
    """Initialize Firebase with credentials from environment variables"""
    global firebase_initialized
    
    try:
        required_vars = [
            "FIREBASE_TYPE",
            "FIREBASE_PROJECT_ID",
            "FIREBASE_PRIVATE_KEY_ID",
            "FIREBASE_PRIVATE_KEY",
            "FIREBASE_CLIENT_EMAIL",
            "FIREBASE_CLIENT_ID",
            "FIREBASE_AUTH_URI",
            "FIREBASE_TOKEN_URI",
            "FIREBASE_AUTH_PROVIDER_X509_CERT_URL",
            "FIREBASE_CLIENT_X509_CERT_URL"
        ]
        
        missing_vars = [var for var in required_vars if not os.getenv(var)]
        if missing_vars:
            logger.warning(f"Firebase not initialized: Missing environment variables: {', '.join(missing_vars)}")
            logger.warning("Firebase notifications will be disabled")
            return

        # Get all required environment variables
        private_key = get_required_env_var("FIREBASE_PRIVATE_KEY")
        formatted_key = format_private_key(private_key)
        
        if not formatted_key:
            logger.error("Failed to format private key correctly")
            return

        firebase_config = {
            "type": get_required_env_var("FIREBASE_TYPE"),
            "project_id": get_required_env_var("FIREBASE_PROJECT_ID"),
            "private_key_id": get_required_env_var("FIREBASE_PRIVATE_KEY_ID"),
            "private_key": formatted_key,
            "client_email": get_required_env_var("FIREBASE_CLIENT_EMAIL"),
            "client_id": get_required_env_var("FIREBASE_CLIENT_ID"),
            "auth_uri": get_required_env_var("FIREBASE_AUTH_URI"),
            "token_uri": get_required_env_var("FIREBASE_TOKEN_URI"),
            "auth_provider_x509_cert_url": get_required_env_var("FIREBASE_AUTH_PROVIDER_X509_CERT_URL"),
            "client_x509_cert_url": get_required_env_var("FIREBASE_CLIENT_X509_CERT_URL")
        }
        
        # Initialize with the credentials
        cred = credentials.Certificate(firebase_config)
        firebase_admin.initialize_app(cred)
        firebase_initialized = True
        logger.info("Firebase initialized successfully")
        
    except Exception as e:
        logger.warning(f"Firebase not initialized: {str(e)}")
        logger.warning("Firebase notifications will be disabled")

def generate_fcm_token():
    """Generate a unique FCM token"""
    return str(uuid.uuid4())

def send_notification_to_user(user_fcm_token, title, body, data=None):
    """Send notification to a specific user"""
    if not firebase_initialized:
        logger.warning("Firebase not initialized. Notification not sent.")
        return False

    if not user_fcm_token:
        logger.warning("No FCM token provided for user notification")
        return False

    try:
        message = messaging.Message(
            notification=messaging.Notification(
                title=title,
                body=body,
            ),
            token=user_fcm_token,
            data=data or {}
        )
        messaging.send(message)
        return True
    except Exception as e:
        logger.error(f"Error sending user notification: {str(e)}")
        return False

def send_notification_to_topic(topic, title, body, data=None):
    """Send notification to a topic"""
    if not firebase_initialized:
        logger.warning("Firebase not initialized. Topic notification not sent.")
        return False

    try:
        message = messaging.Message(
            notification=messaging.Notification(
                title=title,
                body=body,
            ),
            topic=topic,
            data=data or {}
        )
        messaging.send(message)
        return True
    except Exception as e:
        logger.error(f"Error sending topic notification: {str(e)}")
        return False

def subscribe_to_topic(tokens, topic):
    """Subscribe tokens to a topic"""
    if not firebase_initialized:
        logger.warning("Firebase not initialized. Topic subscription not performed.")
        return None

    try:
        response = messaging.subscribe_to_topic(tokens, topic)
        return response
    except Exception as e:
        logger.error(f"Error subscribing to topic: {str(e)}")
        return None