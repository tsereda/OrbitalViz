#!/bin/bash
# Test script for OrbitalViz application

set -e

echo "=== OrbitalViz Test Suite ==="
echo

# Test 1: Check backend dependencies
echo "Test 1: Checking backend dependencies..."
cd backend
python3 -c "import fastapi; import pyscf; import numpy; print('✓ All backend dependencies installed')"
cd ..

# Test 2: Backend API endpoints
echo
echo "Test 2: Starting backend server..."
cd backend
python3 -m uvicorn main:app --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!
cd ..

# Wait for server to start
sleep 5

echo "Testing root endpoint..."
curl -s http://localhost:8000/ | grep -q "PySCF MCSCF" && echo "✓ Root endpoint working" || echo "✗ Root endpoint failed"

echo "Testing molecule info endpoint..."
curl -s http://localhost:8000/api/molecule/info | grep -q "atoms" && echo "✓ Molecule info endpoint working" || echo "✗ Molecule info endpoint failed"

echo "Testing orbital data endpoint (this may take a moment)..."
curl -s -o /tmp/orbital_test.bin http://localhost:8000/api/orbital/0?grid_size=32
if [ -f /tmp/orbital_test.bin ] && [ -s /tmp/orbital_test.bin ]; then
    echo "✓ Orbital data endpoint working"
    SIZE=$(wc -c < /tmp/orbital_test.bin)
    echo "  Downloaded $SIZE bytes"
    rm /tmp/orbital_test.bin
else
    echo "✗ Orbital data endpoint failed"
fi

# Cleanup backend
kill $BACKEND_PID 2>/dev/null || true
sleep 2

# Force kill if still running
if kill -0 $BACKEND_PID 2>/dev/null; then
    kill -9 $BACKEND_PID 2>/dev/null || true
fi

wait $BACKEND_PID 2>/dev/null || true

# Test 3: Frontend build
echo
echo "Test 3: Testing frontend build..."
cd frontend
if [ ! -d "node_modules" ]; then
    echo "Installing frontend dependencies..."
    npm install
fi

npm run build && echo "✓ Frontend build successful" || echo "✗ Frontend build failed"
cd ..

echo
echo "=== All tests completed ==="
