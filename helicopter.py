from models import Helicopter, db
from flask_restful import Resource
from flask import make_response, request, jsonify
from flask_jwt_extended import jwt_required
from admin_decorator import superadmin_required, admin_required

class HelicopterResource(Resource):
    @jwt_required()
    def get(self, id=None):
        if id is None:
            helicopters_all = [helicopter.to_dict() for helicopter in Helicopter.query.all()]
            return make_response(jsonify(helicopters_all), 200)
        else:
            helicopter = Helicopter.query.filter_by(id=id).first()
            if not helicopter:
                return jsonify({"message": "The helicopter ID does not exist"}, 404)
            return make_response(jsonify(helicopter.to_dict()), 200)

    @jwt_required()
    @superadmin_required
    @admin_required
    def post(self):
        data = request.get_json()

        if not data or "model" not in data or "capacity" not in data or "image_url" not in data:
            return jsonify({"message": "Missing required fields: 'model', 'capacity', and 'image_url'"}, 400)

        new_helicopter = Helicopter(
            model=data["model"],
            capacity=data["capacity"],
            image_url=data["image_url"] 
        )

        db.session.add(new_helicopter)
        db.session.commit()

        return make_response(jsonify(new_helicopter.to_dict()), 201)

    @jwt_required()
    @superadmin_required
    @admin_required
    def put(self, id):
        try:
            up_helicopter = Helicopter.query.get(id)
            if not up_helicopter:
                return jsonify({"message": "The helicopter ID does not exist"}, 404)

            data = request.get_json()

            if "model" in data:
                up_helicopter.model = data["model"]
            if "capacity" in data:
                up_helicopter.capacity = data["capacity"]
            if "image_url" in data:
                up_helicopter.image_url = data["image_url"]

            db.session.commit()

            return make_response(jsonify({"message": "Helicopter updated successfully"}), 200)
        except Exception as e:
            db.session.rollback()
            return jsonify({"message": "An error occurred", "error": str(e)}, 500)

    @jwt_required()
    @superadmin_required
    @admin_required
    def delete(self, id):
        try:
            delete_helicopter = Helicopter.query.filter_by(id=id).first()
            if not delete_helicopter:
                return jsonify({"message": f"The helicopter ID {id} does not exist"}, 404)

            db.session.delete(delete_helicopter)
            db.session.commit()

            return jsonify({"message": f"Helicopter ID {id} was successfully deleted"}, 200)
        except Exception as e:
            db.session.rollback()
            return jsonify({"message": "An error occurred", "error": str(e)}, 500)