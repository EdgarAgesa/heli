from flask_restful import Resource
from flask import request, jsonify, current_app
from datetime import datetime
from models import db, Booking, Payment, Client, Admin, NegotiationHistory
from flask_jwt_extended import jwt_required, get_jwt_identity
from mpesa import format_phone_number, initiate_mpesa_payment, wait_for_payment_confirmation
from firebase_notification import send_notification_to_user, send_notification_to_topic
from email_utils import send_payment_receipt_email, send_booking_confirmation_email
import re
import logging

logger = logging.getLogger(__name__)

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
    try:
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
    except Exception as e:
        db.session.rollback()
        raise Exception(f"Payment initiation failed: {str(e)}")

def confirm_payment(payment_id):
    """Confirm payment status"""
    try:
        payment = Payment.query.get(payment_id)
        if not payment:
            raise Exception('Payment not found')
            
        payment_verification = wait_for_payment_confirmation(payment.checkout_request_id)
        
        if payment_verification['status'] == 'success':
            return 'success'
        elif payment_verification['status'] == 'failed':
            return f"Payment failed: {payment_verification.get('details', {}).get('ResultDesc', 'Unknown error')}"
        elif payment_verification['status'] == 'error':
            return f"Payment error: {payment_verification.get('details', 'Unknown error')}"
        else:
            return f"Payment status: {payment_verification.get('status', 'unknown')}"
    except Exception as e:
        return f"Payment confirmation error: {str(e)}"

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
            return self._handle_client_negotiation_request(booking, data, current_user_id)
            
        # Handle counter offer from client
        elif "counter_offer" in data:
            return self._handle_client_counter_offer(booking, data, current_user_id)
            
        # Regular booking updates
        return self._handle_regular_update(booking, data)

    def _handle_direct_payment(self, booking, data):
        """Handle direct payment for a booking"""
        try:
            # Validate phone number format
            if not data['phone_number'] or len(data['phone_number']) < 9:
                return {'message': 'Invalid phone number format. Please provide a valid phone number.'}, 400
                
            # Get the booking
            booking = Booking.query.get(booking.id)
            if not booking:
                return {'message': 'Booking not found'}, 404
                
            # Check if booking is already paid
            if booking.status == 'paid':
                return {'message': 'Booking is already paid'}, 400
                
            # Check if booking is cancelled
            if booking.status == 'cancelled':
                return {'message': 'Cannot process payment for a cancelled booking'}, 400
                
            # Check if booking is expired
            if booking.status == 'expired':
                return {'message': 'Cannot process payment for an expired booking'}, 400
                
            # Check if booking is pending payment
            if booking.status != 'pending_payment':
                return {'message': 'Booking is not in pending payment status'}, 400
                
            # Format phone number for M-Pesa
            formatted_phone = format_phone_number(data['phone_number'])
            
            # Initiate M-Pesa payment
            try:
                logger.info(f"Initiating M-Pesa payment for booking {booking.id} with phone {formatted_phone}")
                mpesa_response = initiate_mpesa_payment(booking.final_amount, formatted_phone)
                
                # Check for M-Pesa specific error codes
                if mpesa_response.get('ResponseCode') != '0':
                    error_msg = mpesa_response.get('ResponseDescription', 'Unknown M-Pesa error')
                    logger.error(f"M-Pesa error: {error_msg}")
                    return {'message': f'Payment initiation failed: {error_msg}'}, 400
                
                # Get checkout request ID
                checkout_request_id = mpesa_response.get('CheckoutRequestID')
                if not checkout_request_id:
                    logger.error("No CheckoutRequestID in M-Pesa response")
                    return {'message': 'Payment initiation failed: No checkout request ID received'}, 500
                
                # Update booking with checkout request ID
                booking.checkout_request_id = checkout_request_id
                booking.payment_phone = formatted_phone
                booking.payment_status = 'pending'
                db.session.commit()
                
                # Wait for payment confirmation
                logger.info(f"Waiting for payment confirmation for booking {booking.id}")
                payment_status = wait_for_payment_confirmation(checkout_request_id)
                
                # Handle payment status
                if payment_status.get('status') == 'success':
                    # Update booking status
                    booking.status = 'paid'
                    booking.payment_status = 'completed'
                    booking.payment_date = datetime.now()
                    db.session.commit()
                    
                    # Send payment receipt email
                    client = Client.query.get(booking.client_id)
                    send_payment_receipt_email(booking, booking, client)
                    
                    # Notify admin
                    notify_admin(f"Payment received for booking #{booking.id}")
                    
                    return {'message': 'Payment successful', 'booking': booking.to_dict()}, 200
                elif payment_status.get('status') == 'failed':
                    # Update booking payment status
                    booking.payment_status = 'failed'
                    db.session.commit()
                    
                    error_details = payment_status.get('details', {})
                    error_message = error_details.get('ResultDesc', 'Payment failed')
                    
                    return {'message': f'Payment failed: {error_message}'}, 400
                else:
                    # Payment is still pending or error occurred
                    return {'message': 'Payment is still pending. Please check your phone for the M-Pesa prompt.'}, 200
                    
            except Exception as e:
                logger.error(f"Error processing M-Pesa payment: {str(e)}")
                return {'message': f'Payment processing error: {str(e)}'}, 500
                
        except Exception as e:
            logger.error(f"Unexpected error in _handle_direct_payment: {str(e)}")
            db.session.rollback()
            return {'message': f'Unexpected error: {str(e)}'}, 500

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

    def _handle_client_negotiation_request(self, booking, data, client_id):
        """Handle initial negotiation request from client"""
        if booking.negotiation_status != "none":
            return {"error": "Negotiation already in progress"}, 400
            
        if "negotiated_amount" not in data:
            return {"error": "Negotiated amount is required"}, 400
            
        negotiated_amount = data["negotiated_amount"]
        original_amount = booking.original_amount
        
        # Validate negotiated amount is less than original amount
        if negotiated_amount >= original_amount:
            return {"error": "Negotiated amount must be less than original amount"}, 400
        
        booking.final_amount = negotiated_amount
        booking.negotiation_status = "requested"
        booking.status = "negotiation_requested"
        
        history = NegotiationHistory(
            booking_id=booking.id,
            user_id=client_id,
            user_type="client",
            old_amount=original_amount,
            new_amount=negotiated_amount,
            action="request",
            notes=data.get("notes", "Client negotiation request")
        )
        db.session.add(history)
        db.session.commit()
        
        # Notify admins
        send_notification_to_topic(
            topic="admin_notifications",
            title="New Negotiation Request",
            body=f"Booking #{booking.id} has a new negotiation request: ${negotiated_amount}",
            data={
                "type": "negotiation_request",
                "booking_id": str(booking.id),
                "amount": str(negotiated_amount)
            }
        )
        
        return {
            "message": "Negotiation request submitted successfully",
            "booking": booking.as_dict()
        }, 200

    def _handle_regular_update(self, booking, data):
        """Handle regular booking updates"""
        try:
            # Handle status updates
            if 'status' in data:
                new_status = data['status']
                
                # Validate status
                valid_statuses = ['pending', 'pending_payment', 'paid', 'cancelled', 'expired']
                if new_status not in valid_statuses:
                    return {'message': f'Invalid status. Must be one of: {", ".join(valid_statuses)}'}, 400
                
                # Special handling for pending_payment status
                if new_status == 'pending_payment':
                    # Only allow transition to pending_payment from pending or negotiation_requested
                    if booking.status not in ['pending', 'negotiation_requested']:
                        return {'message': f'Cannot change status from {booking.status} to pending_payment'}, 400
                    
                    # Set the status
                    booking.status = new_status
                    logger.info(f"Booking {booking.id} status updated to pending_payment")
                else:
                    # For other statuses, just update
                    booking.status = new_status
                    logger.info(f"Booking {booking.id} status updated to {new_status}")
            
            # Handle other fields
            if 'date' in data:
                try:
                    booking.date = datetime.strptime(data['date'], '%Y-%m-%d').date()
                except ValueError:
                    return {'message': 'Invalid date format. Use YYYY-MM-DD'}, 400
            
            if 'time' in data:
                try:
                    booking.time = datetime.strptime(data['time'], '%H:%M').time()
                except ValueError:
                    return {'message': 'Invalid time format. Use HH:MM'}, 400
            
            if 'purpose' in data:
                booking.purpose = data['purpose']
            
            if 'num_passengers' in data:
                booking.num_passengers = data['num_passengers']
            
            # Commit changes
            db.session.commit()
            
            return {'message': 'Booking updated successfully', 'booking': booking.to_dict()}, 200
            
        except Exception as e:
            logger.error(f"Error updating booking: {str(e)}")
            db.session.rollback()
            return {'message': f'Error updating booking: {str(e)}'}, 500

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
                
            # Confirm payment with a timeout
            payment_status = confirm_payment(payment.id)
            
            # Check if payment was successful
            if payment_status == 'success':
                # Update payment status
                payment.payment_status = 'success'
                booking.payment_id = payment.id  # Link payment to booking
                
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
            else:
                # Payment was not successful
                payment.payment_status = 'failed'
                db.session.commit()
                
                return {
                    'message': f'Payment failed: {payment_status}',
                    'booking': booking.to_dict(),
                    'payment': payment.to_dict()
                }, 400
                
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
            # Store only the token string, not the entire notification data
            client.fcm_token = str(data["token"])
        else:
            admin = Admin.query.filter_by(id=current_user_id).first()
            if admin:
                # Store only the token string, not the entire notification data
                admin.fcm_token = str(data["token"])
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