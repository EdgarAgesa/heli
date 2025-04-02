from flask import Blueprint, jsonify
from flask_restful import Api, Resource, reqparse
from models import Admin, db
from flask_bcrypt import Bcrypt
from flask_jwt_extended import (
    jwt_required, create_access_token, current_user, get_jwt_identity
)
from admin_decorator import superadmin_required, admin_required
from firebase_notification import generate_fcm_token
from auth import jwt  # Import the JWT manager from auth.py

admin_auth_bp = Blueprint('admin_auth_bp', __name__, url_prefix='/admin')
admin_api = Api(admin_auth_bp)
bcrypt = Bcrypt()

@jwt.user_lookup_loader
def admin_lookup_callback(_jwt_header, jwt_data):
    identity = jwt_data["sub"]
    admin = Admin.query.get(int(identity))
    return admin

admin_login_args = reqparse.RequestParser()
admin_login_args.add_argument('email', type=str, required=True, help='Email is required')
admin_login_args.add_argument('password', type=str, required=True, help='Password is required')

admin_register_args = reqparse.RequestParser()
admin_register_args.add_argument('name', type=str, required=True, help='Name is required')
admin_register_args.add_argument('email', type=str, required=True, help='Email is required')
admin_register_args.add_argument('phone_number', type=str, required=True, help='Phone number is required')
admin_register_args.add_argument('password', type=str, required=True, help='Password is required')
admin_register_args.add_argument('is_superadmin', type=bool, default=False)

class AdminLogin(Resource):
    def post(self):
        data = admin_login_args.parse_args()
        admin = Admin.query.filter_by(email=data["email"]).first()

        if not admin or not bcrypt.check_password_hash(admin.password, data["password"]):
            return {"message": "Invalid credentials"}, 401

        # Generate new FCM token if admin doesn't have one
        if not admin.fcm_token:
            admin.fcm_token = generate_fcm_token()
            db.session.commit()

        access_token = create_access_token(identity=str(admin.id))
        return {
            "access_token": access_token,
            "admin_id": admin.id,
            "is_superadmin": admin.is_superadmin,
            "fcm_token": admin.fcm_token
        }, 200

class AdminSignup(Resource):
    # @superadmin_required
    def post(self):
        data = admin_register_args.parse_args()

        if Admin.query.filter_by(email=data['email']).first():
            return {"message": "Admin with this email already exists"}, 400

        hashed_password = bcrypt.generate_password_hash(data["password"]).decode('utf-8')
        
        # Generate FCM token automatically
        fcm_token = generate_fcm_token()
        
        new_admin = Admin(
            name=data["name"],
            email=data["email"],
            phone_number=data["phone_number"],
            password=hashed_password,
            is_superadmin=data["is_superadmin"],
            fcm_token=fcm_token
        )
        db.session.add(new_admin)
        db.session.commit()
        return {
            "message": "Admin created successfully",
            "fcm_token": fcm_token
        }, 201

admin_api.add_resource(AdminLogin, '/login')
admin_api.add_resource(AdminSignup, '/signup')
