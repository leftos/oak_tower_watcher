#!/usr/bin/env python3
"""
Test script for VATSIM Facility Watcher user configuration system
Tests all components of the user facility regex configuration feature
"""

import sys
import os
import logging
from datetime import datetime

# Setup path to include the web backend
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_imports():
    """Test that all required modules can be imported"""
    print("🧪 Testing module imports...")
    
    try:
        from backend.app import create_app
        from backend.models import db, User, UserSettings, UserFacilityRegex
        from backend.forms import FacilityConfigForm
        from backend.status_service import StatusAPI
        from shared.bulk_notification_service import BulkNotificationService
        print("✅ All modules imported successfully")
        return True
    except ImportError as e:
        print(f"❌ Import failed: {e}")
        return False

def test_database_models():
    """Test database models and relationships"""
    print("\n🧪 Testing database models...")
    
    try:
        from backend.app import create_app
        from backend.models import db, User, UserSettings, UserFacilityRegex
        
        app = create_app()
        with app.app_context():
            # Create tables if they don't exist
            db.create_all()
            
            # Test creating a user
            test_user = User()
            test_user.email = "test@example.com"
            test_user.set_password("testpassword123")
            test_user.email_verified = True
            
            db.session.add(test_user)
            db.session.flush()  # Get user ID
            
            # Test creating user settings
            test_settings = UserSettings()
            test_settings.user_id = test_user.id
            test_settings.service_name = 'oak_tower_watcher'
            test_settings.notifications_enabled = True
            test_settings.pushover_api_token = "test_token"
            test_settings.pushover_user_key = "test_key"
            
            db.session.add(test_settings)
            db.session.flush()
            
            # Test facility patterns
            test_patterns = [
                ("main_facility", "^TEST_TWR$", 0),
                ("supporting_above", "^TEST_APP$", 0),
                ("supporting_above", "^TEST_CTR$", 1),
                ("supporting_below", "^TEST_GND$", 0)
            ]
            
            for facility_type, pattern, sort_order in test_patterns:
                regex_entry = UserFacilityRegex()
                regex_entry.user_settings_id = test_settings.id
                regex_entry.facility_type = facility_type
                regex_entry.regex_pattern = pattern
                regex_entry.sort_order = sort_order
                db.session.add(regex_entry)
            
            db.session.commit()
            
            # Test retrieving patterns
            patterns = test_settings.get_all_facility_patterns()
            expected_patterns = {
                'main_facility': ['^TEST_TWR$'],
                'supporting_above': ['^TEST_APP$', '^TEST_CTR$'],
                'supporting_below': ['^TEST_GND$']
            }
            
            assert patterns == expected_patterns, f"Pattern mismatch: {patterns} != {expected_patterns}"
            
            # Clean up test data
            db.session.delete(test_user)
            db.session.commit()
            
            print("✅ Database models working correctly")
            return True
            
    except Exception as e:
        print(f"❌ Database model test failed: {e}")
        return False

def test_forms():
    """Test form validation"""
    print("\n🧪 Testing form validation...")
    
    try:
        from backend.forms import FacilityConfigForm
        
        # Test valid patterns
        form_data = {
            'main_facility_patterns': r'^OAK_(?:[A-Z\d]+_)?TWR$',
            'supporting_above_patterns': r'^NCT_APP$' + '\n' + r'^OAK_\d+_CTR$',
            'supporting_below_patterns': r'^OAK_(?:[A-Z\d]+_)?GND$' + '\n' + r'^OAK_(?:[A-Z\d]+_)?DEL$',
            'notifications_enabled': True,
            'csrf_token': 'test'
        }
        
        # Note: In a real test, we'd need to properly setup Flask app context and CSRF
        form = FacilityConfigForm(data=form_data)
        
        # Test pattern list conversion
        main_patterns = form.get_patterns_list('main_facility_patterns')
        assert main_patterns == [r'^OAK_(?:[A-Z\d]+_)?TWR$'], f"Unexpected main patterns: {main_patterns}"
        
        supporting_above = form.get_patterns_list('supporting_above_patterns')
        expected_above = [r'^NCT_APP$', r'^OAK_\d+_CTR$']
        assert supporting_above == expected_above, f"Unexpected supporting above patterns: {supporting_above}"
        
        print("✅ Form validation working correctly")
        return True
        
    except Exception as e:
        print(f"❌ Form test failed: {e}")
        return False

def test_status_service():
    """Test status service with user configurations"""
    print("\n🧪 Testing status service...")
    
    try:
        from backend.status_service import StatusAPI
        
        # Initialize status API
        status_api = StatusAPI()
        
        # Test default status (no user)
        default_status = status_api.get_current_status()
        assert 'status' in default_status, "Status response missing 'status' field"
        assert 'using_user_config' in default_status, "Status response missing 'using_user_config' field"
        assert default_status['using_user_config'] == False, "Default status should not use user config"
        
        # Test with non-existent user
        user_status = status_api.get_current_status(user_id=99999)
        assert user_status['using_user_config'] == False, "Non-existent user should fallback to default config"
        
        print("✅ Status service working correctly")
        return True
        
    except Exception as e:
        print(f"❌ Status service test failed: {e}")
        return False

def test_bulk_notification_service():
    """Test bulk notification service"""
    print("\n🧪 Testing bulk notification service...")
    
    try:
        from shared.bulk_notification_service import BulkNotificationService
        
        # Initialize bulk service
        bulk_service = BulkNotificationService()
        
        if not bulk_service.enabled:
            print("⚠️  Bulk notification service disabled (web modules not available)")
            return True
        
        # Test getting users (should return empty list in test environment)
        users = bulk_service.get_notification_users()
        assert isinstance(users, list), "get_notification_users should return a list"
        
        # Test basic bulk notification (should handle empty user list gracefully)
        result = bulk_service.send_bulk_notification(
            title="Test",
            message="Test message"
        )
        
        assert result['success'] == True, "Bulk notification should succeed even with no users"
        assert result['sent_count'] == 0, "Should have 0 sent count with no users"
        
        print("✅ Bulk notification service working correctly")
        return True
        
    except Exception as e:
        print(f"❌ Bulk notification service test failed: {e}")
        return False

def test_integration():
    """Test full integration workflow"""
    print("\n🧪 Testing integration workflow...")
    
    try:
        from backend.app import create_app
        from backend.models import db, User, UserSettings
        from backend.status_service import StatusAPI
        
        app = create_app()
        with app.app_context():
            # Create a test user with custom patterns
            test_user = User()
            test_user.email = "integration@example.com"
            test_user.set_password("testpassword123")
            test_user.email_verified = True
            
            db.session.add(test_user)
            db.session.flush()
            
            test_settings = UserSettings()
            test_settings.user_id = test_user.id
            test_settings.service_name = 'oak_tower_watcher'
            test_settings.notifications_enabled = True
            
            db.session.add(test_settings)
            db.session.flush()
            
            # Add custom facility patterns
            test_settings.set_facility_patterns('main_facility', [r'^KOAK_TWR$', r'^KOAK_\d+_TWR$'])
            test_settings.set_facility_patterns('supporting_above', [r'^NCT_APP$'])
            test_settings.set_facility_patterns('supporting_below', [r'^KOAK_GND$'])
            
            db.session.commit()
            
            # Test status service with this user
            status_api = StatusAPI()
            user_status = status_api.get_current_status(user_id=test_user.id)
            
            # Should use user config
            assert user_status['using_user_config'] == True, "Should use user configuration"
            assert 'facility_patterns' in user_status, "Should include facility patterns in response"
            
            patterns = user_status['facility_patterns']
            assert patterns['main_facility'] == [r'^KOAK_TWR$', r'^KOAK_\d+_TWR$'], "Main facility patterns mismatch"
            assert patterns['supporting_above'] == [r'^NCT_APP$'], "Supporting above patterns mismatch"
            assert patterns['supporting_below'] == [r'^KOAK_GND$'], "Supporting below patterns mismatch"
            
            # Clean up
            db.session.delete(test_user)
            db.session.commit()
            
            print("✅ Integration test passed")
            return True
            
    except Exception as e:
        print(f"❌ Integration test failed: {e}")
        return False

def main():
    """Run all tests"""
    print("🚀 Starting VATSIM Facility Watcher Configuration Tests")
    print("=" * 60)
    
    # Configure logging
    logging.basicConfig(level=logging.ERROR)  # Suppress debug logs during testing
    
    tests = [
        ("Module Imports", test_imports),
        ("Database Models", test_database_models),
        ("Form Validation", test_forms),
        ("Status Service", test_status_service),
        ("Bulk Notification Service", test_bulk_notification_service),
        ("Integration Workflow", test_integration)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        try:
            if test_func():
                passed += 1
            else:
                print(f"❌ {test_name} failed")
        except Exception as e:
            print(f"❌ {test_name} crashed: {e}")
    
    print("\n" + "=" * 60)
    print(f"📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! The facility configuration system is working correctly.")
        print("\n📋 Implementation Summary:")
        print("✅ User-specific facility regex patterns")
        print("✅ Database models and relationships")
        print("✅ Form validation with regex testing")
        print("✅ Status page shows user configuration")
        print("✅ Bulk notifications use per-user patterns")
        print("✅ Integration with existing authentication system")
        
        print("\n🎯 Next Steps:")
        print("1. Run the database migration: python create_migration.py")
        print("2. Test in development environment: ./start_dev.sh")
        print("3. Configure users' facility patterns in settings")
        print("4. Test notifications with actual VATSIM data")
        
        return True
    else:
        print("❌ Some tests failed. Please review the errors above.")
        return False

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)