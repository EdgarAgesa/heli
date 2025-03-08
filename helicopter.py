from models import Helicopter, db
from flask_restful import Resource
from flask import make_response, request, jsonify
from flask_jwt_extended import jwt_required

class HelicopterResource(Resource):
    @jwt_required()
    def get(self, id=None):
        if id is None:
            # Return all helicopters
            helicopters_all = [helicopter.to_dict() for helicopter in Helicopter.query.all()]
            return make_response(jsonify(helicopters_all), 200)
        else:
            # Return a specific helicopter by ID
            helicopter = Helicopter.query.filter_by(id=id).first()
            if not helicopter:
                return jsonify({"message": "The helicopter ID does not exist"}), 404
            return make_response(jsonify(helicopter.to_dict())), 200

    @jwt_required()
    def post(self):
        data = request.get_json()

        # Validate required fields
        if not data or "model" not in data or "capacity" not in data:
            return jsonify({"message": "Missing required fields: 'model' and 'capacity'"}), 400

        # Create a new helicopter
        new_helicopter = Helicopter(
            model=data["model"],
            capacity=data["capacity"]
        )

        db.session.add(new_helicopter)
        db.session.commit()

        # Return the newly created helicopter
        return make_response(jsonify(new_helicopter.to_dict())), 201

    @jwt_required()
    def put(self, id):
        # Find the helicopter by ID
        up_helicopter = Helicopter.query.get(id)
        if not up_helicopter:
            return jsonify({"message": "The helicopter ID does not exist"}), 404

        data = request.get_json()

        # Update fields if provided
        if "model" in data:
            up_helicopter.model = data["model"]
        if "capacity" in data:
            up_helicopter.capacity = data["capacity"]

        db.session.commit()

        # Return success message
        return make_response(jsonify({"message": "Helicopter updated successfully"})), 200

    @jwt_required()
    def delete(self, id):
        # Find the helicopter by ID
        delete_helicopter = Helicopter.query.filter_by(id=id).first()
        if not delete_helicopter:
            return jsonify({"message": f"The helicopter ID {id} does not exist"}), 404

        # Delete the helicopter
        db.session.delete(delete_helicopter)
        db.session.commit()

        # Return success message
        return jsonify({"message": f"Helicopter ID {id} was successfully deleted"}), 200