from flask_restful import Resource
from flask import jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from models import Booking, db
from admin_decorator import admin_required

class AdminBookingManagementResource(Resource):
    @jwt_required()
    @admin_required
    def get(self, booking_type):
        """
        Get bookings based on type (negotiated, incomplete, completed)
        """
        if booking_type == "negotiated":
            # Get bookings with active negotiations
            bookings = Booking.query.filter(
                Booking.negotiation_status.in_(['requested', 'counter_offer'])
            ).all()
        elif booking_type == "incomplete":
            # Get incomplete bookings (pending or negotiation_requested)
            bookings = Booking.query.filter(
                Booking.status.in_(['pending', 'negotiation_requested'])
            ).all()
        elif booking_type == "completed":
            # Get completed bookings (paid or confirmed)
            bookings = Booking.query.filter(
                Booking.status.in_(['paid', 'confirmed'])
            ).all()
        else:
            return {"message": "Invalid booking type"}, 400

        return jsonify([booking.as_dict() for booking in bookings]) 