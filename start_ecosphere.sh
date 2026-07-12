#!/bin/bash
# EcoSphere Startup & Verification Script

echo "🚀 Starting EcoSphere Docker containers..."
docker-compose up -d

echo "⏳ Waiting for PostgreSQL database to be healthy..."
until [ "$(docker inspect -f '{{.State.Health.Status}}' ecosphere-final-postgres-1)" == "healthy" ]; do
    sleep 2
done

echo "🌱 Seeding database..."
docker exec ecosphere-final-api-1 python3 seed.py

echo "🏆 Triggering worker ESG score calculations..."
docker exec ecosphere-final-worker-1 python3 -c "import sys; sys.path.insert(0, '/api_app'); from worker import compute_scores; import datetime; compute_scores(datetime.datetime.now().strftime('%Y-%m'))"

echo "✨ EcoSphere started successfully!"

# Speaks on macOS
if [[ "$OSTYPE" == "darwin"* ]]; then
    say "Eco Sphere has started successfully and the database is seeded."
fi
