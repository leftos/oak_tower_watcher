# OAK Tower Watcher User Portal

## Overview

A basic user portal has been successfully added to the OAK Tower Watcher website. This system allows users to create accounts and configure personalized settings for each service, starting with the OAK Tower Watcher service.

## Features

### User Authentication
- **Registration**: Users can create accounts with email and password
- **Login/Logout**: Secure session management with Flask-Login
- **Password Security**: Passwords are securely hashed using Werkzeug's password hashing
- **Session Management**: Users stay logged in across browser sessions if they choose "Remember Me"

### User Dashboard
- **Service Overview**: View all available services and their configuration status
- **Account Information**: Display user details like registration date and last login
- **Quick Access**: Direct links to configure each service

### OAK Tower Watcher Settings
- **Pushover Integration**: Configure personal Pushover API Token and User Key
- **Notification Control**: Enable/disable notifications per user
- **Settings Validation**: Form validation ensures proper data entry

## Database Structure

### Users Table
- `id`: Primary key
- `email`: Unique email address (also serves as username)
- `password_hash`: Securely hashed password
- `created_at`: Account creation timestamp
- `last_login`: Last login timestamp
- `is_active`: Account status flag

### User Settings Table
- `id`: Primary key
- `user_id`: Foreign key to users table
- `service_name`: Service identifier (e.g., 'oak_tower_watcher')
- `pushover_api_token`: User's Pushover API token
- `pushover_user_key`: User's Pushover user key
- `notifications_enabled`: Boolean flag for notifications
- `created_at`/`updated_at`: Timestamps

## File Structure

```
web/
├── backend/
│   ├── __init__.py
│   ├── app.py              # Main Flask application
│   ├── auth.py             # Authentication routes
│   ├── forms.py            # WTForms for user input
│   └── models.py           # SQLAlchemy database models
├── templates/
│   ├── base.html           # Base template with navigation
│   └── auth/
│       ├── login.html      # Login form
│       ├── register.html   # Registration form
│       ├── dashboard.html  # User dashboard
│       └── oak_tower_settings.html  # Service settings
├── auth.css                # Styles for authentication pages
├── index.html              # Updated homepage with auth links
└── run_app.py              # Application startup script
```

## Usage Instructions

### For Users

1. **Registration**:
   - Visit the website homepage
   - Click "Register" in the navigation
   - Enter email and password (minimum 8 characters)
   - Confirm password and submit

2. **Login**:
   - Click "Login" in the navigation
   - Enter email and password
   - Optionally check "Remember Me" for persistent sessions

3. **Configure OAK Tower Watcher**:
   - After logging in, go to Dashboard
   - Click "Configure Settings" on the OAK Tower Watcher card
   - Enter your Pushover API Token and User Key
   - Enable/disable notifications as desired
   - Save settings

4. **View Status**:
   - From dashboard, click "View Status" to see current controller information
   - Or visit the status page directly from the homepage

### For Developers

1. **Running the Application**:
   ```bash
   cd web
   source ../web_env/bin/activate
   python3 run_app.py
   ```

2. **Database Management**:
   - Database is automatically created on first run
   - SQLite database stored in `web/instance/users.db`
   - Tables are created automatically using SQLAlchemy

3. **Adding New Services**:
   - Create new settings form in `forms.py`
   - Add routes in `auth.py`
   - Create templates for the new service
   - Update dashboard to show the new service

## Security Features

- **Password Hashing**: Uses Werkzeug's secure password hashing
- **CSRF Protection**: Flask-WTF provides CSRF tokens on all forms
- **Session Security**: Flask-Login manages secure user sessions
- **Input Validation**: WTForms validates all user input
- **Email Validation**: Uses email-validator library for proper email format checking

## Environment Variables

- `SECRET_KEY`: Flask secret key (defaults to development key)
- `DATABASE_URL`: Database connection string (defaults to SQLite)
- `HOST`: Server host (defaults to 0.0.0.0)
- `PORT`: Server port (defaults to 8080)
- `DEBUG`: Debug mode (defaults to False)

## Dependencies

The following packages were added to `requirements_web.txt`:
- Flask-Login==0.6.3
- Flask-WTF==1.1.1
- Flask-SQLAlchemy==3.0.5
- WTForms==3.0.1
- email_validator (automatically installed)

## Future Enhancements

Potential improvements for the user portal:
- Password reset functionality
- Email verification for new accounts
- User profile management
- Multiple Pushover configurations per user
- Admin panel for user management
- API keys for programmatic access
- Integration with other notification services