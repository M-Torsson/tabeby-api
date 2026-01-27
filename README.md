# Tabeby API

Medical clinic management system built with FastAPI.

## Overview

Tabeby API is a comprehensive backend system for managing medical clinics, patient appointments, doctor profiles, and administrative tasks. The system supports multiple user roles including doctors, secretaries, patients, and administrators.

## Key Features

- User authentication and authorization with JWT tokens
- Role-based access control (RBAC)
- Doctor profile management
- Patient registration and profile management
- Booking and appointment management
- Golden booking system for premium services
- Payment tracking and reporting
- Clinic status and availability management
- Advertisement management
- Real-time notifications
- Automated booking archival system
- Rate limiting and caching
- Iraq timezone support (UTC+3)

## Technology Stack

- FastAPI - Modern web framework
- SQLAlchemy - ORM for database operations
- PostgreSQL - Primary database
- JWT - Authentication
- Bcrypt - Password hashing
- Firebase Admin - Push notifications
- APScheduler - Task scheduling

## Project Structure

```
app/
├── main.py              - Application entry point
├── models.py            - Database models
├── schemas.py           - Pydantic schemas
├── database.py          - Database configuration
├── auth.py              - Authentication endpoints
├── users.py             - User management
├── admins.py            - Admin operations
├── doctors.py           - Doctor profile management
├── secretaries.py       - Secretary management
├── patients_register.py - Patient registration
├── patient_profiles.py  - Patient profile management
├── bookings.py          - Booking management
├── golden_bookings.py   - Premium booking system
├── golden_payments.py   - Payment tracking
├── ads.py               - Advertisement management
├── activities.py        - Activity logging
├── departments.py       - Department management
├── staff_router.py      - Staff management with RBAC
├── clinic_info.py       - Clinic information
├── clinic_status.py     - Clinic availability
├── account_status.py    - Account activation management
├── maintenance.py       - Maintenance mode control
├── scheduler.py         - Automated tasks
├── cache.py             - Memory caching system
├── rate_limiter.py      - API rate limiting
├── mailer.py            - Email notifications
├── security.py          - Security utilities
├── rbac.py              - Role-based permissions
├── dependencies.py      - Shared dependencies
├── timezone_utils.py    - Timezone handling
├── timezone_middleware.py - Response timezone conversion
└── firebase_init.py     - Firebase initialization
```

## Core Modules

### Authentication System
- Admin registration and login
- JWT token generation and refresh
- Password reset functionality
- Session management

### Doctor Management
- Create and update doctor profiles
- Manage specializations and clinic locations
- Account status control
- Search and filtering

### Booking System
- Standard and golden booking support
- Real-time availability checking
- Automatic archival of old bookings
- Booking status tracking (booked, served, cancelled, no_show)
- SSE (Server-Sent Events) for real-time updates

### Payment Management
- Track clinic payments
- Monthly and annual reports
- Revenue analytics
- Payment history

### RBAC System
- Staff roles (admin, manager, receptionist, nurse, doctor)
- Granular permissions
- Role assignment and management

## Security Features

- JWT-based authentication
- Password hashing with bcrypt
- Secret key validation for sensitive endpoints
- Rate limiting to prevent abuse
- Session tracking and management

## Database Models

- UserAccount - Unified user accounts
- Admin - Administrative users
- Doctor - Doctor profiles
- Secretary - Secretary accounts
- PatientUser - Patient accounts
- PatientProfile - Patient medical profiles
- Booking - Appointment bookings
- BookingArchive - Historical bookings
- GoldenBooking - Premium bookings
- Payment - Payment records
- Advertisement - Clinic advertisements
- Department - Medical departments
- Staff - Staff members with RBAC
- Activity - Audit logs

## Environment Variables

```
DATABASE_URL=postgresql://user:password@host:port/database
SECRET_KEY=your-secret-key
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=30
DOCTOR_PROFILE_SECRET=your-profile-secret
FIREBASE_CREDENTIALS_JSON=firebase-credentials
EMAIL_FROM=noreply@tabeby.app
RESEND_API_KEY=your-resend-api-key
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USER=your-smtp-user
SMTP_PASSWORD=your-smtp-password
FRONTEND_BASE_URL=https://your-frontend.com
WEB_CONCURRENCY=4
```

## Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Set up environment variables in `.env` file

3. Run database migrations:
```bash
python run_migration.py
```

4. Start the application:
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## API Documentation

Once the application is running, visit:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Timezone Support

The system operates in Iraq timezone (UTC+3). All datetime values in API responses are automatically converted to Iraq time through the timezone middleware.

## Caching

Simple memory-based caching system for frequently accessed data:
- Doctor profiles
- Clinic lists
- Department information
- Configurable TTL and cache size

## Scheduled Tasks

- Automatic archival of bookings older than 30 days
- Runs daily at midnight Iraq time
- Maintains data consistency and performance

## Rate Limiting

Configurable rate limiting to protect API endpoints from abuse:
- Default: 100 requests per minute per IP
- Customizable per endpoint

## Author

Muthana

## Copyright

(c) 2026 Muthana. All rights reserved.

Unauthorized copying or distribution is prohibited.

## License

All rights reserved. This software is proprietary and confidential.
