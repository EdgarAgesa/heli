from datetime import timedelta
from flask_jwt_extended import JWTManager, jwt_required, create_access_token, create_refresh_token, current_user
from flask import Blueprint
from flask_restful import Api, Resource, reqparse
from models import Client, db
from flask_bcrypt import Bcrypt
from flask_jwt_extended import decode_token

auth_bp = Blueprint('auth_bp', __name__, url_prefix='/auth')
auth_api = Api(auth_bp)
bcrypt = Bcrypt()

jwt = JWTManager()

ACCESS_EXPIRES = timedelta(hours=360) 
REFRESH_EXPIRES = timedelta(days=7) 



@jwt.user_lookup_loader
def user_lookup_callback(_jwt_header, jwt_data):
    identity = jwt_data["sub"]
    return Client.query.filter_by(id=identity).first()

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
        
        new_user = Client(
            name=data["name"],
            email=data["email"],
            phone_number=data["phone_number"],
            password=hashed_password
        )
        
        db.session.add(new_user)
        db.session.commit()
        
        return {"message": "Signup successful"}, 201

login_args = reqparse.RequestParser()
login_args.add_argument('email', type=str, required=True, help='Email is required')
login_args.add_argument('password', type=str, required=True, help='Password is required')

class Login(Resource):
    def post(self):
        data = login_args.parse_args()
        
        user = Client.query.filter_by(email=data["email"]).first()
        
        if not user or not bcrypt.check_password_hash(user.password, data["password"]):
            return {"message": "Invalid email or password"}, 401
        
        access_token = create_access_token(identity=str(user.id))
        refresh_token = create_refresh_token(identity=str(user.id))

        jwt.access_token_expires = ACCESS_EXPIRES
        jwt.refresh_token_expires = REFRESH_EXPIRES
        
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "client_id": user.id
        }, 200

    @jwt_required()
    def get(self):
        return {
            "client_id": current_user.id,
            "email": current_user.email
        }, 200

auth_api.add_resource(Signup, '/signup')
auth_api.add_resource(Login, '/login')