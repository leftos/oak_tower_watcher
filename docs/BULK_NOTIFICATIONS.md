# Bulk Notifications Feature

This document describes the bulk notification functionality that allows the system to automatically send state update notifications to all users in the database with valid Pushover tokens and notifications enabled.

## Overview

The bulk notification system extends the existing single-user Pushover notification functionality to support sending notifications to multiple users stored in the database. When a status change occurs (e.g., controller comes online/offline), the system will now:

1. Send notifications using the legacy single-user configuration (if configured)
2. Send notifications to ALL users in the database who have valid Pushover settings and notifications enabled

## Architecture

### Components

1. **BulkNotificationService** (`src/bulk_notification_service.py`)
   - Queries the database for users with valid Pushover credentials
   - Sends notifications to multiple users
   - Handles errors and provides detailed results

2. **Enhanced NotificationManager** (`src/notification_manager.py`)
   - Integrates bulk notification service
   - Sends to both legacy and database users automatically

3. **Web API Endpoints** (`web/backend/api.py`)
   - `/api/test-bulk-pushover` - Test bulk notifications
   - `/api/bulk-notification-stats` - Get statistics about notification-enabled users

4. **Dashboard UI** (`web/templates/auth/dashboard.html`)
   - Bulk notification testing interface
   - User statistics display

## Database Schema

The system uses the existing `UserSettings` table to store per-user Pushover credentials:

```sql
CREATE TABLE user_settings (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL,
    service_name VARCHAR(50) NOT NULL,
    pushover_api_token VARCHAR(255),
    pushover_user_key VARCHAR(255),
    notifications_enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users (id),
    UNIQUE (user_id, service_name)
);
```

## Usage

### Automatic Notifications

Once implemented, bulk notifications work automatically. When the VATSIM monitor detects a status change, it will:

1. Send notification via legacy Pushover service (if configured)
2. Query database for all users with `notifications_enabled=true` and valid `pushover_api_token` and `pushover_user_key`
3. Send individual notifications to each user using their personal Pushover credentials

### Manual Testing

#### Web Dashboard (Admin Only)
**Note**: The bulk notification testing UI has been hidden from regular users to prevent abuse. It will be available in a future admin dashboard.

For now, bulk notifications can be tested via:

#### API Testing
```bash
# Get bulk notification statistics
curl -X GET http://localhost:5000/api/bulk-notification-stats \
  -H "Cookie: session=your_session_cookie"

# Send test bulk notification
curl -X POST http://localhost:5000/api/test-bulk-pushover \
  -H "Content-Type: application/json" \
  -H "Cookie: session=your_session_cookie"
```

#### Command Line Testing
```bash
python test_bulk_notifications.py
```

## Configuration Requirements

### For Database Users
Each user must have configured in their dashboard:
- Valid Pushover API Token
- Valid Pushover User Key  
- Notifications enabled

### For Legacy Single-User Mode
The system still supports the original single-user configuration in `config.json`:

```json
{
  "pushover": {
    "enabled": true,
    "api_token": "your_api_token",
    "user_key": "your_user_key"
  }
}
```

## Monitoring and Logging

The system provides detailed logging for bulk notifications:

```
INFO - Bulk notification service initialized in NotificationManager
INFO - Found 5 users with valid Pushover settings
INFO - Bulk Pushover notifications sent to 4 users: KOAK Main Facility Online!
WARNING - Failed to send bulk notifications to 1 users
```

### Error Handling

The system gracefully handles various error conditions:
- Database connection issues
- Invalid Pushover credentials for individual users
- Network timeouts
- Malformed API responses

Failed notifications to individual users don't prevent notifications to other users.

## Performance Considerations

- Bulk notifications are sent sequentially to avoid rate limiting
- The system caches database queries where possible
- Failed notifications are logged but don't block other notifications
- The web interface provides real-time feedback during bulk operations

## Security

- User credentials are never logged or exposed
- Each user's Pushover credentials are used only for their own notifications
- API endpoints require authentication
- User statistics are anonymized in API responses

## Backwards Compatibility

The bulk notification system is fully backwards compatible:
- Existing single-user configurations continue to work
- Desktop applications (GUI and headless) work without modification
- No database schema changes required (uses existing tables)

## Testing

Run the test script to verify bulk notification functionality:

```bash
python test_bulk_notifications.py
```

This will:
1. Check if the bulk notification service is available
2. Query for users with valid Pushover settings
3. Optionally send test notifications to all users
4. Display detailed results

## Troubleshooting

### Common Issues

1. **"Bulk notification service not available"**
   - Web modules are not available in the current environment
   - Database connection failed
   - Flask application context not available

2. **"No users found with valid Pushover settings"**
   - No users have configured both API token and user key
   - All users have notifications disabled
   - Database query failed

3. **High failure rate in bulk notifications**
   - Users have invalid Pushover credentials
   - Pushover API rate limiting
   - Network connectivity issues

### Debug Mode

Enable debug logging to see detailed information:

```python
import logging
logging.getLogger().setLevel(logging.DEBUG)
```

This will show:
- Database queries being executed
- Individual notification attempts
- Detailed error messages
- API response details