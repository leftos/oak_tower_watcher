#!/usr/bin/env python3
"""
Database models for OAK Tower Watcher user portal
"""

import logging
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import secrets

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
    is_banned = db.Column(db.Boolean, default=False)  # For admin banning functionality
    banned_at = db.Column(db.DateTime, nullable=True)  # When user was banned
    banned_reason = db.Column(db.String(500), nullable=True)  # Reason for ban
    
    # Email verification fields
    email_verified = db.Column(db.Boolean, default=False, nullable=False)
    email_verification_token = db.Column(db.String(255), unique=True, nullable=True)
    email_verification_sent_at = db.Column(db.DateTime, nullable=True)
    
    # Password reset fields
    password_reset_token = db.Column(db.String(255), unique=True, nullable=True)
    password_reset_sent_at = db.Column(db.DateTime, nullable=True)
    
    # General Pushover settings (shared across all apps)
    pushover_api_token = db.Column(db.String(255), nullable=True)
    pushover_user_key = db.Column(db.String(255), nullable=True)
    
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
    
    def generate_verification_token(self):
        """Generate a new email verification token"""
        try:
            logger.debug(f"Generating verification token for user: {self.email}")
            self.email_verification_token = secrets.token_urlsafe(32)
            self.email_verification_sent_at = datetime.utcnow()
            logger.debug(f"Verification token generated for user: {self.email}")
            return self.email_verification_token
        except Exception as e:
            logger.error(f"Error generating verification token for user {self.email}: {str(e)}", exc_info=True)
            raise
    
    def verify_email(self, token):
        """Verify email with the provided token"""
        try:
            logger.debug(f"Verifying email token for user: {self.email}")
            
            if not self.email_verification_token:
                logger.warning(f"No verification token found for user: {self.email}")
                return False
            
            if self.email_verification_token != token:
                logger.warning(f"Invalid verification token for user: {self.email}")
                return False
            
            if self.is_verification_expired():
                logger.warning(f"Verification token expired for user: {self.email}")
                return False
            
            # Mark email as verified and clear token
            self.email_verified = True
            self.email_verification_token = None
            self.email_verification_sent_at = None
            
            logger.info(f"Email verified successfully for user: {self.email}")
            return True
            
        except Exception as e:
            logger.error(f"Error verifying email for user {self.email}: {str(e)}", exc_info=True)
            return False
    
    def is_verification_expired(self):
        """Check if the verification token has expired (48 hours)"""
        try:
            if not self.email_verification_sent_at:
                return True
            
            expiry_time = self.email_verification_sent_at + timedelta(hours=48)
            is_expired = datetime.utcnow() > expiry_time
            
            logger.debug(f"Verification token expired check for user {self.email}: {is_expired}")
            return is_expired
            
        except Exception as e:
            logger.error(f"Error checking verification expiry for user {self.email}: {str(e)}", exc_info=True)
            return True
    
    def can_login(self):
        """Check if user can log in (email must be verified and not banned)"""
        return self.is_active and self.email_verified and not self.is_banned
    
    def ban_user(self, reason=None):
        """Ban a user account"""
        try:
            logger.info(f"Banning user: {self.email}, reason: {reason}")
            self.is_banned = True
            self.banned_at = datetime.utcnow()
            self.banned_reason = reason
            db.session.commit()
            logger.info(f"User banned successfully: {self.email}")
        except Exception as e:
            logger.error(f"Error banning user {self.email}: {str(e)}", exc_info=True)
            db.session.rollback()
            raise
    
    def unban_user(self):
        """Unban a user account"""
        try:
            logger.info(f"Unbanning user: {self.email}")
            self.is_banned = False
            self.banned_at = None
            self.banned_reason = None
            db.session.commit()
            logger.info(f"User unbanned successfully: {self.email}")
        except Exception as e:
            logger.error(f"Error unbanning user {self.email}: {str(e)}", exc_info=True)
            db.session.rollback()
            raise
    
    def generate_password_reset_token(self):
        """Generate a new password reset token"""
        try:
            logger.debug(f"Generating password reset token for user: {self.email}")
            self.password_reset_token = secrets.token_urlsafe(32)
            self.password_reset_sent_at = datetime.utcnow()
            logger.debug(f"Password reset token generated for user: {self.email}")
            return self.password_reset_token
        except Exception as e:
            logger.error(f"Error generating password reset token for user {self.email}: {str(e)}", exc_info=True)
            raise
    
    def verify_password_reset_token(self, token):
        """Verify password reset token"""
        try:
            logger.debug(f"Verifying password reset token for user: {self.email}")
            
            if not self.password_reset_token:
                logger.warning(f"No password reset token found for user: {self.email}")
                return False
            
            if self.password_reset_token != token:
                logger.warning(f"Invalid password reset token for user: {self.email}")
                return False
            
            if self.is_password_reset_expired():
                logger.warning(f"Password reset token expired for user: {self.email}")
                return False
            
            logger.info(f"Password reset token verified successfully for user: {self.email}")
            return True
            
        except Exception as e:
            logger.error(f"Error verifying password reset token for user {self.email}: {str(e)}", exc_info=True)
            return False
    
    def is_password_reset_expired(self):
        """Check if the password reset token has expired (24 hours)"""
        try:
            if not self.password_reset_sent_at:
                return True
            
            expiry_time = self.password_reset_sent_at + timedelta(hours=24)
            is_expired = datetime.utcnow() > expiry_time
            
            logger.debug(f"Password reset token expired check for user {self.email}: {is_expired}")
            return is_expired
            
        except Exception as e:
            logger.error(f"Error checking password reset expiry for user {self.email}: {str(e)}", exc_info=True)
            return True
    
    def reset_password(self, token, new_password):
        """Reset password using token"""
        try:
            logger.debug(f"Attempting to reset password for user: {self.email}")
            
            if not self.verify_password_reset_token(token):
                logger.warning(f"Password reset failed - invalid token for user: {self.email}")
                return False
            
            # Set new password
            self.set_password(new_password)
            
            # Clear password reset token
            self.password_reset_token = None
            self.password_reset_sent_at = None
            
            logger.info(f"Password reset successfully for user: {self.email}")
            return True
            
        except Exception as e:
            logger.error(f"Error resetting password for user {self.email}: {str(e)}", exc_info=True)
            return False
    
    def __repr__(self):
        return f'<User {self.email}>'

class UserSettings(db.Model):
    """User settings for different services"""
    __tablename__ = 'user_settings'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    service_name = db.Column(db.String(50), nullable=False)  # e.g., 'oak_tower_watcher'
    notifications_enabled = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships - import facility models when needed
    @property
    def facility_regexes(self):
        """Get facility regex patterns - dynamically import to avoid circular imports"""
        try:
            from .facility_monitor.models import UserFacilityRegex
            return UserFacilityRegex.query.filter_by(user_settings_id=self.id).all()
        except ImportError:
            return []
    
    # Unique constraint to ensure one setting per user per service
    __table_args__ = (db.UniqueConstraint('user_id', 'service_name', name='unique_user_service'),)
    
    def get_facility_patterns(self, facility_type):
        """Get facility regex patterns for a specific type"""
        try:
            from .facility_monitor.models import UserFacilityRegex
            patterns = UserFacilityRegex.query.filter_by(
                user_settings_id=self.id,
                facility_type=facility_type
            ).order_by(UserFacilityRegex.sort_order).all()
            
            return [pattern.regex_pattern for pattern in patterns]
            
        except Exception as e:
            logger.error(f"Error getting facility patterns for user settings ID {self.id}, type {facility_type}: {str(e)}", exc_info=True)
            return []
    
    def get_all_facility_patterns(self):
        """Get all facility regex patterns organized by type"""
        try:
            return {
                'main_facility': self.get_facility_patterns('main_facility'),
                'supporting_above': self.get_facility_patterns('supporting_above'),
                'supporting_below': self.get_facility_patterns('supporting_below')
            }
        except Exception as e:
            logger.error(f"Error getting all facility patterns for user settings ID {self.id}: {str(e)}", exc_info=True)
            return {
                'main_facility': [],
                'supporting_above': [],
                'supporting_below': []
            }
    
    def set_facility_patterns(self, facility_type, patterns):
        """Set facility regex patterns for a specific type"""
        try:
            from .facility_monitor.models import UserFacilityRegex
            logger.debug(f"Setting facility patterns for user settings ID {self.id}, type {facility_type}")
            
            # Delete existing patterns for this type
            UserFacilityRegex.query.filter_by(
                user_settings_id=self.id,
                facility_type=facility_type
            ).delete()
            
            # Add new patterns
            for i, pattern in enumerate(patterns):
                if pattern.strip():  # Only add non-empty patterns
                    regex = UserFacilityRegex()
                    regex.user_settings_id = self.id
                    regex.facility_type = facility_type
                    regex.regex_pattern = pattern.strip()
                    regex.sort_order = i
                    db.session.add(regex)
            
            db.session.commit()
            logger.debug(f"Successfully set {len(patterns)} facility patterns for user settings ID {self.id}, type {facility_type}")
            
        except Exception as e:
            logger.error(f"Error setting facility patterns for user settings ID {self.id}, type {facility_type}: {str(e)}", exc_info=True)
            db.session.rollback()
            raise
    
    def __repr__(self):
        return f'<UserSettings ID={self.id}:{self.service_name}>'