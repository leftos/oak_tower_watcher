#!/usr/bin/env python3
"""
Database models for OAK Tower Watcher user portal
"""

from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

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
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """Check password against hash"""
        return check_password_hash(self.password_hash, password)
    
    def update_last_login(self):
        """Update last login timestamp"""
        self.last_login = datetime.utcnow()
        db.session.commit()
    
    def get_service_settings(self, service_name):
        """Get settings for a specific service"""
        return UserSettings.query.filter_by(
            user_id=self.id, 
            service_name=service_name
        ).first()
    
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