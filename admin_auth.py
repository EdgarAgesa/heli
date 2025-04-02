from flask_restful import Resource, reqparse
from flask_jwt_extended import create_access_token, create_refresh_token
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from models import Admin
from firebase_notification import generate_fcm_token

db = SQLAlchemy()

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
        
        hashed_password = generate_password_hash(data["password"]).decode('utf-8')
        
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
        
        admin = Admin.query.filter_by(email=data["email"]).first()
        
        if not admin or not check_password_hash(admin.password, data["password"]):
            return {"message": "Invalid email or password"}, 401
        
        # Generate new FCM token if admin doesn't have one
        if not admin.fcm_token:
            admin.fcm_token = generate_fcm_token()
            db.session.commit()
        
        access_token = create_access_token(identity=str(admin.id))
        refresh_token = create_refresh_token(identity=str(admin.id))

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "admin_id": admin.id,
            "fcm_token": admin.fcm_token
        }, 200 