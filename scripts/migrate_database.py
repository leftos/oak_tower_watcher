#!/usr/bin/env python3
"""
Database Migration System for OAK Tower Watcher
Handles versioned database schema upgrades across dev and prod environments
"""

import os
import sys
import sqlite3
import logging
import argparse
from datetime import datetime
from typing import List, Tuple, Optional

# Add project root to path for imports
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

class DatabaseMigrator:
    """Database migration manager with versioning support"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.current_version = 0
        logger.info(f"Initialized migrator for database: {db_path}")
    
    def ensure_schema_version_table(self):
        """Ensure the schema_version table exists"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Create schema_version table if it doesn't exist
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS schema_version (
                        id INTEGER PRIMARY KEY,
                        version INTEGER NOT NULL UNIQUE,
                        description TEXT NOT NULL,
                        applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        applied_by TEXT DEFAULT 'migration_script'
                    )
                """)
                
                # If no version exists, assume we're starting from version 0
                cursor.execute("SELECT MAX(version) FROM schema_version")
                result = cursor.fetchone()
                self.current_version = result[0] if result[0] is not None else 0
                
                conn.commit()
                logger.info(f"Current database schema version: {self.current_version}")
                
        except Exception as e:
            logger.error(f"Error ensuring schema version table: {e}")
            raise
    
    def get_current_version(self) -> int:
        """Get the current database schema version"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT MAX(version) FROM schema_version")
                result = cursor.fetchone()
                return result[0] if result[0] is not None else 0
        except sqlite3.OperationalError:
            # schema_version table doesn't exist yet
            return 0
        except Exception as e:
            logger.error(f"Error getting current version: {e}")
            return 0
    
    def record_migration(self, version: int, description: str):
        """Record a completed migration"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO schema_version (version, description, applied_at)
                    VALUES (?, ?, ?)
                """, (version, description, datetime.now().isoformat()))
                conn.commit()
                logger.info(f"Recorded migration to version {version}: {description}")
        except Exception as e:
            logger.error(f"Error recording migration: {e}")
            raise
    
    def run_migration(self, version: int, description: str, sql_commands: List[str]) -> bool:
        """Run a specific migration"""
        try:
            logger.info(f"Running migration to version {version}: {description}")
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Execute all commands in the migration
                for i, command in enumerate(sql_commands):
                    try:
                        logger.debug(f"Executing command {i+1}/{len(sql_commands)}: {command[:100]}...")
                        cursor.execute(command)
                    except Exception as cmd_error:
                        logger.error(f"Error in command {i+1}: {cmd_error}")
                        raise
                
                conn.commit()
            
            # Record the successful migration
            self.record_migration(version, description)
            self.current_version = version
            
            logger.info(f"Successfully completed migration to version {version}")
            return True
            
        except Exception as e:
            logger.error(f"Migration to version {version} failed: {e}")
            return False
    
    def get_available_migrations(self) -> List[Tuple[int, str, List[str]]]:
        """Get all available migrations"""
        migrations = []
        
        # Migration 1: Move pushover settings to users table
        if self.current_version < 1:
            migrations.append((
                1,
                "Move Pushover settings from user_settings to users table",
                [
                    # Add pushover columns to users table
                    "ALTER TABLE users ADD COLUMN pushover_api_token VARCHAR(255)",
                    "ALTER TABLE users ADD COLUMN pushover_user_key VARCHAR(255)",
                    
                    # Migrate existing data
                    """UPDATE users 
                       SET pushover_api_token = (
                           SELECT pushover_api_token 
                           FROM user_settings 
                           WHERE user_settings.user_id = users.id 
                           AND service_name = 'oak_tower_watcher'
                           AND pushover_api_token IS NOT NULL
                           LIMIT 1
                       )""",
                    
                    """UPDATE users 
                       SET pushover_user_key = (
                           SELECT pushover_user_key 
                           FROM user_settings 
                           WHERE user_settings.user_id = users.id 
                           AND service_name = 'oak_tower_watcher'
                           AND pushover_user_key IS NOT NULL
                           LIMIT 1
                       )""",
                    
                    # Create a backup table for the old data
                    """CREATE TABLE user_settings_backup_v1 AS 
                       SELECT * FROM user_settings""",
                    
                    # Remove pushover columns from user_settings (SQLite doesn't support DROP COLUMN directly)
                    # We'll create a new table and copy data
                    """CREATE TABLE user_settings_new (
                        id INTEGER PRIMARY KEY,
                        user_id INTEGER NOT NULL REFERENCES users(id),
                        service_name VARCHAR(50) NOT NULL,
                        notifications_enabled BOOLEAN DEFAULT 1,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )""",
                    
                    """INSERT INTO user_settings_new 
                       (id, user_id, service_name, notifications_enabled, created_at, updated_at)
                       SELECT id, user_id, service_name, notifications_enabled, created_at, updated_at
                       FROM user_settings""",
                    
                    "DROP TABLE user_settings",
                    "ALTER TABLE user_settings_new RENAME TO user_settings",
                    
                    # Recreate the unique constraint
                    "CREATE UNIQUE INDEX unique_user_service ON user_settings(user_id, service_name)"
                ]
            ))
        
        # Migration 2: Add user_app_access table for sub-app permissions
        if self.current_version < 2:
            migrations.append((
                2,
                "Add user_app_access table for sub-application access control",
                [
                    # Create user_app_access table
                    """CREATE TABLE IF NOT EXISTS user_app_access (
                        id INTEGER PRIMARY KEY,
                        user_id INTEGER NOT NULL REFERENCES users(id),
                        app_name VARCHAR(50) NOT NULL,
                        has_access BOOLEAN DEFAULT 0,
                        granted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        granted_by_admin VARCHAR(120),
                        revoked_at TIMESTAMP,
                        revoked_by_admin VARCHAR(120),
                        UNIQUE(user_id, app_name)
                    )""",
                    
                    # Create index for better performance
                    "CREATE INDEX IF NOT EXISTS idx_user_app_access_user_id ON user_app_access(user_id)",
                    "CREATE INDEX IF NOT EXISTS idx_user_app_access_app_name ON user_app_access(app_name)",
                    
                    # Grant default access to facility_watcher for existing users
                    """INSERT OR IGNORE INTO user_app_access (user_id, app_name, has_access, granted_at, granted_by_admin)
                       SELECT id, 'facility_watcher', 1, CURRENT_TIMESTAMP, 'migration_default'
                       FROM users
                       WHERE is_active = 1 AND email_verified = 1""",
                    
                    # Set default no access to training_monitor for existing users (explicit record)
                    """INSERT OR IGNORE INTO user_app_access (user_id, app_name, has_access, granted_at, granted_by_admin)
                       SELECT id, 'training_monitor', 0, CURRENT_TIMESTAMP, 'migration_default'
                       FROM users
                       WHERE is_active = 1 AND email_verified = 1"""
                ]
            ))
        
        return migrations
    
    def migrate_to_version(self, target_version: int) -> bool:
        """Migrate to a specific version"""
        self.ensure_schema_version_table()
        current = self.get_current_version()
        
        if current >= target_version:
            logger.info(f"Database already at version {current}, target is {target_version}")
            return True
        
        migrations = self.get_available_migrations()
        
        # Run migrations in sequence up to target version
        success = True
        for version, description, commands in migrations:
            if version <= target_version and version > current:
                if not self.run_migration(version, description, commands):
                    success = False
                    break
        
        return success
    
    def migrate_to_latest(self) -> bool:
        """Migrate to the latest available version"""
        self.ensure_schema_version_table()
        migrations = self.get_available_migrations()
        
        if not migrations:
            logger.info("No migrations available")
            return True
        
        latest_version = max(m[0] for m in migrations)
        return self.migrate_to_version(latest_version)
    
    def show_status(self):
        """Show current migration status"""
        self.ensure_schema_version_table()
        current = self.get_current_version()
        migrations = self.get_available_migrations()
        
        print(f"\nDatabase: {self.db_path}")
        print(f"Current schema version: {current}")
        
        if migrations:
            latest = max(m[0] for m in migrations)
            print(f"Latest available version: {latest}")
            
            if current < latest:
                print(f"\nPending migrations:")
                for version, description, _ in migrations:
                    if version > current:
                        print(f"  Version {version}: {description}")
            else:
                print("Database is up to date!")
        else:
            print("No migrations available")
        
        # Show applied migrations
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT version, description, applied_at, applied_by 
                    FROM schema_version 
                    ORDER BY version
                """)
                results = cursor.fetchall()
                
                if results:
                    print(f"\nApplied migrations:")
                    for version, desc, applied_at, applied_by in results:
                        print(f"  Version {version}: {desc} (applied {applied_at} by {applied_by})")
                        
        except sqlite3.OperationalError:
            pass  # Table doesn't exist yet


def find_database_files() -> List[str]:
    """Find all database files that need migration"""
    db_files = []
    
    # Common database locations
    possible_paths = [
        "web/oak_tower_watcher.db",
        "web/oak_tower_watcher_dev.db",
        "web/oak_tower_watcher_prod.db",
        "/app/oak_tower_watcher.db",
        "/app/data/oak_tower_watcher.db",
        # Development environment paths
        "web/per_env/dev/data/users.db",
        "/app/web/per_env/dev/data/users.db",
        # Production environment paths
        "web/per_env/prod/data/users.db",
        "/app/web/per_env/prod/data/users.db"
    ]
    
    for path in possible_paths:
        full_path = os.path.join(project_root, path) if not path.startswith('/') else path
        if os.path.exists(full_path):
            db_files.append(full_path)
    
    return db_files


def main():
    parser = argparse.ArgumentParser(description='Database Migration Tool')
    parser.add_argument('--db', type=str, help='Database file path')
    parser.add_argument('--version', type=int, help='Target version to migrate to')
    parser.add_argument('--latest', action='store_true', help='Migrate to latest version')
    parser.add_argument('--status', action='store_true', help='Show migration status')
    parser.add_argument('--all', action='store_true', help='Migrate all found database files')
    
    args = parser.parse_args()
    
    # Determine which databases to process
    db_files = []
    if args.db:
        # For explicit database path, create it if it doesn't exist
        db_path = args.db
        # Ensure the directory exists
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        db_files.append(db_path)
        if not os.path.exists(db_path):
            logger.info(f"Database file will be created: {db_path}")
    elif args.all:
        db_files = find_database_files()
        if not db_files:
            logger.error("No database files found")
            return 1
    else:
        # Default behavior: find and process all databases
        db_files = find_database_files()
        if not db_files:
            logger.error("No database files found. Use --db to specify a database file.")
            return 1
    
    # Process each database
    success = True
    for db_path in db_files:
        logger.info(f"\n{'='*60}")
        logger.info(f"Processing database: {db_path}")
        logger.info(f"{'='*60}")
        
        migrator = DatabaseMigrator(db_path)
        
        if args.status:
            migrator.show_status()
        elif args.version:
            if not migrator.migrate_to_version(args.version):
                success = False
        elif args.latest:
            if not migrator.migrate_to_latest():
                success = False
        else:
            # Default: migrate to latest
            if not migrator.migrate_to_latest():
                success = False
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())