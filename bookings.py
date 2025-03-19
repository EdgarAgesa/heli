from flask_restful import Resource
from flask import jsonify, request, make_response
from datetime import datetime
from models import Booking, Payment, db, Client, Admin
from flask_jwt_extended import jwt_required, get_jwt_identity
from mpesa import initiate_mpesa_payment, wait_for_payment_confirmation

class BookingsResource(Resource):
    @jwt_required()
    def get(self, id=None):
        current_user_id = get_jwt_identity()
        is_admin = Admin.query.filter_by(id=current_user_id).first() is not None

        if id is None:
            if is_admin:
                bookings_all = [booking.to_dict() for booking in Booking.query.all()]
                return make_response(jsonify(bookings_all), 200)
            else:
                user_bookings = [booking.to_dict() for booking in Booking.query.filter_by(client_id=current_user_id).all()]
                return make_response(jsonify(user_bookings), 200)

        booking = Booking.query.filter_by(id=id).first()
        if not booking:
            return jsonify({"message": "The booking does not exist"}, 404)

        if not is_admin and booking.client_id != current_user_id:
            return jsonify({"message": "You are not authorized to view this booking"}, 403)

        return make_response(jsonify(booking.to_dict()), 200)

    @jwt_required()
    def post(self):
        data = request.get_json()

        required_fields = ["time", "date", "purpose", "status", "helicopter_id", "client_id", "phone_number", "amount"]
        if not all(field in data for field in required_fields):
            return jsonify({"message": "Missing required fields"}, 400)

        try:
            time_obj = datetime.strptime(data["time"], '%H:%M:%S').time()
            date_obj = datetime.strptime(data["date"], '%Y-%m-%d').date()
        except ValueError as e:
            return jsonify({"message": "Invalid time or date format", "error": str(e)}, 400)

        amount = data["amount"]
        phone_number = data["phone_number"]

        # Check if the user is requesting price negotiation
        if data.get("negotiate_price", False):
            new_booking = Booking(
                time=time_obj,
                date=date_obj,
                purpose=data["purpose"],
                status='price_negotiation',
                helicopter_id=data["helicopter_id"],
                client_id=data["client_id"],
                payment_id=None,
                negotiation_status='pending'
            )
            db.session.add(new_booking)
            db.session.commit()
            return make_response(jsonify({
                "message": "Price negotiation requested. Admin will reach out via chat.",
                "booking_id": new_booking.id
            }), 201)
        else:
            # Proceed with normal payment
            payment_result = initiate_mpesa_payment(amount, phone_number)

            if payment_result.get('ResponseCode') != '0':
                return jsonify({"message": "Payment initiation failed", "details": payment_result}, 400)

            checkout_request_id = payment_result['CheckoutRequestID']
            payment_verification = wait_for_payment_confirmation(checkout_request_id)

            if payment_verification['status'] == 'confirmed':
                new_payment = Payment(
                    amount=amount,
                    phone_number=phone_number,
                    merchant_request_id=payment_result['MerchantRequestID'],
                    checkout_request_id=checkout_request_id,
                    payment_status='confirmed'
                )

                db.session.add(new_payment)
                db.session.commit()

                new_booking = Booking(
                    time=time_obj,
                    date=date_obj,
                    purpose=data["purpose"],
                    status='confirmed',
                    helicopter_id=data["helicopter_id"],
                    client_id=data["client_id"],
                    payment_id=new_payment.id
                )

                db.session.add(new_booking)
                db.session.commit()

                return make_response(jsonify(new_booking.to_dict()), 201)
            else:
                return jsonify({"message": "Payment failed or was canceled", "details": payment_verification['details']}, 400)

    @jwt_required()
    def put(self, id):
        current_user_id = get_jwt_identity()
        is_admin = Admin.query.filter_by(id=current_user_id).first() is not None

        up_booking = Booking.query.get(id)

        if not up_booking:
            return jsonify({"message": f"The booking with id {id} does not exist"}, 400)

        if not is_admin and up_booking.client_id != current_user_id:
            return jsonify({"message": "You are not authorized to update this booking"}, 403)

        data = request.get_json()

        # Inside PUT for admin to accept or reject negotiation:
        if is_admin:
            if "final_amount" in data:
                up_booking.final_amount = data["final_amount"]
                up_booking.negotiation_status = 'accepted'
                up_booking.status = 'pending_payment'
                db.session.commit()
                return jsonify({"message": "Final price set. Awaiting user payment."}, 200)
            
            if "negotiation_status" in data and data["negotiation_status"] == "declined":
                up_booking.negotiation_status = 'declined'
                up_booking.status = 'canceled'
                db.session.commit()
                return jsonify({"message": "Negotiation declined by admin."}, 200)


        # Normal updates
        up_booking.time = datetime.strptime(data.get("time", up_booking.time.strftime('%H:%M:%S')), '%H:%M:%S').time()
        up_booking.date = datetime.strptime(data.get("date", up_booking.date.strftime('%Y-%m-%d')), '%Y-%m-%d').date()
        up_booking.purpose = data.get("purpose", up_booking.purpose)
        up_booking.status = data.get("status", up_booking.status)
        up_booking.helicopter_id = data.get("helicopter_id", up_booking.helicopter_id)

        db.session.commit()

        return jsonify({"message": "Booking updated successfully"}), 200