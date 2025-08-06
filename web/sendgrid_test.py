#!/usr/bin/env python3
"""
SendGrid email test for OAK Tower Watcher
Tests SendGrid Web API functionality
"""

import os
import sys
import logging

# Add the project root to Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

def main():
    """Main test function for SendGrid"""
    print("🌐 SendGrid Email Test for VATSIM Facility Watcher")
    print("=" * 50)
    
    # Check if recipient email is provided as argument
    recipient_email = sys.argv[1] if len(sys.argv) > 1 else None
    if recipient_email:
        print(f"📬 Test recipient: {recipient_email}")
    else:
        print("📬 Test recipient: MAIL_DEFAULT_SENDER (default)")
    
    print()
    
    try:
        from web.backend.sendgrid_service import (
            test_sendgrid_config, 
            test_sendgrid_api, 
            send_sendgrid_test_email
        )
    except ImportError as e:
        logger.error(f"❌ Failed to import SendGrid service: {e}")
        logger.error("Make sure sendgrid package is installed: pip install sendgrid")
        return 1
    
    success_count = 0
    total_tests = 3
    
    # Test 1: Configuration
    config_ok, config = test_sendgrid_config()
    if config_ok:
        success_count += 1
    
    print()  # Blank line for readability
    
    # Test 2: API Connection (only if config is OK)
    api_ok = False
    if config_ok:
        api_ok = test_sendgrid_api()
        if api_ok:
            success_count += 1
    else:
        logger.warning("⚠️  Skipping API test due to configuration issues")
    
    print()  # Blank line for readability
    
    # Test 3: Send email (only if previous tests passed)
    if config_ok and api_ok:
        if send_sendgrid_test_email(recipient_email):
            success_count += 1
    else:
        logger.warning("⚠️  Skipping email send test due to configuration/API issues")
    
    print()
    print("=" * 50)
    print(f"📊 Test Results: {success_count}/{total_tests} tests passed")
    
    if success_count == total_tests:
        print("✅ All SendGrid tests passed! Email system is working correctly.")
        print("🎉 Verification emails will now be delivered via SendGrid!")
        return 0
    else:
        print("❌ Some tests failed. Check the logs above for details.")
        return 1

if __name__ == "__main__":
    if len(sys.argv) > 1:
        print(f"Usage: python {sys.argv[0]} [recipient_email]")
        print("If no recipient email is provided, will send to MAIL_DEFAULT_SENDER")
        print()
    
    exit_code = main()
    sys.exit(exit_code)