from flask import Flask, jsonify
from flask_migrate import Migrate
from flask_restful import Api
from flask_cors import CORS
from datetime import timedelta
import os
from dotenv import load_dotenv
import logging
from extensions import jwt, bcrypt, db, mail

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Enable CORS for all routes with proper configuration
CORS(app, resources={
    r"/*": {
        "origins": [
            "http://localhost:8080", 
            "http://127.0.0.1:8080",
            "https://dej-air.netlify.app"
        ],
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"],
        "supports_credentials": True
    }
})

# Configurations
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///db.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False  
app.config["JSON_COMPACT"] = True
app.config["JWT_SECRET_KEY"] = "Helicopter stuff"
app.config["JWT_TOKEN_LOCATION"] = ["headers"]
app.config["JWT_HEADER_NAME"] = "Authorization"
app.config["JWT_HEADER_TYPE"] = "Bearer"
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(days=30)
app.config["JWT_REFRESH_TOKEN_EXPIRES"] = timedelta(days=90)
app.config["JWT_ERROR_MESSAGE_KEY"] = "error"

# JWT Error handlers
@jwt.invalid_token_loader
def invalid_token_callback(error_string):
    logger.error(f"Invalid token: {error_string}")
    return jsonify({
        'error': 'Invalid token',
        'message': error_string
    }), 422

@jwt.unauthorized_loader
def missing_token_callback(error_string):
    logger.error(f"Missing token: {error_string}")
    return jsonify({
        'error': 'Authorization required',
        'message': error_string
    }), 401

@jwt.expired_token_loader
def expired_token_callback(jwt_header, jwt_data):
    logger.error(f"Expired token: {jwt_data}")
    return jsonify({
        'error': 'Token has expired',
        'message': 'Please log in again'
    }), 401

# Email Configuration
app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER')
app.config['MAIL_PORT'] = int(os.getenv('MAIL_PORT', 587))
app.config['MAIL_USE_TLS'] = os.getenv('MAIL_USE_TLS', 'True') == 'True'
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_DEFAULT_SENDER')
app.config['MAIL_MAX_EMAILS'] = None
app.config['MAIL_ASCII_ATTACHMENTS'] = False

# Initialize Flask-SQLAlchemy first
db.init_app(app)

# Create all database tables
with app.app_context():
    # Import models here, after db is initialized but before Migrate
    from models import Admin, Client, Booking, Payment, Helicopter, ChatMessage, NegotiationHistory
    
    # Initialize migrations
    migrate = Migrate(app, db)
    
    # Initialize other extensions
    bcrypt.init_app(app)
    mail.init_app(app)
    jwt.init_app(app)
    
    # Initialize JWT loaders
    from auth import init_jwt
    init_jwt(app)
    
    # Initialize Firebase
    from firebase_notification import initialize_firebase
    initialize_firebase(app)

# Create API instance
api = Api(app)

# Import routes after all extensions are initialized
from bookings import BookingsResource, NegotiatedPaymentResource, NegotiationHistoryResource, FCMTokenResource, BookingStatusResource
from client import ClientResource
from helicopter import HelicopterResource
from payments import PaymentsResource, PaymentResource
from auth import auth_bp
from admin import admin_auth_bp
from chat import ChatResource, NegotiationChatsResource, UnreadChatsResource, ChatReadResource
from admin_bookings import AdminBookingManagementResource

# Register blueprints
from auth import auth_bp
from admin_auth import admin_auth_bp
from chat import chat_bp

app.register_blueprint(auth_bp)
app.register_blueprint(admin_auth_bp)
app.register_blueprint(chat_bp, url_prefix='/booking')

# API resource registration
api.add_resource(BookingsResource, '/booking', '/booking/<int:id>')
api.add_resource(ClientResource, '/client', '/client/<int:id>')
api.add_resource(HelicopterResource, '/helicopter', '/helicopter/<int:id>')
api.add_resource(PaymentsResource, '/payments')
api.add_resource(PaymentResource, '/booking/<int:id>/payment')

# New negotiation-related routes
api.add_resource(NegotiatedPaymentResource, '/booking/<int:booking_id>/pay-negotiated')
api.add_resource(FCMTokenResource, '/fcm-token')
api.add_resource(NegotiationHistoryResource, '/booking/<int:booking_id>/negotiation-history')
api.add_resource(BookingStatusResource, '/booking/<int:booking_id>/status')

# Chat routes
api.add_resource(ChatResource, '/booking/<int:booking_id>/chat')
api.add_resource(ChatReadResource, '/booking/<int:booking_id>/chat/read')
api.add_resource(NegotiationChatsResource, '/negotiation-chats')
api.add_resource(UnreadChatsResource, '/chat/unread')

# Admin booking management routes
api.add_resource(AdminBookingManagementResource, '/admin/bookings/<string:booking_type>')

# Make mail instance available globally
app.mail = mail

if __name__ == '__main__':
    app.run(debug=True)