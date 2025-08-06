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
