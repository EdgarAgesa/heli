from flask_restful import Resource
from flask import request, jsonify
from models import db, ChatMessage, Booking, Client, Admin
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime
from firebase_notification import send_notification_to_user, send_notification_to_topic

def is_admin(user_id):
    return Admin.query.filter_by(id=user_id).first() is not None

class ChatResource(Resource):
    @jwt_required()
    def get(self, booking_id):
        """Get chat messages for a booking"""
        current_user_id = get_jwt_identity()
        booking = Booking.query.get_or_404(booking_id)
        
        # Verify authorization
        if not is_admin(current_user_id) and booking.client_id != current_user_id:
            return {"error": "Unauthorized"}, 403
            
        # Mark messages as read
        ChatMessage.query.filter_by(
            booking_id=booking_id,
            is_read=False
        ).filter(
            ChatMessage.sender_id != current_user_id
        ).update({"is_read": True})
        
        booking.has_unread_messages = False
        db.session.commit()
        
        messages = ChatMessage.query.filter_by(booking_id=booking_id)\
            .order_by(ChatMessage.created_at.asc()).all()
            
        return jsonify([message.to_dict() for message in messages])

    @jwt_required()
    def post(self, booking_id):
        """Send a chat message"""
        current_user_id = get_jwt_identity()
        booking = Booking.query.get_or_404(booking_id)
        
        # Verify authorization
        if not is_admin(current_user_id) and booking.client_id != current_user_id:
            return {"error": "Unauthorized"}, 403
            
        data = request.get_json()
        if not data or 'message' not in data:
            return {"error": "Message is required"}, 400
            
        # Determine sender type
        sender_type = 'admin' if is_admin(current_user_id) else 'client'
        
        # Create message
        message = ChatMessage(
            booking_id=booking_id,
            sender_id=current_user_id,
            sender_type=sender_type,
            message=data['message']
        )
        
        # Update booking's last message info
        booking.last_message_at = datetime.utcnow()
        booking.has_unread_messages = True
        
        db.session.add(message)
        db.session.commit()
        
        # Send notification
        if sender_type == 'client':
            # Notify admins
            send_notification_to_topic(
                topic="admin_notifications",
                title="New Negotiation Message",
                body=f"New message for booking #{booking_id}",
                data={
                    "type": "chat_message",
                    "booking_id": str(booking_id)
                }
            )
        else:
            # Notify client
            client = Client.query.get(booking.client_id)
            if client and client.fcm_token:
                send_notification_to_user(
                    user_fcm_token=client.fcm_token,
                    title="New Message",
                    body=f"New message for booking #{booking_id}",
                    data={
                        "type": "chat_message",
                        "booking_id": str(booking_id)
                    }
                )
        
        return message.to_dict(), 201

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