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
