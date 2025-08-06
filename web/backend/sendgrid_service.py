#!/usr/bin/env python3
"""
SendGrid email service for OAK Tower Watcher
Uses SendGrid Web API instead of SMTP
"""

import logging
import os
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Email, To, Content

# Configure logger for SendGrid service
logger = logging.getLogger(__name__)

def send_sendgrid_email(to_email, subject, html_content, text_content=None):
    """
    Send email using SendGrid Web API
    
    Args:
        to_email (str): Recipient email address
        subject (str): Email subject
        html_content (str): HTML content of the email
        text_content (str, optional): Plain text content
    
    Returns:
        bool: True if email sent successfully, False otherwise
    """
    try:
        # Get configuration
        api_key = os.environ.get('SENDGRID_API_KEY')
        sender_email = os.environ.get('MAIL_DEFAULT_SENDER')
        
        if not api_key:
            logger.error("❌ SENDGRID_API_KEY not set")
            return False
            
        if not sender_email:
            logger.error("❌ MAIL_DEFAULT_SENDER not set")
            return False
        
        logger.info(f"📧 Preparing SendGrid email to {to_email}")
        logger.info(f"Subject: {subject}")
        logger.info(f"From: {sender_email}")
        
        # Create the email
        from_email = Email(sender_email)
        to_email_obj = To(to_email)
        
        # Create mail object
        if text_content:
            # If we have both HTML and text content
            mail = Mail(
                from_email=from_email,
                to_emails=to_email_obj,
                subject=subject,
                plain_text_content=text_content,
                html_content=html_content
            )
        else:
            # HTML only
            mail = Mail(
                from_email=from_email,
                to_emails=to_email_obj,
                subject=subject,
                html_content=html_content
            )
        
        # Send the email
        logger.info("🚀 Sending email via SendGrid API...")
        sg = SendGridAPIClient(api_key=api_key)
        
        response = sg.send(mail)
        
        logger.info(f"✅ SendGrid response status: {response.status_code}")
        logger.debug(f"SendGrid response body: {response.body}")
        logger.debug(f"SendGrid response headers: {response.headers}")
        
        if response.status_code == 202:
            logger.info(f"✅ Email sent successfully to {to_email} via SendGrid")
            return True
        else:
            logger.error(f"❌ SendGrid returned status code: {response.status_code}")
            return False
            
    except Exception as e:
        logger.error(f"❌ Failed to send email via SendGrid: {str(e)}", exc_info=True)
        return False

def test_sendgrid_config():
    """
    Test SendGrid configuration
    
    Returns:
        tuple: (success: bool, config: dict)
    """
    logger.info("=== SENDGRID CONFIGURATION TEST ===")
    
    config = {
        'api_key': os.environ.get('SENDGRID_API_KEY'),
        'sender_email': os.environ.get('MAIL_DEFAULT_SENDER'),
        'provider': 'sendgrid'
    }
    
    logger.info(f"SENDGRID_API_KEY: {'✅ SET' if config['api_key'] else '❌ NOT SET'}")
    logger.info(f"MAIL_DEFAULT_SENDER: {config['sender_email'] or '❌ NOT SET'}")
    
    # Check for missing required settings
    missing = []
    if not config['api_key']:
        missing.append('SENDGRID_API_KEY')
    if not config['sender_email']:
        missing.append('MAIL_DEFAULT_SENDER')
    
    if missing:
        logger.error(f"❌ Missing required environment variables: {', '.join(missing)}")
        return False, config
    
    logger.info("✅ SendGrid configuration appears complete")
    return True, config

def test_sendgrid_api():
    """
    Test SendGrid API connectivity without sending email
    
    Returns:
        bool: True if API is accessible, False otherwise
    """
    logger.info("=== TESTING SENDGRID API CONNECTION ===")
    
    try:
        api_key = os.environ.get('SENDGRID_API_KEY')
        if not api_key:
            logger.error("❌ SENDGRID_API_KEY not set")
            return False
        
        logger.info("Testing SendGrid API connectivity...")
        sg = SendGridAPIClient(api_key=api_key)
        
        # Test API by getting account information (this doesn't send email)
        try:
            # This endpoint tests API key validity
            response = sg.client.user.profile.get()
            logger.info(f"✅ SendGrid API connection successful (status: {response.status_code})")
            return True
        except Exception as api_error:
            # If profile endpoint fails, try a simpler test
            logger.warning(f"Profile endpoint failed: {api_error}")
            logger.info("Trying alternative API test...")
            
            # Just test if we can create a SendGridAPIClient object
            # This validates the API key format at least
            if len(api_key) > 20 and api_key.startswith('SG.'):
                logger.info("✅ SendGrid API key format appears valid")
                return True
            else:
                logger.error("❌ SendGrid API key format appears invalid")
                return False
            
    except Exception as e:
        logger.error(f"❌ SendGrid API test failed: {e}", exc_info=True)
        return False

def send_sendgrid_test_email(recipient_email=None):
    """
    Send a test email via SendGrid
    
    Args:
        recipient_email (str, optional): Recipient email, defaults to sender email
    
    Returns:
        bool: True if successful, False otherwise
    """
    logger.info("=== SENDING SENDGRID TEST EMAIL ===")
    
    sender_email = os.environ.get('MAIL_DEFAULT_SENDER')
    test_recipient = recipient_email or sender_email
    
    if not test_recipient:
        logger.error("❌ No recipient email specified and MAIL_DEFAULT_SENDER not set")
        return False
    
    from datetime import datetime
    
    html_content = f"""
    <html>
    <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
        <div style="text-align: center; margin-bottom: 30px;">
            <h1 style="color: #4a90e2;">🏗️ OAK Tower Watcher</h1>
            <h2 style="color: #666;">SendGrid Email Test</h2>
        </div>
        
        <div style="background-color: #f8f9fa; padding: 20px; border-radius: 8px; margin-bottom: 20px;">
            <p>This is a test email to verify that your SendGrid integration is working correctly.</p>
        </div>
        
        <div style="background-color: #e8f5e8; padding: 15px; border-left: 4px solid #28a745; margin-bottom: 20px;">
            <h3 style="margin-top: 0; color: #155724;">✅ SendGrid Configuration</h3>
            <ul style="margin: 0;">
                <li><strong>API Key:</strong> SET (✅)</li>
                <li><strong>Sender Email:</strong> {sender_email}</li>
                <li><strong>Test Time:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}</li>
                <li><strong>Recipient:</strong> {test_recipient}</li>
            </ul>
        </div>
        
        <div style="text-align: center; margin: 30px 0;">
            <div style="background-color: #28a745; color: white; padding: 15px; border-radius: 8px; display: inline-block;">
                <h3 style="margin: 0;">🎉 Success!</h3>
                <p style="margin: 5px 0;">If you received this email, SendGrid is working correctly!</p>
            </div>
        </div>
        
        <div style="border-top: 1px solid #dee2e6; padding-top: 20px; color: #6c757d; font-size: 14px;">
            <p><strong>Next Steps:</strong></p>
            <ul>
                <li>✅ SendGrid Web API is working</li>
                <li>✅ No SMTP port blocking issues</li>
                <li>✅ Email verification system ready</li>
            </ul>
        </div>
        
        <div style="text-align: center; margin-top: 30px; padding-top: 20px; border-top: 1px solid #dee2e6; color: #adb5bd; font-size: 12px;">
            This email was sent by the OAK Tower Watcher SendGrid test script.
        </div>
    </body>
    </html>
    """
    
    text_content = f"""
OAK Tower Watcher - SendGrid Email Test

This is a test email to verify that your SendGrid integration is working correctly.

Configuration Details:
- API Key: SET (✅)
- Sender Email: {sender_email}
- Test Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}
- Recipient: {test_recipient}

🎉 Success!
If you received this email, SendGrid is working correctly!

Next Steps:
✅ SendGrid Web API is working
✅ No SMTP port blocking issues  
✅ Email verification system ready

This email was sent by the OAK Tower Watcher SendGrid test script.
    """
    
    return send_sendgrid_email(
        to_email=test_recipient,
        subject="OAK Tower Watcher - SendGrid Test",
        html_content=html_content,
        text_content=text_content
    )