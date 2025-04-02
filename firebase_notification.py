import firebase_admin
from firebase_admin import credentials, messaging
from flask import current_app
import uuid
import os
from dotenv import load_dotenv
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

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

def initialize_firebase(app):
    """Initialize Firebase with credentials from environment variables"""
    global firebase_initialized
    
    try:
        # Log which environment variables are missing
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
        firebase_config = {
            "type": get_required_env_var("FIREBASE_TYPE"),
            "project_id": get_required_env_var("FIREBASE_PROJECT_ID"),
            "private_key_id": get_required_env_var("FIREBASE_PRIVATE_KEY_ID"),
            "private_key": get_required_env_var("FIREBASE_PRIVATE_KEY").replace("\\n", "\n"),
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
        logger.info("✅ Firebase initialized successfully")
        
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
        response = messaging.send(message)
        logger.info(f"Notification sent to user: {response}")
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
        response = messaging.send(message)
        logger.info(f"Notification sent to topic {topic}: {response}")
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
        logger.info(f"Subscribed to topic {topic}: {response.success_count} successes")
        return response
    except Exception as e:
        logger.error(f"Error subscribing to topic: {str(e)}")
        return None