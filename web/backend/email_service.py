#!/usr/bin/env python3
"""
Email service for sending verification emails and other notifications
"""

import logging
import os
from flask import current_app, render_template, url_for
from flask_mail import Mail, Message
from threading import Thread

# Configure logger for email service
logger = logging.getLogger(__name__)

mail = Mail()

def init_mail(app):
    """Initialize Flask-Mail with the app"""
    # Email configuration for Namecheap private email
    app.config['MAIL_SERVER'] = os.environ.get('MAIL_SERVER', 'mail.privateemail.com')
    app.config['MAIL_PORT'] = int(os.environ.get('MAIL_PORT', 587))
    app.config['MAIL_USE_TLS'] = os.environ.get('MAIL_USE_TLS', 'true').lower() == 'true'
    app.config['MAIL_USE_SSL'] = os.environ.get('MAIL_USE_SSL', 'false').lower() == 'true'
    app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')
    app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')
    app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_DEFAULT_SENDER', app.config['MAIL_USERNAME'])
    
    # Application-specific settings
    app.config['MAIL_SUBJECT_PREFIX'] = '[OAK Tower Watcher] '
    
    mail.init_app(app)
    logger.info("Email service initialized")

def send_async_email(app, msg):
    """Send email asynchronously in a specific app context"""
    with app.app_context():
        try:
            mail.send(msg)
            logger.info(f"Email sent successfully to {msg.recipients}")
        except Exception as e:
            logger.error(f"Failed to send email to {msg.recipients}: {str(e)}", exc_info=True)

def send_email(to, subject, template, **kwargs):
    """Send email with HTML template"""
    try:
        app = current_app._get_current_object()
        
        # Create message
        msg = Message(
            subject=app.config['MAIL_SUBJECT_PREFIX'] + subject,
            recipients=[to] if isinstance(to, str) else to,
            html=template,
            sender=app.config['MAIL_DEFAULT_SENDER']
        )
        
        logger.info(f"Preparing to send email to {to} with subject: {subject}")
        
        # Send asynchronously
        thread = Thread(target=send_async_email, args=[app, msg])
        thread.start()
        
        return True
        
    except Exception as e:
        logger.error(f"Error preparing email to {to}: {str(e)}", exc_info=True)
        return False

def send_verification_email(user):
    """Send email verification email to user"""
    try:
        logger.info(f"Sending verification email to: {user.email}")
        
        # Generate verification token
        token = user.generate_verification_token()
        
        # Create verification URL
        verification_url = url_for('auth.verify_email', token=token, _external=True)
        
        # Render email template
        html_body = render_template('email/verification.html',
                                  user=user,
                                  verification_url=verification_url)
        
        # Send email
        success = send_email(
            to=user.email,
            subject='Please verify your email address',
            template=html_body
        )
        
        if success:
            logger.info(f"Verification email queued successfully for: {user.email}")
        else:
            logger.error(f"Failed to queue verification email for: {user.email}")
        
        return success
        
    except Exception as e:
        logger.error(f"Error sending verification email to {user.email}: {str(e)}", exc_info=True)
        return False

def send_welcome_email(user):
    """Send welcome email after successful verification"""
    try:
        logger.info(f"Sending welcome email to: {user.email}")
        
        # Render email template
        html_body = render_template('email/welcome.html', user=user)
        
        # Send email
        success = send_email(
            to=user.email,
            subject='Welcome to OAK Tower Watcher!',
            template=html_body
        )
        
        if success:
            logger.info(f"Welcome email queued successfully for: {user.email}")
        else:
            logger.error(f"Failed to queue welcome email for: {user.email}")
        
        return success
        
    except Exception as e:
        logger.error(f"Error sending welcome email to {user.email}: {str(e)}", exc_info=True)
        return False