# DejAir Helicopter Booking System Backend

## System Architecture

### Overview
The DejAir Helicopter Booking System is a comprehensive Flask-based backend system that provides a complete solution for managing helicopter bookings, payments, negotiations, and real-time communications. The system is built with a modular architecture, emphasizing security, scalability, and real-time capabilities.

### Core Components

1. **Application Core (`app.py`)**
   - Flask application initialization and configuration
   - Database setup with SQLAlchemy
   - JWT authentication setup
   - CORS configuration
   - Email service configuration
   - Firebase integration
   - API route registration
   - Blueprint registration for modular organization

2. **Database Models**
   - Client: User account management
   - Admin: Administrative user management
   - Helicopter: Aircraft inventory and details
   - Booking: Reservation management
   - Payment: Transaction records
   - Chat: Communication history
   - NegotiationHistory: Price negotiation tracking

3. **Authentication System**
   - JWT-based token authentication
   - Role-based access control (Client/Admin/Superadmin)
   - Password hashing with bcrypt
   - Token refresh mechanism
   - Session management

4. **Notification System**
   - Firebase Cloud Messaging (FCM) integration
   - Real-time push notifications
   - Email notifications via Flask-Mail
   - Topic-based notification routing
   - Custom notification templates

5. **Payment Integration**
   - M-Pesa payment gateway integration
   - Payment status tracking
   - Transaction history
   - Payment receipt generation
   - Negotiated payment handling

## Technical Stack

### Core Technologies
- **Framework**: Flask 2.x
- **Database**: SQLite with SQLAlchemy ORM
- **Authentication**: Flask-JWT-Extended
- **API**: Flask-RESTful
- **Migrations**: Flask-Migrate
- **CORS**: Flask-CORS
- **Email**: Flask-Mail

### External Services
- **Push Notifications**: Firebase Cloud Messaging
- **Payment Gateway**: M-Pesa
- **Email Service**: Gmail SMTP
- **File Storage**: Local filesystem (configurable for cloud storage)

## Security Features

1. **Authentication Security**
   - JWT token encryption
   - Password hashing with salt
   - Token expiration and refresh
   - Role-based access control

2. **API Security**
   - Request validation
   - Input sanitization
   - CORS protection
   - Rate limiting
   - Error handling

3. **Data Security**
   - Encrypted storage
   - Secure communication
   - Environment variable protection
   - Sensitive data masking

## API Documentation

### Authentication Endpoints

#### Client Authentication
1. **Register New Client**
   ```http
   POST /auth/signup
   Content-Type: application/json
   ```
   Request body and response format detailed in API examples section.

2. **Client Login**
   ```http
   POST /auth/login
   Content-Type: application/json
   ```
   Request body and response format detailed in API examples section.

#### Admin Authentication
1. **Admin Login**
   ```http
   POST /admin/login
   Content-Type: application/json
   ```
   Request body and response format detailed in API examples section.

2. **Create New Admin (Superadmin only)**
   ```http
   POST /admin/signup
   Authorization: Bearer <superadmin_token>
   Content-Type: application/json
   ```
   Request body and response format detailed in API examples section.

### Booking Management

#### Client Booking Endpoints
1. **List Client's Bookings**
   ```http
   GET /booking
   Authorization: Bearer <client_token>
   ```

2. **Create New Booking**
   ```http
   POST /booking
   Authorization: Bearer <client_token>
   Content-Type: application/json
   ```

3. **Update Booking**
   ```http
   PUT /booking/<id>
   Authorization: Bearer <client_token>
   Content-Type: application/json
   ```

#### Admin Booking Endpoints
1. **Get Negotiated Bookings**
   ```http
   GET /admin/bookings/negotiated
   Authorization: Bearer <admin_token>
   ```

2. **Get Incomplete Bookings**
   ```http
   GET /admin/bookings/incomplete
   Authorization: Bearer <admin_token>
   ```

3. **Get Completed Bookings**
   ```http
   GET /admin/bookings/completed
   Authorization: Bearer <admin_token>
   ```

### Negotiation System

1. **Request Negotiation**
   ```http
   PUT /booking/<id>
   Authorization: Bearer <client_token>
   Content-Type: application/json
   ```

2. **Get Negotiation History**
   ```http
   GET /booking/<id>/negotiation-history
   Authorization: Bearer <client_token>
   ```

3. **Process Negotiated Payment**
   ```http
   POST /booking/<id>/pay-negotiated
   Authorization: Bearer <client_token>
   Content-Type: application/json
   ```

### Chat System

1. **Get Chat Messages**
   ```http
   GET /booking/<id>/chat
   Authorization: Bearer <token>
   ```

2. **Send Chat Message**
   ```http
   POST /booking/<id>/chat
   Authorization: Bearer <token>
   Content-Type: application/json
   ```

3. **Get Negotiation Chats**
   ```http
   GET /negotiation-chats
   Authorization: Bearer <token>
   ```

## Setup and Installation

1. **Clone Repository**
   ```bash
   git clone <repository-url>
   cd helicopter-booking-backend
   ```

2. **Create Virtual Environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # Linux/Mac
   venv\Scripts\activate     # Windows
   ```

3. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure Environment Variables**
   Create a `.env` file with the following variables:
   ```env
   # Email Configuration
   MAIL_SERVER=smtp.gmail.com
   MAIL_PORT=587
   MAIL_USE_TLS=True
   MAIL_USERNAME=your-email@gmail.com
   MAIL_PASSWORD=your-app-password
   MAIL_DEFAULT_SENDER=your-email@gmail.com

   # Firebase Configuration
   FIREBASE_TYPE=service_account
   FIREBASE_PROJECT_ID=your-project-id
   FIREBASE_PRIVATE_KEY_ID=your-private-key-id
   FIREBASE_PRIVATE_KEY=your-private-key
   FIREBASE_CLIENT_EMAIL=your-client-email
   FIREBASE_CLIENT_ID=your-client-id
   FIREBASE_AUTH_URI=https://accounts.google.com/o/oauth2/auth
   FIREBASE_TOKEN_URI=https://oauth2.googleapis.com/token
   FIREBASE_AUTH_PROVIDER_X509_CERT_URL=https://www.googleapis.com/oauth2/v1/certs
   FIREBASE_CLIENT_X509_CERT_URL=your-client-cert-url
   ```

5. **Initialize Database**
   ```bash
   flask db init
   flask db migrate
   flask db upgrade
   ```

6. **Run Application**
   ```bash
   python app.py
   ```

## Error Handling

The system implements comprehensive error handling with appropriate HTTP status codes:

- 400: Bad Request
- 401: Unauthorized
- 403: Forbidden
- 404: Not Found
- 409: Conflict
- 500: Internal Server Error

Each error response includes:
```json
{
    "message": "Error description",
    "error_code": "ERROR_CODE",
    "details": {}
}
```

## Testing

1. **Run Unit Tests**
   ```bash
   python -m pytest tests/unit
   ```

2. **Run Integration Tests**
   ```bash
   python -m pytest tests/integration
   ```

## Deployment

### Requirements
- Python 3.8+
- SQLite 3
- Firebase Admin SDK
- Gmail Account (for email notifications)
- M-Pesa API Access

### Production Configuration
1. Set `DEBUG=False` in production
2. Use environment variables for sensitive data
3. Configure proper logging
4. Set up proper database backups
5. Configure SSL/TLS
6. Set up monitoring

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.
