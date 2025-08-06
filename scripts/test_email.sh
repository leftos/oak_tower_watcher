#!/bin/bash
# SendGrid email testing script for OAK Tower Watcher production environment

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}🌐 OAK Tower Watcher SendGrid Email Test${NC}"
echo "================================================="

# Check if Docker Compose is running
if ! docker compose -f docker-compose.prod.yml ps web-api | grep -q "running"; then
    echo -e "${RED}❌ web-api container is not running${NC}"
    echo "Please start it first with:"
    echo "docker compose -f docker-compose.prod.yml up -d"
    exit 1
fi

echo -e "${YELLOW}📋 Current SendGrid environment variables:${NC}"
docker compose -f docker-compose.prod.yml exec web-api env | grep -E "(SENDGRID|MAIL_DEFAULT)" || echo "No SendGrid variables found"
echo

# Get recipient email from command line or use default
RECIPIENT_EMAIL=${1:-""}

# Run SendGrid email test
echo -e "${GREEN}🧪 Running SendGrid email test inside container...${NC}"
echo "================================================="

if [ -n "$RECIPIENT_EMAIL" ]; then
    echo "Testing with recipient: $RECIPIENT_EMAIL"
    docker compose -f docker-compose.prod.yml exec web-api python /app/web/sendgrid_test.py "$RECIPIENT_EMAIL"
else
    echo "Testing with default recipient (MAIL_DEFAULT_SENDER)"
    docker compose -f docker-compose.prod.yml exec web-api python /app/web/sendgrid_test.py
fi

TEST_EXIT_CODE=$?

echo
echo "================================================="
if [ $TEST_EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}✅ SendGrid email test completed successfully!${NC}"
    echo -e "${GREEN}🎉 Check your inbox for the test email.${NC}"
    echo -e "${GREEN}📧 Verification emails are now working via SendGrid!${NC}"
else
    echo -e "${RED}❌ SendGrid email test failed. Check the output above for details.${NC}"
    echo
    echo -e "${YELLOW}💡 Troubleshooting tips:${NC}"
    echo "1. Verify SENDGRID_API_KEY is set correctly in .env file"
    echo "2. Verify MAIL_DEFAULT_SENDER is set in .env file"
    echo "3. Check SendGrid API key is valid and active"
    echo "4. Ensure sender email is verified in SendGrid dashboard"
    echo "5. Check Docker container logs: docker compose -f docker-compose.prod.yml logs web-api"
fi

exit $TEST_EXIT_CODE