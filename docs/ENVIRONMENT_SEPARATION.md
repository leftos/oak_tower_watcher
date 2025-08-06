# Environment Separation Guide

This document explains how the OAK Tower Watcher application separates development and production environments to ensure data isolation and proper configuration management.

## Overview

The application now uses environment-specific configurations to ensure that:
- **Development** and **Production** environments use separate databases
- **Development** and **Production** environments use separate log directories
- Configuration is managed through environment variables
- No accidental data mixing between environments

## Environment Detection

The application automatically detects the environment using these environment variables (in order of priority):
1. `APP_ENV` - Explicitly set environment (`development` or `production`)
2. `FLASK_ENV` - Flask environment variable (if `APP_ENV` is not set)

## Directory Structure

```
oak_tower_watcher/
├── dev_logs/           # Development logs (created automatically)
├── dev_data/           # Development database files (created automatically)
├── logs/               # Production logs (Docker volume)
├── prod_data/          # Production database files (Docker volume)
├── config/
│   ├── config.py       # Application configuration
│   └── env_config.py   # Environment-specific configuration
├── scripts/
│   ├── setup_dev_env.sh    # Development environment setup
│   ├── run_dev.sh          # Development server runner
│   └── test_dev_setup.py   # Development setup tester
├── .env.development    # Development environment variables (auto-generated)
├── .env.prod.template  # Production environment template
└── docker-compose.prod.yml # Production Docker configuration
```

## Development Environment

### Setup

1. **Run the setup script:**
   ```bash
   ./scripts/setup_dev_env.sh
   ```

2. **Test the setup:**
   ```bash
   python scripts/test_dev_setup.py
   ```

3. **Start development server:**
   ```bash
   ./scripts/run_dev.sh
   ```

### Configuration

- **Database:** `sqlite:///dev_data/users_dev.db`
- **Logs:** `dev_logs/web_app_dev.log`
- **Server:** `http://127.0.0.1:5000`
- **Debug Mode:** Enabled
- **Console Logging:** Enabled
- **SQL Query Logging:** Enabled when DEBUG=true

### Environment Variables

Development environment variables are stored in `.env.development`:

```bash
APP_ENV=development
FLASK_ENV=development
DEBUG=true
DATABASE_URL=sqlite:///dev_data/users_dev.db
SECRET_KEY=dev-secret-key-change-in-production-[timestamp]
HOST=127.0.0.1
PORT=5000
```

## Production Environment

### Setup

1. **Copy the template:**
   ```bash
   cp .env.prod.template .env.prod
   ```

2. **Edit `.env.prod` with your production values:**
   ```bash
   nano .env.prod
   ```

3. **Deploy with Docker:**
   ```bash
   docker-compose -f docker-compose.prod.yml --env-file .env.prod up -d
   ```

### Configuration

- **Database:** `sqlite:///prod_data/users.db` (or external database)
- **Logs:** `logs/web_app.log` (with rotation)
- **Server:** `http://0.0.0.0:8080` (behind nginx)
- **Debug Mode:** Disabled
- **Console Logging:** Disabled
- **SQL Query Logging:** Disabled

### Environment Variables

Production environment variables are loaded from `.env.prod`:

```bash
APP_ENV=production
FLASK_ENV=production
SECRET_KEY=your-super-secret-production-key
DATABASE_URL=sqlite:///prod_data/users.db
HOST=0.0.0.0
PORT=8080
# ... other production settings
```

## Database Separation

### Development Database
- **Location:** `dev_data/users_dev.db`
- **Type:** SQLite (default)
- **Features:** 
  - Track modifications enabled for debugging
  - SQL query logging when DEBUG=true
  - Automatic table creation

### Production Database
- **Location:** `prod_data/users.db` (SQLite) or external database
- **Type:** SQLite, PostgreSQL, or MySQL
- **Features:**
  - Track modifications disabled for performance
  - No SQL query logging
  - Persistent Docker volume mapping

### Database Configuration Examples

**SQLite (default):**
```bash
DATABASE_URL=sqlite:///prod_data/users.db
```

**PostgreSQL:**
```bash
DATABASE_URL=postgresql://username:password@localhost:5432/oak_tower_watcher
```

**MySQL:**
```bash
DATABASE_URL=mysql://username:password@localhost:3306/oak_tower_watcher
```

## Log Separation

### Development Logs
- **Directory:** `dev_logs/`
- **File:** `web_app_dev.log`
- **Format:** Includes filename and line numbers for debugging
- **Console Output:** Enabled
- **Rotation:** 5MB max, 3 backup files

### Production Logs
- **Directory:** `logs/`
- **File:** `web_app.log`
- **Format:** Standard production format
- **Console Output:** Disabled
- **Rotation:** 10MB max, 5 backup files
- **Docker Logging:** JSON format with size limits

## Security Considerations

### Development
- Uses a development secret key (automatically generated)
- Debug mode enabled
- Verbose logging
- Local-only access (127.0.0.1)

### Production
- **REQUIRES** a strong, unique secret key
- Debug mode disabled
- Minimal logging
- Network access (0.0.0.0)
- SSL/TLS support via nginx

## File Exclusions

The `.gitignore` file excludes environment-specific files:

```gitignore
# Development environment
dev_logs/
dev_data/
.env.development
*.dev.db

# Production environment
logs/
prod_data/
.env.prod
```

## Troubleshooting

### Common Issues

1. **Environment not detected correctly:**
   - Check `APP_ENV` and `FLASK_ENV` environment variables
   - Verify `.env.development` or `.env.prod` files exist

2. **Database connection errors:**
   - Check `DATABASE_URL` format
   - Ensure database directories exist
   - Verify file permissions

3. **Log file permissions:**
   - Ensure log directories are writable
   - Check Docker volume permissions for production

4. **Production secret key errors:**
   - Ensure `SECRET_KEY` is set in production
   - Verify it's not the development default

### Testing Environment Separation

Run the development setup test:
```bash
python scripts/test_dev_setup.py
```

Check environment detection:
```python
from config.env_config import env_config
print(f"Environment: {env_config.env}")
print(f"Is Production: {env_config.is_production()}")
print(f"Database: {env_config.get_database_config()['uri']}")
print(f"Log Directory: {env_config.get_log_config()['dir']}")
```

## Migration from Old Setup

If you have an existing setup without environment separation:

1. **Backup existing data:**
   ```bash
   cp users.db users.db.backup
   cp -r logs logs.backup
   ```

2. **Run development setup:**
   ```bash
   ./scripts/setup_dev_env.sh
   ```

3. **For production, copy data to new locations:**
   ```bash
   mkdir -p prod_data
   cp users.db.backup prod_data/users.db
   ```

4. **Update your deployment scripts to use the new Docker configuration**

## Best Practices

1. **Never commit environment files to version control**
2. **Use strong, unique secret keys in production**
3. **Regularly rotate production secrets**
4. **Monitor log file sizes and implement rotation**
5. **Use external databases for production when possible**
6. **Test environment separation before deploying**
7. **Keep development and production configurations in sync**