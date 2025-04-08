from flask import Flask
from flask_migrate import Migrate
from flask_restful import Api
from flask_jwt_extended import JWTManager
from flask_cors import CORS
from flask_mail import Mail
from models import db
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Enable CORS for all routes with proper configuration
CORS(app, resources={
    r"/*": {
        "origins": ["http://localhost:8080", "http://127.0.0.1:8080"],
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

# Email Configuration
app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
app.config['MAIL_PORT'] = int(os.getenv('MAIL_PORT', 587))
app.config['MAIL_USE_TLS'] = os.getenv('MAIL_USE_TLS', 'True').lower() == 'true'
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME', 'your-email@gmail.com')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD', 'your-app-password')
app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_DEFAULT_SENDER', 'your-email@gmail.com')
app.config['MAIL_MAX_EMAILS'] = None
app.config['MAIL_ASCII_ATTACHMENTS'] = False

# Initialize extensions
db.init_app(app)
migrate = Migrate(app, db)
jwt = JWTManager(app)

# Initialize mail with the app
mail = Mail()
mail.init_app(app)

# Initialize Firebase
from firebase_notification import initialize_firebase
initialize_firebase(app)

# Create API instance
api = Api(app)

# Import routes after all extensions are initialized
from bookings import BookingsResource, NegotiatedPaymentResource, NegotiationHistoryResource, FCMTokenResource
from client import ClientResource
from helicopter import HelicopterResource
from payments import PaymentsResource
from auth import auth_bp
from admin import admin_auth_bp
from chat import ChatResource, NegotiationChatsResource, UnreadChatsResource, ChatReadResource
from admin_bookings import AdminBookingManagementResource

# Register blueprints
app.register_blueprint(auth_bp)
app.register_blueprint(admin_auth_bp)

# API resource registration
api.add_resource(BookingsResource, '/booking', '/booking/<int:id>')
api.add_resource(ClientResource, '/client', '/client/<int:id>')
api.add_resource(HelicopterResource, '/helicopter', '/helicopter/<int:id>')
api.add_resource(PaymentsResource, '/payments')

# New negotiation-related routes
api.add_resource(NegotiatedPaymentResource, '/booking/<int:booking_id>/pay-negotiated')
api.add_resource(FCMTokenResource, '/fcm-token')
api.add_resource(NegotiationHistoryResource, '/booking/<int:booking_id>/negotiation-history')

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