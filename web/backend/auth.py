#!/usr/bin/env python3
"""
Authentication routes and user management
"""

from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from .models import db, User, UserSettings
from .forms import LoginForm, RegistrationForm, UserSettingsForm

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """User login page"""
    if current_user.is_authenticated:
        return redirect(url_for('auth.dashboard'))
    
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user is None or not user.check_password(form.password.data):
            flash('Invalid email or password')
            return redirect(url_for('auth.login'))
        
        login_user(user, remember=form.remember_me.data)
        user.update_last_login()
        
        next_page = request.args.get('next')
        if not next_page or not next_page.startswith('/'):
            next_page = url_for('auth.dashboard')
        return redirect(next_page)
    
    return render_template('auth/login.html', title='Sign In', form=form)

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """User registration page"""
    if current_user.is_authenticated:
        return redirect(url_for('auth.dashboard'))
    
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(email=form.email.data)
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        
        # Create default settings for OAK Tower Watcher
        default_settings = UserSettings(
            user_id=user.id,
            service_name='oak_tower_watcher',
            notifications_enabled=True
        )
        db.session.add(default_settings)
        db.session.commit()
        
        flash('Congratulations, you are now registered!')
        return redirect(url_for('auth.login'))
    
    return render_template('auth/register.html', title='Register', form=form)

@auth_bp.route('/logout')
@login_required
def logout():
    """User logout"""
    logout_user()
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