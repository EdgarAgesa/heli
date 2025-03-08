from models import Admin, db
from flask_restful import Resource
from flask import jsonify, request, make_response
from flask_jwt_extended import jwt_required

class AdminResource(Resource):
    @jwt_required()
    def get(self, id=None):
        if id is None:
            admin_all = [admin.to_dict() for admin in Admin.query.all()]
            return make_response(jsonify(admin_all), 200)

        admin = Admin.query.filter_by(id=id).first()
        if not admin:
            return jsonify({"message": "The admin ID does not exist"}), 404

        return make_response(jsonify(admin.to_dict()), 200)
    
    @jwt_required()
    def post(self):
        data = request.get_json()

        if not data or not all(key in data for key in ["name", "email", "phone_number"]):
            return jsonify({"message": "Missing required fields"}), 400

        new_admin = Admin(
            name=data["name"],
            email=data["email"],
            phone_number=data["phone_number"],
            is_superadmin=data.get("is_superadmin", False)  # Default to False if not provided
        )

        db.session.add(new_admin)
        db.session.commit()

        return make_response(jsonify(new_admin.to_dict()), 201)
    
    @jwt_required()
    def put(self, id):
        admin = Admin.query.get(id)

        if not admin:
            return jsonify({"message": f"Admin with ID {id} does not exist"}), 400

        data = request.get_json()

        admin.name = data.get("name", admin.name)
        admin.email = data.get("email", admin.email)
        admin.phone_number = data.get("phone_number", admin.phone_number)
        admin.is_superadmin = data.get("is_superadmin", admin.is_superadmin)

        db.session.commit()

        return jsonify({"message": "Admin updated successfully"}), 200
    
    @jwt_required()
    def delete(self, id):
        delete_admin = Admin.query.filter_by(id=id).first()

        if not delete_admin:
            return jsonify({"message": "The admin does not exist"}), 404

        db.session.delete(delete_admin)
        db.session.commit()

        return jsonify({"message": f"Admin with ID {id} was successfully deleted"}), 200
