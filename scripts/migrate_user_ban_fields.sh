#!/bin/bash

# Database migration script to add user banning fields
# Adds: is_banned, banned_at, banned_reason columns to users table

set -e  # Exit on any error

echo "🔧 OAK Tower Watcher - User Ban Fields Migration"
echo "================================================"

# Get project root directory
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
echo "Project root: $PROJECT_ROOT"

# Database paths
DEV_DB_PATH="$PROJECT_ROOT/web/per_env/dev/data/users.db"
PROD_DB_PATH="$PROJECT_ROOT/web/per_env/prod/data/users.db"

# Function to check if column exists
column_exists() {
    local db_path="$1"
    local table_name="$2"
    local column_name="$3"
    
    if [ ! -f "$db_path" ]; then
        return 1
    fi
    
    sqlite3 "$db_path" "PRAGMA table_info($table_name);" | grep -q "$column_name"
}

# Function to backup database
backup_database() {
    local db_path="$1"
    local backup_path="${db_path}.backup.$(date +%Y%m%d_%H%M%S)"
    
    echo "  📁 Creating backup: $(basename "$backup_path")"
    cp "$db_path" "$backup_path"
    echo "  ✅ Backup created successfully"
}

# Function to migrate database
migrate_database() {
    local db_path="$1"
    local db_name="$2"
    
    echo ""
    echo "🗄️  Migrating $db_name database"
    echo "  Database: $db_path"
    
    if [ ! -f "$db_path" ]; then
        echo "  ⚠️  Database file not found. Skipping $db_name migration."
        return 0
    fi
    
    # Create backup
    backup_database "$db_path"
    
    # Check if columns already exist
    local needs_migration=false
    
    if ! column_exists "$db_path" "users" "is_banned"; then
        needs_migration=true
    fi
    
    if ! column_exists "$db_path" "users" "banned_at"; then
        needs_migration=true
    fi
    
    if ! column_exists "$db_path" "users" "banned_reason"; then
        needs_migration=true
    fi
    
    if [ "$needs_migration" = false ]; then
        echo "  ✅ All ban fields already exist. No migration needed."
        return 0
    fi
    
    echo "  🔄 Adding ban fields to users table..."
    
    # Add columns if they don't exist
    if ! column_exists "$db_path" "users" "is_banned"; then
        echo "  ➕ Adding is_banned column..."
        sqlite3 "$db_path" "ALTER TABLE users ADD COLUMN is_banned BOOLEAN DEFAULT 0;" || {
            echo "  ❌ Failed to add is_banned column"
            exit 1
        }
    else
        echo "  ✅ is_banned column already exists"
    fi
    
    if ! column_exists "$db_path" "users" "banned_at"; then
        echo "  ➕ Adding banned_at column..."
        sqlite3 "$db_path" "ALTER TABLE users ADD COLUMN banned_at DATETIME NULL;" || {
            echo "  ❌ Failed to add banned_at column"
            exit 1
        }
    else
        echo "  ✅ banned_at column already exists"
    fi
    
    if ! column_exists "$db_path" "users" "banned_reason"; then
        echo "  ➕ Adding banned_reason column..."
        sqlite3 "$db_path" "ALTER TABLE users ADD COLUMN banned_reason VARCHAR(500) NULL;" || {
            echo "  ❌ Failed to add banned_reason column"
            exit 1
        }
    else
        echo "  ✅ banned_reason column already exists"
    fi
    
    # Verify the migration
    echo "  🔍 Verifying migration..."
    if column_exists "$db_path" "users" "is_banned" && \
       column_exists "$db_path" "users" "banned_at" && \
       column_exists "$db_path" "users" "banned_reason"; then
        echo "  ✅ Migration completed successfully!"
    else
        echo "  ❌ Migration verification failed!"
        exit 1
    fi
    
    # Show updated table schema
    echo "  📋 Updated users table schema:"
    sqlite3 "$db_path" "PRAGMA table_info(users);" | while IFS='|' read -r cid name type notnull default_val pk; do
        if [[ "$name" == "is_banned" || "$name" == "banned_at" || "$name" == "banned_reason" ]]; then
            echo "    ✨ $name: $type (${notnull:+NOT NULL }${default_val:+DEFAULT $default_val})"
        fi
    done
}

# Function to show current table info
show_table_info() {
    local db_path="$1"
    local db_name="$2"
    
    if [ ! -f "$db_path" ]; then
        echo "  Database not found: $db_path"
        return
    fi
    
    echo ""
    echo "📊 Current $db_name database schema:"
    echo "  Users table columns:"
    sqlite3 "$db_path" "PRAGMA table_info(users);" | while IFS='|' read -r cid name type notnull default_val pk; do
        echo "    - $name: $type"
    done
}

# Main execution
main() {
    echo ""
    echo "🔍 Checking current database schemas..."
    
    # Show current schemas
    show_table_info "$DEV_DB_PATH" "Development"
    show_table_info "$PROD_DB_PATH" "Production"
    
    # Confirm migration
    echo ""
    echo "⚠️  This will modify your database files. Backups will be created automatically."
    read -p "Continue with migration? (y/N): " -n 1 -r
    echo
    
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Migration cancelled."
        exit 0
    fi
    
    echo ""
    echo "🚀 Starting migration process..."
    
    # Migrate development database
    migrate_database "$DEV_DB_PATH" "Development"
    
    # Migrate production database
    migrate_database "$PROD_DB_PATH" "Production"
    
    echo ""
    echo "🎉 Migration completed successfully!"
    echo ""
    echo "📋 Summary:"
    echo "  ✅ Added is_banned column (BOOLEAN, default: false)"
    echo "  ✅ Added banned_at column (DATETIME, nullable)"
    echo "  ✅ Added banned_reason column (VARCHAR(500), nullable)"
    echo ""
    echo "🛡️  Security Notes:"
    echo "  - Banned users cannot log in"
    echo "  - Banned emails cannot re-register"
    echo "  - Admin panel provides ban/unban functionality"
    echo ""
    echo "💡 Next steps:"
    echo "  1. Set ADMIN_USERNAME and ADMIN_PASSWORD environment variables"
    echo "  2. Access admin panel at /admin/login"
    echo "  3. Test user banning functionality"
}

# Check if sqlite3 is installed
if ! command -v sqlite3 &> /dev/null; then
    echo "❌ sqlite3 is required but not installed."
    echo "   Install with: sudo apt-get install sqlite3 (Ubuntu/Debian)"
    echo "   or: brew install sqlite (macOS)"
    exit 1
fi

# Run main function
main "$@"