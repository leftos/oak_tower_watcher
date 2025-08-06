#!/usr/bin/env python3
"""
Email service for sending verification emails and other notifications
Uses SendGrid Web API exclusively
"""

import logging
import os
from flask import current_app, render_template, url_for

# Configure logger for email service
logger = logging.getLogger(__name__)

# Import SendGrid service
from .sendgrid_service import send_sendgrid_email

def init_mail(app):
    """Initialize SendGrid email service"""
    # SendGrid configuration
    app.config['SENDGRID_API_KEY'] = os.environ.get('SENDGRID_API_KEY')
    app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_DEFAULT_SENDER')
    
    # Application-specific settings
    app.config['MAIL_SUBJECT_PREFIX'] = '[VATSIM Facility Watcher] '
    
    # Log configuration
    logger.info("=== SendGrid Email Configuration ===")
    logger.info(f"SENDGRID_API_KEY: {'✅ SET' if app.config['SENDGRID_API_KEY'] else '❌ NOT SET'}")
    logger.info(f"MAIL_DEFAULT_SENDER: {app.config['MAIL_DEFAULT_SENDER'] or '❌ NOT SET'}")
    
    # Validate required configuration
    if not app.config['SENDGRID_API_KEY']:
        logger.error("❌ SENDGRID_API_KEY is required but not set")
        raise RuntimeError("SENDGRID_API_KEY environment variable is required")
    
    if not app.config['MAIL_DEFAULT_SENDER']:
        logger.error("❌ MAIL_DEFAULT_SENDER is required but not set")
        raise RuntimeError("MAIL_DEFAULT_SENDER environment variable is required")
    
    logger.info("✅ SendGrid email service initialized successfully")

def send_email(to, subject, template, **kwargs):
    """Send email using SendGrid Web API"""
    try:
        app = current_app._get_current_object()
        
        logger.info(f"📧 Preparing to send email to {to}")
        logger.info(f"Subject: {subject}")
        logger.info(f"Using SendGrid Web API")
        
        full_subject = app.config['MAIL_SUBJECT_PREFIX'] + subject
        
        # Send via SendGrid
        success = send_sendgrid_email(
            to_email=to,
            subject=full_subject,
            html_content=template
        )
        
        if success:
            logger.info(f"✅ Email sent successfully to {to}")
        else:
            logger.error(f"❌ Failed to send email to {to}")
        
        return success
        
    except Exception as e:
        logger.error(f"❌ Error preparing email to {to}: {str(e)}", exc_info=True)
        return False

def send_verification_email(user):
    """Send email verification email to user"""
    try:
        logger.info(f"📧 Sending verification email to: {user.email}")
        
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
            logger.info(f"✅ Verification email sent successfully to: {user.email}")
        else:
            logger.error(f"❌ Failed to send verification email to: {user.email}")
        
        return success
        
    except Exception as e:
        logger.error(f"❌ Error sending verification email to {user.email}: {str(e)}", exc_info=True)
        return False

def send_welcome_email(user):
    """Send welcome email after successful verification"""
    try:
        logger.info(f"📧 Sending welcome email to: {user.email}")
        
        # Render email template
        html_body = render_template('email/welcome.html', user=user)
        
        # Send email
        success = send_email(
            to=user.email,
            subject='Welcome to VATSIM Facility Watcher!',
            template=html_body
        )
        
        if success:
            logger.info(f"✅ Welcome email sent successfully to: {user.email}")
        else:
            logger.error(f"❌ Failed to send welcome email to: {user.email}")
        
        return success
        
    except Exception as e:
        logger.error(f"❌ Error sending welcome email to {user.email}: {str(e)}", exc_info=True)
        return False

def send_password_reset_email(user):
    """Send password reset email to user"""
    try:
        logger.info(f"📧 Sending password reset email to: {user.email}")
        
        # Generate password reset token
        token = user.generate_password_reset_token()
        
        # Create password reset URL
        reset_url = url_for('auth.reset_password_confirm', token=token, _external=True)
        
        # Render email template
        html_body = render_template('email/password_reset.html',
                                  user=user,
                                  reset_url=reset_url)
        
        # Send email
        success = send_email(
            to=user.email,
            subject='Password Reset Request',
            template=html_body
        )
        
        if success:
            logger.info(f"✅ Password reset email sent successfully to: {user.email}")
        else:
            logger.error(f"❌ Failed to send password reset email to: {user.email}")
        
        return success
        
    except Exception as e:
        logger.error(f"❌ Error sending password reset email to {user.email}: {str(e)}", exc_info=True)
        return False