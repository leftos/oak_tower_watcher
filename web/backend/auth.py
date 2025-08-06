#!/usr/bin/env python3
"""
Authentication routes and user management
"""

import logging
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from .models import db, User, UserSettings
from .forms import LoginForm, RegistrationForm, UserSettingsForm

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
        # Create new user
        logger.debug(f"Creating new user: {email}")
        user = User(email=email)
        user.set_password(form.password.data)
        
        db.session.add(user)
        db.session.commit()
        logger.info(f"User created successfully: {email}, ID: {user.id}")
        
        # Create default settings for OAK Tower Watcher
        logger.debug(f"Creating default settings for user: {email}")
        default_settings = UserSettings(
            user_id=user.id,
            service_name='oak_tower_watcher',
            notifications_enabled=True
        )
        db.session.add(default_settings)
        db.session.commit()
        logger.info(f"Default settings created for user: {email}")
        
        flash('Congratulations, you are now registered!')
        logger.info(f"Registration completed successfully for: {email}")
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