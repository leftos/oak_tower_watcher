#!/usr/bin/env python3
"""
Database models for VATSIM Facility Monitoring
"""

import logging
from datetime import datetime
from ..models import db

# Configure logger for facility models module
logger = logging.getLogger(__name__)

class UserFacilityRegex(db.Model):
    """User-specific facility regex patterns"""
    __tablename__ = 'user_facility_regexes'
    
    id = db.Column(db.Integer, primary_key=True)
    user_settings_id = db.Column(db.Integer, db.ForeignKey('user_settings.id'), nullable=False)
    facility_type = db.Column(db.String(50), nullable=False)  # 'main_facility', 'supporting_above', 'supporting_below'
    regex_pattern = db.Column(db.String(255), nullable=False)
    sort_order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<UserFacilityRegex {self.facility_type}:{self.regex_pattern}>'

class UserFacilityStatusCache(db.Model):
    """Cache for user facility status to enable transition notifications"""
    __tablename__ = 'user_facility_status_cache'
    
    id = db.Column(db.Integer, primary_key=True)
    user_settings_id = db.Column(db.Integer, db.ForeignKey('user_settings.id'), nullable=False)
    status = db.Column(db.String(100), nullable=False)
    main_controllers = db.Column(db.Text)  # JSON string
    supporting_above = db.Column(db.Text)  # JSON string
    supporting_below = db.Column(db.Text)  # JSON string
    last_checked_at = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Unique constraint to ensure one cache entry per user settings
    __table_args__ = (db.UniqueConstraint('user_settings_id', name='unique_user_settings_cache'),)
    
    def __repr__(self):
        return f'<UserFacilityStatusCache user_settings_id={self.user_settings_id} status={self.status}>'

def create_facility_tables():
    """Create facility monitoring tables"""
    try:
        db.create_all()
        logger.info("Facility monitoring database tables created successfully")
    except Exception as e:
        logger.error(f"Error creating facility monitoring tables: {e}")
        raise