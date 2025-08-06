#!/usr/bin/env python3
"""
Environment-specific configuration management for OAK Tower Watcher
Handles separation between development and production environments
"""

import os
import logging
from typing import Dict, Any


class EnvironmentConfig:
    """Environment-specific configuration handler"""
    
    def __init__(self):
        self.env = os.environ.get('APP_ENV', 'development').lower()
        self.flask_env = os.environ.get('FLASK_ENV', 'development').lower()
        
        # Use FLASK_ENV if APP_ENV is not set and FLASK_ENV is production
        if self.env == 'development' and self.flask_env == 'production':
            self.env = 'production'
    
    def is_production(self) -> bool:
        """Check if running in production environment"""
        return self.env == 'production'
    
    def is_development(self) -> bool:
        """Check if running in development environment"""
        return self.env == 'development'
    
    def get_database_config(self) -> Dict[str, Any]:
        """Get database configuration based on environment"""
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        if self.is_production():
            db_uri = os.environ.get('DATABASE_URL')

            # If using SQLite, ensure the path is absolute within the container.
            if db_uri and db_uri.startswith('sqlite:///'):
                path_part = db_uri.split('sqlite:///', 1)[1]
                if not os.path.isabs(path_part):
                    db_path = os.path.join(project_root, path_part)
                    db_uri = f'sqlite:///{db_path}'
            elif not db_uri:  # Default if DATABASE_URL is not set at all
                db_path = os.path.join(project_root, "web", "per_env", "prod", "data", "users.db")
                db_uri = f'sqlite:///{db_path}'

            return {
                'uri': db_uri,
                'track_modifications': False,
                'echo': False
            }
        else:
            default_db_uri = os.environ.get('DATABASE_URL')
            if not default_db_uri:
                # Use absolute path for SQLite in development
                default_db_uri = f'sqlite:///{os.path.join(project_root, "web", "per_env", "dev", "data", "users.db")}'
            
            return {
                'uri': default_db_uri,
                'track_modifications': True,  # Enable for development debugging
                'echo': os.environ.get('DEBUG', 'False').lower() == 'true'  # SQL query logging in debug mode
            }
    
    def get_log_config(self) -> Dict[str, Any]:
        """Get logging configuration based on environment"""
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        if self.is_production():
            return {
                'level': logging.INFO,
                'dir': os.path.join(project_root, 'web', 'per_env', 'prod', 'logs'),
                'filename': 'web_app.log',
                'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                'console_output': False,  # Disable console output in production
                'max_bytes': 10 * 1024 * 1024,  # 10MB
                'backup_count': 5
            }
        else:
            return {
                'level': logging.DEBUG if os.environ.get('DEBUG', 'False').lower() == 'true' else logging.INFO,
                'dir': os.path.join(project_root, 'web', 'per_env', 'dev', 'logs'),
                'filename': 'web_app.log',
                'format': '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
                'console_output': True,  # Enable console output in development
                'max_bytes': 5 * 1024 * 1024,  # 5MB
                'backup_count': 3
            }
    
    def get_flask_config(self) -> Dict[str, Any]:
        """Get Flask-specific configuration based on environment"""
        if self.is_production():
            return {
                'SECRET_KEY': os.environ.get('SECRET_KEY'),  # Must be set in production
                'DEBUG': False,
                'TESTING': False,
                'HOST': os.environ.get('HOST', '0.0.0.0'),
                'PORT': int(os.environ.get('PORT', 8080))
            }
        else:
            return {
                'SECRET_KEY': os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production'),
                'DEBUG': os.environ.get('DEBUG', 'True').lower() == 'true',
                'TESTING': False,
                'HOST': os.environ.get('HOST', '127.0.0.1'),
                'PORT': int(os.environ.get('PORT', 5000))
            }
    
    def validate_production_config(self) -> bool:
        """Validate that required production configuration is present"""
        if not self.is_production():
            return True
        
        required_vars = ['SECRET_KEY']
        missing_vars = []
        
        for var in required_vars:
            if not os.environ.get(var):
                missing_vars.append(var)
        
        if missing_vars:
            logging.error(f"Missing required production environment variables: {', '.join(missing_vars)}")
            return False
        
        # Check that SECRET_KEY is not the default development key
        secret_key = os.environ.get('SECRET_KEY', '')
        if 'dev-secret' in secret_key.lower():
            logging.error("Production SECRET_KEY appears to be a development key")
            return False
        
        return True
    
    def setup_directories(self):
        """Create necessary directories based on environment"""
        db_config = self.get_database_config()
        log_config = self.get_log_config()
        
        # Create database directory if using SQLite
        db_uri = db_config['uri']
        if db_uri.startswith('sqlite:///'):
            db_path = db_uri.replace('sqlite:///', '')
            absolute_db_path = os.path.abspath(db_path)
            logging.info(f"Database URI: {db_uri}")
            logging.info(f"Database absolute path: {absolute_db_path}")
            db_dir = os.path.dirname(db_path)
            if db_dir and not os.path.exists(db_dir):
                os.makedirs(db_dir, exist_ok=True)
                logging.info(f"Created database directory: {db_dir}")
        
        # Create log directory
        log_dir = log_config['dir']
        if not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)
            logging.info(f"Created log directory: {log_dir}")
    
    def get_environment_info(self) -> Dict[str, Any]:
        """Get information about the current environment"""
        return {
            'environment': self.env,
            'flask_env': self.flask_env,
            'is_production': self.is_production(),
            'is_development': self.is_development(),
            'database_uri': self.get_database_config()['uri'],
            'log_directory': self.get_log_config()['dir'],
            'debug_mode': self.get_flask_config()['DEBUG']
        }


# Global instance
env_config = EnvironmentConfig()