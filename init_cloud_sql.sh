#!/bin/bash
# Script to initialize Cloud SQL database for Iran Protest Map

set -e

PROJECT_ID=${PROJECT_ID:-"iran-map-483919"}
REGION=${REGION:-"us-central1"}
DB_INSTANCE="iran-map-db"
DB_NAME="iran_map"
DB_USER="postgres"
SERVICE_URL=$(gcloud run services describe iran-protest-map --region=$REGION --format='value(status.url)' 2>/dev/null || echo "")

echo "============================================"
echo "  Initializing Cloud SQL Database"
echo "============================================"
echo "Project: $PROJECT_ID"
echo "Instance: $DB_INSTANCE"
echo "Database: $DB_NAME"
echo ""

# Step 1: Enable PostGIS extension
echo "[1/3] Enabling PostGIS extension..."
echo "Connecting to Cloud SQL..."
echo "Run these SQL commands:"
echo ""
echo "CREATE EXTENSION IF NOT EXISTS postgis;"
echo "SELECT PostGIS_Version();"
echo "\\q"
echo ""
read -p "Press Enter after you've connected and enabled PostGIS..."

# Alternative: Use psql if Cloud SQL Proxy is set up
# gcloud sql connect $DB_INSTANCE --user=$DB_USER --database=$DB_NAME <<EOF
# CREATE EXTENSION IF NOT EXISTS postgis;
# SELECT PostGIS_Version();
# EOF

# Step 2: Trigger table creation via API
if [ -n "$SERVICE_URL" ]; then
    echo ""
    echo "[2/3] Creating database tables via API..."
    curl -X POST "$SERVICE_URL/api/init-db" \
        -H "Content-Type: application/json" \
        -w "\nHTTP Status: %{http_code}\n"
else
    echo ""
    echo "[2/3] Service URL not found. Please initialize manually:"
    echo "   curl -X POST \"<YOUR_SERVICE_URL>/api/init-db\""
fi

# Step 3: Verify
echo ""
echo "[3/3] Verifying setup..."
if [ -n "$SERVICE_URL" ]; then
    echo "Checking health endpoint..."
    curl -s "$SERVICE_URL/health" | jq . || echo "Health check failed"
    
    echo ""
    echo "Checking stats endpoint..."
    curl -s "$SERVICE_URL/api/stats" | jq . || echo "Stats endpoint failed"
fi

echo ""
echo "============================================"
echo "  Database initialization complete!"
echo "============================================"

