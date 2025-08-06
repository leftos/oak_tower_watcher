#!/usr/bin/env python3
"""
Minimal database interface for bulk notifications
Only includes what's needed to query users for notifications
"""

import os
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional

from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, ForeignKey, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship

Base = declarative_base()

class MinimalUser(Base):
    """Minimal User model for bulk notifications"""
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    email = Column(String(120), nullable=False)
    is_active = Column(Boolean, default=True)
    email_verified = Column(Boolean, default=False)
    
    # Relationship to settings
    settings = relationship('MinimalUserSettings', back_populates='user')

class MinimalUserSettings(Base):
    """Minimal UserSettings model for bulk notifications"""
    __tablename__ = 'user_settings'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    service_name = Column(String(50), nullable=False)
    pushover_api_token = Column(String(255))
    pushover_user_key = Column(String(255))
    notifications_enabled = Column(Boolean, default=True)
    
    # Relationship to user
    user = relationship('MinimalUser', back_populates='settings')
    # Relationship to facility patterns
    facility_regexes = relationship('MinimalUserFacilityRegex', back_populates='user_settings')
    
    def get_all_facility_patterns(self):
        """Get all facility regex patterns organized by type"""
        try:
            patterns = {
                'main_facility': [],
                'supporting_above': [],
                'supporting_below': []
            }
            
            for regex in self.facility_regexes:
                if regex.facility_type in patterns:
                    patterns[regex.facility_type].append(regex.regex_pattern)
            
            return patterns
        except Exception as e:
            logging.error(f"Error getting facility patterns: {e}")
            return {
                'main_facility': [],
                'supporting_above': [],
                'supporting_below': []
            }

class MinimalUserFacilityRegex(Base):
    """Minimal UserFacilityRegex model for bulk notifications"""
    __tablename__ = 'user_facility_regexes'
    
    id = Column(Integer, primary_key=True)
    user_settings_id = Column(Integer, ForeignKey('user_settings.id'), nullable=False)
    facility_type = Column(String(50), nullable=False)
    regex_pattern = Column(String(255), nullable=False)
    sort_order = Column(Integer, default=0)
    
    # Relationship to user settings
    user_settings = relationship('MinimalUserSettings', back_populates='facility_regexes')

class DatabaseInterface:
    """Minimal database interface for bulk notifications"""
    
    def __init__(self, database_url: Optional[str] = None):
        self.engine = None
        self.session_factory = None
        self.enabled = False
        
        # Use environment variable or default
        db_url = database_url or os.getenv('DATABASE_URL')
        if not db_url:
            logging.warning("No database URL configured - database interface disabled")
            return
        
        try:
            self.engine = create_engine(db_url)
            self.session_factory = sessionmaker(bind=self.engine)
            self.enabled = True
            logging.info(f"Database interface initialized successfully: {db_url}")
        except Exception as e:
            logging.error(f"Failed to initialize database interface: {e}")
            self.enabled = False
    
    def get_notification_users(self, service_name: str = 'oak_tower_watcher') -> List[Dict[str, Any]]:
        """
        Get all users with valid Pushover credentials and notifications enabled
        
        Args:
            service_name: The service name to filter by
            
        Returns:
            List of user notification settings with facility patterns
        """
        if not self.enabled or not self.session_factory:
            return []
        
        try:
            session = self.session_factory()
            
            # Query for users with valid Pushover settings and notifications enabled
            results = session.query(MinimalUserSettings, MinimalUser).join(
                MinimalUser, MinimalUserSettings.user_id == MinimalUser.id
            ).filter(
                MinimalUserSettings.service_name == service_name,
                MinimalUserSettings.notifications_enabled == True,
                MinimalUserSettings.pushover_api_token.isnot(None),
                MinimalUserSettings.pushover_user_key.isnot(None),
                MinimalUserSettings.pushover_api_token != '',
                MinimalUserSettings.pushover_user_key != '',
                MinimalUser.is_active == True,
                MinimalUser.email_verified == True
            ).all()
            
            # Convert to list of dictionaries
            user_settings = []
            for settings, user in results:
                facility_patterns = settings.get_all_facility_patterns()
                
                user_settings.append({
                    'user_id': user.id,
                    'user_email': user.email,
                    'pushover_api_token': settings.pushover_api_token,
                    'pushover_user_key': settings.pushover_user_key,
                    'service_name': settings.service_name,
                    'facility_patterns': facility_patterns
                })
            
            session.close()
            logging.info(f"Found {len(user_settings)} users with valid Pushover settings")
            return user_settings
            
        except Exception as e:
            logging.error(f"Error querying notification users: {e}")
            return []
    
    def test_connection(self) -> bool:
        """Test database connection"""
        if not self.enabled or not self.session_factory:
            return False
        
        try:
            session = self.session_factory()
            # Simple test query
            result = session.execute(text("SELECT 1")).scalar()
            session.close()
            return result == 1
        except Exception as e:
            logging.error(f"Database connection test failed: {e}")
            return False