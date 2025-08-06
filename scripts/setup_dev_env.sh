#!/bin/bash
# Development Environment Setup Script for OAK Tower Watcher
# This script sets up the development environment with proper separation from production

set -e  # Exit on any error

echo "🚀 Setting up OAK Tower Watcher Development Environment..."

# Get the project root directory
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

echo "📁 Project root: $PROJECT_ROOT"

# Create development directories
echo "📂 Creating development directories..."
mkdir -p dev_logs
mkdir -p dev_data

# Set development environment variables
echo "🔧 Setting up development environment variables..."

# Create or update .env.development file
cat > .env.development << EOF
# Development Environment Configuration
APP_ENV=development
FLASK_ENV=development
DEBUG=true

# Development Database (SQLite) - using absolute path
DATABASE_URL=sqlite:///$PROJECT_ROOT/dev_data/users_dev.db

# Development Secret Key (DO NOT use in production)
SECRET_KEY=dev-secret-key-change-in-production-$(date +%s)

# Development Server Configuration
HOST=127.0.0.1
PORT=5000

# Email Configuration (optional for development)
# MAIL_SERVER=localhost
# MAIL_PORT=1025
# MAIL_USE_TLS=false
# MAIL_USE_SSL=false
# MAIL_USERNAME=
# MAIL_PASSWORD=

# Development Pushover (optional)
# PUSHOVER_API_TOKEN=
# PUSHOVER_USER_KEY=
EOF

echo "✅ Created .env.development file"

# Create development run script
cat > scripts/run_dev.sh << 'EOF'
#!/bin/bash
# Development run script with environment separation

# Get the project root directory
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

echo "🔧 Loading development environment..."

# Load development environment variables
if [ -f .env.development ]; then
    export $(grep -v '^#' .env.development | xargs)
    echo "✅ Loaded development environment variables"
else
    echo "❌ .env.development file not found. Run scripts/setup_dev_env.sh first."
    exit 1
fi

echo "🌍 Environment: $APP_ENV"
echo "🗄️  Database: $DATABASE_URL"
echo "📝 Logs: dev_logs/"
echo "🖥️  Server: http://$HOST:$PORT"
echo ""

# Check if virtual environment exists
if [ ! -d "web_env" ]; then
    echo "⚠️  Virtual environment not found. Creating one..."
    python3 -m venv web_env
    echo "✅ Created virtual environment"
fi

# Activate virtual environment
echo "🔄 Activating virtual environment..."
source web_env/bin/activate

# Install/upgrade dependencies
echo "📦 Installing/updating dependencies..."
pip install -r requirements_web.txt

echo ""
echo "🚀 Starting development server..."
echo "   Access the application at: http://$HOST:$PORT"
echo "   Press Ctrl+C to stop the server"
echo ""

# Run the development server
python web/run_app.py
EOF

chmod +x scripts/run_dev.sh
echo "✅ Created development run script: scripts/run_dev.sh"

# Create development testing script
cat > scripts/test_dev_setup.py << 'EOF'
#!/usr/bin/env python3
"""
Test script to verify development environment setup
"""

import os
import sys
import sqlite3
from pathlib import Path

def test_directories():
    """Test that development directories exist"""
    print("🧪 Testing directory structure...")
    
    required_dirs = ['dev_logs', 'dev_data']
    for dir_name in required_dirs:
        if os.path.exists(dir_name):
            print(f"  ✅ {dir_name}/ exists")
        else:
            print(f"  ❌ {dir_name}/ missing")
            return False
    return True

def test_env_file():
    """Test that .env.development file exists and has required variables"""
    print("🧪 Testing environment configuration...")
    
    env_file = '.env.development'
    if not os.path.exists(env_file):
        print(f"  ❌ {env_file} missing")
        return False
    
    print(f"  ✅ {env_file} exists")
    
    required_vars = ['APP_ENV', 'DATABASE_URL', 'SECRET_KEY']
    with open(env_file, 'r') as f:
        content = f.read()
        
    for var in required_vars:
        if f"{var}=" in content:
            print(f"  ✅ {var} configured")
        else:
            print(f"  ❌ {var} missing")
            return False
    
    return True

def test_database_path():
    """Test database path configuration"""
    print("🧪 Testing database configuration...")
    
    # Load environment variables from .env.development
    env_vars = {}
    if os.path.exists('.env.development'):
        with open('.env.development', 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    env_vars[key] = value
    
    db_url = env_vars.get('DATABASE_URL', '')
    if 'dev_data' in db_url:
        print(f"  ✅ Database configured for development: {db_url}")
        return True
    else:
        print(f"  ❌ Database not configured for development: {db_url}")
        return False

def test_import():
    """Test that the application can be imported"""
    print("🧪 Testing application import...")
    
    try:
        # Add project root to path
        project_root = os.path.dirname(os.path.abspath(__file__))
        sys.path.insert(0, project_root)
        
        # Set development environment
        os.environ['APP_ENV'] = 'development'
        os.environ['DATABASE_URL'] = 'sqlite:///dev_data/test.db'
        os.environ['SECRET_KEY'] = 'test-key'
        
        from config.env_config import env_config
        
        if env_config.is_development():
            print("  ✅ Environment configuration working")
            print(f"  ✅ Environment: {env_config.env}")
            return True
        else:
            print("  ❌ Environment not detected as development")
            return False
            
    except ImportError as e:
        print(f"  ❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False

def main():
    """Run all tests"""
    print("🔍 Testing OAK Tower Watcher Development Environment Setup")
    print("=" * 60)
    
    tests = [
        test_directories,
        test_env_file,
        test_database_path,
        test_import
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        try:
            if test():
                passed += 1
            print()  # Empty line between tests
        except Exception as e:
            print(f"  ❌ Test failed with exception: {e}")
            print()
    
    print("=" * 60)
    print(f"📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Development environment is ready.")
        print("\n🚀 To start development:")
        print("   ./scripts/run_dev.sh")
        return True
    else:
        print("❌ Some tests failed. Please check the setup.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
EOF

chmod +x scripts/test_dev_setup.py
echo "✅ Created development test script: scripts/test_dev_setup.py"

# Update .gitignore to exclude development files
echo "📝 Updating .gitignore for development files..."

# Check if .gitignore exists and add development-specific entries
if [ -f .gitignore ]; then
    # Add development-specific ignores if not already present
    if ! grep -q "dev_logs/" .gitignore; then
        echo "" >> .gitignore
        echo "# Development environment" >> .gitignore
        echo "dev_logs/" >> .gitignore
        echo "dev_data/" >> .gitignore
        echo ".env.development" >> .gitignore
        echo "*.dev.db" >> .gitignore
        echo "✅ Updated .gitignore with development entries"
    else
        echo "✅ .gitignore already contains development entries"
    fi
else
    echo "⚠️  .gitignore not found, creating one..."
    cat > .gitignore << EOF
# Development environment
dev_logs/
dev_data/
.env.development
*.dev.db

# Production environment
logs/
prod_data/
.env.prod

# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# Virtual environments
web_env/
venv/
env/

# IDE
.vscode/
.idea/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db
EOF
    echo "✅ Created .gitignore"
fi

echo ""
echo "🎉 Development environment setup complete!"
echo ""
echo "📋 Summary:"
echo "   • Created dev_logs/ directory for development logs"
echo "   • Created dev_data/ directory for development database"
echo "   • Created .env.development with development configuration"
echo "   • Created scripts/run_dev.sh for easy development server startup"
echo "   • Created scripts/test_dev_setup.py for testing the setup"
echo "   • Updated .gitignore to exclude development files"
echo ""
echo "🧪 Test the setup:"
echo "   python scripts/test_dev_setup.py"
echo ""
echo "🚀 Start development server:"
echo "   ./scripts/run_dev.sh"
echo ""
echo "📚 Development vs Production:"
echo "   Development: Uses dev_logs/, dev_data/, localhost:5000"
echo "   Production:  Uses logs/, prod_data/, Docker containers"