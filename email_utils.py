from flask import current_app, render_template
from flask_mail import Message
from datetime import datetime
from extensions import mail  # <-- Add this import

def send_payment_receipt_email(booking, payment, client):
    """Send payment receipt email to client"""
    print("send_payment_receipt_email called")
    try:
        with current_app.app_context():
            msg = Message(
                subject=f"Payment Receipt - Booking #{booking.id}",
                recipients=[client.email],
                sender=current_app.config['MAIL_DEFAULT_SENDER']
            )
            # Use your HTML template for a styled, detailed email
            msg.html = render_template(
                'payment_receipt.html',
                booking=booking,
                payment=payment,
                client=client,
                date=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            )
            mail.send(msg)
            current_app.logger.info(f"Payment receipt email sent to {client.email}")
            print(f"Payment receipt email sent to {client.email}")
            return True
    except Exception as e:
        current_app.logger.error(f"Failed to send payment receipt email: {str(e)}")
        print(f"Failed to send payment receipt email: {str(e)}")
        return False

def send_booking_confirmation_email(booking, client):
    """Send booking confirmation email to client"""
    try:
        with current_app.app_context():
            msg = Message(
                subject=f"Booking Confirmation - Booking #{booking.id}",
                recipients=[client.email],
                sender=current_app.config['MAIL_DEFAULT_SENDER']
            )
            
            msg.html = render_template(
                'booking_confirmation.html',
                booking=booking,
                client=client,
                date=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            )
            
            # Use current_app.mail instead of importing mail
            mail.send(msg)
            current_app.logger.info(f"Booking confirmation email sent to {client.email}")
            return True
    except Exception as e:
        current_app.logger.error(f"Failed to send booking confirmation email: {str(e)}")
        return False

def send_password_reset_email(email, reset_url):
    from flask_mail import Message
    from flask import current_app
    msg = Message(
        subject="Password Reset Request",
        recipients=[email],
        body=f"Click the link to reset your password: {reset_url}"
    )
    mail = current_app.extensions.get('mail')
    mail.send(msg)