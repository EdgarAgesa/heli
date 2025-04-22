from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy_serializer import SerializerMixin
from datetime import time, date
from extensions import bcrypt, db

# db = SQLAlchemy()

class BaseModel(db.Model, SerializerMixin):
    __abstract__ = True

    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"{self.__class__.__name__} (id={self.id})"

    def to_dict(self):
        result = {}
        for column in self.__table__.columns:
            value = getattr(self, column.name)
            if isinstance(value, time):
                result[column.name] = value.isoformat()
            elif isinstance(value, date):
                result[column.name] = value.isoformat()
            else:
                result[column.name] = value
        return result

class Client(BaseModel):
    __tablename__ = "clients"

    name = db.Column(db.String(60), nullable=False)
    phone_number = db.Column(db.String(14), unique=True, nullable=False)
    email = db.Column(db.String(90), unique=True, nullable=True)
    password = db.Column(db.String(128), nullable=False)
    fcm_token = db.Column(db.String(255))  # Firebase Cloud Messaging token
    bookings = db.relationship('Booking', backref='client', lazy=True, cascade="all, delete-orphan")

    def set_password(self, password):
        self.password = bcrypt.generate_password_hash(password).decode('utf-8')

    def check_password(self, password):
        return bcrypt.check_password_hash(self.password, password)

class Admin(BaseModel):
    __tablename__ = "admins"

    name = db.Column(db.String(60), nullable=False)
    phone_number = db.Column(db.String(14), unique=True, nullable=False)
    email = db.Column(db.String(90), unique=True, nullable=True)
    password = db.Column(db.String(128), nullable=False)  # Use this directly
    is_superadmin = db.Column(db.Boolean, default=False)
    fcm_token = db.Column(db.String(255))  # Firebase Cloud Messaging token

    def set_password(self, password):
        """Hash and set the password"""
        self.password = bcrypt.generate_password_hash(password).decode('utf-8')

    def check_password(self, password):
        """Check if the password matches"""
        return bcrypt.check_password_hash(self.password, password)

    def __repr__(self):
        return f"Admin (id={self.id})"

class Helicopter(BaseModel):
    __tablename__ = "helicopters"

    model = db.Column(db.String, unique=True, nullable=False)
    capacity = db.Column(db.Integer, nullable=False)
    image_url = db.Column(db.String)
    bookings = db.relationship('Booking', backref='helicopter', lazy=True, cascade="all, delete-orphan")

    def as_dict(self):
        return {
            'id': self.id,
            'model': self.model,
            'capacity': self.capacity,
            'image_url': self.image_url,
            'bookings': [booking.to_dict() for booking in self.bookings]
        }

class Payment(BaseModel):
    __tablename__ = "payments"

    amount = db.Column(db.Integer, nullable=False)
    phone_number = db.Column(db.String(14), nullable=False)
    merchant_request_id = db.Column(db.String(50), nullable=False)
    checkout_request_id = db.Column(db.String(50), nullable=False)
    payment_status = db.Column(db.String, default="pending")
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

class ChatMessage(BaseModel):
    __tablename__ = "chat_messages"

    booking_id = db.Column(
        db.Integer,
        db.ForeignKey('bookings.id', ondelete="CASCADE"),  # <-- Add ondelete
        nullable=False
    )
    sender_id = db.Column(db.Integer, nullable=False)  # ID of user who sent the message
    sender_type = db.Column(db.String, nullable=False)  # 'client' or 'admin'
    message = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    booking = db.relationship(
        'Booking',
        back_populates='chat_messages'
    )

    def to_dict(self):
        return {
            'id': self.id,
            'booking_id': self.booking_id,
            'sender_id': self.sender_id,
            'sender_type': self.sender_type,
            'message': self.message,
            'is_read': self.is_read,
            'created_at': self.created_at.isoformat()
        }

class Booking(BaseModel):
    __tablename__ = "bookings"

    time = db.Column(db.Time, nullable=False)
    date = db.Column(db.Date, nullable=False)
    purpose = db.Column(db.String, nullable=False)
    status = db.Column(db.String, default="pending")
    original_amount = db.Column(db.Integer)  # Initial price
    final_amount = db.Column(db.Integer)  # Negotiated price
    negotiation_status = db.Column(db.String, default="none")  # none, requested, counter_offer, accepted, rejected
    num_passengers = db.Column(db.Integer, nullable=False)  # Number of passengers
    helicopter_id = db.Column(db.Integer, db.ForeignKey('helicopters.id', ondelete="CASCADE"), nullable=False)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id', ondelete="CASCADE"), nullable=False)
    payment_id = db.Column(db.Integer, db.ForeignKey('payments.id', ondelete="CASCADE"), nullable=True)
    has_unread_messages = db.Column(db.Boolean, default=False)  # Track unread messages
    last_message_at = db.Column(db.DateTime)  # Track last message timestamp
    chat_messages = db.relationship(
        'ChatMessage',
        back_populates='booking',
        lazy=True,
        cascade="all, delete-orphan"
    )

    def as_dict(self):
        return {
            'id': self.id,
            'time': self.time.isoformat(),
            'date': self.date.isoformat(),
            'purpose': self.purpose,
            'status': self.status,
            'original_amount': self.original_amount,
            'final_amount': self.final_amount,
            'negotiation_status': self.negotiation_status,
            'num_passengers': self.num_passengers,
            'helicopter': self.helicopter.as_dict(),
            'client': self.client.to_dict(),
            'payment': self.payment.to_dict() if self.payment else None,
            'has_unread_messages': self.has_unread_messages,
            'last_message_at': self.last_message_at.isoformat() if self.last_message_at else None,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }

class NegotiationHistory(BaseModel):
    __tablename__ = "negotiation_history"

    booking_id = db.Column(db.Integer, db.ForeignKey('bookings.id'), nullable=False)
    user_id = db.Column(db.Integer, nullable=False)  # ID of user who made the change
    user_type = db.Column(db.String, nullable=False)  # 'client' or 'admin'
    old_amount = db.Column(db.Integer)
    new_amount = db.Column(db.Integer)
    action = db.Column(db.String, nullable=False)  # 'request', 'counter', 'accept', 'reject'
    notes = db.Column(db.String)

    def to_dict(self):
        return {
            'id': self.id,
            'booking_id': self.booking_id,
            'user_id': self.user_id,
            'user_type': self.user_type,
            'old_amount': self.old_amount,
            'new_amount': self.new_amount,
            'action': self.action,
            'notes': self.notes,
            'created_at': self.created_at.isoformat()
        }