#!/bin/bash

# Narrify Phase 1 - Quick Start Script

echo "=================================="
echo "  NARRIFY PHASE 1 - STARTING"
echo "=================================="
echo ""

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "❌ Virtual environment not found!"
    echo "   Run: python -m venv venv"
    echo "   Then: source venv/bin/activate (Linux/Mac)"
    echo "   Or: venv\\Scripts\\activate (Windows)"
    exit 1
fi

# Check if .env exists
if [ ! -f ".env" ]; then
    echo ".env file not found, copying from .env.example..."
    cp .env.example .env
    echo ".env file created. Please customize if needed."
fi

# Activate virtual environment
source venv/bin/activate

# Check if requirements are installed
python -c "import fastapi" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "❌ Dependencies not installed!"
    echo "   Run: pip install -r requirements.txt"
    exit 1
fi

echo "✅ Environment ready"
echo ""
echo "🚀 Starting Narrify API server..."
echo ""
echo "   API docs: http://localhost:8000/docs"
echo "   Health check: http://localhost:8000/api/health"
echo ""
echo "   Press Ctrl+C to stop"
echo ""

# Start server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
