# VATSIM Facility Watcher - User Configuration Deployment Guide

This guide provides instructions for deploying and verifying the user facility configuration feature.

## 🚀 Deployment Steps

### 1. Database Migration

First, run the database migration to create the new `user_facility_regexes` table:

```bash
# Simple migration (recommended)
dotenv run -- python create_migration_simple.py
```

### 2. Restart the Web Application

Restart your web application to load the new models and functionality:

```bash
# If using Docker Compose - use the actual container name
docker restart vatsim-web-api

# If using systemd service
sudo systemctl restart your-web-service
```

## 🧪 Testing the Implementation

### Running Tests in Docker Container

The comprehensive test suite should be run within the Docker container to ensure all dependencies are available:

```bash
# Check running containers first
docker ps

# Enter the web API container (use actual container name)
docker exec -it vatsim-web-api bash

# Run the database migration first
python create_migration_simple.py

# Run the test suite
python test_facility_config.py
```

### Manual Testing Steps

1. **User Registration & Login**
   - Register a new user account
   - Verify email and log in

2. **Configure Facility Patterns**
   - Navigate to Dashboard → "Configure Settings"
   - Set custom facility regex patterns:
     - Main Facility: `^YOUR_AIRPORT_TWR$`
     - Supporting Above: `^YOUR_APP$`
     - Supporting Below: `^YOUR_AIRPORT_GND$`
   - Test patterns using the regex101.com link
   - Save configuration

3. **Verify Status Page**
   - Visit `/oak-tower-status.html` while logged in
   - Confirm "Personal Configuration Active" badge appears
   - Check pattern counts match your configuration

4. **Test API Endpoints**
   ```bash
   # Test status with user config
   curl -H "Cookie: session=YOUR_SESSION" http://localhost:8080/api/status
   
   # Test personalized notifications (if configured)
   curl -X POST -H "Cookie: session=YOUR_SESSION" \
        http://localhost:8080/api/test-personalized-bulk-notification
   ```

## ✅ Verification Checklist

### Database Verification
- [ ] `user_facility_regexes` table exists
- [ ] Table has correct columns: id, user_settings_id, facility_type, regex_pattern, sort_order, created_at
- [ ] Foreign key relationship to user_settings works

### Frontend Verification  
- [ ] Settings page shows facility configuration section
- [ ] Regex patterns can be saved and loaded
- [ ] Form validation works for invalid regex patterns
- [ ] regex101.com link opens correctly
- [ ] Examples and help text are displayed

### Backend Verification
- [ ] User facility patterns are stored correctly
- [ ] Status API returns user-specific configurations when authenticated
- [ ] Default patterns used when user has no custom config
- [ ] Bulk notifications use per-user patterns

### Integration Verification
- [ ] Status page shows personal configuration badge when using custom patterns
- [ ] Pattern counts display correctly
- [ ] Settings link works from status page
- [ ] Notifications sent based on individual user configurations

## 🔧 Troubleshooting

### Common Issues

**Import Errors When Running Tests**
- Solution: Run tests within Docker container where dependencies are installed

**Database Permission Errors**
- Solution: Use `create_migration_simple.py` instead of `create_migration.py`
- Ensure proper file permissions on database directory

**Status Page Not Showing User Config**
- Check: User is logged in and has saved custom patterns
- Verify: API endpoint returns `"using_user_config": true`

**Form Validation Errors**
- Check: Regex patterns are valid
- Test: Use regex101.com to validate patterns before saving

### Debug Commands

```bash
# Check database schema
sqlite3 /path/to/users.db ".schema user_facility_regexes"

# Verify user patterns
sqlite3 /path/to/users.db "SELECT * FROM user_facility_regexes;"

# Test API endpoint
curl -v http://localhost:8080/api/status
```

## 📋 Default Patterns

If users don't configure custom patterns, the system uses these Oakland Tower defaults:

```json
{
  "main_facility": ["^OAK_(?:\\d+_)?TWR$"],
  "supporting_above": ["^NCT_APP$", "^OAK_\\d+_CTR$"],
  "supporting_below": ["^OAK_(?:\\d+_)?GND$", "^OAK_(?:\\d+_)?DEL$"]
}
```

## 🎯 Feature Summary

- ✅ User-specific facility regex patterns
- ✅ Database models with proper relationships  
- ✅ Form validation and user-friendly interface
- ✅ Status page integration with visual indicators
- ✅ Personalized bulk notifications
- ✅ API endpoints for testing and configuration
- ✅ Backwards compatibility with existing system
- ✅ Link to regex101.com for pattern testing
- ✅ Examples and help documentation

## 🚨 Production Notes

1. **Backup Database**: Always backup your database before running migrations
2. **Test Environment**: Test thoroughly in staging before production deployment  
3. **User Communication**: Notify users about new facility configuration options
4. **Documentation**: Update user documentation with facility configuration instructions

The facility configuration system is now ready for production use!