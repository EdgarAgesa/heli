from flask_jwt_extended import JWTManager
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager
from flask_bcrypt import Bcrypt
from flask_mail import Mail
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Create logger
logger = logging.getLogger('heli')

# Initialize extensions
db = SQLAlchemy()
jwt = JWTManager()
bcrypt = Bcrypt()
mail = Mail()
logger = logging.getLogger(__name__)
