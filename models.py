from flask_sqlalchemy import SQLAlchemy
from sqlalchemy_serializer import SerializerMixin  
from datetime import datetime  
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class BaseModel(db.Model, SerializerMixin):
    __abstract__ = True

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(60), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)  
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)  

    def __repr__(self):
        return f"{self.__class__.__name__} (id={self.id}, name={self.name})"

class Client(BaseModel):
    __tablename__ = "clients"

    phone_number = db.Column(db.String(14), unique=True, nullable=False)  
    email = db.Column(db.String(90), unique=True, nullable=True)
    password = db.Column(db.String(128), nullable=False)  

    bookings = db.relationship('Booking', backref='client', lazy=True) 

    def set_password(self, password):
        """Hashes and sets the password"""
        self.password = generate_password_hash(password)

    def check_password(self, password):
        """Verifies the password"""
        return check_password_hash(self.password, password)

class Admin(BaseModel):
    __tablename__ = "admins"

    phone_number = db.Column(db.String(14), unique=True, nullable=False)  
    email = db.Column(db.String(90), unique=True, nullable=True)
    is_superadmin = db.Column(db.Boolean, default=False)  

class Helicopter(BaseModel):
    __tablename__ = "helicopters"

    model = db.Column(db.String, unique=True, nullable=False)
    capacity = db.Column(db.Integer, nullable=False)  

    bookings = db.relationship('Booking', backref='helicopter', lazy=True)  

class Booking(BaseModel):
    __tablename__ = "bookings"

    time = db.Column(db.Time, nullable=False)
    date = db.Column(db.Date, nullable=False)
    purpose = db.Column(db.String, nullable=False)
    status = db.Column(db.String, default="pending")  

    helicopter_id = db.Column(db.Integer, db.ForeignKey('helicopters.id'), nullable=False) 
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=False) 
    payment_id = db.Column(db.Integer, db.ForeignKey('payments.id'), nullable=True)  

class Payment(BaseModel):
    __tablename__ = "payments"

    amount = db.Column(db.Integer, nullable=False)
    payment_status = db.Column(db.String, default="pending")  

    receipts = db.relationship('Receipt', backref='payment', lazy=True)

class Receipt(BaseModel):
    __tablename__ = "receipts"

    receipt_number = db.Column(db.String, nullable=False)  
    payment_id = db.Column(db.Integer, db.ForeignKey('payments.id'), nullable=False)
