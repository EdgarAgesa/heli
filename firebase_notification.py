import firebase_admin
from firebase_admin import credentials, messaging
from flask import current_app
import uuid

# Initialize Firebase
def initialize_firebase(app):
    try:
        # Get path from config
        cred_path = app.config['FIREBASE_CREDENTIALS_PATH']
        
        # Initialize with the correct path
        cred = credentials.Certificate(cred_path)
        firebase_admin.initialize_app(cred)
        app.logger.info("✅ Firebase initialized successfully")
    except Exception as e:
        app.logger.error(f"🔥 Error initializing Firebase: {str(e)}")
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