#!/usr/bin/env python3
"""
Minimal database interface for bulk notifications
Only includes what's needed to query users for notifications
"""

import os
import logging
import json
from datetime import datetime, timedelta
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

class MinimalUserFacilityStatusCache(Base):
    """Minimal UserFacilityStatusCache model for status caching"""
    __tablename__ = 'user_facility_status_cache'
    
    id = Column(Integer, primary_key=True)
    user_settings_id = Column(Integer, ForeignKey('user_settings.id'), nullable=False)
    status = Column(String(100), nullable=False)
    main_controllers = Column(String(2000))  # JSON string
    supporting_above = Column(String(2000))  # JSON string
    supporting_below = Column(String(2000))  # JSON string
    last_checked_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship to user settings
    user_settings = relationship('MinimalUserSettings')

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
    
    def get_cached_status(self, user_settings_id: int) -> Optional[Dict[str, Any]]:
        """
        Get cached facility status for a user
        
        Args:
            user_settings_id: The user settings ID
            
        Returns:
            Dictionary with cached status data or None if not found
        """
        if not self.enabled or not self.session_factory:
            return None
        
        try:
            session = self.session_factory()
            
            cache_entry = session.query(MinimalUserFacilityStatusCache).filter_by(
                user_settings_id=user_settings_id
            ).first()
            
            if not cache_entry:
                session.close()
                return None
            
            # Parse JSON data
            main_controllers = json.loads(cache_entry.main_controllers) if cache_entry.main_controllers else []
            supporting_above = json.loads(cache_entry.supporting_above) if cache_entry.supporting_above else []
            supporting_below = json.loads(cache_entry.supporting_below) if cache_entry.supporting_below else []
            
            result = {
                'status': cache_entry.status,
                'main_controllers': main_controllers,
                'supporting_above': supporting_above,
                'supporting_below': supporting_below,
                'last_checked_at': cache_entry.last_checked_at
            }
            
            session.close()
            logging.debug(f"Retrieved cached status for user_settings_id {user_settings_id}: {cache_entry.status}")
            return result
            
        except Exception as e:
            logging.error(f"Error getting cached status for user_settings_id {user_settings_id}: {e}")
            return None
    
    def update_cached_status(
        self,
        user_settings_id: int,
        status: str,
        main_controllers: List[Dict[str, Any]],
        supporting_above: List[Dict[str, Any]],
        supporting_below: List[Dict[str, Any]]
    ) -> bool:
        """
        Update cached facility status for a user
        
        Args:
            user_settings_id: The user settings ID
            status: Status string
            main_controllers: List of main controller data
            supporting_above: List of supporting above controller data
            supporting_below: List of supporting below controller data
            
        Returns:
            True if successful, False otherwise
        """
        if not self.enabled or not self.session_factory:
            return False
        
        try:
            session = self.session_factory()
            
            # Convert lists to JSON strings
            main_json = json.dumps(main_controllers) if main_controllers else None
            above_json = json.dumps(supporting_above) if supporting_above else None
            below_json = json.dumps(supporting_below) if supporting_below else None
            
            # Check if entry exists
            cache_entry = session.query(MinimalUserFacilityStatusCache).filter_by(
                user_settings_id=user_settings_id
            ).first()
            
            current_time = datetime.utcnow()
            
            if cache_entry:
                # Update existing entry
                cache_entry.status = status
                cache_entry.main_controllers = main_json
                cache_entry.supporting_above = above_json
                cache_entry.supporting_below = below_json
                cache_entry.last_checked_at = current_time
                cache_entry.updated_at = current_time
            else:
                # Create new entry
                cache_entry = MinimalUserFacilityStatusCache()
                cache_entry.user_settings_id = user_settings_id
                cache_entry.status = status
                cache_entry.main_controllers = main_json
                cache_entry.supporting_above = above_json
                cache_entry.supporting_below = below_json
                cache_entry.last_checked_at = current_time
                cache_entry.created_at = current_time
                cache_entry.updated_at = current_time
                session.add(cache_entry)
            
            session.commit()
            session.close()
            
            logging.debug(f"Updated cached status for user_settings_id {user_settings_id}: {status}")
            return True
            
        except Exception as e:
            logging.error(f"Error updating cached status for user_settings_id {user_settings_id}: {e}")
            return False
    
    def clear_cached_status(self, user_settings_id: int) -> bool:
        """
        Clear cached facility status for a user (e.g., when they change facility patterns)
        
        Args:
            user_settings_id: The user settings ID
            
        Returns:
            True if successful, False otherwise
        """
        if not self.enabled or not self.session_factory:
            return False
        
        try:
            session = self.session_factory()
            
            # Delete cache entry
            deleted = session.query(MinimalUserFacilityStatusCache).filter_by(
                user_settings_id=user_settings_id
            ).delete()
            
            session.commit()
            session.close()
            
            logging.debug(f"Cleared cached status for user_settings_id {user_settings_id} (deleted {deleted} entries)")
            return True
            
        except Exception as e:
            logging.error(f"Error clearing cached status for user_settings_id {user_settings_id}: {e}")
            return False
    
    def get_all_user_facility_patterns(self, service_name: str = 'oak_tower_watcher') -> Dict[str, List[str]]:
        """
        Get all unique facility patterns from all users to create comprehensive monitoring.
        If no user patterns exist, returns default patterns from config.
        
        Args:
            service_name: The service name to filter by
            
        Returns:
            Dictionary with aggregated facility patterns by type
        """
        if not self.enabled or not self.session_factory:
            # Return default patterns when database is not available
            from config.config import load_config
            config = load_config()
            return config.get("callsigns", {
                'main_facility': [],
                'supporting_above': [],
                'supporting_below': []
            })
        
        try:
            session = self.session_factory()
            
            # Query ALL active users with facility patterns (not just those with notifications enabled)
            # The web monitoring service should monitor all facilities users care about
            results = session.query(MinimalUserSettings, MinimalUser).join(
                MinimalUser, MinimalUserSettings.user_id == MinimalUser.id
            ).filter(
                MinimalUserSettings.service_name == service_name,
                MinimalUser.is_active == True,
                MinimalUser.email_verified == True
            ).all()
            
            # Aggregate all unique patterns
            aggregated_patterns = {
                'main_facility': set(),
                'supporting_above': set(),
                'supporting_below': set()
            }
            
            for settings, user in results:
                facility_patterns = settings.get_all_facility_patterns()
                
                # Add patterns to respective sets (using sets to avoid duplicates)
                for pattern_type, patterns in facility_patterns.items():
                    if pattern_type in aggregated_patterns:
                        for pattern in patterns:
                            if pattern.strip():  # Only add non-empty patterns
                                aggregated_patterns[pattern_type].add(pattern.strip())
            
            session.close()
            
            # Convert sets to lists
            result = {
                pattern_type: list(pattern_set)
                for pattern_type, pattern_set in aggregated_patterns.items()
            }
            
            total_patterns = sum(len(patterns) for patterns in result.values())
            
            # If no user patterns found at all, return default patterns
            if total_patterns == 0:
                logging.info("No user facility patterns found - returning default patterns")
                from config.config import load_config
                config = load_config()
                return config.get("callsigns", {
                    'main_facility': [],
                    'supporting_above': [],
                    'supporting_below': []
                })
            
            logging.info(f"Aggregated {total_patterns} unique facility patterns from {len(results)} users")
            return result
            
        except Exception as e:
            logging.error(f"Error getting aggregated facility patterns: {e}")
            # Return default patterns on error
            from config.config import load_config
            config = load_config()
            return config.get("callsigns", {
                'main_facility': [],
                'supporting_above': [],
                'supporting_below': []
            })
    
    def cleanup_old_cache_entries(self, days_old: int = 30) -> int:
        """
        Clean up old cache entries
        
        Args:
            days_old: Delete entries older than this many days
            
        Returns:
            Number of entries deleted
        """
        if not self.enabled or not self.session_factory:
            return 0
        
        try:
            session = self.session_factory()
            
            cutoff_date = datetime.utcnow() - timedelta(days=days_old)
            
            deleted = session.query(MinimalUserFacilityStatusCache).filter(
                MinimalUserFacilityStatusCache.last_checked_at < cutoff_date
            ).delete()
            
            session.commit()
            session.close()
            
            if deleted > 0:
                logging.info(f"Cleaned up {deleted} old cache entries (older than {days_old} days)")
            
            return deleted
            
        except Exception as e:
            logging.error(f"Error cleaning up old cache entries: {e}")
            return 0