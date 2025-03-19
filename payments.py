from flask_restful import Resource
from flask import jsonify, make_response
from models import Payment, Booking, Client, Admin, db
from flask_jwt_extended import jwt_required, get_jwt_identity

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