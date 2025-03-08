from flask import Flask
from flask_migrate import Migrate
from flask_restful import Api
from flask_jwt_extended import JWTManager
from flask_cors import CORS  # Import CORS
from models import db
from bookings import BookingsResource
from client import ClientResource
from admin import AdminResource
from helicopter import HelicopterResource
from auth import auth_bp, jwt  

app = Flask(__name__)

# Enable CORS for all routes
CORS(app)  # Initialize CORS

# ✅ Corrected database configuration
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///db.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False  
app.config["JSON_COMPACT"] = True
app.config["JWT_SECRET_KEY"] = "Helicopter stuff"

# ✅ Initialize extensions
db.init_app(app)
migrate = Migrate(app, db)
jwt.init_app(app)  #

api = Api(app)

app.register_blueprint(auth_bp) 

# ✅ Fixed API resource registration
api.add_resource(BookingsResource, '/booking', '/booking/<int:id>')
api.add_resource(ClientResource, '/client', '/client/<int:id>')
api.add_resource(AdminResource, '/admin', '/admin/<int:id>')
api.add_resource(HelicopterResource, '/helicopter', '/helicopter/<int:id>')

if __name__ == '__main__':
    app.run(debug=True)