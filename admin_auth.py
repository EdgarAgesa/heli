from flask_restful import Resource, reqparse, Api
from flask import Blueprint
from flask_jwt_extended import create_access_token, create_refresh_token, jwt_required, get_jwt_identity
from werkzeug.security import check_password_hash
from models import Admin
from extensions import db, logger, bcrypt
from firebase_notification import generate_fcm_token
from datetime import timedelta

# Extended token expiration times
ACCESS_EXPIRES = timedelta(days=30)
REFRESH_EXPIRES = timedelta(days=90)

# Create blueprint
admin_auth_bp = Blueprint('admin_auth_bp', __name__, url_prefix='/admin')
admin_auth_api = Api(admin_auth_bp)

class AdminSignup(Resource):
    def post(self):
        register_args = reqparse.RequestParser()
        register_args.add_argument('name', type=str, required=True, help='Name is required')
        register_args.add_argument('email', type=str, required=True, help='Email is required')
        register_args.add_argument('phone_number', type=str, required=True, help='Phone number is required')
        register_args.add_argument('password', type=str, required=True, help='Password is required')
        register_args.add_argument('confirmation_password', type=str, required=True, help='Password confirmation is required')

        data = register_args.parse_args()
        
        if data["password"] != data["confirmation_password"]:
            return {"message": "Passwords don't match"}, 400
        
        if Admin.query.filter_by(email=data['email']).first():
            return {"message": "Email already exists"}, 400
        
        # Hash the password using bcrypt
        hashed_password = bcrypt.generate_password_hash(data["password"]).decode('utf-8')
        
        # Generate FCM token automatically
        fcm_token = generate_fcm_token()
        
        new_admin = Admin(
            name=data["name"],
            email=data["email"],
            phone_number=data["phone_number"],
            password=hashed_password,
            fcm_token=fcm_token
        )
        
        db.session.add(new_admin)
        db.session.commit()
        
        return {
            "message": "Admin signup successful",
            "fcm_token": fcm_token
        }, 201

class AdminLogin(Resource):
    def post(self):
        login_args = reqparse.RequestParser()
        login_args.add_argument('email', type=str, required=True, help='Email is required')
        login_args.add_argument('password', type=str, required=True, help='Password is required')

        data = login_args.parse_args()
        
        print("Admin login attempt:", data["email"])
        admin = Admin.query.filter_by(email=data["email"]).first()
        print("Admin found:", admin)

        # Use the check_password method from the Admin model
        if not admin or not admin.check_password(data["password"]):
            return {"message": "Invalid email or password"}, 401
        
        # Generate new FCM token if needed
        if not admin.fcm_token:
            admin.fcm_token = generate_fcm_token()
            db.session.commit()
        
        access_token = create_access_token(
            identity=str(admin.id),
            expires_delta=ACCESS_EXPIRES,
            additional_claims={
                'role': 'admin',
                'email': admin.email
            }
        )
        refresh_token = create_refresh_token(
            identity=str(admin.id),
            expires_delta=REFRESH_EXPIRES
        )
        
        logger.info(f"Created admin tokens for user {admin.id}")
        
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "admin_id": admin.id,
            "fcm_token": admin.fcm_token
        }, 200

class AdminLogout(Resource):
    @jwt_required()
    def post(self):
        try:
            user_id = get_jwt_identity()
            admin = Admin.query.get(user_id)
            
            if admin:
                admin.fcm_token = None
                db.session.commit()
                logger.info(f"Admin {user_id} logged out successfully")
                return {"message": "Successfully logged out"}, 200
            
            logger.error(f"Admin not found for ID: {user_id}")
            return {"message": "Admin not found"}, 404
            
        except Exception as e:
            logger.error(f"Error during admin logout: {str(e)}")
            return {"message": "Error during logout"}, 422

# Add resources
admin_auth_api.add_resource(AdminSignup, '/signup')
admin_auth_api.add_resource(AdminLogin, '/login')
admin_auth_api.add_resource(AdminLogout, '/logout')