#!/usr/bin/env python3
"""
Database models for OAK ARTCC Training Session Monitoring
"""

import logging
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
import json
from ..models import db

# Configure logger for training models module
logger = logging.getLogger(__name__)

class TrainingSessionSettings(db.Model):
    """User settings for training session monitoring"""
    __tablename__ = 'training_session_settings'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    service_name = db.Column(db.String(50), nullable=False, default='oak_training_monitor')
    
    # OAK ARTCC credentials
    php_session_key = db.Column(db.String(255), nullable=True)
    session_key_last_validated = db.Column(db.DateTime, nullable=True)
    
    # Notification preferences
    notifications_enabled = db.Column(db.Boolean, default=True)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    monitored_ratings = db.relationship('TrainingMonitoredRating', backref='settings', lazy=True, cascade='all, delete-orphan')
    session_cache = db.relationship('TrainingSessionCache', backref='settings', lazy=True, cascade='all, delete-orphan')
    
    # Unique constraint
    __table_args__ = (db.UniqueConstraint('user_id', 'service_name', name='unique_user_training_service'),)
    
    def get_monitored_ratings(self):
        """Get list of monitored rating patterns"""
        try:
            ratings = TrainingMonitoredRating.query.filter_by(
                settings_id=self.id
            ).order_by(TrainingMonitoredRating.sort_order).all()
            
            return [rating.rating_pattern for rating in ratings]
            
        except Exception as e:
            logger.error(f"Error getting monitored ratings for settings ID {self.id}: {str(e)}", exc_info=True)
            return []
    
    def set_monitored_ratings(self, rating_patterns):
        """Set monitored rating patterns"""
        try:
            logger.debug(f"Setting monitored ratings for settings ID {self.id}: {rating_patterns}")
            
            # Delete existing ratings
            TrainingMonitoredRating.query.filter_by(settings_id=self.id).delete()
            
            # Add new ratings
            for i, pattern in enumerate(rating_patterns):
                if pattern.strip():  # Only add non-empty patterns
                    rating = TrainingMonitoredRating()
                    rating.settings_id = self.id
                    rating.rating_pattern = pattern.strip()
                    rating.sort_order = i
                    db.session.add(rating)
            
            db.session.commit()
            logger.debug(f"Successfully set {len(rating_patterns)} monitored ratings for settings ID {self.id}")
            
        except Exception as e:
            logger.error(f"Error setting monitored ratings for settings ID {self.id}: {str(e)}", exc_info=True)
            db.session.rollback()
            raise
    
    def is_session_key_expired(self):
        """Check if session key needs validation (weekly check)"""
        if not self.session_key_last_validated:
            return True
        
        week_ago = datetime.utcnow() - timedelta(days=7)
        return self.session_key_last_validated < week_ago
    
    def mark_session_key_validated(self):
        """Mark session key as recently validated"""
        try:
            self.session_key_last_validated = datetime.utcnow()
            db.session.commit()
            logger.debug(f"Marked session key as validated for settings ID {self.id}")
        except Exception as e:
            logger.error(f"Error marking session key as validated for settings ID {self.id}: {str(e)}", exc_info=True)
            db.session.rollback()
            raise
    
    def __repr__(self):
        return f'<TrainingSessionSettings ID={self.id} user_id={self.user_id}>'


class TrainingMonitoredRating(db.Model):
    """Rating patterns that users want to monitor (e.g., S1-OAK, S2-OAK, S1-SFO)"""
    __tablename__ = 'training_monitored_ratings'
    
    id = db.Column(db.Integer, primary_key=True)
    settings_id = db.Column(db.Integer, db.ForeignKey('training_session_settings.id'), nullable=False)
    rating_pattern = db.Column(db.String(50), nullable=False)  # e.g., 'S1-OAK', 'S2-OAK'
    sort_order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<TrainingMonitoredRating {self.rating_pattern}>'


class TrainingSessionCache(db.Model):
    """Cached training session data for users"""
    __tablename__ = 'training_session_cache'
    
    id = db.Column(db.Integer, primary_key=True)
    settings_id = db.Column(db.Integer, db.ForeignKey('training_session_settings.id'), nullable=False)
    
    # Cached session data (JSON)
    cached_sessions = db.Column(db.Text)  # JSON string of training sessions
    last_fetched_at = db.Column(db.DateTime, nullable=False)
    fetch_successful = db.Column(db.Boolean, default=True)
    error_message = db.Column(db.Text)  # Store error if fetch failed
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Unique constraint
    __table_args__ = (db.UniqueConstraint('settings_id', name='unique_settings_cache'),)
    
    def get_sessions(self):
        """Get parsed training sessions from cache"""
        try:
            if not self.cached_sessions:
                return []
            
            return json.loads(self.cached_sessions)
        except (json.JSONDecodeError, TypeError) as e:
            logger.error(f"Error parsing cached sessions for cache ID {self.id}: {str(e)}")
            return []
    
    def set_sessions(self, sessions):
        """Set training sessions in cache"""
        try:
            self.cached_sessions = json.dumps(sessions, ensure_ascii=False)
            self.last_fetched_at = datetime.utcnow()
            self.fetch_successful = True
            self.error_message = None
            logger.debug(f"Cached {len(sessions)} training sessions for cache ID {self.id}")
        except Exception as e:
            logger.error(f"Error caching sessions for cache ID {self.id}: {str(e)}", exc_info=True)
            raise
    
    def set_fetch_error(self, error_message):
        """Set error state for failed fetch"""
        try:
            self.last_fetched_at = datetime.utcnow()
            self.fetch_successful = False
            self.error_message = error_message
            logger.warning(f"Set fetch error for cache ID {self.id}: {error_message}")
        except Exception as e:
            logger.error(f"Error setting fetch error for cache ID {self.id}: {str(e)}", exc_info=True)
            raise
    
    def is_cache_stale(self, max_age_hours=1):
        """Check if cache is stale and needs refresh"""
        if not self.last_fetched_at:
            return True
        
        threshold = datetime.utcnow() - timedelta(hours=max_age_hours)
        return self.last_fetched_at < threshold
    
    def get_filtered_sessions(self, rating_patterns):
        """
        Get sessions from cache filtered by specific rating patterns
        This allows immediate filtering without re-scraping when user updates their monitored ratings
        """
        if not self.cached_sessions or not self.fetch_successful:
            return []
        
        try:
            all_sessions = json.loads(self.cached_sessions)
            
            if not rating_patterns:
                return []
            
            # Filter sessions that match any of the rating patterns
            filtered_sessions = []
            for session in all_sessions:
                session_rating = session.get('rating_pattern', '')
                if session_rating and session_rating in rating_patterns:
                    filtered_sessions.append(session)
            
            logger.debug(f"Filtered {len(filtered_sessions)} sessions from {len(all_sessions)} total for cache ID {self.id}")
            return filtered_sessions
            
        except (json.JSONDecodeError, TypeError) as e:
            logger.error(f"Error parsing cached sessions for filtering in cache ID {self.id}: {e}")
            return []
    
    def __repr__(self):
        return f'<TrainingSessionCache ID={self.id} settings_id={self.settings_id} successful={self.fetch_successful}>'


class GlobalTrainingSessionCache(db.Model):
    """Global cache for all training sessions (scraped once per check cycle)"""
    __tablename__ = 'global_training_session_cache'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Global cached session data (JSON)
    cached_sessions = db.Column(db.Text)  # JSON string of all training sessions
    last_scraped_at = db.Column(db.DateTime, nullable=False)
    scrape_successful = db.Column(db.Boolean, default=True)
    error_message = db.Column(db.Text)  # Store error if scrape failed
    session_key_used = db.Column(db.String(50))  # Track which key was used (for debugging)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def get_all_sessions(self):
        """Get all parsed training sessions from global cache"""
        try:
            if not self.cached_sessions:
                return []
            
            return json.loads(self.cached_sessions)
        except (json.JSONDecodeError, TypeError) as e:
            logger.error(f"Error parsing global cached sessions: {str(e)}")
            return []
    
    def set_sessions(self, sessions, session_key_type='service'):
        """Set training sessions in global cache"""
        try:
            self.cached_sessions = json.dumps(sessions, ensure_ascii=False)
            self.last_scraped_at = datetime.utcnow()
            self.scrape_successful = True
            self.error_message = None
            self.session_key_used = session_key_type
            logger.info(f"Global cache updated with {len(sessions)} training sessions using {session_key_type} key")
        except Exception as e:
            logger.error(f"Error setting global cached sessions: {str(e)}", exc_info=True)
            raise
    
    def set_scrape_error(self, error_message, session_key_type='service'):
        """Set error state for failed global scrape"""
        try:
            self.last_scraped_at = datetime.utcnow()
            self.scrape_successful = False
            self.error_message = error_message
            self.session_key_used = session_key_type
            logger.warning(f"Global cache scrape failed using {session_key_type} key: {error_message}")
        except Exception as e:
            logger.error(f"Error setting global cache scrape error: {str(e)}", exc_info=True)
            raise
    
    def is_cache_stale(self, max_age_hours=1):
        """Check if global cache is stale and needs refresh"""
        if not self.last_scraped_at:
            return True
        
        threshold = datetime.utcnow() - timedelta(hours=max_age_hours)
        return self.last_scraped_at < threshold
    
    def filter_sessions_by_ratings(self, rating_patterns):
        """
        Filter sessions from global cache by specific rating patterns
        
        Args:
            rating_patterns: List of rating patterns to filter by
            
        Returns:
            Filtered list of sessions
        """
        if not self.cached_sessions or not self.scrape_successful:
            return []
        
        try:
            all_sessions = json.loads(self.cached_sessions)
            
            if not rating_patterns:
                return []
            
            # Filter sessions that match any of the rating patterns
            filtered_sessions = []
            for session in all_sessions:
                session_rating = session.get('rating_pattern', '')
                if session_rating and session_rating in rating_patterns:
                    filtered_sessions.append(session)
            
            logger.debug(f"Filtered {len(filtered_sessions)} sessions from {len(all_sessions)} total sessions")
            return filtered_sessions
            
        except (json.JSONDecodeError, TypeError) as e:
            logger.error(f"Error parsing global cached sessions for filtering: {e}")
            return []
    
    def __repr__(self):
        return f'<GlobalTrainingSessionCache ID={self.id} successful={self.scrape_successful} last_scraped={self.last_scraped_at}>'


class TrainingSessionNotificationLog(db.Model):
    """Log of sent notifications to prevent duplicates"""
    __tablename__ = 'training_session_notification_log'
    
    id = db.Column(db.Integer, primary_key=True)
    settings_id = db.Column(db.Integer, db.ForeignKey('training_session_settings.id'), nullable=False)
    
    # Session identification
    session_hash = db.Column(db.String(255), nullable=False)  # Hash of session details for deduplication
    student_name = db.Column(db.String(255))
    instructor_name = db.Column(db.String(255))
    module_name = db.Column(db.String(255))
    session_date = db.Column(db.String(50))
    session_time = db.Column(db.String(100))
    matching_rating = db.Column(db.String(50))  # Which rating pattern matched
    
    # Notification details
    notification_sent_at = db.Column(db.DateTime, default=datetime.utcnow)
    notification_type = db.Column(db.String(50), default='new_session')  # 'new_session', 'session_key_expired'
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<TrainingSessionNotificationLog ID={self.id} type={self.notification_type} rating={self.matching_rating}>'


# Available rating patterns (predefined list that admin can expand)
AVAILABLE_RATING_PATTERNS = [
    'S1-OAK',
    'S2-OAK',
    'S1-SFO',
    'S2-SFO',
]

def get_available_rating_patterns():
    """Get list of available rating patterns for users to select"""
    return AVAILABLE_RATING_PATTERNS.copy()


def create_training_tables():
    """Create training session monitoring tables including global cache"""
    try:
        db.create_all()
        logger.info("Training session monitoring database tables created successfully (including global cache)")
    except Exception as e:
        logger.error(f"Error creating training session monitoring tables: {e}")
        raise