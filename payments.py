from flask_restful import Resource
from flask import jsonify, make_response, request
from models import Payment, Booking, Client, Admin, db
from flask_jwt_extended import jwt_required, get_jwt_identity, verify_jwt_in_request
import datetime
import logging
import json
from mpesa import initiate_mpesa_payment, wait_for_payment_confirmation, SHORTCODE, CALLBACK_URL
import os

logger = logging.getLogger(__name__)

def is_admin(user_id):
    return Admin.query.filter_by(id=user_id).first() is not None

def format_phone_number(phone_number):
    # Remove any non-digit characters
    phone_number = ''.join(filter(str.isdigit, phone_number))
    # Add Kenyan country code if not present
    if not phone_number.startswith('254'):
        if phone_number.startswith('0'):
            phone_number = '254' + phone_number[1:]
        else:
            phone_number = '254' + phone_number
    return phone_number

def wait_for_payment_confirmation(checkout_request_id):
    # Implement payment confirmation logic here
    return {
        'status': 'success'
    }

def send_payment_receipt_email(booking, payment, client):
    # Implement payment receipt email sending logic here
    pass

def notify_admin(message):
    # Implement admin notification logic here
    pass

class PaymentsResource(Resource):
    @jwt_required()
    def get(self):
        current_user_id = get_jwt_identity()  # Get the ID of the currently authenticated user

        # Check if the current user is an admin
        is_admin = Admin.query.filter_by(id=current_user_id).first() is not None

        if is_admin:
            # If the user is an admin, fetch all payments
            payments = Payment.query.all()
            payment_details = []
            for payment in payments:
                booking = Booking.query.filter_by(payment_id=payment.id).first()
                if booking:
                    client = Client.query.filter_by(id=booking.client_id).first()
                    payment_details.append({
                        "booking_id": booking.id,
                        "client_name": client.name,
                        "client_email": client.email,
                        "client_phone_number": client.phone_number,
                        "amount_paid": payment.amount,
                        "payment_status": payment.payment_status,
                        "payment_date": payment.created_at.isoformat(),
                        "helicopter_model": booking.helicopter.model,  # Optional: Include helicopter details
                        "purpose": booking.purpose  # Optional: Include booking purpose
                    })
            return make_response(jsonify(payment_details), 200)
        else:
            # If the user is not an admin, fetch only their payments
            bookings = Booking.query.filter_by(client_id=current_user_id).all()
            payment_details = []
            for booking in bookings:
                if booking.payment:  # Check if the booking has an associated payment
                    payment_details.append({
                        "booking_id": booking.id,
                        "client_name": booking.client.name,
                        "client_email": booking.client.email,
                        "client_phone_number": booking.client.phone_number,
                        "amount_paid": booking.payment.amount,
                        "payment_status": booking.payment.payment_status,
                        "payment_date": booking.payment.created_at.isoformat(),
                        "helicopter_model": booking.helicopter.model,  # Optional: Include helicopter details
                        "purpose": booking.purpose  # Optional: Include booking purpose
                    })
            return make_response(jsonify(payment_details), 200)

class PaymentResource(Resource):
    @jwt_required()
    def post(self, id):
        try:
            verify_jwt_in_request()
            user_id = get_jwt_identity()
            
            data = request.get_json()
            
            # Validate required fields
            required_fields = ['phone_number']
            if not all(field in data for field in required_fields):
                return {"error": "Missing required fields"}, 400
            
            # Get booking
            booking = Booking.query.get_or_404(id)
            
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
            formatted_phone = format_phone_number(data['phone_number'])
            
            # Initiate M-Pesa payment
            try:
                logger.info(f"Initiating M-Pesa payment for booking {booking.id} with phone {formatted_phone}")
                
                # Prepare payment details
                amount = booking.final_amount
                
                # Use the SHORTCODE from mpesa.py
                business_short_code = SHORTCODE
                
                # Call the M-Pesa STK push function
                mpesa_response = initiate_mpesa_payment(amount, formatted_phone)
                
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
                payment = Payment.query.get(booking.payment_id)
                checkout_request_id = payment.checkout_request_id  # This is the string from M-Pesa
                payment_status = wait_for_payment_confirmation(checkout_request_id)
                
                # Handle payment status
                if payment_status.get('status') == 'success':
                    # Update booking status
                    booking.status = 'paid'
                    booking.payment_status = 'completed'
                    booking.payment_date = datetime.datetime.now()
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
                    # Payment is still pending
                    return {
                        'message': 'Payment initiated successfully. Please check your phone for the M-Pesa prompt.',
                        'booking': booking.to_dict(),
                        'checkout_request_id': checkout_request_id
                    }, 200
                    
            except Exception as e:
                logger.error(f"Error processing M-Pesa payment: {str(e)}")
                return {'message': f'Payment processing error: {str(e)}'}, 500
                
        except Exception as e:
            logger.error(f"Unexpected error in PaymentResource.post: {str(e)}")
            db.session.rollback()
            return {'message': f'Unexpected error: {str(e)}'}, 500