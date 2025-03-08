from models import Booking, db
from flask_restful import Resource
from flask import jsonify, request, make_response
from datetime import datetime
from flask_jwt_extended import jwt_required

class BookingsResource(Resource):
    @jwt_required()
    def get(self, id=None):
        if id is None:
            bookings_all = [booking.to_dict() for booking in Booking.query.all()]
            return make_response(jsonify(bookings_all), 200)

        booking = Booking.query.filter_by(id=id).first()
        if not booking:
            return jsonify({"message": "The booking does not exist"}), 404

        return make_response(jsonify(booking.to_dict()), 200)
    
    @jwt_required()
    def post(self):
        data = request.get_json()

        required_fields = ["time", "date", "purpose", "status", "helicopter_id", "client_id"]
        if not all(field in data for field in required_fields):
            return jsonify({"message": "Missing required fields"}), 400

        new_booking = Booking(
            time=data["time"],
            date=data["date"],
            purpose=data["purpose"],
            status=data["status"],
            helicopter_id=data["helicopter_id"],
            client_id=data["client_id"],
            # payment_id=data.get("payment_id") 
        )

        db.session.add(new_booking)
        db.session.commit()

        return make_response(jsonify(new_booking.to_dict()), 201)
    
    @jwt_required()
    def put(self, id):
        up_booking = Booking.query.get(id)

        if not up_booking:
            return jsonify({"message": f"The booking with id {id} does not exist"}), 400

        data = request.get_json()

        
        up_booking.time = data.get("time", datetime.utcnow().time())
        up_booking.date = data.get("date", up_booking.date)
        up_booking.purpose = data.get("purpose", up_booking.purpose)
        up_booking.status = data.get("status", up_booking.status)
        up_booking.helicopter_id = data.get("helicopter_id", up_booking.helicopter_id)

        db.session.commit()

        return jsonify({"message": "Booking updated successfully"}), 200
    
    @jwt_required()
    def delete(self, id):
        delete_booking = Booking.query.filter_by(id=id).first()

        if not delete_booking:
            return jsonify({"message": "The booking does not exist"}), 404

        db.session.delete(delete_booking)
        db.session.commit()

        return jsonify({"message": f"Booking with id {id} was successfully deleted"}), 200
