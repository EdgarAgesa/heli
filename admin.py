from flask import Blueprint, jsonify
from flask_restful import Api, Resource, reqparse
from flask_jwt_extended import (
    jwt_required, create_access_token,
    create_refresh_token, get_jwt_identity
)
from datetime import timedelta
from admin_decorator import superadmin_required, admin_required
from firebase_notification import generate_fcm_token
from extensions import jwt, bcrypt, db
from models import Admin

admin_auth_bp = Blueprint('admin_auth_bp', __name__, url_prefix='/admin')
admin_api = Api(admin_auth_bp)

# JWT callbacks are now handled in auth.py

login_args = reqparse.RequestParser()
login_args.add_argument('email', type=str, required=True, help='Email is required')
login_args.add_argument('password', type=str, required=True, help='Password is required')

admin_register_args = reqparse.RequestParser()
admin_register_args.add_argument('name', type=str, required=True, help='Name is required')
admin_register_args.add_argument('email', type=str, required=True, help='Email is required')
admin_register_args.add_argument('phone_number', type=str, required=True, help='Phone number is required')
admin_register_args.add_argument('password', type=str, required=True, help='Password is required')
admin_register_args.add_argument('is_superadmin', type=bool, default=False)

class AdminLogin(Resource):
    def post(self):
        data = login_args.parse_args()
        
        admin = Admin.query.filter_by(email=data["email"]).first()
        
        if not admin or not bcrypt.check_password_hash(admin.password, data["password"]):
            return {"message": "Invalid email or password"}, 401
        
        # Generate new FCM token
        admin.fcm_token = generate_fcm_token()
        db.session.commit()
        
        access_token = create_access_token(
            identity=admin,
            expires_delta=timedelta(days=30)
        )
        refresh_token = create_refresh_token(
            identity=admin,
            expires_delta=timedelta(days=90)
        )

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "admin_id": admin.id,
            "fcm_token": admin.fcm_token,
            "is_superadmin": admin.is_superadmin,
            "name": admin.name
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
