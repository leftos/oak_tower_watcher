# Email Verification Setup Guide

This guide explains how to configure email verification for the OAK Tower Watcher web application using Namecheap private email.

## Overview

The email verification system:
- Requires users to verify their email address before they can log in
- Sends verification emails with a 48-hour expiration
- Automatically deletes unverified accounts after the verification period expires
- Sends welcome emails after successful verification

## Namecheap Email Configuration

Based on the Namecheap private email configuration guide, you'll need to set the following environment variables:

### Required Environment Variables

```bash
# Email server settings (Namecheap Private Email)
MAIL_SERVER=mail.privateemail.com
MAIL_PORT=587
MAIL_USE_TLS=true
MAIL_USE_SSL=false

# Your email credentials
MAIL_USERNAME=your-email@yourdomain.com
MAIL_PASSWORD=your-email-password

# Default sender (usually same as username)
MAIL_DEFAULT_SENDER=your-email@yourdomain.com
```

### Setting Environment Variables

#### For Development (Linux/Mac):
```bash
export MAIL_SERVER=mail.privateemail.com
export MAIL_PORT=587
export MAIL_USE_TLS=true
export MAIL_USE_SSL=false
export MAIL_USERNAME=your-email@yourdomain.com
export MAIL_PASSWORD=your-email-password
export MAIL_DEFAULT_SENDER=your-email@yourdomain.com
```

#### For Production:
Set these variables in your production environment configuration (e.g., systemd service file, Docker environment, etc.).

#### Using a .env file (optional):
Create a `.env` file in your project root:
```
MAIL_SERVER=mail.privateemail.com
MAIL_PORT=587
MAIL_USE_TLS=true
MAIL_USE_SSL=false
MAIL_USERNAME=your-email@yourdomain.com
MAIL_PASSWORD=your-email-password
MAIL_DEFAULT_SENDER=your-email@yourdomain.com
```

## Installation

1. Install the required dependencies:
```bash
cd /path/to/oak_tower_watcher
source web_env/bin/activate
pip install -r requirements_web.txt
```

2. Set up your email environment variables (see above)

3. Run database migrations to add the new email verification fields:
```bash
cd web
python -c "from backend.app import app; from backend.models import db; app.app_context().push(); db.create_all()"
```

## Testing Email Configuration

You can test your email configuration by registering a new account:

1. Start the web application:
```bash
cd web
python run_app.py
```

2. Navigate to the registration page and create a new account
3. Check your email for the verification message
4. Click the verification link to complete the process

## Email Templates

The system includes two email templates:

### Verification Email (`web/templates/email/verification.html`)
- Sent immediately after registration
- Contains a verification link that expires in 48 hours
- Styled with inline CSS for email client compatibility

### Welcome Email (`web/templates/email/welcome.html`)
- Sent after successful email verification
- Welcomes the user and explains next steps
- Includes links to the dashboard and features

## Security Features

- **Token-based verification**: Uses cryptographically secure tokens
- **Time-limited verification**: Links expire after 48 hours
- **Account cleanup**: Unverified accounts are automatically deleted after expiration
- **No information disclosure**: Doesn't reveal whether an email exists in the system
- **Secure token generation**: Uses `secrets.token_urlsafe()` for token generation

## User Flow

1. **Registration**: User fills out registration form
2. **Account Creation**: System creates user account with `email_verified=False`
3. **Verification Email**: System sends verification email with unique token
4. **Email Verification**: User clicks link in email to verify
5. **Account Activation**: System marks email as verified and sends welcome email
6. **Login Access**: User can now log in to their account

## Troubleshooting

### Common Issues

1. **Emails not sending**:
   - Check environment variables are set correctly
   - Verify Namecheap email credentials
   - Check application logs for error messages

2. **Verification links not working**:
   - Ensure the web application is accessible at the URL in the email
   - Check that the token hasn't expired (48 hours)
   - Verify database connectivity

3. **Users can't log in**:
   - Confirm email verification was completed
   - Check that `email_verified` field is `True` in database

### Log Files

Check the application logs for detailed error information:
```bash
tail -f logs/web_app.log
```

## Database Schema Changes

The following fields were added to the `users` table:

- `email_verified` (Boolean, default: False)
- `email_verification_token` (String, unique, nullable)
- `email_verification_sent_at` (DateTime, nullable)

## API Endpoints

### Email Verification Endpoints

- `GET /auth/verify-email/<token>` - Verify email with token
- `GET /auth/resend-verification` - Resend verification form
- `POST /auth/resend-verification` - Process resend request

### Modified Endpoints

- `POST /auth/register` - Now sends verification email
- `POST /auth/login` - Now checks email verification status

## Configuration Reference

### Namecheap Private Email Settings

According to Namecheap documentation:

- **Incoming Mail Server**: mail.privateemail.com
- **IMAP Port**: 993 (SSL), 143 (TLS)
- **POP3 Port**: 995 (SSL), 110 (TLS)
- **Outgoing Mail Server**: mail.privateemail.com
- **SMTP Port**: 465 (SSL), 587 (TLS)

For this application, we use SMTP with TLS on port 587.

## Support

If you encounter issues:

1. Check the application logs
2. Verify your Namecheap email settings
3. Test email sending manually if needed
4. Ensure all environment variables are properly set

For Namecheap-specific email issues, refer to their support documentation or contact their support team.