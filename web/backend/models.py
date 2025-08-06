#!/usr/bin/env python3
"""
Database models for OAK Tower Watcher user portal
"""

import logging
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

# Configure logger for models module
logger = logging.getLogger(__name__)

db = SQLAlchemy()

class User(UserMixin, db.Model):
    """User model for authentication and settings"""
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)
    is_active = db.Column(db.Boolean, default=True)
    
    # Relationship to user settings
    settings = db.relationship('UserSettings', backref='user', lazy=True, cascade='all, delete-orphan')
    
    def set_password(self, password):
        """Set password hash"""
        try:
            logger.debug(f"Setting password hash for user: {self.email}")
            self.password_hash = generate_password_hash(password)
            logger.debug(f"Password hash set successfully for user: {self.email}")
        except Exception as e:
            logger.error(f"Error setting password hash for user {self.email}: {str(e)}", exc_info=True)
            raise
    
    def check_password(self, password):
        """Check password against hash"""
        try:
            logger.debug(f"Checking password for user: {self.email}")
            
            if not self.password_hash:
                logger.warning(f"No password hash found for user: {self.email}")
                return False
            
            if not password:
                logger.warning(f"Empty password provided for user: {self.email}")
                return False
            
            result = check_password_hash(self.password_hash, password)
            logger.debug(f"Password check result for user {self.email}: {'VALID' if result else 'INVALID'}")
            return result
            
        except Exception as e:
            logger.error(f"Error checking password for user {self.email}: {str(e)}", exc_info=True)
            return False
    
    def update_last_login(self):
        """Update last login timestamp"""
        try:
            logger.debug(f"Updating last login timestamp for user: {self.email}")
            self.last_login = datetime.utcnow()
            db.session.commit()
            logger.debug(f"Last login timestamp updated successfully for user: {self.email}")
        except Exception as e:
            logger.error(f"Error updating last login for user {self.email}: {str(e)}", exc_info=True)
            db.session.rollback()
            raise
    
    def get_service_settings(self, service_name):
        """Get settings for a specific service"""
        try:
            logger.debug(f"Getting service settings for user {self.email}, service: {service_name}")
            settings = UserSettings.query.filter_by(
                user_id=self.id,
                service_name=service_name
            ).first()
            logger.debug(f"Service settings {'found' if settings else 'not found'} for user {self.email}, service: {service_name}")
            return settings
        except Exception as e:
            logger.error(f"Error getting service settings for user {self.email}, service {service_name}: {str(e)}", exc_info=True)
            return None
    
    def __repr__(self):
        return f'<User {self.email}>'

class UserSettings(db.Model):
    """User settings for different services"""
    __tablename__ = 'user_settings'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    service_name = db.Column(db.String(50), nullable=False)  # e.g., 'oak_tower_watcher'
    pushover_api_token = db.Column(db.String(255))
    pushover_user_key = db.Column(db.String(255))
    notifications_enabled = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Unique constraint to ensure one setting per user per service
    __table_args__ = (db.UniqueConstraint('user_id', 'service_name', name='unique_user_service'),)
    
    def __repr__(self):
        return f'<UserSettings {self.user.email}:{self.service_name}>'