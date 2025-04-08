import firebase_admin
from firebase_admin import credentials, messaging
from flask import current_app
import json

class NotificationService:
    def __init__(self):
        try:
            # Initialize Firebase Admin SDK
            cred = credentials.Certificate(current_app.config['FIREBASE_CREDENTIALS'])
            firebase_admin.initialize_app(cred)
        except ValueError:
            # App already initialized
            pass

    def send_notification(self, token, title, body, data=None):
        """
        Send a notification to a specific device using FCM token.
        
        Args:
            token (str): FCM token of the target device
            title (str): Notification title
            body (str): Notification body
            data (dict, optional): Additional data to send with the notification
        
        Returns:
            bool: True if notification was sent successfully, False otherwise
        """
        try:
            message = messaging.Message(
                notification=messaging.Notification(
                    title=title,
                    body=body
                ),
                data=data or {},
                token=token
            )
            
            response = messaging.send(message)
            current_app.logger.info(f"Successfully sent notification: {response}")
            return True
            
        except Exception as e:
            current_app.logger.error(f"Failed to send notification: {str(e)}")
            return False

    def send_multicast_notification(self, tokens, title, body, data=None):
        """
        Send a notification to multiple devices using FCM tokens.
        
        Args:
            tokens (list): List of FCM tokens
            title (str): Notification title
            body (str): Notification body
            data (dict, optional): Additional data to send with the notification
        
        Returns:
            tuple: (success_count, failure_count)
        """
        try:
            message = messaging.MulticastMessage(
                notification=messaging.Notification(
                    title=title,
                    body=body
                ),
                data=data or {},
                tokens=tokens
            )
            
            response = messaging.send_multicast(message)
            current_app.logger.info(f"Successfully sent multicast notification: {response}")
            return response.success_count, response.failure_count
            
        except Exception as e:
            current_app.logger.error(f"Failed to send multicast notification: {str(e)}")
            return 0, len(tokens)

    def send_topic_notification(self, topic, title, body, data=None):
        """
        Send a notification to all devices subscribed to a topic.
        
        Args:
            topic (str): Topic name
            title (str): Notification title
            body (str): Notification body
            data (dict, optional): Additional data to send with the notification
        
        Returns:
            bool: True if notification was sent successfully, False otherwise
        """
        try:
            message = messaging.Message(
                notification=messaging.Notification(
                    title=title,
                    body=body
                ),
                data=data or {},
                topic=topic
            )
            
            response = messaging.send(message)
            current_app.logger.info(f"Successfully sent topic notification: {response}")
            return True
            
        except Exception as e:
            current_app.logger.error(f"Failed to send topic notification: {str(e)}")
            return False

    def subscribe_to_topic(self, tokens, topic):
        """
        Subscribe devices to a topic.
        
        Args:
            tokens (list): List of FCM tokens
            topic (str): Topic name
        
        Returns:
            tuple: (success_count, failure_count)
        """
        try:
            response = messaging.subscribe_to_topic(tokens, topic)
            current_app.logger.info(f"Successfully subscribed to topic: {response}")
            return response.success_count, response.failure_count
            
        except Exception as e:
            current_app.logger.error(f"Failed to subscribe to topic: {str(e)}")
            return 0, len(tokens)

    def unsubscribe_from_topic(self, tokens, topic):
        """
        Unsubscribe devices from a topic.
        
        Args:
            tokens (list): List of FCM tokens
            topic (str): Topic name
        
        Returns:
            tuple: (success_count, failure_count)
        """
        try:
            response = messaging.unsubscribe_from_topic(tokens, topic)
            current_app.logger.info(f"Successfully unsubscribed from topic: {response}")
            return response.success_count, response.failure_count
            
        except Exception as e:
            current_app.logger.error(f"Failed to unsubscribe from topic: {str(e)}")
            return 0, len(tokens) 