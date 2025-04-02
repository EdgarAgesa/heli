import firebase_admin
from firebase_admin import credentials, messaging
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize Firebase Admin SDK with credentials from environment variables
cred = credentials.Certificate({
    "type": os.getenv("FIREBASE_TYPE"),
    "project_id": os.getenv("FIREBASE_PROJECT_ID"),
    "private_key_id": os.getenv("FIREBASE_PRIVATE_KEY_ID"),
    "private_key": os.getenv("FIREBASE_PRIVATE_KEY").replace("\\n", "\n"),
    "client_email": os.getenv("FIREBASE_CLIENT_EMAIL"),
    "client_id": os.getenv("FIREBASE_CLIENT_ID"),
    "auth_uri": os.getenv("FIREBASE_AUTH_URI"),
    "token_uri": os.getenv("FIREBASE_TOKEN_URI"),
    "auth_provider_x509_cert_url": os.getenv("FIREBASE_AUTH_PROVIDER_X509_CERT_URL"),
    "client_x509_cert_url": os.getenv("FIREBASE_CLIENT_X509_CERT_URL")
})

firebase_app = firebase_admin.initialize_app(cred)

def send_notification_to_user(user_fcm_token, title, body, data=None):
    """
    Send a notification to a specific user using their FCM token.
    
    Args:
        user_fcm_token (str): The FCM token of the user
        title (str): The notification title
        body (str): The notification body
        data (dict, optional): Additional data to send with the notification
    """
    try:
        message = messaging.Message(
            notification=messaging.Notification(
                title=title,
                body=body
            ),
            data=data or {},
            token=user_fcm_token
        )
        
        response = messaging.send(message)
        print(f"Successfully sent notification: {response}")
        return True, response
        
    except Exception as e:
        print(f"Error sending notification: {str(e)}")
        return False, str(e) 