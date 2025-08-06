# OAK Tower Watcher - Web Implementation

The **Web Implementation** provides a comprehensive Flask-based web interface for the OAK Tower Watcher system with full user authentication, notification management, and API endpoints.

## Overview

This implementation serves as the primary web interface for users to:
- **Register and manage accounts** with email verification
- **Configure notification settings** (Pushover integration)
- **Monitor VATSIM controller status** through web dashboard
- **Access real-time API endpoints** for status data
- **Test notification systems** through web interface

## Key Features

### User Authentication & Management
- **User Registration**: Email-based account creation with verification
- **Email Verification**: SendGrid-powered email verification system
- **Secure Login/Logout**: Flask-Login session management with "Remember Me"
- **Password Security**: Werkzeug password hashing and validation
- **User Dashboard**: Personalized settings and notification management

### VATSIM Integration
- **Real-time Status API**: Live controller status monitoring
- **JSON API Endpoints**: RESTful interface for external integrations
- **Shared Core Logic**: Uses `shared/vatsim_core.py` for consistent data
- **Controller Information**: ARTCC roster integration for controller names

### Notification System
- **Pushover Integration**: Mobile push notifications via user credentials
- **Individual Testing**: Per-user notification testing
- **Bulk Notifications**: Admin-level bulk notification capabilities
- **Settings Management**: User-configurable notification preferences

### Web Interface
- **Responsive Design**: Mobile-friendly web interface
- **Status Dashboard**: Real-time controller status display
- **Settings Management**: Web-based configuration interface
- **Static File Serving**: Secure static asset delivery

## Architecture

```
web/
├── backend/                    # Flask application backend
│   ├── __init__.py            # Package initialization
│   ├── app.py                 # Main Flask application factory
│   ├── auth.py                # Authentication routes and logic
│   ├── api.py                 # API endpoints for status and testing
│   ├── models.py              # SQLAlchemy database models
│   ├── forms.py               # WTForms for user input validation
│   ├── status_service.py      # VATSIM status API service
│   ├── email_service.py       # Email verification service
│   ├── sendgrid_service.py    # SendGrid email backend
│   └── security.py           # Security middleware and rate limiting
├── templates/                 # Jinja2 HTML templates
│   ├── base.html             # Base template with navigation
│   ├── auth/                 # Authentication templates
│   │   ├── login.html        # User login form
│   │   ├── register.html     # User registration form
│   │   ├── dashboard.html    # User dashboard
│   │   └── oak_tower_settings.html  # Service settings
│   └── email/                # Email templates
│       ├── verification.html  # Email verification template
│       └── welcome.html      # Welcome email template
├── static files              # CSS, JavaScript, images
│   ├── auth.css              # Authentication styling
│   ├── status-page.css       # Status page styling
│   ├── dashboard.js          # Dashboard JavaScript
│   └── status-page.js        # Status page JavaScript
├── requirements.txt          # Python dependencies
├── run_app.py               # Application startup script
└── README.md                # This documentation
```

## Dependencies

The web implementation requires the following Python packages (see `requirements.txt`):

### Core Framework
- **Flask 3.1.1**: Web application framework
- **Flask-CORS 6.0.1**: Cross-origin resource sharing
- **Flask-Login 0.6.3**: User session management
- **Flask-WTF 1.2.2**: Form handling with CSRF protection
- **Flask-SQLAlchemy 3.1.1**: Database ORM
- **Werkzeug 3.1.3**: WSGI utilities and password hashing

### Forms and Validation
- **WTForms 3.0.1**: Form validation and rendering
- **email-validator 2.2.0**: Email address validation

### Web Server
- **gunicorn 21.2.0**: Production WSGI server

### External APIs
- **requests 2.31.0**: HTTP client for VATSIM API
- **beautifulsoup4 4.12.2**: HTML parsing for ARTCC roster
- **lxml 6.0.0**: XML/HTML processing backend
- **sendgrid 6.11.0**: Email delivery service

## Configuration

### Environment Variables

The web application requires several environment variables:

```bash
# Flask Configuration
SECRET_KEY=your-super-secret-key-change-this-in-production
FLASK_ENV=development  # or 'production'
DEBUG=False           # Set to True for development

# Database Configuration
DATABASE_URL=sqlite:///oak_tower_watcher.db  # or PostgreSQL URL for production

# Email Configuration (SendGrid)
SENDGRID_API_KEY=your-sendgrid-api-key
MAIL_DEFAULT_SENDER=noreply@yourdomain.com

# Application Configuration
ENVIRONMENT=development  # development, staging, or production
```

### Configuration Files

The application uses the shared configuration system:
- `config/config.json`: Main VATSIM API and monitoring settings
- `config/env_config.py`: Environment-specific configurations

## Setup and Installation

### 1. Install Dependencies

```bash
cd web/
pip install -r requirements.txt
```

### 2. Configure Environment

Create a `.env` file or set environment variables:

```bash
export SECRET_KEY="your-secret-key-here"
export SENDGRID_API_KEY="your-sendgrid-api-key"
export MAIL_DEFAULT_SENDER="noreply@yourdomain.com"
export DATABASE_URL="sqlite:///oak_tower_watcher.db"
```

### 3. Initialize Database

The database will be automatically created when you first run the application.

### 4. Run the Application

#### Development Mode
```bash
python run_app.py
```

#### Production Mode with Gunicorn
```bash
gunicorn -w 4 -b 0.0.0.0:5000 "backend.app:app"
```

The application will be available at `http://localhost:5000`

## API Endpoints

### Public Endpoints

- `GET /` - Homepage
- `GET /robots.txt` - Search engine robots file
- `GET /api/status` - Current VATSIM controller status
- `GET /api/health` - Health check endpoint
- `GET /api/config` - Basic configuration information

### Authentication Endpoints

- `GET /auth/login` - Login form
- `POST /auth/login` - Process login
- `GET /auth/register` - Registration form
- `POST /auth/register` - Process registration
- `GET /auth/logout` - User logout
- `GET /auth/verify-email/<token>` - Email verification
- `GET /auth/resend-verification` - Resend verification email

### Protected User Endpoints

- `GET /auth/dashboard` - User dashboard
- `GET /auth/settings/oak_tower_watcher` - Service settings
- `POST /auth/settings/oak_tower_watcher` - Update settings
- `POST /api/test-pushover` - Test individual Pushover notifications
- `POST /api/test-bulk-pushover` - Test bulk notifications (admin)
- `GET /api/bulk-notification-stats` - Notification statistics

## Database Models

### User Model
- Email-based authentication
- Password hashing with Werkzeug
- Email verification system
- Last login tracking
- Account activation status

### UserSettings Model
- Service-specific settings (oak_tower_watcher)
- Pushover API credentials storage
- Notification preferences
- User-specific configurations

## Security Features

### Authentication Security
- **Password Hashing**: Secure Werkzeug password hashing
- **CSRF Protection**: Flask-WTF CSRF tokens on all forms
- **Session Security**: Flask-Login secure session management
- **Email Verification**: Required email verification for account activation

### Rate Limiting
- **API Rate Limiting**: Configurable rate limits per endpoint
- **Login Protection**: Failed login attempt tracking
- **Static File Protection**: Secure static file serving with type restrictions

### Input Validation
- **Form Validation**: WTForms validation on all user inputs
- **Email Validation**: Proper email format and domain checking
- **Path Security**: Protection against directory traversal attacks

## Integration with Shared Components

The web implementation uses the reorganized shared components:

```python
from shared.vatsim_core import VATSIMCore           # VATSIM API client
from shared.utils import load_artcc_roster          # ARTCC roster utilities
from shared.pushover_service import PushoverService # Push notifications
from shared.bulk_notification_service import BulkNotificationService
```

This ensures consistency across all implementations while maintaining the web-specific user interface and authentication features.

## Comparison with Other Implementations

| Feature | Web Implementation | Desktop Implementation | Headless Implementation |
|---------|-------------------|----------------------|------------------------|
| **User Interface** | Web browser interface | Native PyQt6 GUI | None (API only) |
| **User Management** | Full user accounts | Single-user | Multi-user via API |
| **Authentication** | Email + password | None | None |
| **Notifications** | Pushover via web | Desktop + Pushover | Pushover |
| **Configuration** | Web-based settings | GUI dialogs | File-based |
| **Deployment** | Web server required | Desktop installation | Docker/server |
| **Multi-user** | ✅ Yes | ❌ No | ✅ Yes (via API) |
| **Remote Access** | ✅ Yes | ❌ No | ✅ Yes (API) |
| **Email Features** | ✅ Yes | ❌ No | ❌ No |

## Development

### Running in Development Mode

1. Set environment variables for development
2. Enable debug mode: `export DEBUG=True`
3. Use development database: `sqlite:///dev_oak_tower_watcher.db`
4. Run with: `python run_app.py`

### Database Migrations

The application uses Flask-SQLAlchemy. For schema changes:
1. Modify models in `backend/models.py`
2. The database will auto-create tables on startup
3. For production, consider using Flask-Migrate for proper migrations

## Troubleshooting

### Common Issues

**Email Verification Not Working**
- Check `SENDGRID_API_KEY` is set correctly
- Verify `MAIL_DEFAULT_SENDER` is configured
- Check SendGrid dashboard for delivery status

**Database Errors**
- Ensure database directory is writable
- Check database URL format
- Verify SQLAlchemy connection string

**Import Errors**
- Ensure `shared/` directory is accessible
- Check Python path configuration
- Verify all dependencies are installed

**Authentication Issues**
- Check `SECRET_KEY` is set and secure
- Verify session configuration
- Check user account status and email verification

### Logging

The application provides detailed logging:
- **Development**: Console output enabled
- **Production**: File-based logging with rotation
- **Log Location**: Configured via environment settings

### Performance

For production deployment:
- Use Gunicorn with multiple workers
- Configure reverse proxy (nginx)
- Use PostgreSQL instead of SQLite
- Enable static file caching
- Configure proper SSL/TLS

## Support

For issues specific to the web implementation:
1. Check application logs
2. Verify environment configuration
3. Test API endpoints individually
4. Check database connectivity
5. Validate email service configuration

The web implementation provides the most feature-complete interface for the OAK Tower Watcher system, suitable for multi-user deployments and remote access scenarios.