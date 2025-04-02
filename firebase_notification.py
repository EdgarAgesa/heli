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
            error_msg = f"Missing Firebase environment variables: {', '.join(missing_vars)}"
            logger.error(error_msg)
            raise ValueError(error_msg)

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
        logger.info("✅ Firebase initialized successfully")
        
    except ValueError as e:
        error_msg = f"Firebase configuration error: {str(e)}"
        logger.error(error_msg)
        logger.error("Please ensure all Firebase environment variables are set in your deployment environment.")
        raise
    except Exception as e:
        error_msg = f"Error initializing Firebase: {str(e)}"
        logger.error(error_msg)
        raise

def generate_fcm_token():
    """Generate a unique FCM token"""
    return str(uuid.uuid4())

def send_notification_to_user(user_fcm_token, title, body, data=None):
    if not user_fcm_token:
        current_app.logger.warning("No FCM token provided for user notification")
        return False

    message = messaging.Message(
        notification=messaging.Notification(
            title=title,
            body=body,
        ),
        token=user_fcm_token,
        data=data or {}
    )
    try:
        response = messaging.send(message)
        current_app.logger.info(f"Notification sent to user: {response}")
        return True
    except Exception as e:
        current_app.logger.error(f"Error sending user notification: {str(e)}")
        return False

def send_notification_to_topic(topic, title, body, data=None):
    message = messaging.Message(
        notification=messaging.Notification(
            title=title,
            body=body,
        ),
        topic=topic,
        data=data or {}
    )
    try:
        response = messaging.send(message)
        current_app.logger.info(f"Notification sent to topic {topic}: {response}")
        return True
    except Exception as e:
        current_app.logger.error(f"Error sending topic notification: {str(e)}")
        return False

def subscribe_to_topic(tokens, topic):
    try:
        response = messaging.subscribe_to_topic(tokens, topic)
        current_app.logger.info(f"Subscribed to topic {topic}: {response.success_count} successes")
        return response
    except Exception as e:
        current_app.logger.error(f"Error subscribing to topic: {str(e)}")
        return None