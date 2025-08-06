#!/usr/bin/env python3
"""
Test script for bulk notification functionality
"""

import sys
import os
import logging

# Add the project root to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.bulk_notification_service import BulkNotificationService

def test_bulk_notification_service():
    """Test the bulk notification service"""
    print("Testing Bulk Notification Service...")
    
    # Initialize the service
    bulk_service = BulkNotificationService()
    
    if not bulk_service.enabled:
        print("❌ Bulk notification service is not available")
        print("   This is expected if web modules are not available")
        return False
    
    print("✅ Bulk notification service initialized successfully")
    
    # Test getting notification users
    print("\nGetting users with valid Pushover settings...")
    users = bulk_service.get_notification_users()
    
    print(f"📊 Found {len(users)} users with valid Pushover settings")
    
    if users:
        print("\nUser details:")
        for i, user in enumerate(users, 1):
            print(f"  {i}. {user['user_email']} ({user['service_name']})")
            print(f"     API Token: {'✓' if user['pushover_api_token'] else '✗'}")
            print(f"     User Key: {'✓' if user['pushover_user_key'] else '✗'}")
        
        # Ask if user wants to send test notifications
        response = input(f"\nSend test notification to all {len(users)} users? (y/N): ")
        if response.lower() == 'y':
            print("\nSending test notifications...")
            result = bulk_service.test_bulk_notification()
            
            if result['success']:
                print(f"✅ Test completed successfully")
                print(f"   Sent: {result.get('sent_count', 0)} users")
                print(f"   Failed: {result.get('failed_count', 0)} users")
                
                if result.get('details'):
                    print("\nDetails:")
                    for detail in result['details']:
                        status = "✅" if detail['status'] == 'sent' else "❌"
                        print(f"   {status} {detail['user_email']}: {detail['message']}")
            else:
                print(f"❌ Test failed: {result.get('error', 'Unknown error')}")
        else:
            print("Test notifications skipped")
    else:
        print("No users found with valid Pushover settings")
    
    return True

if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s"
    )
    
    print("🔔 Bulk Notification Service Test")
    print("=" * 40)
    
    try:
        success = test_bulk_notification_service()
        if success:
            print("\n✅ Test completed successfully")
        else:
            print("\n❌ Test failed")
            sys.exit(1)
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        logging.exception("Test error")
        sys.exit(1)