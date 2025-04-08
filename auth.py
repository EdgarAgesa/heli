from datetime import timedelta
from flask_jwt_extended import JWTManager, jwt_required, create_access_token, create_refresh_token, current_user
from flask import Blueprint
from flask_restful import Api, Resource, reqparse
from models import Client, db
from flask_bcrypt import Bcrypt
from flask_jwt_extended import decode_token
from firebase_notification import generate_fcm_token

auth_bp = Blueprint('auth_bp', __name__, url_prefix='/auth')
auth_api = Api(auth_bp)
bcrypt = Bcrypt()

jwt = JWTManager()

# Extended token expiration times
ACCESS_EXPIRES = timedelta(days=30)  # Access token now lasts 30 days
REFRESH_EXPIRES = timedelta(days=90)  # Refresh token now lasts 90 days

@jwt.user_lookup_loader
def user_lookup_callback(_jwt_header, jwt_data):
    identity = jwt_data["sub"]
    try:
        # Convert identity to integer if it's a string
        user_id = int(identity) if isinstance(identity, str) else identity
        return Client.query.get(user_id)
    except (ValueError, TypeError):
        return None

@jwt.user_identity_loader
def user_identity_callback(user):
    if user:
        return str(user.id)
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
        
        # Generate new FCM token if user doesn't have one
        if not user.fcm_token:
            user.fcm_token = generate_fcm_token()
            db.session.commit()
        
        access_token = create_access_token(identity=str(user.id))
        refresh_token = create_refresh_token(identity=str(user.id))

        jwt.access_token_expires = ACCESS_EXPIRES
        jwt.refresh_token_expires = REFRESH_EXPIRES
        
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

auth_api.add_resource(Signup, '/signup')
auth_api.add_resource(Login, '/login')