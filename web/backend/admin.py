#!/usr/bin/env python3
"""
Admin panel for user management
"""

import json
import logging
import os
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session, abort
from werkzeug.security import check_password_hash, generate_password_hash
from .models import db, User, UserSettings
from .facility_monitor.models import UserFacilityRegex
from .security import rate_limit

# Configure logger
logger = logging.getLogger(__name__)

admin_bp = Blueprint('admin', __name__)

def check_admin_auth():
    """Check if current session is authenticated as admin"""
    return session.get('admin_authenticated', False)

def authenticate_admin(username, password):
    """Authenticate admin using environment variables"""
    try:
        admin_username = os.environ.get('ADMIN_USERNAME')
        admin_password = os.environ.get('ADMIN_PASSWORD')
        
        if not admin_username or not admin_password:
            logger.error("Admin credentials not set in environment variables")
            return False
        
        # Simple string comparison for username and password
        if username == admin_username and password == admin_password:
            logger.info(f"Admin authentication successful for username: {username}")
            return True
        else:
            logger.warning(f"Admin authentication failed for username: {username}")
            return False
            
    except Exception as e:
        logger.error(f"Error during admin authentication: {str(e)}", exc_info=True)
        return False

def require_admin():
    """Decorator to require admin authentication"""
    def decorator(f):
        def decorated_function(*args, **kwargs):
            if not check_admin_auth():
                flash('Admin authentication required.', 'error')
                return redirect(url_for('admin.login'))
            return f(*args, **kwargs)
        decorated_function.__name__ = f.__name__
        return decorated_function
    return decorator

@admin_bp.route('/login', methods=['GET', 'POST'])
@rate_limit(max_requests=5, window_minutes=15)  # Strict rate limiting for admin login
def login():
    """Admin login page"""
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        
        if not username or not password:
            flash('Username and password are required.', 'error')
            return render_template('admin/login.html')
        
        if authenticate_admin(username, password):
            session['admin_authenticated'] = True
            session['admin_login_time'] = datetime.utcnow().isoformat()
            flash('Admin login successful.', 'success')
            return redirect(url_for('admin.dashboard'))
        else:
            flash('Invalid admin credentials.', 'error')
            return render_template('admin/login.html')
    
    return render_template('admin/login.html')

@admin_bp.route('/logout')
def logout():
    """Admin logout"""
    session.pop('admin_authenticated', None)
    session.pop('admin_login_time', None)
    flash('Admin logout successful.', 'info')
    return redirect(url_for('admin.login'))

@admin_bp.route('/dashboard')
@require_admin()
def dashboard():
    """Admin dashboard"""
    try:
        # Get user statistics
        total_users = User.query.count()
        active_users = User.query.filter_by(is_active=True, is_banned=False).count()
        banned_users = User.query.filter_by(is_banned=True).count()
        unverified_users = User.query.filter_by(email_verified=False).count()
        
        # Get recent users (last 10)
        recent_users = User.query.order_by(User.created_at.desc()).limit(10).all()
        
        stats = {
            'total_users': total_users,
            'active_users': active_users,
            'banned_users': banned_users,
            'unverified_users': unverified_users,
            'recent_users': recent_users
        }
        
        return render_template('admin/dashboard.html', stats=stats)
        
    except Exception as e:
        logger.error(f"Error loading admin dashboard: {str(e)}", exc_info=True)
        flash('Error loading dashboard.', 'error')
        return render_template('admin/dashboard.html', stats={})

@admin_bp.route('/users')
@require_admin()
def users():
    """List all users"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = 20
        
        # Build query based on filters
        query = User.query
        
        # Filter by status
        status_filter = request.args.get('status', 'all')
        if status_filter == 'active':
            query = query.filter_by(is_active=True, is_banned=False)
        elif status_filter == 'banned':
            query = query.filter_by(is_banned=True)
        elif status_filter == 'unverified':
            query = query.filter_by(email_verified=False)
        
        # Search by email
        search = request.args.get('search', '').strip()
        if search:
            query = query.filter(User.email.contains(search))
        
        # Paginate results
        users_pagination = query.order_by(User.created_at.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        return render_template('admin/users.html', 
                             users=users_pagination,
                             status_filter=status_filter,
                             search=search)
        
    except Exception as e:
        logger.error(f"Error loading users list: {str(e)}", exc_info=True)
        flash('Error loading users list.', 'error')
        return render_template('admin/users.html', users=None)

@admin_bp.route('/user/<int:user_id>')
@require_admin()
def user_detail(user_id):
    """Show detailed user information"""
    try:
        user = User.query.get_or_404(user_id)
        
        # Get user settings with facility configurations
        user_settings = UserSettings.query.filter_by(user_id=user.id).all()
        
        # Build comprehensive user data for JSON display
        user_data = {
            'basic_info': {
                'id': user.id,
                'email': user.email,
                'created_at': user.created_at.isoformat() if user.created_at else None,
                'last_login': user.last_login.isoformat() if user.last_login else None,
                'is_active': user.is_active,
                'is_banned': user.is_banned,
                'banned_at': user.banned_at.isoformat() if user.banned_at else None,
                'banned_reason': user.banned_reason,
                'email_verified': user.email_verified,
                'email_verification_sent_at': user.email_verification_sent_at.isoformat() if user.email_verification_sent_at else None
            },
            'settings': []
        }
        
        for setting in user_settings:
            facility_patterns = setting.get_all_facility_patterns()
            setting_data = {
                'id': setting.id,
                'service_name': setting.service_name,
                'notifications_enabled': setting.notifications_enabled,
                'has_pushover_config': bool(setting.pushover_api_token and setting.pushover_user_key),
                'created_at': setting.created_at.isoformat() if setting.created_at else None,
                'updated_at': setting.updated_at.isoformat() if setting.updated_at else None,
                'facility_patterns': facility_patterns
            }
            user_data['settings'].append(setting_data)
        
        return render_template('admin/user_detail.html', 
                             user=user, 
                             user_data=user_data,
                             user_data_json=json.dumps(user_data, indent=2))
        
    except Exception as e:
        logger.error(f"Error loading user detail for ID {user_id}: {str(e)}", exc_info=True)
        flash('Error loading user details.', 'error')
        return redirect(url_for('admin.users'))

@admin_bp.route('/user/<int:user_id>/ban', methods=['POST'])
@require_admin()
def ban_user(user_id):
    """Ban a user"""
    try:
        user = User.query.get_or_404(user_id)
        reason = request.form.get('reason', 'Banned by administrator').strip()
        
        if user.is_banned:
            flash(f'User {user.email} is already banned.', 'warning')
        else:
            user.ban_user(reason)
            flash(f'User {user.email} has been banned successfully.', 'success')
            logger.info(f"Admin banned user: {user.email}, reason: {reason}")
        
        return redirect(url_for('admin.user_detail', user_id=user_id))
        
    except Exception as e:
        logger.error(f"Error banning user ID {user_id}: {str(e)}", exc_info=True)
        flash('Error banning user.', 'error')
        return redirect(url_for('admin.users'))

@admin_bp.route('/user/<int:user_id>/unban', methods=['POST'])
@require_admin()
def unban_user(user_id):
    """Unban a user"""
    try:
        user = User.query.get_or_404(user_id)
        
        if not user.is_banned:
            flash(f'User {user.email} is not banned.', 'warning')
        else:
            user.unban_user()
            flash(f'User {user.email} has been unbanned successfully.', 'success')
            logger.info(f"Admin unbanned user: {user.email}")
        
        return redirect(url_for('admin.user_detail', user_id=user_id))
        
    except Exception as e:
        logger.error(f"Error unbanning user ID {user_id}: {str(e)}", exc_info=True)
        flash('Error unbanning user.', 'error')
        return redirect(url_for('admin.users'))

@admin_bp.route('/api/user-stats')
@require_admin()
def api_user_stats():
    """API endpoint for user statistics"""
    try:
        stats = {
            'total_users': User.query.count(),
            'active_users': User.query.filter_by(is_active=True, is_banned=False).count(),
            'banned_users': User.query.filter_by(is_banned=True).count(),
            'unverified_users': User.query.filter_by(email_verified=False).count(),
            'timestamp': datetime.utcnow().isoformat()
        }
        return jsonify(stats)
        
    except Exception as e:
        logger.error(f"Error getting user stats: {str(e)}", exc_info=True)
        return jsonify({'error': 'Failed to get user statistics'}), 500