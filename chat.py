from flask import Blueprint, jsonify
from flask_restful import Api, Resource, reqparse
from models import db, ChatMessage, Booking, Client, Admin
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime
from firebase_notification import send_notification_to_user, send_notification_to_topic
import logging

logger = logging.getLogger(__name__)

chat_bp = Blueprint('chat_bp', __name__, url_prefix='/chat')
chat_api = Api(chat_bp)

def is_admin(user_id):
    """Check if the user is an admin by checking if they exist in the Admin table"""
    try:
        # Convert user_id to integer if it's a string
        admin_id = int(user_id) if isinstance(user_id, str) else user_id
        
        # Get the user from the Admin table
        admin = Admin.query.get(admin_id)
        
        # Return True if the user exists in the Admin table
        return admin is not None
    except (ValueError, TypeError):
        logger.error(f"Invalid user_id format: {user_id}")
        return False

chat_args = reqparse.RequestParser()
chat_args.add_argument('message', type=str, required=True, help='Message is required')

class ChatResource(Resource):
    @jwt_required()
    def post(self, booking_id):
        """Send a chat message"""
        data = chat_args.parse_args()
        user_id = get_jwt_identity()
        
        # Verify authorization
        booking = Booking.query.get_or_404(booking_id)
        if not is_admin(user_id) and booking.client_id != int(user_id):
            return {"error": "Unauthorized"}, 403
        
        # Determine if the sender is an admin
        sender_type = 'admin' if is_admin(user_id) else 'client'
        
        # Get sender name
        if sender_type == "admin":
            admin = Admin.query.get(user_id)
            sender_name = admin.name if admin else "Admin"
        else:
            client = Client.query.get(user_id)
            sender_name = client.name if client else "User"
        
        # Create the chat message
        chat_message = ChatMessage(
            booking_id=booking_id,
            sender_id=user_id,
            sender_type=sender_type,
            message=data['message']
        )
        db.session.add(chat_message)
        db.session.commit()
        
        # Send notifications based on sender type
        if sender_type == 'admin':
            # Send notification to client
            client = Client.query.get(booking.client_id)
            if client and client.fcm_token:
                # Ensure all values in notification data are strings
                notification_data = {
                    'type': 'chat_message',
                    'booking_id': str(booking_id),
                    'sender_type': sender_type,
                    'sender_name': sender_name,
                    'message': data['message'],
                    'timestamp': datetime.utcnow().isoformat()
                }
                send_notification_to_user(
                    client.fcm_token,
                    f"New message from {sender_name}",
                    data['message'],
                    notification_data
                )
        else:
            # Send notification to all admins
            # Ensure all values in notification data are strings
            notification_data = {
                'type': 'chat_message',
                'booking_id': str(booking_id),
                'sender_type': sender_type,
                'sender_name': sender_name,
                'message': data['message'],
                'timestamp': datetime.utcnow().isoformat()
            }
            send_notification_to_topic(
                'admin_notifications',
                f"New message from {sender_name}",
                data['message'],
                notification_data
            )
        
        return {
            'message': 'Message sent successfully',
            'chat_message': {
                'id': chat_message.id,
                'booking_id': chat_message.booking_id,
                'sender_id': chat_message.sender_id,
                'sender_type': chat_message.sender_type,
                'sender_name': sender_name,
                'message': chat_message.message,
                'created_at': chat_message.created_at.isoformat()
            }
        }, 201

    @jwt_required()
    def get(self, booking_id):
        """Get chat messages for a booking"""
        user_id = get_jwt_identity()
        
        # Verify authorization
        booking = Booking.query.get_or_404(booking_id)
        if not is_admin(user_id) and booking.client_id != int(user_id):
            return {"error": "Unauthorized"}, 403
        
        # Get chat messages for the booking
        messages = ChatMessage.query.filter_by(booking_id=booking_id).order_by(ChatMessage.created_at).all()
        
        # Format messages with sender names
        formatted_messages = []
        for msg in messages:
            if msg.sender_type == 'admin':
                sender = Admin.query.get(int(msg.sender_id))
                sender_name = sender.name if sender else 'Admin'
            else:
                sender = Client.query.get(int(msg.sender_id))
                sender_name = sender.name if sender else 'Client'
            
            formatted_messages.append({
                'id': msg.id,
                'booking_id': msg.booking_id,
                'sender_id': msg.sender_id,
                'sender_type': msg.sender_type,
                'sender_name': sender_name,
                'message': msg.message,
                'created_at': msg.created_at.isoformat()
            })
        
        return {'messages': formatted_messages}, 200

# Register the resource with the booking_id parameter
chat_api.add_resource(ChatResource, '/<int:booking_id>')

class ChatReadResource(Resource):
    @jwt_required()
    def put(self, booking_id):
        """Mark all messages in a booking as read"""
        current_user_id = get_jwt_identity()
        booking = Booking.query.get_or_404(booking_id)
        
        # Verify authorization
        if not is_admin(current_user_id) and booking.client_id != current_user_id:
            return {"error": "Unauthorized"}, 403
            
        # Mark all unread messages as read
        ChatMessage.query.filter_by(
            booking_id=booking_id,
            is_read=False
        ).filter(
            ChatMessage.sender_id != current_user_id
        ).update({"is_read": True})
        
        booking.has_unread_messages = False
        db.session.commit()
        
        return {"message": "Messages marked as read"}, 200

class NegotiationChatsResource(Resource):
    @jwt_required()
    def get(self):
        """Get all bookings with active negotiations"""
        current_user_id = get_jwt_identity()
        
        # Get all bookings with active negotiations
        if is_admin(current_user_id):
            # Admin sees all bookings with active negotiations
            bookings = Booking.query.filter(
                Booking.negotiation_status.in_(['requested', 'counter_offer'])
            ).order_by(Booking.last_message_at.desc()).all()
        else:
            # Clients only see their own bookings with active negotiations
            bookings = Booking.query.filter(
                Booking.client_id == current_user_id,
                Booking.negotiation_status.in_(['requested', 'counter_offer'])
            ).order_by(Booking.last_message_at.desc()).all()
            
        return jsonify([booking.as_dict() for booking in bookings])

class UnreadChatsResource(Resource):
    @jwt_required()
    def get(self):
        """Get count of unread chat messages for the current user"""
        current_user_id = get_jwt_identity()
        
        # Check if user is admin or client
        is_admin_user = is_admin(current_user_id)
        
        if is_admin_user:
            # For admins, count all unread messages across all bookings
            unread_count = ChatMessage.query.filter_by(
                is_read=False
            ).filter(
                ChatMessage.sender_type == 'client'
            ).count()
        else:
            # For clients, count unread messages in their bookings
            unread_count = ChatMessage.query.join(
                Booking, ChatMessage.booking_id == Booking.id
            ).filter(
                Booking.client_id == current_user_id,
                ChatMessage.is_read == False,
                ChatMessage.sender_type == 'admin'
            ).count()
        
        return jsonify({"count": unread_count}) 