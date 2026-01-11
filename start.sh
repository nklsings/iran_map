#!/bin/bash

# Cloud Run provides PORT env var (default 8080)
export PORT=${PORT:-8080}
export HOSTNAME="0.0.0.0"

echo "============================================"
echo "  Iran Protest Map - Starting Services"
echo "============================================"
echo "Frontend PORT: $PORT"
echo "Backend PORT: 8000"
echo "DATABASE_URL: ${DATABASE_URL:0:50}..."
echo ""

# Start FastAPI backend on port 8000
echo "[1/2] Starting FastAPI backend..."
cd /app
python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --log-level info &
BACKEND_PID=$!

# Wait for backend to be ready (up to 60 seconds)
echo "Waiting for backend to be ready..."
MAX_WAIT=60
WAITED=0
while [ $WAITED -lt $MAX_WAIT ]; do
    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        echo "✓ Backend is ready!"
        break
    fi
    
    # Check if process is still running
    if ! kill -0 $BACKEND_PID 2>/dev/null; then
        echo "✗ ERROR: Backend process died"
        exit 1
    fi
    
    sleep 1
    WAITED=$((WAITED + 1))
    if [ $((WAITED % 5)) -eq 0 ]; then
        echo "  Still waiting for backend... ($WAITED seconds)"
    fi
done

if [ $WAITED -ge $MAX_WAIT ]; then
    echo "✗ ERROR: Backend failed to start within $MAX_WAIT seconds"
    exit 1
fi

# Start Next.js frontend on Cloud Run PORT
echo "[2/2] Starting Next.js frontend on port $PORT..."
node server.js &
FRONTEND_PID=$!

# Wait a moment for frontend to bind
sleep 2

echo ""
echo "============================================"
echo "  All services started successfully!"
echo "  Frontend: http://0.0.0.0:$PORT"
echo "  Backend:  http://0.0.0.0:8000"
echo "============================================"

# Handle graceful shutdown
shutdown() {
    echo ""
    echo "Shutting down services..."
    kill $BACKEND_PID $FRONTEND_PID 2>/dev/null || true
    wait $BACKEND_PID $FRONTEND_PID 2>/dev/null || true
    echo "Shutdown complete"
    exit 0
}
trap shutdown SIGTERM SIGINT SIGQUIT

# Wait for either process to exit
wait -n $BACKEND_PID $FRONTEND_PID

# If we get here, one process exited
echo "A service exited unexpectedly"
shutdown
