from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy_serializer import SerializerMixin
from datetime import time, date

db = SQLAlchemy()

class BaseModel(db.Model, SerializerMixin):
    __abstract__ = True

    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"{self.__class__.__name__} (id={self.id})"

    def to_dict(self):
        # Convert all columns to a dictionary
        result = {}
        for column in self.__table__.columns:
            value = getattr(self, column.name)
            # Handle time and date objects
            if isinstance(value, time):
                result[column.name] = value.isoformat()  # Convert time to string
            elif isinstance(value, date):
                result[column.name] = value.isoformat()  # Convert date to string
            else:
                result[column.name] = value
        return result

class Client(BaseModel):
    __tablename__ = "clients"

    name = db.Column(db.String(60), nullable=False)
    phone_number = db.Column(db.String(14), unique=True, nullable=False)  
    email = db.Column(db.String(90), unique=True, nullable=True)
    password = db.Column(db.String(128), nullable=False)  

    # Cascade deletes for bookings when a client is deleted
    bookings = db.relationship('Booking', backref='client', lazy=True, cascade="all, delete-orphan")

    def set_password(self, password):
        self.password = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password, password)

class Admin(BaseModel):
    __tablename__ = "admins"

    name = db.Column(db.String(60), nullable=False)
    phone_number = db.Column(db.String(14), unique=True, nullable=False)  
    email = db.Column(db.String(90), unique=True, nullable=True)
    password = db.Column(db.String(128), nullable=False) 
    is_superadmin = db.Column(db.Boolean, default=False)

    def set_password(self, password):
        self.password = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password, password)

class Helicopter(BaseModel):
    __tablename__ = "helicopters"

    model = db.Column(db.String, unique=True, nullable=False)
    capacity = db.Column(db.Integer, nullable=False)
    image_url = db.Column(db.String)  

    # Cascade deletes for bookings when a helicopter is deleted
    bookings = db.relationship('Booking', backref='helicopter', lazy=True, cascade="all, delete-orphan")

    def as_dict(self):
        return {
            'id': self.id,
            'model': self.model,
            'capacity': self.capacity,
            'image_url': self.image_url,
            'bookings': [booking.to_dict() for booking in self.bookings]  # Convert Booking objects to dictionaries
        }  

class Payment(BaseModel):
    __tablename__ = "payments"

    amount = db.Column(db.Integer, nullable=False)
    phone_number = db.Column(db.String(14), nullable=False)  # Phone number used for payment
    merchant_request_id = db.Column(db.String(50), nullable=False)  # M-Pesa MerchantRequestID
    checkout_request_id = db.Column(db.String(50), nullable=False)  # M-Pesa CheckoutRequestID
    payment_status = db.Column(db.String, default="pending")  # Payment status (pending, confirmed, failed)

    # Cascade deletes for bookings when a payment is deleted
    bookings = db.relationship('Booking', backref='payment', lazy=True, cascade="all, delete-orphan")

    def to_dict(self):
        return {
            'id': self.id,
            'amount': self.amount,
            'phone_number': self.phone_number,
            'merchant_request_id': self.merchant_request_id,
            'checkout_request_id': self.checkout_request_id,
            'payment_status': self.payment_status,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }

class Booking(BaseModel):
    __tablename__ = "bookings"

    time = db.Column(db.Time, nullable=False)
    date = db.Column(db.Date, nullable=False)
    purpose = db.Column(db.String, nullable=False)
    status = db.Column(db.String, default="pending") 
    final_amount = db.Column(db.Integer, nullable=True)  
    negotiation_status = db.Column(db.String, default="none")  

    helicopter_id = db.Column(db.Integer, db.ForeignKey('helicopters.id', ondelete="CASCADE"), nullable=False) 
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id', ondelete="CASCADE"), nullable=False) 
    payment_id = db.Column(db.Integer, db.ForeignKey('payments.id', ondelete="CASCADE"), nullable=True)

    def as_dict(self):
        return {
            'id': self.id,
            'time': self.time.isoformat(),  # Convert time to string
            'date': self.date.isoformat(),  # Convert date to string
            'purpose': self.purpose,
            'status': self.status,
            'helicopter': self.helicopter.as_dict(),  # Convert Helicopter object to dictionary
            'client': self.client.to_dict(),  # Convert Client object to dictionary
            'final_amount': self.final_amount,
            'negotiation_status': self.negotiation_status,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'payment_id': self.payment_id,
            'payment': self.payment.to_dict() if self.payment else None  # Convert Payment object to dictionary
        }

class Receipt(BaseModel):
    __tablename__ = "receipts"

    receipt_number = db.Column(db.String, nullable=False)  
    payment_id = db.Column(db.Integer, db.ForeignKey('payments.id', ondelete="CASCADE"), nullable=False)

    def to_dict(self):
        return {
            'id': self.id,
            'receipt_number': self.receipt_number,
            'payment_id': self.payment_id,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }