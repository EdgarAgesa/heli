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

# Removed AdminLogin and AdminSignup classes and their routes
