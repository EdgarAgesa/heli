from flask_restful import Resource
from flask import request, jsonify, current_app
from datetime import datetime
from models import db, Booking, Payment, Client, Admin, NegotiationHistory
from flask_jwt_extended import jwt_required, get_jwt_identity, verify_jwt_in_request, get_jwt
from mpesa import format_phone_number, initiate_mpesa_payment, wait_for_payment_confirmation
from firebase_notification import send_notification_to_user, send_notification_to_topic
from email_utils import send_payment_receipt_email, send_booking_confirmation_email
import re
import logging
import time

logger = logging.getLogger(__name__)

def is_admin(user):
    """Check if a user is an admin"""
    if isinstance(user, Admin):
        return True
    elif isinstance(user, (int, str)):
        return Admin.query.filter_by(id=user).first() is not None
    return False

def notify_admin(message):
    """Send notification to all admins"""
    send_notification_to_topic(
        topic="admin_notifications",
        title="Admin Notification",
        body=message
    )

def initiate_payment(booking, phone_number):
    """Initiate payment process with improved error handling"""
    try:
        formatted_phone = format_phone_number(phone_number)
        logger.info(f"Initiating payment of {booking.final_amount} for booking {booking.id} to {formatted_phone}")
        
        payment_result = initiate_mpesa_payment(booking.final_amount, formatted_phone)
        
        if payment_result.get('ResponseCode') != '0':
            error_msg = payment_result.get('ResponseDescription', 'Payment initiation failed')
            logger.error(f"Payment initiation failed: {error_msg}")
            raise Exception(error_msg)
            
        payment = Payment(
            amount=booking.final_amount,
            phone_number=formatted_phone,
            merchant_request_id=payment_result['MerchantRequestID'],
            checkout_request_id=payment_result['CheckoutRequestID'],
            payment_status='pending'
        )
        db.session.add(payment)
        db.session.commit()
        
        return payment
    except Exception as e:
        db.session.rollback()
        logger.error(f"Payment initiation error: {str(e)}")
        raise Exception(f"Payment initiation failed: {str(e)}")

def confirm_payment(checkout_request_id, max_attempts=24, delay=5):
    """Confirm payment status with improved waiting logic"""
    logger.info(f"Confirming payment for checkout request: {checkout_request_id}")
    
    for attempt in range(max_attempts):
        try:
            logger.info(f"Payment verification attempt {attempt + 1}/{max_attempts}")
            result = wait_for_payment_confirmation(checkout_request_id)
            
            if result.get('status') == 'success':
                logger.info("Payment confirmed successfully")
                return {
                    'status': 'success',
                    'details': 'Payment confirmed',
                    'response': result
                }
            elif result.get('status') == 'pending':
                logger.info(f"Payment still processing, waiting {delay} seconds")
                time.sleep(delay)
                continue
            elif result.get('status') == 'failed':
                logger.warning(f"Payment failed: {result.get('details')}")
                return {
                    'status': 'failed',
                    'details': result.get('details'),
                    'response': result
                }
            else:
                logger.error(f"Unexpected payment status: {result.get('status')}")
                if attempt < max_attempts - 1:
                    time.sleep(delay)
                    continue
                else:
                    return {
                        'status': 'error',
                        'details': 'Maximum attempts reached without confirmation'
                    }
        except Exception as e:
            logger.error(f"Error verifying payment: {str(e)}")
            if attempt < max_attempts - 1:
                time.sleep(delay)
                continue
            else:
                return {
                    'status': 'error',
                    'details': str(e)
                }
    
    return {
        'status': 'failed',
        'details': 'Payment verification timed out'
    }

class BookingsResource(Resource):
    @jwt_required()
    def get(self, id=None):
        try:
            # Log request headers for debugging
            auth_header = request.headers.get('Authorization')
            logger.info(f"Auth header: {auth_header}")
            
            verify_jwt_in_request()
            user_id = get_jwt_identity()
            logger.info(f"User ID from token: {user_id}")
            
            if id is None:
                # Check if user is admin
                admin = Admin.query.get(user_id)
                if admin:
                    logger.info(f"Admin user {user_id} fetching all bookings")
                    bookings = Booking.query.all()
                else:
                    logger.info(f"Client {user_id} fetching their bookings")
                    bookings = Booking.query.filter_by(client_id=user_id).all()
                return jsonify([booking.as_dict() for booking in bookings])
            
            booking = Booking.query.get_or_404(id)
            admin = Admin.query.get(user_id)
            if not admin and booking.client_id != user_id:
                return {"error": "Unauthorized"}, 403
            
            return jsonify(booking.as_dict())
        except Exception as e:
            logger.error(f"Error getting booking: {str(e)}")
            return {"error": str(e)}, 500

    @jwt_required()
    def post(self):
        current_user_id = get_jwt_identity()
        data = request.get_json()
        required_fields = ['helicopter_id', 'date', 'time', 'purpose', 'num_passengers', 'original_amount']
        for field in required_fields:
            if field not in data:
                return {'message': f'{field} is required'}, 400
        try:
            time_obj = datetime.strptime(data['time'], '%H:%M:%S').time()
            date_obj = datetime.strptime(data['date'], '%Y-%m-%d').date()
            booking = Booking(
                client_id=current_user_id,
                helicopter_id=data['helicopter_id'],
                date=date_obj,
                time=time_obj,
                purpose=data['purpose'],
                num_passengers=data['num_passengers'],
                original_amount=data['original_amount'],
                final_amount=data['original_amount'],
                status='pending',
                negotiation_status='none'
            )
            db.session.add(booking)
            db.session.commit()
            notify_admin(f"New booking #{booking.id} created")
            return {
                'message': 'Booking created successfully. Please proceed with payment or negotiation.',
                'booking': booking.to_dict()
            }, 201
        except Exception as e:
            db.session.rollback()
            return {'message': f'Failed to create booking: {str(e)}'}, 500

    @jwt_required()
    def put(self, id):
        current_user_id = get_jwt_identity()
        booking = Booking.query.get_or_404(id)
        if not is_admin(current_user_id) and booking.client_id != current_user_id:
            return {"error": "Unauthorized"}, 403
        data = request.get_json()

        # Payment
        if "payment" in data and data["payment"]:
            return self._handle_direct_payment(booking, data)

        # Admin negotiation
        if is_admin(current_user_id) and "negotiation_action" in data:
            return self._handle_admin_negotiation_action(booking, data, current_user_id)

        # Client negotiation request
        if "negotiation_request" in data:
            return self._handle_client_negotiation_request(booking, data, current_user_id)

        # Client counter offer
        if "counter_offer" in data:
            return self._handle_client_counter_offer(booking, data, current_user_id)

        # Regular update
        return self._handle_regular_update(booking, data)

    def _handle_direct_payment(self, booking, data):
        try:
            if not data.get('phone_number'):
                return {'message': 'Phone number is required'}, 400
            if booking.status == 'paid':
                return {'message': 'Booking is already paid'}, 400
            if booking.status == 'cancelled':
                return {'message': 'Cannot process payment for a cancelled booking'}, 400
            if booking.status not in ['pending_payment', 'pending']:
                return {'message': 'Booking is not in a payable state'}, 400

            formatted_phone = format_phone_number(data['phone_number'])
            mpesa_response = initiate_mpesa_payment(booking.final_amount, formatted_phone)
            checkout_request_id = mpesa_response.get('CheckoutRequestID')
            if not checkout_request_id:
                return {'message': 'Payment initiation failed: No checkout request ID received'}, 500

            # Create Payment record
            payment = Payment(
                amount=booking.final_amount,
                phone_number=formatted_phone,
                merchant_request_id=mpesa_response.get('MerchantRequestID'),
                checkout_request_id=checkout_request_id,
                payment_status='pending'
            )
            db.session.add(payment)
            db.session.commit()

            # Link payment to booking
            booking.payment_id = payment.id
            booking.payment_status = 'pending'
            db.session.commit()

            # Now confirm payment using the real CheckoutRequestID
            payment_status = confirm_payment(checkout_request_id)
            if payment_status['status'] == 'success':
                payment.payment_status = 'success'
                booking.status = 'paid'
                db.session.commit()
                logger.info("About to send payment receipt email...")
                client = Client.query.get(booking.client_id)
                logger.info(f"Client email: {getattr(client, 'email', None)}")
                send_payment_receipt_email(booking, payment, client)
                return {'message': 'Payment successful', 'booking': booking.to_dict()}, 200
            else:
                payment.payment_status = 'failed'
                db.session.commit()
                return {'message': f'Payment failed: {payment_status}', 'booking': booking.to_dict()}, 400
        except Exception as e:
            db.session.rollback()
            return {'message': f'Payment failed: {str(e)}'}, 500

    def _handle_admin_negotiation_action(self, booking, data, admin_id):
        try:
            required_fields = ['negotiation_action', 'final_amount', 'notes']
            if not all(field in data for field in required_fields):
                return {'message': 'Missing required fields'}, 400

            negotiation = NegotiationHistory(
                booking_id=booking.id,
                action=data['negotiation_action'],
                new_amount=data['final_amount'],
                notes=data['notes'],
                user_id=admin_id,
                user_type='admin'
            )
            db.session.add(negotiation)

            if data['negotiation_action'] == 'accept':
                booking.status = 'pending_payment'
                booking.negotiation_status = 'accepted'
                booking.final_amount = data['final_amount']
            elif data['negotiation_action'] == 'reject':
                booking.status = 'cancelled'
                booking.negotiation_status = 'rejected'
            elif data['negotiation_action'] == 'counter':
                booking.status = 'negotiation'
                booking.negotiation_status = 'counter_offer'
                booking.final_amount = data['final_amount']
            else:
                return {'message': 'Invalid negotiation action'}, 400

            db.session.commit()
            # ...notify client...
            return {'message': 'Negotiation action processed successfully', 'booking': booking.to_dict()}, 200
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error handling negotiation action: {str(e)}")
            return {'message': str(e)}, 500

    def _handle_client_counter_offer(self, booking, data, client_id):
        try:
            required_fields = ['negotiated_amount', 'notes']
            if not all(field in data for field in required_fields):
                return {'message': 'Missing required fields'}, 400

            negotiation = NegotiationHistory(
                booking_id=booking.id,
                action='counter',
                new_amount=data['negotiated_amount'],
                notes=data['notes'],
                user_id=client_id,
                user_type='client'
            )
            db.session.add(negotiation)

            booking.status = 'negotiation'
            booking.negotiation_status = 'counter_offer'
            booking.final_amount = data['negotiated_amount']

            db.session.commit()
            # ...notify admin...
            return {'message': 'Counter offer submitted successfully', 'booking': booking.to_dict()}, 200
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error handling client counter offer: {str(e)}")
            return {'message': str(e)}, 500

    def _handle_client_negotiation_request(self, booking, data, client_id):
        try:
            required_fields = ['negotiated_amount', 'notes']
            if not all(field in data for field in required_fields):
                return {'message': 'Missing required fields'}, 400

            negotiation = NegotiationHistory(
                booking_id=booking.id,
                action='request',
                new_amount=data['negotiated_amount'],
                notes=data['notes'],
                user_id=client_id,
                user_type='client'
            )
            db.session.add(negotiation)

            booking.status = 'negotiation'
            booking.negotiation_status = 'requested'
            booking.final_amount = data['negotiated_amount']

            db.session.commit()
            # ...notify admin...
            return {'message': 'Negotiation request submitted successfully', 'booking': booking.to_dict()}, 200
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error handling client negotiation request: {str(e)}")
            return {'message': str(e)}, 500

    def _handle_regular_update(self, booking, data):
        """Handle regular booking updates"""
        try:
            # Update booking fields
            for key, value in data.items():
                if hasattr(booking, key):
                    setattr(booking, key, value)
            
            db.session.commit()
            return {'message': 'Booking updated successfully', 'booking': booking.to_dict()}, 200
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error updating booking: {str(e)}")
            return {'message': str(e)}, 500

class PaymentResource(Resource):
    @jwt_required()
    def post(self):
        try:
            verify_jwt_in_request()
            user_id = get_jwt_identity()
            
            data = request.get_json()
            
            # Validate required fields
            required_fields = ['booking_id', 'phone_number']
            if not all(field in data for field in required_fields):
                return {"error": "Missing required fields"}, 400
            
            booking_id = data['booking_id']
            phone_number = data['phone_number']
            
            # Get booking
            booking = Booking.query.get_or_404(booking_id)
            
            # Check if user is authorized
            if not is_admin(user_id) and booking.client_id != user_id:
                return {"error": "Unauthorized"}, 403
            
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
            formatted_phone = format_phone_number(phone_number)
            
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
            logger.error(f"Unexpected error in PaymentResource.post: {str(e)}")
            db.session.rollback()
            return {'message': f'Unexpected error: {str(e)}'}, 500

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
            payment_status = confirm_payment(payment.checkout_request_id)
            
            # Check if payment was successful
            if payment_status['status'] == 'success':
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
                    'message': f'Payment failed: {payment_status["details"]}',
                    'booking': booking.to_dict(),
                    'payment': payment.to_dict()
                }, 400
                
        except Exception as e:
            db.session.rollback()
            return {'message': f'Payment failed: {str(e)}'}, 500

class FCMTokenResource(Resource):
    @jwt_required()
    def post(self):
        try:
            current_user_id = get_jwt_identity()
            logger.info(f"Updating FCM token for user {current_user_id}")
            
            data = request.get_json()
            if not data or "token" not in data:
                return {"error": "FCM token is required"}, 400
            
            # Convert string ID to int for database query
            user_id = int(current_user_id)
            token = str(data["token"])
            
            # Update token for client or admin
            client = Client.query.filter_by(id=user_id).first()
            if client:
                # Store token for client
                client.fcm_token = token
                logger.info(f"Updated FCM token for client {user_id}: {token}")
            else:
                admin = Admin.query.filter_by(id=user_id).first()
                if admin:
                    # Store token for admin
                    admin.fcm_token = token
                    logger.info(f"Updated FCM token for admin {user_id}: {token}")
                    
                    # Subscribe admin to admin notifications topic
                    send_notification_to_topic(
                        topic="admin_notifications",
                        title="Admin Notifications",
                        body="You are now subscribed to admin notifications",
                        data={"type": "admin_subscription"}
                    )
                    logger.info(f"Subscribed admin {user_id} to admin notifications topic")
                else:
                    logger.error(f"User not found: {user_id}")
                    return {"error": "User not found"}, 404
            
            db.session.commit()
            return {"message": "FCM token updated successfully"}, 200
            
        except Exception as e:
            logger.error(f"Error updating FCM token: {str(e)}")
            return {"error": "Error updating FCM token"}, 500

class BookingStatusResource(Resource):
    @jwt_required()
    def get(self, booking_id):
        try:
            current_user_id = get_jwt_identity()
            booking = Booking.query.get_or_404(booking_id)
            
            # Verify authorization
            if not is_admin(current_user_id) and booking.client_id != current_user_id:
                return {"error": "Unauthorized"}, 403
            
            # Get associated payment if it exists
            payment = None
            if booking.payment_id:
                payment = Payment.query.get(booking.payment_id)
            
            response = {
                'status': booking.status,
                'payment_status': payment.payment_status if payment else None,
                'amount': booking.final_amount,
                'id': booking.id,
                'date': booking.date.isoformat() if booking.date else None,
                'time': booking.time.isoformat() if booking.time else None,
                'final_amount': booking.final_amount,
                'original_amount': booking.original_amount,
                'payment_id': payment.id if payment else None,
                'merchant_request_id': payment.merchant_request_id if payment else None,
                'checkout_request_id': payment.checkout_request_id if payment else None
            }
            
            return jsonify(response)
            
        except Exception as e:
            logger.error(f"Error getting booking status: {str(e)}")
            return {"error": "Error getting booking status"}, 500

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

class PaymentConfirmationResource(Resource):
    @jwt_required()
    def get(self, checkout_request_id):
        """Check payment status endpoint"""
        try:
            verify_jwt_in_request()
            user_id = get_jwt_identity()
            
            # Find booking by checkout request ID
            booking = Booking.query.filter_by(checkout_request_id=checkout_request_id).first()
            if not booking:
                return {"error": "Booking not found"}, 404
                
            # Check authorization
            if not is_admin(user_id) and booking.client_id != user_id:
                return {"error": "Unauthorized"}, 403
                
            # Check payment status
            payment = Payment.query.get(booking.payment_id)
            checkout_request_id = payment.checkout_request_id  # This is the string from M-Pesa
            payment_verification = wait_for_payment_confirmation(checkout_request_id)
            
            if payment_verification['status'] == 'success':
                # Update booking status
                booking.status = 'paid'
                booking.payment_status = 'completed'
                # booking.payment_date = datetime.now()  # Uncomment if your model supports this
                db.session.commit()
                
                # Send notifications
                client = Client.query.get(booking.client_id)
                if client:
                    send_payment_receipt_email(booking, booking, client)
                    send_booking_confirmation_email(booking, client)
                    notify_admin(f"Payment completed for booking #{booking.id}")
                
                return {
                    'status': 'success',
                    'message': 'Payment confirmed',
                    'booking': booking.as_dict()
                }, 200
                
            elif payment_verification['status'] == 'pending':
                return {
                    'status': 'pending',
                    'message': 'Payment still processing'
                }, 202
                
            else:  # failed or error
                return {
                    'status': 'failed',
                    'message': payment_verification.get('details', 'Payment failed')
                }, 400
                
        except Exception as e:
            logger.error(f"Payment confirmation error: {str(e)}")
            return {"error": str(e)}, 500