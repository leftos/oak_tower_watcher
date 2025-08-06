#!/usr/bin/env python3
"""
Authentication routes and user management
"""

import logging
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from .models import db, User, UserSettings
from .forms import LoginForm, RegistrationForm, UserSettingsForm, PasswordResetRequestForm, PasswordResetForm
from .email_service import send_verification_email, send_welcome_email, send_password_reset_email
from .security import email_verification_required

# Configure logger for auth module
logger = logging.getLogger(__name__)

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """User login page"""
    logger.info(f"Login attempt - Method: {request.method}, IP: {request.remote_addr}, User-Agent: {request.headers.get('User-Agent', 'Unknown')}")
    
    if current_user.is_authenticated:
        logger.info(f"User already authenticated: {current_user.email}")
        return redirect(url_for('auth.dashboard'))
    
    form = LoginForm()
    
    if request.method == 'GET':
        logger.info("Serving login form")
        return render_template('auth/login.html', title='Sign In', form=form)
    
    # POST request - process login
    logger.info("Processing login form submission")
    
    if not form.validate_on_submit():
        logger.warning(f"Form validation failed. Errors: {form.errors}")
        return render_template('auth/login.html', title='Sign In', form=form)
    
    email = form.email.data
    password = form.password.data
    remember_me = form.remember_me.data
    
    logger.info(f"Login attempt for email: {email}")
    
    try:
        # Query user from database
        logger.debug(f"Querying database for user with email: {email}")
        user = User.query.filter_by(email=email).first()
        
        if user is None:
            logger.warning(f"Login failed - User not found: {email}")
            flash('Invalid email or password')
            return redirect(url_for('auth.login'))
        
        logger.debug(f"User found: {user.email}, ID: {user.id}, Active: {user.is_active}")
        
        # Check if user is active
        if not user.is_active:
            logger.warning(f"Login failed - User account disabled: {email}")
            flash('Account is disabled. Please contact support.')
            return redirect(url_for('auth.login'))
        
        # Check if email is verified
        if not user.email_verified:
            logger.warning(f"Login failed - Email not verified for user: {email}")
            flash('Please verify your email address before logging in. Check your inbox for the verification email.')
            return render_template('auth/login.html', title='Sign In', form=form, show_resend_link=True, user_email=email)
        
        # Check password
        logger.debug(f"Checking password for user: {email}")
        password_valid = user.check_password(password)
        
        if not password_valid:
            logger.warning(f"Login failed - Invalid password for user: {email}")
            flash('Invalid email or password')
            return redirect(url_for('auth.login'))
        
        # Successful authentication
        logger.info(f"Login successful for user: {email}")
        
        # Log the user in
        logger.debug(f"Calling login_user with remember_me={remember_me}")
        login_user(user, remember=remember_me)
        
        # Update last login timestamp
        logger.debug(f"Updating last login timestamp for user: {email}")
        user.update_last_login()
        
        # Handle next page redirect
        next_page = request.args.get('next')
        if next_page:
            logger.debug(f"Next page requested: {next_page}")
            if not next_page.startswith('/'):
                logger.warning(f"Invalid next page URL (external): {next_page}, redirecting to dashboard")
                next_page = url_for('auth.dashboard')
        else:
            next_page = url_for('auth.dashboard')
        
        logger.info(f"Redirecting user {email} to: {next_page}")
        return redirect(next_page)
        
    except Exception as e:
        logger.error(f"Unexpected error during login for {email}: {str(e)}", exc_info=True)
        flash('An unexpected error occurred. Please try again.')
        return redirect(url_for('auth.login'))

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """User registration page"""
    logger.info(f"Registration attempt - Method: {request.method}, IP: {request.remote_addr}")
    
    if current_user.is_authenticated:
        logger.info(f"User already authenticated during registration: {current_user.email}")
        return redirect(url_for('auth.dashboard'))
    
    form = RegistrationForm()
    
    if request.method == 'GET':
        logger.info("Serving registration form")
        return render_template('auth/register.html', title='Register', form=form)
    
    # POST request - process registration
    logger.info("Processing registration form submission")
    
    if not form.validate_on_submit():
        logger.warning(f"Registration form validation failed. Errors: {form.errors}")
        return render_template('auth/register.html', title='Register', form=form)
    
    email = form.email.data
    logger.info(f"Registration attempt for email: {email}")
    
    try:
        # Create new user (email_verified defaults to False)
        logger.debug(f"Creating new user: {email}")
        user = User(email=email)
        user.set_password(form.password.data)
        
        # Add user to session and flush to get the ID
        db.session.add(user)
        db.session.flush()  # This assigns the user.id without committing
        logger.info(f"User created with ID: {user.id}")
        
        # Create default settings for OAK Tower Watcher
        logger.debug(f"Creating default settings for user: {email}")
        default_settings = UserSettings(
            user_id=user.id,
            service_name='oak_tower_watcher',
            notifications_enabled=True
        )
        db.session.add(default_settings)
        db.session.commit()
        logger.info(f"User and default settings created successfully for: {email}")
        
        # Send verification email
        logger.debug(f"Sending verification email to: {email}")
        if send_verification_email(user):
            db.session.commit()  # Save the verification token
            flash('Registration successful! Please check your email and click the verification link to activate your account.')
            logger.info(f"Registration completed and verification email sent for: {email}")
        else:
            flash('Registration successful, but there was an issue sending the verification email. Please contact support.')
            logger.warning(f"Registration completed but verification email failed for: {email}")
        
        return redirect(url_for('auth.login'))
        
    except Exception as e:
        logger.error(f"Error during registration for {email}: {str(e)}", exc_info=True)
        db.session.rollback()
        flash('An error occurred during registration. Please try again.')
        return render_template('auth/register.html', title='Register', form=form)

@auth_bp.route('/logout')
@login_required
def logout():
    """User logout"""
    user_email = current_user.email if current_user.is_authenticated else "Unknown"
    logger.info(f"User logout: {user_email}, IP: {request.remote_addr}")
    
    try:
        logout_user()
        logger.info(f"User logged out successfully: {user_email}")
        return redirect(url_for('index'))
    except Exception as e:
        logger.error(f"Error during logout for user {user_email}: {str(e)}", exc_info=True)
        # Still try to redirect even if logout had issues
        return redirect(url_for('index'))

@auth_bp.route('/dashboard')
@login_required
@email_verification_required
def dashboard():
    """User dashboard"""
    # Get user's OAK Tower Watcher settings
    oak_settings = current_user.get_service_settings('oak_tower_watcher')
    if not oak_settings:
        # Create default settings if they don't exist
        oak_settings = UserSettings(
            user_id=current_user.id,
            service_name='oak_tower_watcher',
            notifications_enabled=True
        )
        db.session.add(oak_settings)
        db.session.commit()
    
    return render_template('auth/dashboard.html', 
                         title='Dashboard', 
                         oak_settings=oak_settings)

@auth_bp.route('/settings/oak_tower_watcher', methods=['GET', 'POST'])
@login_required
@email_verification_required
def oak_tower_settings():
    """OAK Tower Watcher settings page"""
    settings = current_user.get_service_settings('oak_tower_watcher')
    if not settings:
        settings = UserSettings(
            user_id=current_user.id,
            service_name='oak_tower_watcher',
            notifications_enabled=True
        )
        db.session.add(settings)
        db.session.commit()
    
    form = UserSettingsForm()
    
    if form.validate_on_submit():
        settings.pushover_api_token = form.pushover_api_token.data
        settings.pushover_user_key = form.pushover_user_key.data
        settings.notifications_enabled = form.notifications_enabled.data
        db.session.commit()
        flash('Your settings have been updated!')
        return redirect(url_for('auth.dashboard'))
    elif request.method == 'GET':
        form.pushover_api_token.data = settings.pushover_api_token
        form.pushover_user_key.data = settings.pushover_user_key
        form.notifications_enabled.data = settings.notifications_enabled
    
    return render_template('auth/oak_tower_settings.html',
                         title='OAK Tower Watcher Settings',
                         form=form)

@auth_bp.route('/verify-email/<token>')
def verify_email(token):
    """Verify email address with token"""
    logger.info(f"Email verification attempt with token: {token[:10]}...")
    
    try:
        # Find user with this verification token
        user = User.query.filter_by(email_verification_token=token).first()
        
        if not user:
            logger.warning(f"Invalid verification token: {token[:10]}...")
            flash('Invalid or expired verification link.')
            return redirect(url_for('auth.login'))
        
        logger.debug(f"Found user for verification: {user.email}")
        
        # Check if already verified
        if user.email_verified:
            logger.info(f"User already verified: {user.email}")
            flash('Your email is already verified. You can log in now.')
            return redirect(url_for('auth.login'))
        
        # Verify the email
        if user.verify_email(token):
            db.session.commit()
            logger.info(f"Email verification successful for: {user.email}")
            
            # Send welcome email
            send_welcome_email(user)
            
            flash('Email verified successfully! You can now log in to your account.')
            return redirect(url_for('auth.login'))
        else:
            logger.warning(f"Email verification failed for: {user.email}")
            
            # Check if token expired and delete user if so
            if user.is_verification_expired():
                logger.info(f"Verification expired, deleting user: {user.email}")
                db.session.delete(user)
                db.session.commit()
                flash('Your verification link has expired. Please register again.')
                return redirect(url_for('auth.register'))
            else:
                flash('Email verification failed. Please try again or contact support.')
                return redirect(url_for('auth.login'))
        
    except Exception as e:
        logger.error(f"Error during email verification: {str(e)}", exc_info=True)
        db.session.rollback()
        flash('An error occurred during verification. Please try again.')
        return redirect(url_for('auth.login'))

@auth_bp.route('/resend-verification', methods=['GET', 'POST'])
def resend_verification():
    """Resend verification email"""
    if request.method == 'GET':
        return render_template('auth/resend_verification.html', title='Resend Verification')
    
    # POST request
    email = request.form.get('email', '').strip().lower()
    logger.info(f"Resend verification request for: {email}")
    
    if not email:
        flash('Please enter your email address.')
        return render_template('auth/resend_verification.html', title='Resend Verification')
    
    try:
        user = User.query.filter_by(email=email).first()
        
        if not user:
            # Don't reveal if email exists or not for security
            flash('If an account with that email exists and is not yet verified, a new verification email has been sent.')
            return redirect(url_for('auth.login'))
        
        if user.email_verified:
            flash('This email address is already verified. You can log in now.')
            return redirect(url_for('auth.login'))
        
        # Check if verification period expired and delete user if so
        if user.is_verification_expired():
            logger.info(f"User verification period expired, deleting account: {email}")
            db.session.delete(user)
            db.session.commit()
            flash('Your registration has expired. Please register again.')
            return redirect(url_for('auth.register'))
        
        # Send new verification email
        if send_verification_email(user):
            db.session.commit()  # Save the new verification token
            logger.info(f"Verification email resent to: {email}")
        
        flash('If an account with that email exists and is not yet verified, a new verification email has been sent.')
        return redirect(url_for('auth.login'))
        
    except Exception as e:
        logger.error(f"Error resending verification email: {str(e)}", exc_info=True)
        db.session.rollback()
        flash('An error occurred. Please try again.')
        return render_template('auth/resend_verification.html', title='Resend Verification')

@auth_bp.route('/reset-password', methods=['GET', 'POST'])
def reset_password_request():
    """Request password reset"""
    logger.info(f"Password reset request - Method: {request.method}, IP: {request.remote_addr}")
    
    if current_user.is_authenticated:
        logger.info(f"Authenticated user accessing password reset: {current_user.email}")
        return redirect(url_for('auth.dashboard'))
    
    form = PasswordResetRequestForm()
    
    if request.method == 'GET':
        logger.info("Serving password reset request form")
        return render_template('auth/reset_password_request.html', title='Reset Password', form=form)
    
    # POST request - process password reset request
    logger.info("Processing password reset request form submission")
    
    if not form.validate_on_submit():
        logger.warning(f"Password reset request form validation failed. Errors: {form.errors}")
        return render_template('auth/reset_password_request.html', title='Reset Password', form=form)
    
    email = form.email.data
    logger.info(f"Password reset request for email: {email}")
    
    try:
        user = User.query.filter_by(email=email).first()
        
        if user and user.email_verified and user.is_active:
            # Send password reset email
            logger.debug(f"Sending password reset email to: {email}")
            if send_password_reset_email(user):
                db.session.commit()  # Save the reset token
                logger.info(f"Password reset email sent to: {email}")
            else:
                logger.warning(f"Failed to send password reset email to: {email}")
        else:
            # Log different reasons but don't reveal to user
            if not user:
                logger.info(f"Password reset requested for non-existent user: {email}")
            elif not user.email_verified:
                logger.info(f"Password reset requested for unverified user: {email}")
            elif not user.is_active:
                logger.info(f"Password reset requested for inactive user: {email}")
        
        # Always show the same message for security (don't reveal if email exists)
        flash('If an account with that email address exists, you will receive a password reset email shortly.')
        return redirect(url_for('auth.login'))
        
    except Exception as e:
        logger.error(f"Error processing password reset request for {email}: {str(e)}", exc_info=True)
        db.session.rollback()
        flash('An error occurred. Please try again.')
        return render_template('auth/reset_password_request.html', title='Reset Password', form=form)

@auth_bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password_confirm(token):
    """Confirm password reset with token"""
    logger.info(f"Password reset confirmation - Token: {token[:10]}..., Method: {request.method}")
    
    if current_user.is_authenticated:
        logger.info(f"Authenticated user accessing password reset confirmation: {current_user.email}")
        return redirect(url_for('auth.dashboard'))
    
    # Find user with this reset token
    try:
        user = User.query.filter_by(password_reset_token=token).first()
        
        if not user:
            logger.warning(f"Invalid password reset token: {token[:10]}...")
            flash('Invalid or expired password reset link.')
            return redirect(url_for('auth.reset_password_request'))
        
        logger.debug(f"Found user for password reset: {user.email}")
        
        # Check if token is valid and not expired
        if not user.verify_password_reset_token(token):
            logger.warning(f"Password reset token verification failed for: {user.email}")
            # Clear expired token
            user.password_reset_token = None
            user.password_reset_sent_at = None
            db.session.commit()
            flash('Your password reset link has expired. Please request a new one.')
            return redirect(url_for('auth.reset_password_request'))
        
        form = PasswordResetForm()
        
        if request.method == 'GET':
            logger.info(f"Serving password reset form for user: {user.email}")
            return render_template('auth/reset_password_confirm.html',
                                 title='Reset Password', form=form, token=token)
        
        # POST request - process password reset
        logger.info(f"Processing password reset confirmation for user: {user.email}")
        
        if not form.validate_on_submit():
            logger.warning(f"Password reset form validation failed. Errors: {form.errors}")
            return render_template('auth/reset_password_confirm.html',
                                 title='Reset Password', form=form, token=token)
        
        # Reset the password
        if user.reset_password(token, form.password.data):
            db.session.commit()
            logger.info(f"Password reset successfully for user: {user.email}")
            flash('Your password has been reset successfully! You can now log in with your new password.')
            return redirect(url_for('auth.login'))
        else:
            logger.error(f"Password reset failed for user: {user.email}")
            flash('Password reset failed. Please try again or request a new reset link.')
            return redirect(url_for('auth.reset_password_request'))
        
    except Exception as e:
        logger.error(f"Error during password reset confirmation: {str(e)}", exc_info=True)
        db.session.rollback()
        flash('An error occurred during password reset. Please try again.')
        return redirect(url_for('auth.reset_password_request'))