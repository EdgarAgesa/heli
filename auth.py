from datetime import timedelta
from flask_jwt_extended import (
    jwt_required, create_access_token, create_refresh_token,
    current_user, get_jwt_identity, decode_token, verify_jwt_in_request
)
from flask import Blueprint, request, url_for, current_app
from flask_restful import Resource, Api, reqparse
from itsdangerous import URLSafeTimedSerializer
from models import Client, Admin
from extensions import jwt, bcrypt, db, logger
from firebase_notification import generate_fcm_token
from email_utils import send_password_reset_email  # You need to implement this

auth_bp = Blueprint('auth_bp', __name__, url_prefix='/auth')
auth_api = Api(auth_bp)

# Extended token expiration times
ACCESS_EXPIRES = timedelta(days=30)  # Access token now lasts 30 days
REFRESH_EXPIRES = timedelta(days=90)  # Refresh token now lasts 90 days

def init_jwt(app):
    """Initialize JWT loaders for both client and admin authentication"""
    
    @jwt.user_lookup_loader
    def user_lookup_callback(_jwt_header, jwt_data):
        identity = jwt_data["sub"]
        try:
            # First try to find a client
            user = Client.query.get(identity)
            if user:
                return user
                
            # If not found, try to find an admin
            admin = Admin.query.get(identity)
            if admin:
                return admin
                
            return None
        except (ValueError, TypeError):
            logger.error(f"Invalid user_id format: {identity}")
            return None
    
    @jwt.user_identity_loader
    def user_identity_callback(user):
        # If user is already an ID, return it as is
        if isinstance(user, (int, str)):
            return user
            
        # If user is a model instance, return its ID
        if isinstance(user, (Client, Admin)):
            return user.id
            
        # Default case
        return None

register_args = reqparse.RequestParser()
register_args.add_argument('name', type=str, required=True, help='Name is required')
register_args.add_argument('email', type=str, required=True, help='Email is required')
register_args.add_argument('phone_number', type=str, required=True, help='Phone number is required')
register_args.add_argument('password', type=str, required=True, help='Password is required')
register_args.add_argument('confirmation_password', type=str, required=True, help='Password confirmation is required')

class Signup(Resource):
    def post(self):
        data = register_args.parse_args()
        
        if data["password"] != data["confirmation_password"]:
            return {"message": "Passwords don't match"}, 400
        
        if Client.query.filter_by(email=data['email']).first():
            return {"message": "Email already exists"}, 400
        
        hashed_password = bcrypt.generate_password_hash(data["password"]).decode('utf-8')
        
        # Generate FCM token automatically
        fcm_token = generate_fcm_token()
        
        new_user = Client(
            name=data["name"],
            email=data["email"],
            phone_number=data["phone_number"],
            password=hashed_password,
            fcm_token=fcm_token
        )
        
        db.session.add(new_user)
        db.session.commit()
        
        return {
            "message": "Signup successful",
            "client_id": new_user.id,
            "fcm_token": fcm_token
        }, 201

login_args = reqparse.RequestParser()
login_args.add_argument('email', type=str, required=True, help='Email is required')
login_args.add_argument('password', type=str, required=True, help='Password is required')

class Login(Resource):
    def post(self):
        data = login_args.parse_args()
        
        user = Client.query.filter_by(email=data["email"]).first()
        
        if not user or not bcrypt.check_password_hash(user.password, data["password"]):
            return {"message": "Invalid email or password"}, 401
        
        # Clear any existing FCM token
        user.fcm_token = None
        
        # Generate new FCM token
        user.fcm_token = generate_fcm_token()
        db.session.commit()
        
        # Create tokens
        access_token = create_access_token(
            identity=str(user.id),  # Convert to string here
            expires_delta=ACCESS_EXPIRES,
            additional_claims={
                'role': 'user',
                'email': user.email
            }
        )
        refresh_token = create_refresh_token(
            identity=str(user.id),  # Convert to string here
            expires_delta=REFRESH_EXPIRES
        )
        
        logger.info(f"Created tokens for user {user.id}")
        
        # Log token creation
        logger.info(f"Created access token for user {user.id}")
        
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "client_id": user.id,
            "fcm_token": user.fcm_token,
            "name": user.name,
            "email": user.email
        }, 200

    @jwt_required()
    def get(self):
        return {
            "client_id": current_user.id,
            "email": current_user.email,
            "name": current_user.name,
            "fcm_token": current_user.fcm_token
        }, 200

class Logout(Resource):
    @jwt_required()
    def post(self):
        try:
            verify_jwt_in_request()
            user_id = get_jwt_identity()
            
            # Try to find user in both Client and Admin tables
            user = Client.query.get(user_id)
            if not user:
                user = Admin.query.get(user_id)
            
            if user:
                user.fcm_token = None
                db.session.commit()
                
            return {"message": "Successfully logged out"}, 200
        except Exception as e:
            logger.error(f"Error during logout: {str(e)}")
            return {"message": "Error during logout"}, 422

# Serializer for generating tokens
def get_serializer():
    return URLSafeTimedSerializer(current_app.config["JWT_SECRET_KEY"])

class ForgotPassword(Resource):
    def post(self):
        data = request.get_json()
        email = data.get("email")
        user = Client.query.filter_by(email=email).first()
        user_type = "client"
        if not user:
            user = Admin.query.filter_by(email=email).first()
            user_type = "admin"
        if not user:
            return {"message": "If the email exists, a reset link will be sent."}, 200

        serializer = get_serializer()
        token = serializer.dumps({"email": user.email, "type": user_type}, salt="password-reset-salt")
        frontend_url = "https://dejair-skyline-rentals.vercel.app"  # <-- your frontend base URL
        reset_url = f"{frontend_url}/reset-password?token={token}"
        send_password_reset_email(user.email, reset_url)
        return {"message": "If the email exists, a reset link will be sent."}, 200

class ResetPassword(Resource):
    def post(self):
        data = request.get_json()
        token = data.get("token")
        new_password = data.get("new_password")
        confirm_password = data.get("confirm_password")
        if new_password != confirm_password:
            return {"message": "Passwords do not match."}, 400

        serializer = get_serializer()
        try:
            data_token = serializer.loads(token, salt="password-reset-salt", max_age=3600)
            email = data_token["email"]
            user_type = data_token.get("type", "client")

            if user_type == "client":
                user = Client.query.filter_by(email=email).first()
            else:
                user = Admin.query.filter_by(email=email).first()

            if not user:
                return {"message": "User not found."}, 404

            # Use the model's set_password method
            user.set_password(new_password)
            db.session.commit()

            return {"message": "Password reset successful."}, 200
        except Exception as e:
            logger.error(f"Password reset error: {str(e)}")
            return {"message": "Invalid or expired token."}, 400

auth_api.add_resource(Signup, '/signup')
auth_api.add_resource(Login, '/login')
auth_api.add_resource(Logout, '/logout')
auth_api.add_resource(ForgotPassword, '/forgot-password')
auth_api.add_resource(ResetPassword, '/reset-password', endpoint='resetpassword')