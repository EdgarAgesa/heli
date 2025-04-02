from flask_restful import Resource
from flask import request, jsonify, current_app
from datetime import datetime
from models import db, Booking, Payment, Client, Admin, NegotiationHistory
from flask_jwt_extended import jwt_required, get_jwt_identity
from mpesa import initiate_mpesa_payment, wait_for_payment_confirmation
from firebase_notification import send_notification_to_user, send_notification_to_topic
from email_utils import send_payment_receipt_email, send_booking_confirmation_email
import re

def is_admin(user_id):
    return Admin.query.filter_by(id=user_id).first() is not None

def notify_admin(message):
    """Send notification to all admins"""
    send_notification_to_topic(
        topic="admin_notifications",
        title="Admin Notification",
        body=message
    )

def initiate_payment(booking, phone_number):
    """Initiate payment process"""
    payment_result = initiate_mpesa_payment(booking.final_amount, phone_number)
    
    if payment_result.get('ResponseCode') != '0':
        raise Exception(payment_result.get('ResponseDescription', 'Payment initiation failed'))
        
    payment = Payment(
        amount=booking.final_amount,
        phone_number=phone_number,
        merchant_request_id=payment_result['MerchantRequestID'],
        checkout_request_id=payment_result['CheckoutRequestID'],
        payment_status='pending'
    )
    db.session.add(payment)
    db.session.commit()
    
    return payment

def confirm_payment(payment_id):
    """Confirm payment status"""
    payment = Payment.query.get(payment_id)
    if not payment:
        raise Exception('Payment not found')
        
    payment_verification = wait_for_payment_confirmation(payment.checkout_request_id)
    
    if payment_verification['status'] == 'confirmed':
        return 'success'
    else:
        return payment_verification.get('message', 'Payment failed')

class BookingsResource(Resource):
    @jwt_required()
    def get(self, id=None):
        current_user_id = get_jwt_identity()
        
        if id is None:
            if is_admin(current_user_id):
                bookings = Booking.query.all()
            else:
                bookings = Booking.query.filter_by(client_id=current_user_id).all()
            return jsonify([booking.as_dict() for booking in bookings])
        
        booking = Booking.query.get_or_404(id)
        if not is_admin(current_user_id) and booking.client_id != current_user_id:
            return {"error": "Unauthorized"}, 403
            
        return jsonify(booking.as_dict())

    @jwt_required()
    def post(self):
        current_user_id = get_jwt_identity()
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['helicopter_id', 'date', 'time', 'purpose', 'num_passengers']
        for field in required_fields:
            if field not in data:
                return {'message': f'{field} is required'}, 400
                
        try:
            # Convert time string to time object
            time_obj = datetime.strptime(data['time'], '%H:%M:%S').time()
            
            # Convert date string to date object
            date_obj = datetime.strptime(data['date'], '%Y-%m-%d').date()
            
            # Create booking
            booking = Booking(
                client_id=current_user_id,
                helicopter_id=data['helicopter_id'],
                date=date_obj,
                time=time_obj,
                purpose=data['purpose'],
                num_passengers=data['num_passengers'],
                original_amount=data.get('amount', 0),
                final_amount=data.get('amount', 0),
                status='pending'
            )
            
            db.session.add(booking)
            db.session.commit()
            
            # Notify admin of new booking
            notify_admin(f"New booking #{booking.id} created")
            
            return {
                'message': 'Booking created successfully. Please proceed with payment or negotiation.',
                'booking': booking.to_dict()
            }, 201
            
        except ValueError as e:
            return {'message': f'Invalid date or time format: {str(e)}'}, 400
        except Exception as e:
            db.session.rollback()
            return {'message': f'Failed to create booking: {str(e)}'}, 500

    @jwt_required()
    def put(self, id):
        current_user_id = get_jwt_identity()
        booking = Booking.query.get_or_404(id)
        
        # Authorization check
        if not is_admin(current_user_id) and booking.client_id != current_user_id:
            return {"error": "Unauthorized"}, 403
            
        data = request.get_json()
        
        # Handle direct payment
        if "payment" in data and data["payment"]:
            return self._handle_direct_payment(booking, data)
        
        # Admin-specific negotiation handling
        if is_admin(current_user_id):
            if "negotiation_action" in data:
                return self._handle_admin_negotiation_action(booking, data, current_user_id)
        
        # Client-specific negotiation handling
        elif "negotiation_request" in data:
            if booking.status != 'pending':
                return {'message': 'Booking is not in pending state'}, 400
                
            if 'negotiated_amount' not in data:
                return {'message': 'Negotiated amount is required'}, 400
                
            negotiated_amount = data['negotiated_amount']
            
            # Validate negotiated amount is less than original amount
            if negotiated_amount >= booking.original_amount:
                return {'message': 'Negotiated amount must be less than original amount'}, 400
                
            booking.final_amount = negotiated_amount
            booking.negotiation_status = 'requested'
            booking.status = 'negotiation_requested'
            
            history = NegotiationHistory(
                booking_id=booking.id,
                user_id=current_user_id,
                user_type='client',
                old_amount=booking.original_amount,
                new_amount=negotiated_amount,
                action='request',
                notes=data.get('notes', 'Client requested negotiation')
            )
            db.session.add(history)
            db.session.commit()
            
            # Notify admins
            notify_admin(f"New negotiation request for booking #{booking.id}")
            
            return {
                'message': 'Negotiation request submitted successfully',
                'booking': booking.as_dict()
            }, 200
        elif "counter_offer" in data:
            return self._handle_client_counter_offer(booking, data, current_user_id)
        
        # Regular booking updates
        return self._handle_regular_update(booking, data)

    def _handle_direct_payment(self, booking, data):
        if booking.status != 'pending':
            return {'message': 'Booking is not in pending state'}, 400
            
        if 'phone_number' not in data:
            return {'message': 'Phone number is required for payment'}, 400
            
        phone_number = data['phone_number']
        
        # Validate phone number format
        if not re.match(r'^\+?1?\d{9,15}$', phone_number):
            return {'message': 'Invalid phone number format'}, 400
            
        try:
            # Ensure booking is attached to session
            db.session.add(booking)
            
            # Initiate payment
            payment = initiate_payment(booking, phone_number)
            if not payment:
                return {'message': 'Failed to initiate payment'}, 500
                
            # Ensure payment is attached to session
            db.session.add(payment)
            db.session.flush()  # Flush to get payment.id
            
            # Confirm payment
            payment_status = confirm_payment(payment.id)
            if payment_status != 'success':
                return {'message': f'Payment failed: {payment_status}'}, 400
                
            # Refresh payment instance to get fresh data
            db.session.refresh(payment)
            
            # Update payment status
            payment.payment_status = payment_status
            
            # Update booking status
            booking.status = 'paid'
            booking.payment_id = payment.id  # Link payment to booking
            
            # Commit all changes
            db.session.commit()
            
            # Refresh both objects to ensure we have fresh data
            db.session.refresh(payment)
            db.session.refresh(booking)
            
            # Send booking confirmation email
            client = Client.query.get(booking.client_id)
            send_booking_confirmation_email(booking, client)
            
            # Notify admin
            notify_admin(f"Payment received for booking #{booking.id}")
            
            return {
                'message': 'Payment successful and booking confirmed',
                'booking': booking.to_dict(),
                'payment': payment.to_dict()
            }, 200
            
        except Exception as e:
            db.session.rollback()
            return {'message': f'Payment failed: {str(e)}'}, 500

    def _handle_admin_negotiation_action(self, booking, data, admin_id):
        action = data["negotiation_action"]
        
        if action == "accept":
            if "final_amount" not in data:
                return {"error": "Missing final_amount for acceptance"}, 400
                
            # Record old and new amounts
            old_amount = booking.final_amount or booking.original_amount
            new_amount = data["final_amount"]
            
            booking.final_amount = new_amount
            booking.negotiation_status = "accepted"
            booking.status = "pending_payment"
            
            # Record in history
            history = NegotiationHistory(
                booking_id=booking.id,
                user_id=admin_id,
                user_type="admin",
                old_amount=old_amount,
                new_amount=new_amount,
                action="accept",
                notes=data.get("notes", "Admin accepted negotiation")
            )
            db.session.add(history)
            db.session.commit()
            
            # Notify client
            client = Client.query.get(booking.client_id)
            if client and client.fcm_token:
                send_notification_to_user(
                    user_fcm_token=client.fcm_token,
                    title="Negotiation Accepted!",
                    body=f"Your booking #{booking.id} negotiation was accepted",
                    data={
                        "type": "negotiation_update",
                        "booking_id": str(booking.id),
                        "status": "accepted",
                        "final_amount": str(new_amount)
                    }
                )
            
            return {
                "message": "Negotiation accepted successfully",
                "booking": booking.as_dict()
            }, 200
            
        elif action == "reject":
            booking.negotiation_status = "rejected"
            booking.status = "cancelled"
            
            history = NegotiationHistory(
                booking_id=booking.id,
                user_id=admin_id,
                user_type="admin",
                old_amount=booking.final_amount or booking.original_amount,
                new_amount=None,
                action="reject",
                notes=data.get("notes", "Admin rejected negotiation")
            )
            db.session.add(history)
            db.session.commit()
            
            # Notify client
            client = Client.query.get(booking.client_id)
            if client and client.fcm_token:
                send_notification_to_user(
                    user_fcm_token=client.fcm_token,
                    title="Negotiation Rejected",
                    body=f"Your booking #{booking.id} negotiation was rejected",
                    data={
                        "type": "negotiation_update",
                        "booking_id": str(booking.id),
                        "status": "rejected"
                    }
                )
            
            return {
                "message": "Negotiation rejected",
                "booking": booking.as_dict()
            }, 200
            
        else:
            return {"error": "Invalid negotiation action"}, 400

    def _handle_client_counter_offer(self, booking, data, client_id):
        if booking.negotiation_status not in ["requested", "counter_offer"]:
            return {"error": "Cannot submit counter offer in current state"}, 400
            
        if "counter_offer" not in data:
            return {"error": "Counter offer amount is required"}, 400
            
        counter_offer = data["counter_offer"]
        old_amount = booking.final_amount or booking.original_amount
        
        # Validate counter offer is less than current amount
        if counter_offer >= old_amount:
            return {"error": "Counter offer must be less than current amount"}, 400
        
        booking.final_amount = counter_offer
        booking.negotiation_status = "counter_offer"
        
        history = NegotiationHistory(
            booking_id=booking.id,
            user_id=client_id,
            user_type="client",
            old_amount=old_amount,
            new_amount=counter_offer,
            action="counter",
            notes=data.get("notes", "Client counter offer")
        )
        db.session.add(history)
        db.session.commit()
        
        # Notify admins
        send_notification_to_topic(
            topic="admin_notifications",
            title="New Counter Offer",
            body=f"Booking #{booking.id} has a new counter offer: ${counter_offer}",
            data={
                "type": "counter_offer",
                "booking_id": str(booking.id),
                "amount": str(counter_offer)
            }
        )
        
        return {
            "message": "Counter offer submitted successfully",
            "booking": booking.as_dict()
        }, 200

    def _handle_regular_update(self, booking, data):
        # Handle non-negotiation related updates
        if "time" in data:
            try:
                booking.time = datetime.strptime(data["time"], '%H:%M:%S').time()
            except ValueError:
                return {"error": "Invalid time format"}, 400
                
        if "date" in data:
            try:
                booking.date = datetime.strptime(data["date"], '%Y-%m-%d').date()
            except ValueError:
                return {"error": "Invalid date format"}, 400
                
        if "purpose" in data:
            booking.purpose = data["purpose"]
            
        if "status" in data:
            if data["status"] not in ["pending", "pending_payment", "confirmed", "cancelled"]:
                return {"error": "Invalid status"}, 400
            booking.status = data["status"]
            
        db.session.commit()
        return {"message": "Booking updated successfully", "booking": booking.as_dict()}, 200

class NegotiatedPaymentResource(Resource):
    @jwt_required()
    def post(self, booking_id):
        current_user_id = str(get_jwt_identity())  # Convert to string for comparison
        booking = Booking.query.get_or_404(booking_id)
        
        # Verify authorization
        if current_user_id != str(booking.client_id):  # Convert both to string for comparison
            return {'message': 'Unauthorized'}, 403
            
        # Verify booking status
        if booking.status != 'pending_payment' or booking.negotiation_status != 'accepted':
            return {'message': 'Booking is not in the correct state for payment'}, 400
            
        # Get request data
        data = request.get_json()
        if not data or 'phone_number' not in data:
            return {'message': 'Phone number is required'}, 400
            
        phone_number = data['phone_number']
        
        # Validate phone number format
        if not re.match(r'^\+?1?\d{9,15}$', phone_number):
            return {'message': 'Invalid phone number format'}, 400
            
        try:
            # Initiate payment
            payment = initiate_payment(booking, phone_number)
            if not payment:
                return {'message': 'Failed to initiate payment'}, 500
                
            # Confirm payment
            payment_status = confirm_payment(payment.id)
            if payment_status != 'success':
                return {'message': f'Payment failed: {payment_status}'}, 400
                
            # Update payment status
            payment.payment_status = payment_status
            booking.payment_id = payment.id  # Link payment to booking
            db.session.commit()
            
            # Update booking status
            booking.status = 'paid'
            db.session.commit()
            
            # Send payment receipt email
            client = Client.query.get(booking.client_id)
            send_payment_receipt_email(booking, payment, client)
            
            # Notify admin
            notify_admin(f"Payment received for booking #{booking.id}")
            
            return {
                'message': 'Payment successful',
                'booking': booking.to_dict(),
                'payment': payment.to_dict()
            }, 200
            
        except Exception as e:
            db.session.rollback()
            return {'message': f'Payment failed: {str(e)}'}, 500

class FCMTokenResource(Resource):
    @jwt_required()
    def post(self):
        current_user_id = get_jwt_identity()
        data = request.get_json()
        
        if not data or "token" not in data:
            return {"error": "FCM token is required"}, 400
            
        # Update token for client or admin
        client = Client.query.filter_by(id=current_user_id).first()
        if client:
            client.fcm_token = data["token"]
        else:
            admin = Admin.query.filter_by(id=current_user_id).first()
            if admin:
                admin.fcm_token = data["token"]
            else:
                return {"error": "User not found"}, 404
                
        db.session.commit()
        return {"message": "FCM token updated successfully"}, 200

class NegotiationHistoryResource(Resource):
    @jwt_required()
    def get(self, booking_id):
        current_user_id = get_jwt_identity()
        booking = Booking.query.get_or_404(booking_id)
        
        # Verify authorization
        if not is_admin(current_user_id) and booking.client_id != current_user_id:
            return {"error": "Unauthorized"}, 403
            
        history = NegotiationHistory.query.filter_by(booking_id=booking_id)\
            .order_by(NegotiationHistory.created_at.asc()).all()
            
        return jsonify([item.to_dict() for item in history])