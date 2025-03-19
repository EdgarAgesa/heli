from flask import Flask
from flask_migrate import Migrate
from flask_restful import Api
from flask_jwt_extended import JWTManager
from flask_cors import CORS
from models import db
from bookings import BookingsResource
from client import ClientResource
from helicopter import HelicopterResource
from payments import PaymentsResource
from auth import auth_bp, jwt  
from admin import admin_auth_bp  # ✅ Import your admin blueprint

app = Flask(__name__)

# Enable CORS for all routes
CORS(app)

# Configurations
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///db.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False  
app.config["JSON_COMPACT"] = True
app.config["JWT_SECRET_KEY"] = "Helicopter stuff"

# Initialize extensions
db.init_app(app)
migrate = Migrate(app, db)
jwt.init_app(app)

api = Api(app)

# Register blueprints
app.register_blueprint(auth_bp)
app.register_blueprint(admin_auth_bp)  # ✅ Register the admin routes here

# API resource registration
api.add_resource(BookingsResource, '/booking', '/booking/<int:id>')
api.add_resource(ClientResource, '/client', '/client/<int:id>')
api.add_resource(HelicopterResource, '/helicopter', '/helicopter/<int:id>')
api.add_resource(PaymentsResource, '/payments')

if __name__ == '__main__':
    app.run(debug=True)
